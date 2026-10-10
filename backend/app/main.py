import hashlib
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.graph import run_agent
from app.analytics import serialize_property
from app.config import settings
from app.db import Base, SessionLocal, engine, ensure_columns, get_db
from app.models import AgentRun, Conversation, Message, Property, User
from app.portfolio import user_properties
from app.seed import backfill_city, seed_from_csv

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    db = SessionLocal()
    try:
        seed_from_csv(db)
        backfill_city(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Portfly", version="1.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


class ChatIn(BaseModel):
    user_id: str
    message: str
    conversation_id: int | None = None


_desk_scheme = HTTPBearer(auto_error=False, description="Business desk token (the DESK_TOKEN server setting)")


def require_desk_token(credentials: HTTPAuthorizationCredentials | None = Depends(_desk_scheme)) -> None:
    """Guard for the business desk. Fails closed: with no DESK_TOKEN configured nothing gets in."""
    expected = settings.desk_token
    if not expected:
        raise HTTPException(503, "Business desk is disabled: DESK_TOKEN is not configured on the server.")
    supplied = credentials.credentials if credentials else ""
    if not secrets.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(401, "Missing or invalid desk token.", headers={"WWW-Authenticate": "Bearer"})


@app.get("/api/health")
def health():
    return {"ok": True, "openrouter": bool(settings.openrouter_api_key)}


@app.get("/api/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.user_id).all()
    return [
        {
            "user_id": u.user_id,
            "name": u.name,
            "city": u.city,
            "preferences": u.preferences,
            "preferred_locations": u.preferred_locations,
            "property_count": len(u.properties),
            "conversation_count": len(u.conversations),
            "attention_count": sum(1 for c in u.conversations if c.needs_attention),
        }
        for u in users
    ]


@app.get("/api/users/{user_id}/properties")
def list_user_properties(user_id: str, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Unknown user")
    return [serialize_property(p) for p in user_properties(db, user_id)]


# ---- per-conversation keys -------------------------------------------------------------------
# A conversation is a capability: whoever holds its key may read and continue it. The key is created
# with the conversation, shown to the browser exactly once, and only its SHA-256 hash is stored.
# It travels in a request header, never in a URL, so it stays out of access logs and browser history.
_NO_SUCH_HASH = hashlib.sha256(b"portfly:no-such-conversation").hexdigest()


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _authorize_conversation(db: Session, user_id: str, conversation_id: int, supplied_key: str | None) -> Conversation:
    """Return the conversation if `supplied_key` is its key, else raise.

    401 = no key supplied. 403 = everything else (wrong key, another user's conversation, unknown id,
    or a legacy conversation with no key). All the 403 cases are deliberately identical so that
    conversation ids cannot be probed. The hash comparison always runs, in constant time."""
    if not supplied_key:
        raise HTTPException(401, "A conversation key is required.", headers={"WWW-Authenticate": "ConversationKey"})
    convo = db.get(Conversation, conversation_id)
    stored = convo.access_key_hash if convo is not None and convo.user_id == user_id else None
    same = secrets.compare_digest(_hash_key(supplied_key), stored or _NO_SUCH_HASH)
    if not (same and stored):
        raise HTTPException(403, "Conversation not found or key invalid.")
    return convo


@app.get("/api/users/{user_id}/conversations/{conversation_id}/messages")
def conversation_messages(
    user_id: str,
    conversation_id: int,
    response: Response,
    db: Session = Depends(get_db),
    x_conversation_key: str | None = Header(default=None, description="The conversation's secret key, returned once when it was created."),
):
    """Chat history (role + text only) so the chat page survives a refresh. Requires the conversation's
    key. No tool calls, timings or flags: those are desk-only."""
    c = _authorize_conversation(db, user_id, conversation_id, x_conversation_key)
    response.headers["Cache-Control"] = "no-store"
    return {
        "conversation_id": c.id,
        "user_id": c.user_id,
        "messages": [{"role": m.role, "content": m.content} for m in c.messages],
    }


@app.get("/api/conversations", dependencies=[Depends(require_desk_token)])
def list_conversations(db: Session = Depends(get_db)):
    rows = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    out = []
    for c in rows:
        last = c.messages[-1].content if c.messages else ""
        out.append(
            {
                "id": c.id,
                "user_id": c.user_id,
                "user_name": c.user.name if c.user else c.user_id,
                "title": c.title,
                "needs_attention": c.needs_attention,
                "attention_reason": c.attention_reason,
                "attention_kind": c.attention_kind,
                "updated_at": c.updated_at,
                "message_count": len(c.messages),
                "last_message": last[:180],
            }
        )
    return out


@app.get("/api/conversations/{conversation_id}", dependencies=[Depends(require_desk_token)])
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c:
        raise HTTPException(404, "Unknown conversation")
    runs = (
        db.query(AgentRun)
        .filter(AgentRun.conversation_id == c.id)
        .order_by(AgentRun.id.desc())
        .all()
    )
    return {
        "id": c.id,
        "user_id": c.user_id,
        "user_name": c.user.name,
        "needs_attention": c.needs_attention,
        "attention_reason": c.attention_reason,
        "attention_kind": c.attention_kind,
        "active_scenario": c.active_scenario,
        "last_mentioned_property_ids": c.last_mentioned_property_ids,
        "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at}
            for m in c.messages
        ],
        "runs": [
            {
                "id": r.id,
                "status": r.status,
                "error_message": r.error_message,
                "total_ms": r.total_ms,
                "model_ms": r.model_ms,
                "tool_ms": r.tool_ms,
                "overhead_ms": max(0.0, (r.total_ms or 0) - (r.model_ms or 0) - (r.tool_ms or 0)),
                "llm_calls": r.llm_calls,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "used_fallback": r.used_fallback,
                "created_at": r.created_at,
                "tools": [
                    {
                        "id": t.id,
                        "tool_name": t.tool_name,
                        "ok": t.ok,
                        "blocked": t.blocked,
                        "arguments": t.arguments_json,
                        "duration_ms": t.duration_ms,
                        "hypothetical": t.hypothetical,
                        "result_preview": t.result_preview,
                    }
                    for t in r.tool_calls
                ],
            }
            for r in runs
        ],
    }


@app.get("/api/dashboard", dependencies=[Depends(require_desk_token)])
def dashboard(db: Session = Depends(get_db)):
    convos = db.query(Conversation).all()
    runs = db.query(AgentRun).order_by(AgentRun.id.desc()).limit(50).all()
    flagged = [c for c in convos if c.needs_attention]
    totals = [r.total_ms for r in runs if r.total_ms]
    errors = [r for r in runs if r.status == "error"]
    return {
        "users": db.query(User).count(),
        "properties": db.query(Property).count(),
        "conversations": len(convos),
        "attention_count": len(flagged),
        "avg_total_ms": (sum(totals) / len(totals)) if totals else 0,
        "p50_total_ms": _pct(totals, 0.5),
        "p95_total_ms": _pct(totals, 0.95),
        "avg_model_ms": (sum(r.model_ms for r in runs) / len(runs)) if runs else 0,
        "avg_tool_ms": (sum(r.tool_ms for r in runs) / len(runs)) if runs else 0,
        "error_runs": len(errors),
        "fallback_runs": sum(1 for r in runs if r.used_fallback),
        "prompt_tokens": sum(r.prompt_tokens for r in runs),
        "completion_tokens": sum(r.completion_tokens for r in runs),
        "recent_runs": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "status": r.status,
                "total_ms": r.total_ms,
                "model_ms": r.model_ms,
                "tool_ms": r.tool_ms,
                "used_fallback": r.used_fallback,
                "error_message": r.error_message,
                "created_at": r.created_at,
            }
            for r in runs
        ],
        "flagged": [
            {
                "id": c.id,
                "user_id": c.user_id,
                "reason": c.attention_reason,
                "kind": c.attention_kind,
            }
            for c in flagged
        ],
    }


