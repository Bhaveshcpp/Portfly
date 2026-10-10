"""Shared client for the eval and latency scripts.

Default: boots the app in-process on a throw-away SQLite file, so every run starts from the seed
data and never touches your real DB. Pass --base-url to hit a deployed instance instead
(note: that WILL write to its database; the eval adds and updates properties).
"""

from __future__ import annotations

import os
import tempfile
from typing import Any


class Client:
    def __init__(self, base_url: str | None = None, model: str | None = None, token: str | None = None):
        self.base_url = base_url
        self._keys: dict[int, str] = {}  # conversation id -> its secret key (the API only reveals it once)
        if not base_url:
            token = token or "portfly-local-eval"  # in-process only: the app is configured with this same value below
            os.environ["DESK_TOKEN"] = token
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        if model:
            os.environ["OPENROUTER_MODEL"] = model
        if base_url:
            import httpx

            self._http = httpx.Client(base_url=base_url.rstrip("/"), timeout=120, headers=self.headers)
            self._ctx = None
        else:
            tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            tmp.close()
            os.remove(tmp.name)  # let SQLAlchemy create it fresh
            os.environ["DATABASE_URL"] = f"sqlite:///{tmp.name}"
            from fastapi.testclient import TestClient

            from app.main import app

            self._ctx = TestClient(app, headers=self.headers)
            self._ctx.__enter__()  # runs startup: create tables + seed
            self._http = self._ctx

    def reset(self) -> None:
        """Back to the seed data so one case cannot contaminate the next (in-process runs only)."""
        if self.base_url:
            return
        from app.db import Base, SessionLocal, engine
        from app.seed import seed_from_csv

        self._keys.clear()  # ids restart after a reset, so old keys must not be reused
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        db = SessionLocal()
        try:
            seed_from_csv(db)
        finally:
            db.close()

    def close(self) -> None:
        if self._ctx:
            self._ctx.__exit__(None, None, None)

    def get(self, path: str) -> Any:
        r = self._http.get(path)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict | None = None, headers: dict | None = None) -> Any:
        r = self._http.post(path, json=body or {}, headers=headers)
        r.raise_for_status()
        return r.json()

    def health(self) -> dict:
        return self.get("/api/health")

    def chat(self, user_id: str, message: str, conversation_id: int | None = None) -> dict:
        headers = {"X-Conversation-Key": self._keys[conversation_id]} if conversation_id in self._keys else None
        reply = self.post("/api/chat", {"user_id": user_id, "message": message, "conversation_id": conversation_id}, headers)
        key = reply.pop("conversation_key", None)  # present only when the conversation was just created
        if key:
            self._keys[reply["conversation_id"]] = key
        return reply

    def last_run(self, conversation_id: int) -> dict:
        """The most recent agent run (with its tool calls) for a conversation."""
        return self.get(f"/api/conversations/{conversation_id}")["runs"][0]

    def conversation(self, conversation_id: int) -> dict:
        return self.get(f"/api/conversations/{conversation_id}")

    def properties(self, user_id: str) -> list[dict]:
        return self.get(f"/api/users/{user_id}/properties")

    def prop(self, user_id: str, property_id: str) -> dict | None:
        return next((p for p in self.properties(user_id) if p["property_id"] == property_id), None)
