"""Deterministic keyword path used when no OpenRouter key is set (demo/CI) or the model fails.

It exercises the exact same validated domain functions, through the same tracer, as the
LLM path. It is NOT meant to match the agent's language understanding."""

from __future__ import annotations

import re
from typing import Any

from app import portfolio
from app.agent.tools import ToolContext, trace

_AMOUNT = re.compile(r"₹?\s*(\d[\d,]*(?:\.\d+)?)\s*(crores?|cr|lakhs?|lacs?)\b", re.I)
_AREA = re.compile(r"(-?\d[\d,]*)\s*(?:sq\.?\s*ft|sqft|square\s*feet)", re.I)
_HISTORY = re.compile(r"apprecia|since (?:i )?(?:bought|purchase)|cagr|\birr\b|return on|profit|capital gain|last year|over time|how much have i made", re.I)
HANDOFF_RE = re.compile(
    r"legal advice|lawyer|attorney|\btax(?:es|ation)?\b|capital gains|stamp duty|\bgst\b|valuer|"
    r"third.party valuation|(?:speak|talk) to (?:a |an |your )?(?:human|person|someone|agent|manager)|complain",
    re.I,
)
_WRITE_INTENT = re.compile(r"\b(add|update|change|set|modify|revalue)\b", re.I)


def inr(n: float | None) -> str:
    if n is None:
        return "n/a"
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n >= 10_000_000:
        return f"{sign}₹{n / 10_000_000:.2f} Cr"
    if n >= 100_000:
        return f"{sign}₹{n / 100_000:.2f} L"
    return f"{sign}₹{n:,.0f}"


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def _amount(text: str) -> str | None:
    m = _AMOUNT.search(text)
    return f"{m.group(1)} {m.group(2)}" if m else None


def _type_group(lower: str) -> str | None:
    if "retail" in lower or "shop" in lower:
        return "Retail"
    if "residential" in lower or "apartment" in lower or "villa" in lower:
        return "Residential"
    if "office" in lower or "commercial" in lower:
        return "Office"
    return None


def _find_place(lower: str, props: list[dict[str, Any]]) -> str | None:
    for p in props:
        locality = p["location"].split(",")[0].strip().lower()
        key = locality if any(ch.isdigit() for ch in locality) else locality.split()[0]
        if key in lower:
            return key
    for p in props:
        if p["city"].lower() in lower:
            return p["city"]
    return None


def _call(ctx: ToolContext, name: str, args: dict[str, Any], fn, **kw) -> dict[str, Any]:
    import json

    return json.loads(trace(ctx, name, args, fn, **kw))


def _line(p: dict[str, Any]) -> str:
    return f"• {p['property_id']}: {p['sub_type']} in {p['location']} — {inr(p['current_estimated_value_inr'])}, rent {inr(p['annual_rent_inr'])}/yr, {p['occupancy_status']}"


def _speak_metrics(m: dict[str, Any]) -> str:
    lines = [
        f"Your portfolio: {m['property_count']} properties worth {inr(m['total_portfolio_value_inr'])}, "
        f"earning {inr(m['total_annual_rent_inr'])}/yr (yield {_pct(m['portfolio_yield'])})."
    ]
    for group, s in sorted(m["by_type_group"].items(), key=lambda kv: -kv[1]["value_inr"]):
        lines.append(f"• {group}: {inr(s['value_inr'])} ({_pct(s['share_of_value'])} of value, {s['count']} {'property' if s['count'] == 1 else 'properties'}, yield {_pct(s['yield'])})")
    cities = sorted(m["by_city"].items(), key=lambda kv: -kv[1]["value_inr"])
    lines.append("By city: " + ", ".join(f"{c} {_pct(s['share_of_value'])}" for c, s in cities))
    idle = m.get("non_income_assets") or []
    if idle:
        lines.append(f"{len(idle)} propert{'y earns' if len(idle) == 1 else 'ies earn'} no rent ({', '.join(a['property_id'] for a in idle)}).")
    return "\n".join(lines)


