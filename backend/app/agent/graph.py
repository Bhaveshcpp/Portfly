"""Agent runner: one LangGraph ReAct agent, bounded history, real telemetry, sticky attention flags."""

from __future__ import annotations

import re
import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from sqlalchemy.orm import Session

from app import portfolio
from app.agent import fallback
from app.agent.tools import PREVIEW_CHARS, ToolContext, build_tools, trace  # noqa: F401
from app.config import ROOT, settings
from app.models import AgentRun, Conversation, Message, ToolCall, User

SOUL_PATH = ROOT / "SOUL.md"

HANDOFF_RE = fallback.HANDOFF_RE
PRIORITY = {"clarification": 1, "handoff": 2, "error": 3}
STICKY = {"handoff", "error"}
HANDOFF_NOTE = "I've flagged this for our team so a human can follow up with you."
ERROR_REPLY = "Sorry, I hit a problem on my side and couldn't finish that. Your portfolio data hasn't been changed by this failure. Please try again in a moment."


def _soul_text() -> str:
    if SOUL_PATH.exists():
        return SOUL_PATH.read_text(encoding="utf-8")
    return "You are Portfly, a careful real-estate portfolio analyst."


def _system_prompt(user: User, recent: list[dict[str, Any]], scenario: dict[str, Any] | None) -> str:
    context = []
    if recent:
        context.append(
            "Recently discussed properties (resolve 'it', 'that one', 'which one' against these; still call tools for numbers):\n"
            + "\n".join(f"- {p['property_id']}: {p['sub_type']} in {p['location']}" for p in recent)
        )
    if scenario:
        context.append(
            "A what-if is active in this conversation (hypothetical, NOT saved): "
            f"excluded={scenario.get('exclude_ids') or []}, value_overrides={scenario.get('value_overrides') or {}}, "
            f"additions={len(scenario.get('additions') or [])}. For 'how would that change…' questions re-run "
            "evaluate_hypothetical_scenario with these inputs and describe the delta."
        )
    return f"""{_soul_text()}

Current user (never access another user's properties):
- user_id: {user.user_id}
- name: {user.name}
- home city: {user.city}
- preferences: {user.preferences}
- preferred locations: {user.preferred_locations}
- stated value preference: {user.portfolio_value_preference_inr}

Rules:
- Always call tools for portfolio facts. Never invent holdings, rents or values, and never do arithmetic yourself:
  use calculate_portfolio_metrics and the 'delta' returned by evaluate_hypothetical_scenario.
- Pass money to tools exactly as the user wrote it ('14 Cr', '50 lakh'); the server converts units. Never invent Cr/lakh. If they say a bare number like 'worth 12' with no unit or ₹, ask which they mean — do not call add/update with 12 or '12 Cr'.
- purchase_price_inr is missing and there are no dates. Say so; never invent appreciation or historical returns.
- Office and Commercial Office are grouped as Office.
- What-ifs use evaluate_hypothetical_scenario and never update_property. Label results as hypothetical.
- If a tool returns needs_clarification, ask the user that one question; do not guess or retry silently.
- After add_property succeeds, tell the user any 'assumptions' it returned. After update_property, state old and new values.
- Legal, tax or formal valuation questions: give no advice; say a human will follow up.
- Speak INR in crore/lakh. Keep replies short, WhatsApp style.
{chr(10).join(context)}
"""


def _history(messages: list[Message], user_text: str) -> list:
    """Bounded prior turns. The current user message is already saved, so drop it here:
    it is appended separately, and including it twice confuses the model."""
    msgs = list(messages)
    if msgs and msgs[-1].role == "user" and msgs[-1].content == user_text:
        msgs = msgs[:-1]
    out = []
    for msg in msgs[-settings.max_history_messages :]:
        out.append(HumanMessage(content=msg.content) if msg.role == "user" else AIMessage(content=msg.content))
    return out


class TimingHandler(BaseCallbackHandler):
    """Measures each model call separately from tool time and counts tokens."""

    def __init__(self) -> None:
        self._starts: dict[Any, float] = {}
        self.durations_ms: list[float] = []
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):  # noqa: ANN001
        self._starts[run_id] = time.perf_counter()

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):  # noqa: ANN001
        self._starts.setdefault(run_id, time.perf_counter())

    def _stop(self, run_id) -> None:  # noqa: ANN001
        started = self._starts.pop(run_id, None)
        if started is not None:
            self.durations_ms.append((time.perf_counter() - started) * 1000)

    def on_llm_end(self, response, *, run_id, **kwargs):  # noqa: ANN001
        self._stop(run_id)
        for generations in response.generations:
            for gen in generations:
                usage = getattr(getattr(gen, "message", None), "usage_metadata", None) or {}
                self.prompt_tokens += int(usage.get("input_tokens", 0) or 0)
                self.completion_tokens += int(usage.get("output_tokens", 0) or 0)

    def on_llm_error(self, error, *, run_id, **kwargs):  # noqa: ANN001
        self._stop(run_id)


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.openrouter_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=0.1,
        max_tokens=settings.llm_max_tokens,
        timeout=45,
        max_retries=1,
    )


def _extract_reply(result: dict[str, Any]) -> str:
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            content = msg.content
            if isinstance(content, list):
                content = "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
            return (content or "").strip()
    return ""


