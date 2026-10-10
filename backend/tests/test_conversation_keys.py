"""Per-conversation keys: whoever holds the key may read and continue a conversation; nobody else can.

No network and no model: the DB is the in-memory fixture and the agent run is stubbed."""

import hashlib
import re
import secrets

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import settings
from app.db import get_db
from app.models import Conversation, Message

DESK = "unit-test-desk-token"
H = "X-Conversation-Key"


def fake_run_agent(db, convo, user, text):
    db.add(Message(conversation_id=convo.id, role="assistant", content=f"echo: {text}"))
    db.commit()
    return {"reply": f"echo: {text}", "needs_attention": False}


@pytest.fixture()
def api(db, monkeypatch):
    monkeypatch.setattr(settings, "desk_token", DESK)
    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    main.app.dependency_overrides[get_db] = lambda: db
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def start(api, user="U001", text="hello"):
    r = api.post("/api/chat", json={"user_id": user, "message": text})
    assert r.status_code == 200, r.text
    body = r.json()
    return body["conversation_id"], body["conversation_key"], body


def history(api, user, cid, key=None, **kw):
    headers = {H: key} if key is not None else {}
    return api.get(f"/api/users/{user}/conversations/{cid}/messages", headers=headers, **kw)


def say(api, user, cid, text, key=None):
    headers = {H: key} if key is not None else {}
    return api.post("/api/chat", json={"user_id": user, "conversation_id": cid, "message": text}, headers=headers)


def msg_count(db):
    return db.query(Message).count()


# ---------------------------------------------------------------- creation
def test_new_conversation_returns_a_strong_key_exactly_once_and_stores_only_its_hash(api, db):
    cid, key, body = start(api)
    assert len(key) >= 43 and re.fullmatch(r"[A-Za-z0-9_-]+", key)  # 32 random bytes, url-safe
    stored = db.get(Conversation, cid).access_key_hash
    assert stored == hashlib.sha256(key.encode()).hexdigest() and stored != key
    again = say(api, "U001", cid, "second", key).json()
    assert "conversation_key" not in again and key not in str(again)  # never repeated after creation
    assert key not in str(db.get(Conversation, cid).__dict__)  # not stored in plain text


def test_keys_are_unique_per_conversation(api):
    keys = {start(api)[1] for _ in range(20)}
    assert len(keys) == 20


def test_responses_are_not_cacheable(api):
    cid, key, _ = start(api)
    assert api.post("/api/chat", json={"user_id": "U001", "message": "x"}).headers["cache-control"] == "no-store"
    assert history(api, "U001", cid, key).headers["cache-control"] == "no-store"


# ---------------------------------------------------------------- valid access
def test_valid_key_can_read_and_continue(api, db):
    cid, key, _ = start(api, text="first")
    r = say(api, "U001", cid, "second", key)
    assert r.status_code == 200 and r.json()["reply"] == "echo: second"
    h = history(api, "U001", cid, key)
    assert h.status_code == 200
    assert [m["content"] for m in h.json()["messages"]] == ["first", "echo: first", "second", "echo: second"]


# ---------------------------------------------------------------- unauthorized history reads
def test_history_without_key_is_401(api):
    cid, _, _ = start(api)
    assert history(api, "U001", cid).status_code == 401
    assert history(api, "U001", cid, "").status_code == 401


def test_history_with_wrong_key_is_403(api):
    cid, key, _ = start(api)
    assert history(api, "U001", cid, key[:-1] + ("A" if key[-1] != "A" else "B")).status_code == 403
    assert history(api, "U001", cid, "x").status_code == 403


def test_key_in_the_url_does_not_work(api):
    cid, key, _ = start(api)
    for qs in (f"?key={key}", f"?x_conversation_key={key}", f"?conversation_key={key}"):
        assert history(api, "U001", cid).status_code == 401
        r = api.get(f"/api/users/U001/conversations/{cid}/messages{qs}")
        assert r.status_code == 401


# ---------------------------------------------------------------- unauthorized attempts to continue
def test_continue_without_or_with_wrong_key_is_rejected_and_writes_nothing(api, db):
    cid, key, _ = start(api)
    before = msg_count(db)
    assert say(api, "U001", cid, "intruder").status_code == 401
    assert say(api, "U001", cid, "intruder", "wrong").status_code == 403
    assert msg_count(db) == before  # no user message, no agent run
    assert "intruder" not in [m["content"] for m in history(api, "U001", cid, key).json()["messages"]]