def _speak_scenario(r: dict[str, Any]) -> str:
    d = r["delta"]
    parts = []
    if r["excluded_property_ids"]:
        parts.append("excluding " + ", ".join(r["excluded_property_ids"]))
    if r["value_overrides"]:
        parts.append("re-valuing " + ", ".join(f"{k} at {inr(v)}" for k, v in r["value_overrides"].items()))
    if r["hypothetical_additions"]:
        parts.append(f"adding {len(r['hypothetical_additions'])} imaginary propert{'y' if len(r['hypothetical_additions']) == 1 else 'ies'}")
    shares = ", ".join(f"{g} {_pct(d['type_share_before'][g])}→{_pct(d['type_share_after'][g])}" for g in d["type_share_before"])
    return (
        f"What-if ({' and '.join(parts)}) — nothing was saved.\n"
        f"Value: {inr(r['actual']['total_portfolio_value_inr'])} → {inr(r['scenario']['total_portfolio_value_inr'])} ({inr(d['value_change_inr'])}).\n"
        f"Annual rent: {inr(r['actual']['total_annual_rent_inr'])} → {inr(r['scenario']['total_annual_rent_inr'])}. "
        f"Yield: {_pct(d['yield_before'])} → {_pct(d['yield_after'])}.\n"
        f"Type mix: {shares}."
    )


