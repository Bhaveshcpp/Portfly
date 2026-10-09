"""LangChain tools. Every tool is closed over one user_id and goes through trace(),
so the dashboard gets real arguments, durations and outcomes for each call."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app import portfolio
from app.analytics import normalize_type_group

PREVIEW_CHARS = 900


@dataclass
class ToolContext:
    """Per-request state shared between the tools and the agent runner."""

    db: Session
    user_id: str
    records: list[dict[str, Any]] = field(default_factory=list)
    scenario: dict[str, Any] | None = None  # inputs of the latest successful what-if
    wrote: bool = False  # a real write succeeded this turn (invalidates any stale what-if)


def _property_ids(result: Any) -> list[str]:
    ids: list[str] = []
    if isinstance(result, dict):
        for p in result.get("properties") or []:
            ids.append(p["property_id"])
        if isinstance(result.get("property"), dict):
            ids.append(result["property"]["property_id"])
        ids.extend(result.get("excluded_property_ids") or [])
        ids.extend((result.get("value_overrides") or {}).keys())
    return list(dict.fromkeys(ids))


def trace(ctx: ToolContext, name: str, args: dict[str, Any], fn: Callable[[], dict[str, Any]], *, hypothetical: bool = False) -> str:
    """Run one tool body, time it, record it, and return JSON the model can read."""
    started = time.perf_counter()
    exc_text = None
    try:
        result = fn()
    except Exception as exc:  # a tool must never crash the whole turn
        ctx.db.rollback()
        exc_text = f"{type(exc).__name__}: {exc}"
        result = {"ok": False, "error": "The tool failed unexpectedly. Tell the user and offer to retry.", "detail": exc_text}
    duration_ms = (time.perf_counter() - started) * 1000
    payload = json.dumps(result, default=str)
    blocked = isinstance(result, dict) and result.get("needs_clarification") is True
    ctx.records.append(
        {
            "tool_name": name,
            "arguments": {k: v for k, v in args.items() if v is not None},
            "result_preview": payload[:PREVIEW_CHARS],
            "ok": exc_text is None,
            "blocked": blocked,
            "error": exc_text,
            "clarification": result.get("message") if blocked else None,
            "duration_ms": duration_ms,
            "hypothetical": hypothetical,
            "property_ids": _property_ids(result),
        }
    )
    if isinstance(result, dict) and result.get("ok") is True and name in {"add_property", "update_property"}:
        ctx.wrote = True
    return payload


def build_tools(ctx: ToolContext) -> list:
    db, user_id = ctx.db, ctx.user_id

    @tool
    def list_properties(
        type_group: str | None = None,
        location_contains: str | None = None,
        min_value_inr: float | str | None = None,
        occupancy_status: str | None = None,
    ) -> str:
        """List this user's properties, optionally filtered. type_group is Retail, Residential or Office
        (Commercial Office is part of Office). location_contains matches locality or city, e.g. 'Mumbai'.
        min_value_inr may be passed as the user said it, e.g. '10 Cr'. occupancy_status is Tenanted, Vacant or Self-occupied."""
        args = dict(type_group=type_group, location_contains=location_contains, min_value_inr=min_value_inr, occupancy_status=occupancy_status)

        def run() -> dict[str, Any]:
            try:
                rows = portfolio.search_properties(db, user_id, **args)
            except portfolio.InputError as exc:
                return {"ok": False, "needs_clarification": True, "message": str(exc)}
            return {"ok": True, "count": len(rows), "properties": rows}

        return trace(ctx, "list_properties", args, run)

    @tool
    def calculate_portfolio_metrics() -> str:
        """Exact totals for this user: portfolio value, annual rent, yield, exposure by type group
        (Retail/Residential/Office) and by city, occupancy, highest value/rent, and assets earning no rent.
        Use this for any total, share, comparison or concentration question. Never do this arithmetic yourself."""
        return trace(ctx, "calculate_portfolio_metrics", {}, lambda: {"ok": True, **portfolio.metrics_for_user(db, user_id)})

    @tool
    def add_property(
        property_type: str,
        location: str,
        area_sqft: float | str,
        current_estimated_value_inr: float | str,
        city: str | None = None,
        sub_type: str | None = None,
        annual_rent_inr: float | str | None = None,
        occupancy_status: str | None = None,
        confirmed: bool = False,
    ) -> str:
        """Save a NEW property for this user. Required: property_type (Retail, Residential or Office), location,
        area_sqft and current_estimated_value_inr. Pass money exactly as the user said it ('12 Cr', '50 lakh').
        If they give a bare number (e.g. 12) with no Cr/lakh/₹, do not assume crore — ask them to clarify instead of calling this tool.
        If the tool returns needs_clarification, ask the user and only retry with confirmed=true after they agree.
        Always tell the user any 'assumptions' returned (assumed city, assumed occupancy)."""
        args = dict(
            property_type=property_type, location=location, area_sqft=area_sqft,
            current_estimated_value_inr=current_estimated_value_inr, city=city, sub_type=sub_type,
            annual_rent_inr=annual_rent_inr, occupancy_status=occupancy_status, confirmed=confirmed or None,
        )
        payload = {k: v for k, v in args.items() if k != "confirmed"}
        return trace(ctx, "add_property", args, lambda: portfolio.add_property(db, user_id, payload, confirmed=confirmed))

    @tool
    def update_property(
        property_id: str | None = None,
        location_hint: str | None = None,
        type_hint: str | None = None,
        current_estimated_value_inr: float | str | None = None,
        annual_rent_inr: float | str | None = None,
        occupancy_status: str | None = None,
        area_sqft: float | str | None = None,
        confirmed: bool = False,
    ) -> str:
        """Change ONE existing property. Identify it by property_id (preferred, e.g. from recently discussed
        properties) or by location_hint / type_hint. If several match you get candidates: ask the user which one.
        Pass money exactly as the user said it ('14 Cr'). Never invent a unit; a bare 12 is not 12 Cr — ask first.
        Retry with confirmed=true only after the user agrees to a flagged change."""
        args = dict(
            property_id=property_id, location_hint=location_hint, type_hint=type_hint,
            current_estimated_value_inr=current_estimated_value_inr, annual_rent_inr=annual_rent_inr,
            occupancy_status=occupancy_status, area_sqft=area_sqft, confirmed=confirmed or None,
        )
        updates = {
            k: args[k]
            for k in ("current_estimated_value_inr", "annual_rent_inr", "occupancy_status", "area_sqft")
        }
        return trace(
            ctx,
            "update_property",
            args,
            lambda: portfolio.update_property(
                db, user_id, property_id=property_id, location_hint=location_hint,
                type_hint=type_hint, updates=updates, confirmed=confirmed,
            ),
        )

    @tool
    def evaluate_hypothetical_scenario(
        exclude_property_ids: list[str] | None = None,
        exclude_location_hint: str | None = None,
        exclude_type_group: str | None = None,
        value_overrides: dict[str, float | str] | None = None,
        hypothetical_additions: list[dict[str, float | str]] | None = None,
    ) -> str:
        """WHAT-IF ONLY. Never saves anything. Exclude properties (by ids, by location_hint such as 'Bandra', or by
        type group), re-value properties via value_overrides {property_id: '14 Cr'}, or add imaginary properties
        (dicts with property_type, area_sqft, current_estimated_value_inr, optional location/annual_rent_inr).
        Returns actual vs scenario metrics plus an exact 'delta'. Describe results as hypothetical, not real."""
        args = dict(
            exclude_property_ids=exclude_property_ids, exclude_location_hint=exclude_location_hint,
            exclude_type_group=exclude_type_group, value_overrides=value_overrides,
            hypothetical_additions=hypothetical_additions,
        )

        def run() -> dict[str, Any]:
            ids = list(exclude_property_ids or [])
            by_hint: list[str] = []
            if exclude_location_hint:
                by_hint += [p.property_id for p in portfolio.match_properties(db, user_id, location_hint=exclude_location_hint)]
            if exclude_type_group:
                group = normalize_type_group(exclude_type_group)
                by_hint += [p.property_id for p in portfolio.user_properties(db, user_id) if p.type_group == group]
            result = portfolio.scenario_for_user(
                db, user_id, exclude_ids=ids + by_hint, value_overrides=value_overrides, additions=hypothetical_additions
            )
            if (exclude_location_hint or exclude_type_group) and not by_hint and not ids and result.get("ok") is False:
                return _clarify_no_match(exclude_location_hint or exclude_type_group)
            if result.get("ok"):
                result["excluded_by_hint"] = by_hint
                ctx.scenario = {
                    "exclude_ids": result["excluded_property_ids"],
                    "value_overrides": result["value_overrides"],
                    "additions": result["hypothetical_additions"],
                }
            return result

        return trace(ctx, "evaluate_hypothetical_scenario", args, run, hypothetical=True)

    return [list_properties, calculate_portfolio_metrics, add_property, update_property, evaluate_hypothetical_scenario]


def _clarify_no_match(hint: str | None) -> dict[str, Any]:
    return {"ok": False, "needs_clarification": True, "message": f"No property of this user matches '{hint}'. Ask which one they mean."}
