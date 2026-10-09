"""Domain operations on a user's portfolio. Every function is scoped to one user_id.

All validation lives here (not in the prompt) so the rules hold no matter which
model, tool wrapper or fallback path calls them.
"""

from __future__ import annotations

import math
import re
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics import (
    apply_scenario,
    city_of,
    compare_metrics,
    compute_metrics,
    normalize_type_group,
    parse_city,
    serialize_property,
)
from app.models import Property, User

CRORE = 10_000_000
LAKH = 100_000

VALID_GROUPS = {"Retail", "Residential", "Office"}
OCCUPANCY = {
    "tenanted": "Tenanted",
    "let": "Tenanted",
    "rented": "Tenanted",
    "vacant": "Vacant",
    "empty": "Vacant",
    "self-occupied": "Self-occupied",
    "self occupied": "Self-occupied",
    "owner-occupied": "Self-occupied",
    "owner occupied": "Self-occupied",
}

MIN_VALUE_INR = 100_000  # below ₹1 lakh is almost certainly a unit slip (e.g. "12" instead of "12 Cr")
MAX_VALUE_INR = 100_000 * CRORE
MIN_PER_SQFT, MAX_PER_SQFT = 1_000, 500_000  # outside this range: ask before saving
MIN_AREA, MAX_AREA = 10, 10_000_000

_UNITS = {
    "crore": CRORE, "crores": CRORE, "cr": CRORE, "crs": CRORE,
    "lakh": LAKH, "lakhs": LAKH, "lac": LAKH, "lacs": LAKH,
    "k": 1_000, "million": 1_000_000, "mn": 1_000_000,
}


class InputError(ValueError):
    """User-facing validation problem; message is safe to show or relay."""


# ----------------------------------------------------------------------------- parsing


