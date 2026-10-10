from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80))
    preferences: Mapped[str] = mapped_column(String(200))
    preferred_locations: Mapped[str] = mapped_column(String(200))
    portfolio_value_preference_inr: Mapped[str] = mapped_column(String(80))

    properties: Mapped[list["Property"]] = relationship(back_populates="owner")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")


class Property(Base):
    __tablename__ = "properties"

    property_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    property_type: Mapped[str] = mapped_column(String(80))
    type_group: Mapped[str] = mapped_column(String(40), index=True)
    sub_type: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(80), default="", index=True)
    area_sqft: Mapped[float] = mapped_column(Float)
    current_estimated_value_inr: Mapped[float] = mapped_column(Float)
    purchase_price_inr: Mapped[float | None] = mapped_column(Float, nullable=True)
    annual_rent_inr: Mapped[float] = mapped_column(Float, default=0)
    occupancy_status: Mapped[str] = mapped_column(String(40))
    tenant_status: Mapped[str] = mapped_column(String(40))
    ownership_percent: Mapped[float] = mapped_column(Float, default=100)
    status: Mapped[str] = mapped_column(String(40), default="Active")

    owner: Mapped[User] = relationship(back_populates="properties")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="WhatsApp chat")
    needs_attention: Mapped[bool] = mapped_column(Boolean, default=False)
    attention_reason: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # "clarification" auto-clears; "error" and "handoff" stay until the desk resolves them
    attention_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # inputs of the latest what-if so "how would that change my portfolio?" has something to refer to
    active_scenario: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_mentioned_property_ids: Mapped[list] = mapped_column(JSON, default=list)
    # SHA-256 (hex) of the conversation's secret key; the key itself is never stored.
    # NULL = a conversation created before keys existed: no public access, desk-only.
    access_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.id"
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_ms: Mapped[float] = mapped_column(Float, default=0)
    model_ms: Mapped[float] = mapped_column(Float, default=0)
    tool_ms: Mapped[float] = mapped_column(Float, default=0)
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="agent_runs")
    tool_calls: Mapped[list["ToolCall"]] = relationship(back_populates="run")


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(80))
    arguments_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_preview: Mapped[str] = mapped_column(Text, default="")
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)  # validation said "ask the user first"
    duration_ms: Mapped[float] = mapped_column(Float, default=0)
    hypothetical: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped[AgentRun] = relationship(back_populates="tool_calls")