# ---------------------------------------------------------------- cross-user
def test_another_user_cannot_use_a_valid_key_on_someone_elses_conversation(api, db):
    cid, key, _ = start(api, "U001")
    before = msg_count(db)
    assert history(api, "U002", cid, key).status_code == 403
    assert say(api, "U002", cid, "hi", key).status_code == 403
    assert msg_count(db) == before


def test_keys_do_not_work_across_conversations(api):
    cid_a, key_a, _ = start(api, "U001")
    cid_b, key_b, _ = start(api, "U001")
    assert history(api, "U001", cid_a, key_b).status_code == 403
    assert say(api, "U001", cid_b, "hi", key_a).status_code == 403


def test_all_denials_look_identical_so_ids_cannot_be_probed(api, db):
    cid, key, _ = start(api, "U001")
    legacy = Conversation(user_id="U001", title="old", access_key_hash=None)
    db.add(legacy); db.commit()
    denials = [
        history(api, "U001", cid, "wrong"),          # wrong key
        history(api, "U002", cid, key),              # right key, wrong user
        history(api, "U001", 987654, "wrong"),       # no such conversation
        history(api, "U001", legacy.id, "anything"),  # legacy conversation
    ]
    assert {(r.status_code, r.text) for r in denials} == {(403, denials[0].text)}


# ---------------------------------------------------------------- legacy conversations (no key)
def test_legacy_conversation_is_never_opened_to_the_public(api, db):
    legacy = Conversation(user_id="U001", title="before keys existed", access_key_hash=None)
    db.add(legacy); db.flush()
    db.add(Message(conversation_id=legacy.id, role="user", content="old private message")); db.commit()
    before = msg_count(db)
    for guess in ("", "anything", _guess := "portfly:no-such-conversation", hashlib.sha256(b"portfly:no-such-conversation").hexdigest()):
        assert history(api, "U001", legacy.id, guess).status_code in (401, 403)
        assert say(api, "U001", legacy.id, "hijack", guess).status_code in (401, 403)
    assert msg_count(db) == before
    # the business desk can still see it, with the desk token
    r = api.get(f"/api/conversations/{legacy.id}", headers={"Authorization": f"Bearer {DESK}"})
    assert r.status_code == 200 and "old private message" in r.text


# ---------------------------------------------------------------- never leaked
def test_key_and_hash_never_appear_in_desk_or_other_responses(api, db):
    cid, key, _ = start(api, "U001")
    other_cid, other_key, _ = start(api, "U002")
    digest = hashlib.sha256(key.encode()).hexdigest()
    desk = {"Authorization": f"Bearer {DESK}"}
    pages = [
        api.get("/api/conversations", headers=desk),
        api.get(f"/api/conversations/{cid}", headers=desk),
        api.get("/api/dashboard", headers=desk),
        api.get("/api/users"),
        api.get("/api/users/U001/properties"),
        say(api, "U001", cid, "again", key),
        history(api, "U001", cid, key),
        history(api, "U002", other_cid, other_key),  # a different user's own, valid, response
    ]
    for r in pages:
        assert key not in r.text and digest not in r.text, r.request.url
        assert "access_key" not in r.text


# ---------------------------------------------------------------- constant-time comparison
def test_every_key_check_runs_one_constant_time_comparison(api, db, monkeypatch):
    cid, key, _ = start(api)
    legacy = Conversation(user_id="U001", title="old", access_key_hash=None)
    db.add(legacy); db.commit()
    calls = []
    real = secrets.compare_digest
    monkeypatch.setattr(main.secrets, "compare_digest", lambda a, b: calls.append(1) or real(a, b))
    for conv, user, k in ((cid, "U001", key), (cid, "U001", "wrong"), (cid, "U002", key), (987654, "U001", "x"), (legacy.id, "U001", "x")):
        calls.clear()
        history(api, user, conv, k)
        assert len(calls) == 1, (conv, user)  # same work whether valid, wrong, foreign, missing or legacy


# ---------------------------------------------------------------- desk protection and public chat still behave
def test_desk_token_protection_is_unchanged(api):
    cid, key, _ = start(api)
    assert api.get("/api/dashboard").status_code == 401
    assert api.get(f"/api/conversations/{cid}", headers={"Authorization": f"Bearer {key}"}).status_code == 401  # a conversation key is not a desk token
    assert api.get("/api/dashboard", headers={"Authorization": f"Bearer {DESK}"}).status_code == 200
    assert api.get("/api/health").status_code == 200
