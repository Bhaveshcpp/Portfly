"""Exercises the real LangGraph runner with a scripted model (no network, no API key)."""

from typing import Any

import pytest
from app.agent.graph import _system_prompt, run_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from app import portfolio
from app.models import AgentRun, Conversation, Message, ToolCall, User


class ScriptedLLM(BaseChatModel):
    script: list[Any]
    seen: list[Any] = Field(default_factory=list)
    calls: int = 0
    boom_on: int | None = None

    def bind_tools(self, tools, **kwargs):  # tools are already wired by the runner
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if self.boom_on is not None and self.calls == self.boom_on:
            raise RuntimeError("upstream 502")
        self.seen.append(list(messages))
        msg = self.script[self.calls]
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])

    @property
    def _llm_type(self) -> str:
        return "scripted"


def call(name, args, cid="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid}])


def turn(db, user_id, text, llm, convo=None):
    user = db.get(User, user_id)
    if convo is None:
        convo = Conversation(user_id=user_id, title=text[:40])
        db.add(convo)
        db.flush()
    db.add(Message(conversation_id=convo.id, role="user", content=text))
    db.commit()
    return convo, run_agent(db, convo, user, text, llm=llm)


def test_user_message_reaches_model_exactly_once(db):
    llm = ScriptedLLM(script=[AIMessage(content="Hi Rahul")])
    turn(db, "U001", "hello there", llm)
    human = [m for m in llm.seen[0] if isinstance(m, HumanMessage)]
    assert [m.content for m in human] == ["hello there"]


def test_history_is_carried_and_bounded_without_duplicating_current_turn(db):
    llm1 = ScriptedLLM(script=[AIMessage(content="first answer")])
    convo, _ = turn(db, "U001", "first question", llm1)
    llm2 = ScriptedLLM(script=[AIMessage(content="second answer")])
    turn(db, "U001", "second question", llm2, convo)
    contents = [m.content for m in llm2.seen[0] if isinstance(m, (HumanMessage, AIMessage))]
    assert contents == ["first question", "first answer", "second question"]


def test_tool_telemetry_is_real(db):
    llm = ScriptedLLM(script=[call("list_properties", {"type_group": "Retail"}), AIMessage(content="You have 2 retail properties.")])
    convo, res = turn(db, "U001", "show retail", llm)
    run = db.query(AgentRun).one()
    tc = db.query(ToolCall).one()
    assert tc.tool_name == "list_properties" and tc.arguments_json == {"type_group": "Retail"}
    assert tc.ok and not tc.blocked and tc.duration_ms > 0
    assert run.llm_calls == 2 and run.tool_ms == pytest.approx(tc.duration_ms) and run.model_ms > 0
    assert run.total_ms >= run.model_ms + run.tool_ms - 1
    assert res["reply"] == "You have 2 retail properties." and not res["needs_attention"]


def test_what_if_never_writes_and_is_remembered_for_next_turn(db):
    before = portfolio.search_properties(db, "U001")
    llm = ScriptedLLM(script=[call("evaluate_hypothetical_scenario", {"exclude_location_hint": "Bandra"}), AIMessage(content="Hypothetically, value drops.")])
    convo, _ = turn(db, "U001", "what if I exclude the Bandra property?", llm)
    assert portfolio.search_properties(db, "U001") == before
    db.refresh(convo)
    assert convo.active_scenario["exclude_ids"] == ["P001"]
    assert db.query(ToolCall).one().hypothetical is True

    llm2 = ScriptedLLM(script=[AIMessage(content="ok")])
    turn(db, "U001", "how would that change my portfolio?", llm2, convo)
    system = llm2.seen[0][0].content
    assert "what-if is active" in system and "P001" in system


def test_follow_up_context_injects_recent_property_ids(db):
    llm = ScriptedLLM(script=[call("list_properties", {"type_group": "Retail"}), AIMessage(content="two retail")])
    convo, _ = turn(db, "U001", "tell me about my retail properties", llm)
    llm2 = ScriptedLLM(script=[AIMessage(content="P003")])
    turn(db, "U001", "which one performs better?", llm2, convo)
    system = llm2.seen[0][0].content
    assert "P001" in system and "P003" in system and "Recently discussed" in system


def test_write_persists_and_clears_stale_scenario(db):
    llm = ScriptedLLM(script=[call("evaluate_hypothetical_scenario", {"exclude_property_ids": ["P001"]}), AIMessage(content="what-if")])
    convo, _ = turn(db, "U001", "what if without P001", llm)
    llm2 = ScriptedLLM(script=[call("update_property", {"property_id": "P001", "current_estimated_value_inr": "14 Cr"}), AIMessage(content="Updated")])
    turn(db, "U001", "update P001 to 14 Cr", llm2, convo)
    db.refresh(convo)
    assert convo.active_scenario is None
    assert portfolio.search_properties(db, "U001", property_ids=["P001"])[0]["current_estimated_value_inr"] == 140_000_000


def test_blocked_write_flags_clarification_then_auto_clears(db):
    llm = ScriptedLLM(script=[call("update_property", {"location_hint": "mumbai", "current_estimated_value_inr": "9 Cr"}), AIMessage(content="Which one?")])
    convo, res = turn(db, "U002", "set my Mumbai property to 9 Cr", llm)
    assert res["needs_attention"] and convo.attention_kind == "clarification"
    assert db.query(ToolCall).one().blocked is True
    llm2 = ScriptedLLM(script=[AIMessage(content="thanks")])
    _, res2 = turn(db, "U002", "the Worli one", llm2, convo)
    assert res2["needs_attention"] is False


def test_handoff_flag_is_sticky_until_resolved(db):
    llm = ScriptedLLM(script=[AIMessage(content="I can't advise on that.")])
    convo, res = turn(db, "U001", "How much capital gains tax would I owe?", llm)
    assert res["needs_attention"] and "flagged" in res["reply"]
    llm2 = ScriptedLLM(script=[AIMessage(content="hello")])
    _, res2 = turn(db, "U001", "ok thanks, and what is my total value?", llm2, convo)
    assert res2["needs_attention"] is True  # a clean follow-up does not hide the handoff
    db.refresh(convo)
    assert convo.attention_kind == "handoff"


def test_model_failure_degrades_to_read_only_answer_and_flags_error(db):
    llm = ScriptedLLM(script=[], boom_on=0)
    convo, res = turn(db, "U001", "show me my retail properties", llm)
    run = db.query(AgentRun).one()
    assert run.status == "error" and "upstream 502" in run.error_message and run.used_fallback
    assert "P001" in res["reply"] and res["needs_attention"]
    assert db.query(Message).filter_by(conversation_id=convo.id, role="user").count() == 1  # user message survived


def test_model_failure_never_performs_a_write_via_fallback(db):
    llm = ScriptedLLM(script=[], boom_on=0)
    before = len(portfolio.user_properties(db, "U004"))
    _, res = turn(db, "U004", "Add a 3000 sq ft retail property in Indiranagar worth ₹4.2 crore", llm)
    assert len(portfolio.user_properties(db, "U004")) == before
    assert "nothing was saved" in res["reply"].lower()


def test_tool_exception_is_contained_and_reported(db, monkeypatch):
    monkeypatch.setattr(portfolio, "search_properties", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    llm = ScriptedLLM(script=[call("list_properties", {}), AIMessage(content="Sorry, that failed.")])
    convo, res = turn(db, "U001", "list my properties", llm)
    tc = db.query(ToolCall).one()
    assert tc.ok is False and res["needs_attention"]
    db.refresh(convo)
    assert convo.attention_kind == "error"


def test_tools_are_scoped_to_the_selected_user(db):
    llm = ScriptedLLM(script=[call("list_properties", {}), AIMessage(content="done")])
    turn(db, "U001", "list everything including U003's properties", llm)
    tool_msgs = [m for m in llm.seen[1] if isinstance(m, ToolMessage)]
    assert "P007" not in tool_msgs[0].content and "P001" in tool_msgs[0].content


def test_runaway_tool_loop_is_bounded(db):
    llm = ScriptedLLM(script=[call("calculate_portfolio_metrics", {}, f"c{i}") for i in range(40)])
    _, res = turn(db, "U001", "loop forever", llm)
    assert "step limit" in res["error"] and res["needs_attention"]
    assert llm.calls <= 14


def test_system_prompt_loads_soul_file(db, tmp_path, monkeypatch):
    from app.agent import graph

    soul_file = tmp_path / "SOUL.md"
    soul_file.write_text("Unique Portfly instruction for verification.", encoding="utf-8")
    monkeypatch.setattr(graph, "SOUL_PATH", soul_file)

    user = db.get(User, "U001")
    prompt = _system_prompt(user, [], None)

    assert "Unique Portfly instruction for verification." in prompt