def parse_inr(value: Any) -> float | None:
    """'₹14 Cr' -> 140000000.0, '50 lakh' -> 5000000.0, '1,20,00,000' -> 12000000.0.

    The model is told to pass amounts exactly as the user wrote them; unit conversion
    happens here, deterministically, instead of inside the LLM.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise InputError("An amount must be a number, not true/false.")
    if isinstance(value, (int, float)):
        amount = float(value)
    else:
        s = str(value).lower()
        s = re.sub(r"₹|\binr\b|\brs\.?(?=\s|\d)", "", s).replace(",", "").strip()
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([a-z]+)?", s)
        if not m:
            raise InputError(f"I couldn't read '{value}' as an amount in rupees.")
        unit = m.group(2)
        if unit and unit not in _UNITS:
            raise InputError(f"I don't recognise the unit '{unit}' in '{value}'. Use Cr, lakh or plain rupees.")
        amount = float(m.group(1)) * _UNITS.get(unit, 1)
    if not math.isfinite(amount):
        raise InputError("That amount isn't a valid number.")
    return amount


def _parse_area(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise InputError("Area must be a number of square feet.")
    try:
        area = float(str(value).lower().replace(",", "").replace("sqft", "").replace("sq ft", "").strip())
    except ValueError:
        raise InputError(f"I couldn't read '{value}' as an area in sq ft.") from None
    if not math.isfinite(area):
        raise InputError("Area isn't a valid number.")
    return area


def _normalize_occupancy(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    key = str(value).strip().lower()
    if key not in OCCUPANCY:
        raise InputError("Occupancy must be Tenanted, Vacant or Self-occupied.")
    return OCCUPANCY[key]


def _clarify(message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "needs_clarification": True, "message": message, **extra}


def _check_ranges(area: float | None, value: float | None, rent: float | None) -> None:
    if area is not None and not (MIN_AREA <= area <= MAX_AREA):
        raise InputError(f"Area of {area:,.0f} sq ft looks wrong (expected {MIN_AREA}–{MAX_AREA:,}). Ask the user to confirm.")
    if value is not None:
        if value <= 0:
            raise InputError("Value must be greater than zero.")
        if value < MIN_VALUE_INR:
            raise InputError(
                f"₹{value:,.0f} is below ₹1 lakh, which is almost certainly a unit slip. "
                "Ask the user to restate the value (for example '12 Cr')."
            )
        if value > MAX_VALUE_INR:
            raise InputError("That value is above ₹10,000 Cr; ask the user to confirm it.")
    if rent is not None and rent < 0:
        raise InputError("Annual rent cannot be negative.")


def _per_sqft_warning(area: float | None, value: float | None) -> str | None:
    if not area or not value:
        return None
    per = value / area
    if per < MIN_PER_SQFT or per > MAX_PER_SQFT:
        return (
            f"That works out to ₹{per:,.0f} per sq ft, which is outside the usual range "
            f"(₹{MIN_PER_SQFT:,}–₹{MAX_PER_SQFT:,}). Ask the user to double-check area and value."
        )
    return None


def _occupancy_conflict(occupancy: str | None, rent: float | None) -> str | None:
    rent = rent or 0
    if occupancy == "Tenanted" and rent == 0:
        return "The property is Tenanted but annual rent is ₹0. Ask for the rent, or confirm that it really is rent-free."
    if occupancy in {"Vacant", "Self-occupied"} and rent > 0:
        return f"The property is {occupancy} but has annual rent of ₹{rent:,.0f}. Ask which one is right."
    return None


# ----------------------------------------------------------------------------- reads


def next_property_id(db: Session) -> str:
    rows = db.query(Property.property_id).all()
    max_n = 0
    for (pid,) in rows:
        if pid and pid[0].upper() == "P":
            try:
                max_n = max(max_n, int(pid[1:]))
            except ValueError:
                continue
    return f"P{max_n + 1:03d}"


def user_properties(db: Session, user_id: str) -> list[Property]:
    return (
        db.query(Property)
        .filter(Property.user_id == user_id, Property.status == "Active")
        .order_by(Property.property_id)
        .all()
    )


def search_properties(
    db: Session,
    user_id: str,
    *,
    type_group: str | None = None,
    location_contains: str | None = None,
    min_value_inr: float | str | None = None,
    occupancy_status: str | None = None,
    property_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    q = db.query(Property).filter(Property.user_id == user_id, Property.status == "Active")
    if type_group:
        q = q.filter(func.lower(Property.type_group) == normalize_type_group(type_group).lower())
    if location_contains:
        like = f"%{location_contains.strip()}%"
        q = q.filter(Property.location.ilike(like) | Property.city.ilike(like))
    min_value = parse_inr(min_value_inr)
    if min_value is not None:
        q = q.filter(Property.current_estimated_value_inr > min_value)
    if occupancy_status:
        occ = _normalize_occupancy(occupancy_status)
        q = q.filter(func.lower(Property.occupancy_status) == occ.lower())
    if property_ids:
        q = q.filter(Property.property_id.in_(property_ids))
    return [serialize_property(p) for p in q.order_by(Property.property_id).all()]


def match_properties(
    db: Session,
    user_id: str,
    *,
    property_id: str | None = None,
    location_hint: str | None = None,
    type_hint: str | None = None,
) -> list[Property]:
    rows = user_properties(db, user_id)
    if property_id:
        return [p for p in rows if p.property_id.upper() == property_id.strip().upper()]
    matches = rows
    if location_hint:
        hint = location_hint.lower()
        matches = [p for p in matches if hint in p.location.lower() or hint in (p.city or "").lower()]
    if type_hint:
        group = normalize_type_group(type_hint)
        matches = [
            p
            for p in matches
            if p.type_group.lower() == group.lower() or type_hint.lower() in (p.property_type or "").lower()
        ]
    return matches


def metrics_for_user(db: Session, user_id: str) -> dict[str, Any]:
    return compute_metrics(user_properties(db, user_id))


# ----------------------------------------------------------------------------- city


def resolve_city(db: Session, user_id: str, location: str, city_arg: str | None) -> tuple[str, str, str | None] | None:
    """Return (full_location, city, assumption_note). None means 'ask the user which city'."""
    loc = location.strip()
    if city_arg and city_arg.strip():
        city = city_arg.strip()
        return (loc if "," in loc else f"{loc}, {city}"), city, None
    if "," in loc:
        return loc, parse_city(loc), None
    for p in user_properties(db, user_id):
        if p.location.split(",")[0].strip().lower() == loc.lower():
            c = city_of(p)
            return f"{loc}, {c}", c, f"City set to {c}, matching your existing property {p.property_id} in {loc}."
    user = db.get(User, user_id)
    home = (user.city if user else "") or ""
    if home and "ncr" not in home.lower():
        return f"{loc}, {home}", home, f"No city was given, so I assumed {home} (your home city)."
    return None


# ----------------------------------------------------------------------------- writes


def add_property(db: Session, user_id: str, payload: dict[str, Any], *, confirmed: bool = False) -> dict[str, Any]:
    missing = [
        f for f in ("property_type", "location", "area_sqft", "current_estimated_value_inr") if payload.get(f) in (None, "")
    ]
    if missing:
        return _clarify(f"Need these fields before saving: {', '.join(missing)}. Ask the user for them.", missing_fields=missing)

    try:
        area = _parse_area(payload["area_sqft"])
        value = parse_inr(payload["current_estimated_value_inr"])
        rent = parse_inr(payload.get("annual_rent_inr"))
        occupancy = _normalize_occupancy(payload.get("occupancy_status"))
        _check_ranges(area, value, rent)
        ownership = float(payload.get("ownership_percent") or 100)
        if not (0 < ownership <= 100):
            raise InputError("Ownership percent must be between 1 and 100.")
    except (InputError, ValueError) as exc:
        return _clarify(str(exc))

    group = normalize_type_group(payload["property_type"])
    if group not in VALID_GROUPS:
        return _clarify(
            f"'{payload['property_type']}' isn't a type I track. Use Retail, Residential or Office "
            "(Commercial Office counts as Office). Ask the user which fits."
        )

    resolved = resolve_city(db, user_id, str(payload["location"]), payload.get("city"))
    if resolved is None:
        return _clarify(f"Which city is '{payload['location']}' in? Ask the user before saving.")
    full_location, city, city_note = resolved

    assumptions: list[str] = [city_note] if city_note else []
    if occupancy is None:
        occupancy = "Tenanted" if (rent or 0) > 0 else "Vacant"
        assumptions.append(f"Occupancy wasn't given, so it was set to {occupancy}.")
    if not rent:
        assumptions.append("No rent recorded (₹0).")

    if not confirmed:
        conflict = _occupancy_conflict(occupancy, rent)
        if conflict:
            return _clarify(conflict + " If the user confirms, call again with confirmed=true.", can_confirm=True)
        warning = _per_sqft_warning(area, value)
        if warning:
            return _clarify(warning + " If they confirm it is right, call again with confirmed=true.", can_confirm=True)
        for p in user_properties(db, user_id):
            if p.location.lower() == full_location.lower() and p.type_group == group and abs(p.area_sqft - area) < 1:
                return _clarify(
                    f"This looks like a duplicate of {p.property_id} ({p.location}, {p.area_sqft:,.0f} sq ft). "
                    "Ask whether it is a separate property; if yes, call again with confirmed=true.",
                    can_confirm=True,
                    duplicate_of=p.property_id,
                )

    prop = Property(
        property_id=next_property_id(db),
        user_id=user_id,
        property_type=str(payload["property_type"]).strip().title(),
        type_group=group,
        sub_type=payload.get("sub_type") or str(payload["property_type"]).strip().title(),
        location=full_location,
        city=city,
        area_sqft=area,
        current_estimated_value_inr=value,
        purchase_price_inr=None,
        annual_rent_inr=rent or 0.0,
        occupancy_status=occupancy,
        tenant_status="Yes" if occupancy == "Tenanted" else "No",
        ownership_percent=ownership,
        status="Active",
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return {"ok": True, "property": serialize_property(prop), "assumptions": assumptions}


_UPDATABLE = {"current_estimated_value_inr", "annual_rent_inr", "occupancy_status", "area_sqft", "sub_type"}


def update_property(
    db: Session,
    user_id: str,
    *,
    property_id: str | None = None,
    location_hint: str | None = None,
    type_hint: str | None = None,
    updates: dict[str, Any] | None = None,
    confirmed: bool = False,
) -> dict[str, Any]:
    if not (property_id or location_hint or type_hint):
        return _clarify("Which property? Ask the user for a property id, location or type.")
    matches = match_properties(db, user_id, property_id=property_id, location_hint=location_hint, type_hint=type_hint)
    if not matches:
        return _clarify("No matching property found for this user. Ask which property they mean.")
    if len(matches) > 1:
        return _clarify(
            "Multiple properties match. Ask the user to pick one before updating.",
            candidates=[serialize_property(p) for p in matches],
        )
    prop = matches[0]

    raw = {k: v for k, v in (updates or {}).items() if k in _UPDATABLE and v not in (None, "")}
    if not raw:
        return _clarify("No valid fields to update. I can change value, annual rent, occupancy, area or sub-type.")

    try:
        changes: dict[str, Any] = {}
        if "current_estimated_value_inr" in raw:
            changes["current_estimated_value_inr"] = parse_inr(raw["current_estimated_value_inr"])
        if "annual_rent_inr" in raw:
            changes["annual_rent_inr"] = parse_inr(raw["annual_rent_inr"])
        if "area_sqft" in raw:
            changes["area_sqft"] = _parse_area(raw["area_sqft"])
        if "occupancy_status" in raw:
            changes["occupancy_status"] = _normalize_occupancy(raw["occupancy_status"])
        if "sub_type" in raw:
            changes["sub_type"] = str(raw["sub_type"]).strip()
        _check_ranges(changes.get("area_sqft"), changes.get("current_estimated_value_inr"), changes.get("annual_rent_inr"))
    except InputError as exc:
        return _clarify(str(exc))

    new_value = changes.get("current_estimated_value_inr", prop.current_estimated_value_inr)
    new_area = changes.get("area_sqft", prop.area_sqft)
    new_rent = changes.get("annual_rent_inr", prop.annual_rent_inr)
    new_occ = changes.get("occupancy_status", prop.occupancy_status)

    if not confirmed:
        if "occupancy_status" in changes or "annual_rent_inr" in changes:
            conflict = _occupancy_conflict(new_occ, new_rent)
            if conflict:
                return _clarify(
                    f"For {prop.property_id}: {conflict} If the user confirms, call again with confirmed=true.",
                    can_confirm=True,
                )
        if "current_estimated_value_inr" in changes or "area_sqft" in changes:
            warning = _per_sqft_warning(new_area, new_value)
            if warning:
                return _clarify(f"For {prop.property_id}: {warning} If they confirm, call again with confirmed=true.", can_confirm=True)

    previous = {k: getattr(prop, k) for k in changes}
    for key, value in changes.items():
        setattr(prop, key, value)
    if "occupancy_status" in changes:
        prop.tenant_status = "Yes" if prop.occupancy_status == "Tenanted" else "No"
    db.commit()
    db.refresh(prop)
    return {"ok": True, "property": serialize_property(prop), "applied": changes, "previous": previous}


# ----------------------------------------------------------------------------- what-if


def scenario_for_user(
    db: Session,
    user_id: str,
    *,
    exclude_ids: list[str] | None = None,
    value_overrides: dict[str, Any] | None = None,
    additions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pure what-if. Reads the portfolio, never writes."""
    actual = user_properties(db, user_id)
    known = {p.property_id for p in actual}
    exclude = list(dict.fromkeys(exclude_ids or []))
    try:
        overrides = {}
        for pid, raw in (value_overrides or {}).items():
            amount = parse_inr(raw)
            _check_ranges(None, amount, None)
            overrides[pid] = amount
        adds = []
        for i, add in enumerate(additions or [], start=1):
            missing = [f for f in ("property_type", "area_sqft", "current_estimated_value_inr") if add.get(f) in (None, "")]
            if missing:
                raise InputError(f"Hypothetical property #{i} is missing: {', '.join(missing)}.")
            area = _parse_area(add["area_sqft"])
            value = parse_inr(add["current_estimated_value_inr"])
            rent = parse_inr(add.get("annual_rent_inr"))
            _check_ranges(area, value, rent)
            adds.append({**add, "area_sqft": area, "current_estimated_value_inr": value, "annual_rent_inr": rent or 0})
    except InputError as exc:
        return _clarify(str(exc))

    unknown = sorted((set(exclude) | set(overrides)) - known)
    if unknown:
        return _clarify(f"These property ids don't exist for this user: {', '.join(unknown)}.", unknown_ids=unknown)
    if not (exclude or overrides or adds):
        return _clarify("Nothing to evaluate. Say what to exclude, re-value or add.")

    projected = apply_scenario(actual, exclude_ids=exclude, value_overrides=overrides, additions=adds)
    before, after = compute_metrics(actual), compute_metrics(projected)
    return {
        "ok": True,
        "hypothetical": True,
        "persisted": False,
        "excluded_property_ids": exclude,
        "value_overrides": overrides,
        "hypothetical_additions": adds,
        "actual": before,
        "scenario": after,
        "delta": compare_metrics(before, after),
        "message": "This is a what-if view. Real portfolio rows were not changed.",
    }
