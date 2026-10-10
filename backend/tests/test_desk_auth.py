"""Access control for the business desk. No network, no model: the DB is the in-memory fixture."""

import hashlib

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import settings
from app.db import get_db
from app.models import Conversation, Message

TOKEN = "unit-test-desk-token"
CONV_KEY = "unit-test-conversation-key"


@pytest.fixture()
def client(db, monkeypatch):
    monkeypatch.setattr(settings, "desk_token", TOKEN)
    convo = Conversation(user_id="U001", title="hello", access_key_hash=hashlib.sha256(CONV_KEY.encode()).hexdigest())
    db.add(convo)
    db.flush()
    db.add_all([Message(conversation_id=convo.id, role="user", content="hi"), Message(conversation_id=convo.id, role="assistant", content="hello")])
    db.commit()
    main.app.dependency_overrides[get_db] = lambda: db
    # no `with`: skips the startup hook, so the real DB file is never touched
    yield TestClient(main.app), convo.id
    main.app.dependency_overrides.clear()


DESK_ENDPOINTS = [
    ("get", "/api/dashboard"),
    ("get", "/api/conversations"),
    ("get", "/api/conversations/{cid}"),
    ("post", "/api/conversations/{cid}/resolve"),
]


@pytest.mark.parametrize("method,path", DESK_ENDPOINTS)
def test_desk_endpoints_reject_missing_and_wrong_tokens(client, method, path):
    c, cid = client
    url = path.format(cid=cid)
    assert getattr(c, method)(url).status_code == 401
    assert getattr(c, method)(url, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert getattr(c, method)(url, headers={"Authorization": f"Basic {TOKEN}"}).status_code == 401


@pytest.mark.parametrize("method,path", DESK_ENDPOINTS)
def test_desk_endpoints_accept_the_right_token(client, method, path):
    c, cid = client
    assert getattr(c, method)(path.format(cid=cid), headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200


@pytest.mark.parametrize("method,path", DESK_ENDPOINTS)
def test_desk_fails_closed_when_no_token_is_configured(client, monkeypatch, method, path):
    c, cid = client
    monkeypatch.setattr(settings, "desk_token", "")
    for headers in ({}, {"Authorization": "Bearer "}, {"Authorization": f"Bearer {TOKEN}"}):
        assert getattr(c, method)(path.format(cid=cid), headers=headers).status_code == 503


def test_public_endpoints_stay_open(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(main, "run_agent", lambda *a, **k: {"reply": "ok", "needs_attention": False})  # never call a real model in tests
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/users").status_code == 200
    assert c.get("/api/users/U001/properties").status_code == 200
    assert c.post("/api/chat", json={"user_id": "U001", "message": "hello"}).status_code == 200


def test_chat_history_endpoint_is_keyed_and_minimal(client):
    c, cid = client
    ok = c.get(f"/api/users/U001/conversations/{cid}/messages", headers={"X-Conversation-Key": CONV_KEY})
    assert ok.status_code == 200
    body = ok.json()
    assert body["messages"] == [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    assert set(body) == {"conversation_id", "user_id", "messages"}  # no runs, tool calls, timings or flags
    assert c.get(f"/api/users/U001/conversations/{cid}/messages").status_code == 401  # no key, no history
    # (full key / cross-user / legacy coverage lives in test_conversation_keys.py)