def _decide_attention(records: list[dict[str, Any]], handoff: bool, error: str | None) -> tuple[str | None, str | None]:
    if error:
        return "error", f"Agent error: {error[:200]}"
    failed = [r for r in records if not r["ok"]]
    if failed:
        return "error", f"Tool failure in {failed[0]['tool_name']}: {(failed[0]['error'] or '')[:160]}"
    if handoff:
        return "handoff", "User asked for legal/tax/valuation advice or a human."
    blocked = [r for r in records if r["blocked"]]
    if blocked:
        return "clarification", f"Waiting on user: {(blocked[-1]['clarification'] or '')[:200]}"
    return None, None


def _apply_attention(conversation: Conversation, kind: str | None, reason: str | None) -> None:
    current = conversation.attention_kind
    if kind:
        if current in STICKY and current != kind:
            if PRIORITY[kind] > PRIORITY[current]:
                conversation.attention_kind = kind
                conversation.attention_reason = f"{reason} (earlier: {conversation.attention_reason})"[:400]
            # lower priority than an unresolved sticky flag: keep the sticky one
        else:
            conversation.attention_kind, conversation.attention_reason = kind, reason
    elif current == "clarification":
        conversation.attention_kind = None
        conversation.attention_reason = None
    conversation.needs_attention = conversation.attention_kind is not None


def run_agent(db: Session, conversation: Conversation, user: User, user_text: str, llm: Any | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    run = AgentRun(conversation_id=conversation.id, user_id=user.user_id, status="running")
    db.add(run)
    db.commit()  # persisted now so a later rollback can't lose the run or the user's message
    run_id, conv_id, user_id = run.id, conversation.id, user.user_id

    ctx = ToolContext(db=db, user_id=user_id)
    timing = TimingHandler()
    last_ids = list(conversation.last_mentioned_property_ids or [])
    scenario = conversation.active_scenario
    history = _history(conversation.messages, user_text)

    reply, error, used_fallback = "", None, False
    try:
        if llm is None and not settings.openrouter_api_key:
            used_fallback = True
            reply = fallback.answer(ctx, user_text, last_ids=last_ids, scenario=scenario)
        else:
            recent = portfolio.search_properties(db, user_id, property_ids=last_ids) if last_ids else []
            graph = create_react_agent(llm or _build_llm(), build_tools(ctx))
            result = graph.invoke(
                {"messages": [SystemMessage(content=_system_prompt(user, recent, scenario)), *history, HumanMessage(content=user_text)]},
                config={"callbacks": [timing], "recursion_limit": settings.max_agent_steps},
            )
            reply = _extract_reply(result)
            if "need more steps" in reply.lower():  # LangGraph's quiet way of saying the step limit was hit
                reply, error = "", "Agent step limit reached (possible tool loop)"
            elif not reply:
                error = "Model returned an empty reply"
    except Exception as exc:  # model/network/graph failure
        db.rollback()
        error = f"{type(exc).__name__}: {str(exc)[:300]}"

    if error and not reply:
        # degrade to a read-only deterministic answer; never let the fallback write after a failure
        try:
            reply = fallback.answer(ctx, user_text, last_ids=last_ids, scenario=scenario, read_only=True)
            used_fallback = True
        except Exception as exc2:
            db.rollback()
            error += f" | fallback failed: {type(exc2).__name__}"
            reply = ERROR_REPLY

    handoff = bool(HANDOFF_RE.search(user_text))
    if handoff and "flagged" not in reply.lower():
        reply = f"{reply}\n\n{HANDOFF_NOTE}".strip()

    total_ms = (time.perf_counter() - started) * 1000
    tool_ms = sum(r["duration_ms"] for r in ctx.records)
    model_ms = sum(timing.durations_ms)

    # ---- persist telemetry (re-fetch rows: the session may have been rolled back)
    run = db.get(AgentRun, run_id)
    conversation = db.get(Conversation, conv_id)
    run.status = "error" if error else "ok"
    run.error_message = error
    run.total_ms, run.tool_ms, run.model_ms = total_ms, tool_ms, model_ms
    run.used_fallback = used_fallback
    run.llm_calls = len(timing.durations_ms)
    run.prompt_tokens, run.completion_tokens = timing.prompt_tokens, timing.completion_tokens
    for rec in ctx.records:
        db.add(
            ToolCall(
                run_id=run_id,
                tool_name=rec["tool_name"],
                arguments_json=rec["arguments"],
                result_preview=rec["result_preview"],
                ok=rec["ok"],
                blocked=rec["blocked"],
                duration_ms=rec["duration_ms"],
                hypothetical=rec["hypothetical"],
            )
        )

    # ---- conversation state
    mentioned = [pid for rec in ctx.records if rec["tool_name"] != "calculate_portfolio_metrics" and not rec["blocked"] for pid in rec["property_ids"]]
    typed = re.findall(r"\bP\d{3}\b", user_text, flags=re.I)
    focus = list(dict.fromkeys([i.upper() for i in typed] + mentioned))
    if focus:
        conversation.last_mentioned_property_ids = focus[:10]
    if ctx.scenario:
        conversation.active_scenario = ctx.scenario
    elif ctx.wrote:
        conversation.active_scenario = None  # real data changed; an old what-if would now be stale

    kind, reason = _decide_attention(ctx.records, handoff, error)
    _apply_attention(conversation, kind, reason)

    db.add(Message(conversation_id=conv_id, role="assistant", content=reply))
    db.commit()
    return {
        "reply": reply,
        "needs_attention": conversation.needs_attention,
        "attention_reason": conversation.attention_reason,
        "total_ms": total_ms,
        "tool_ms": tool_ms,
        "model_ms": model_ms,
        "llm_calls": run.llm_calls,
        "used_fallback": used_fallback,
        "error": error,
    }