def answer(ctx: ToolContext, text: str, *, last_ids: list[str], scenario: dict[str, Any] | None, read_only: bool = False) -> str:
    db, user_id = ctx.db, ctx.user_id
    lower = text.lower()
    props = [p for p in portfolio.search_properties(db, user_id)]

    if HANDOFF_RE.search(text):
        return "That needs a specialist: I can't give legal, tax or formal valuation advice. I can share your portfolio numbers to help that conversation."

    if _HISTORY.search(lower):
        return (
            "I can't answer that honestly: purchase prices and purchase dates aren't in your portfolio data, "
            "so I can't compute appreciation or historical returns. I can give current value, rent and yield. "
            "If you share what you paid and when, I can note it down."
        )

    # ---- writes
    if _WRITE_INTENT.search(lower) and (_amount(lower) or _AREA.search(lower)):
        if read_only:
            return "I couldn't complete that change just now, and nothing was saved. Please try again in a moment."
        if re.search(r"\badd\b", lower):
            area = _AREA.search(lower)
            loc = re.search(r"\bin ([A-Za-z][A-Za-z .]+?)(?:\s+(?:worth|valued|for|at|priced)\b|[.,]|$)", text)
            payload = {
                "property_type": _type_group(lower) or "",
                "location": loc.group(1).strip() if loc else "",
                "area_sqft": area.group(1) if area else None,
                "current_estimated_value_inr": _amount(lower),
            }
            res = _call(ctx, "add_property", payload, lambda: portfolio.add_property(db, user_id, payload))
            if not res.get("ok"):
                return res["message"]
            p = res["property"]
            note = (" " + " ".join(res["assumptions"])) if res["assumptions"] else ""
            return f"Added {p['property_id']}: {p['sub_type']} in {p['location']}, {p['area_sqft']:,.0f} sq ft, {inr(p['current_estimated_value_inr'])}.{note}"
        place = _find_place(lower, props)
        tg = _type_group(lower)
        pid = last_ids[0] if (not place and not tg and len(last_ids) == 1) else None
        updates = {"current_estimated_value_inr": _amount(lower)}
        args = {"property_id": pid, "location_hint": place, "type_hint": tg, **updates}
        res = _call(ctx, "update_property", args, lambda: portfolio.update_property(db, user_id, property_id=pid, location_hint=place, type_hint=tg, updates=updates))
        if not res.get("ok"):
            if res.get("candidates"):
                return "Which one do you mean?\n" + "\n".join(_line(c) for c in res["candidates"])
            return res["message"]
        p, prev = res["property"], res["previous"].get("current_estimated_value_inr")
        return f"Updated {p['property_id']} ({p['location']}): value {inr(prev)} → {inr(p['current_estimated_value_inr'])}. This is saved."

    # ---- what-if
    if re.search(r"what if|exclud|without|suppose|hypothetic", lower):
        place, tg = _find_place(lower, props), _type_group(lower)
        if place or tg:
            args = {"exclude_location_hint": place, "exclude_type_group": None if place else tg}

            def run():
                ids = [p.property_id for p in portfolio.match_properties(db, user_id, location_hint=place)] if place else \
                      [p["property_id"] for p in props if p["type_group"] == tg]
                r = portfolio.scenario_for_user(db, user_id, exclude_ids=ids)
                if r.get("ok"):
                    ctx.scenario = {"exclude_ids": r["excluded_property_ids"], "value_overrides": {}, "additions": []}
                return r

            res = _call(ctx, "evaluate_hypothetical_scenario", args, run, hypothetical=True)
            return _speak_scenario(res) if res.get("ok") else res["message"]

    if re.search(r"how would that change|that change|what changes|impact", lower):
        if scenario:
            res = _call(ctx, "evaluate_hypothetical_scenario", {"replay": True}, lambda: portfolio.scenario_for_user(
                db, user_id, exclude_ids=scenario.get("exclude_ids"), value_overrides=scenario.get("value_overrides"), additions=scenario.get("additions")), hypothetical=True)
            return _speak_scenario(res) if res.get("ok") else res["message"]
        return "I don't have a what-if in progress. Tell me what to exclude or re-value and I'll show the impact (without changing anything)."

    # ---- analysis
    if re.search(r"perform|better|best|worst", lower):
        pool = [p for p in props if p["property_id"] in last_ids] if last_ids else props
        pool = [p for p in pool if p["rental_yield"] is not None]
        if not pool:
            return "Which properties should I compare? Tell me a type or location."
        ranked = sorted(pool, key=lambda p: -(p["rental_yield"] or 0))
        scope = "the properties we just discussed" if last_ids else "your portfolio"
        out = [f"Ranked by rental yield across {scope} (current value, not cost — I have no purchase prices):"]
        out += [f"• {p['property_id']} {p['location']}: {_pct(p['rental_yield'])}" for p in ranked]
        return "\n".join(out)

    if re.search(r"\brent\b", lower) and re.search(r"highest|most|top|max|generat", lower):
        m = _call(ctx, "calculate_portfolio_metrics", {}, lambda: {"ok": True, **portfolio.metrics_for_user(db, user_id)})
        h = m.get("highest_rent")
        return f"{h['property_id']} in {h['location']} earns the most: {inr(h['annual_rent_inr'])}/yr." if h else "None of your properties currently earn rent."

    if re.search(r"total|look like|exposure|compare|yield|how much|share|concentrat|breakdown|allocation|diversif", lower):
        m = _call(ctx, "calculate_portfolio_metrics", {}, lambda: {"ok": True, **portfolio.metrics_for_user(db, user_id)})
        return _speak_metrics(m)

    # ---- default: filtered list
    args: dict[str, Any] = {
        "type_group": _type_group(lower),
        "location_contains": _find_place(lower, props),
        "min_value_inr": _amount(lower) if re.search(r"above|over|more than|>", lower) else None,
        "occupancy_status": "Vacant" if "vacant" in lower else None,
    }
    clean = {k: v for k, v in args.items() if v is not None}
    res = _call(ctx, "list_properties", clean, lambda: {"ok": True, "properties": portfolio.search_properties(db, user_id, **clean)})
    rows = res["properties"]
    if not rows:
        return "No properties match that."
    return f"{len(rows)} propert{'y' if len(rows) == 1 else 'ies'}:\n" + "\n".join(_line(p) for p in rows)