@app.post("/api/chat")
def chat(
    body: ChatIn,
    response: Response,
    db: Session = Depends(get_db),
    x_conversation_key: str | None = Header(default=None, description="Required to continue an existing conversation."),
):
    user = db.get(User, body.user_id)
    if not user:
        raise HTTPException(404, "Unknown user")
    new_key: str | None = None
    if body.conversation_id:
        # Authorise BEFORE anything is written: a rejected request must not touch the conversation.
        convo = _authorize_conversation(db, body.user_id, body.conversation_id, x_conversation_key)
    else:
        new_key = secrets.token_urlsafe(32)  # 256 bits from the OS CSPRNG
        convo = Conversation(user_id=body.user_id, title=body.message[:80] or "Chat", access_key_hash=_hash_key(new_key))
        db.add(convo)
        db.flush()
    db.add(Message(conversation_id=convo.id, role="user", content=body.message))
    convo.updated_at = datetime.utcnow()
    db.commit()  # the user's message is durable before the agent runs, even if the run fails
    result = run_agent(db, convo, user, body.message)
    response.headers["Cache-Control"] = "no-store"
    payload = {"conversation_id": convo.id, **result}
    if new_key:
        payload["conversation_key"] = new_key  # the only time the key is ever sent
    return payload


@app.post("/api/conversations/{conversation_id}/resolve", dependencies=[Depends(require_desk_token)])
def resolve_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Desk action: clear an attention flag once a human has dealt with it."""
    c = db.get(Conversation, conversation_id)
    if not c:
        raise HTTPException(404, "Unknown conversation")
    c.needs_attention, c.attention_kind, c.attention_reason = False, None, None
    db.commit()
    return {"ok": True}


STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        requested_file = STATIC_DIR / full_path

        if requested_file.is_file() and requested_file.resolve().is_relative_to(STATIC_DIR.resolve()):
            return FileResponse(requested_file)

        return FileResponse(STATIC_DIR / "index.html")
