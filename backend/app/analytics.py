"""Deterministic portfolio math. The model must never do this arithmetic."""

from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace
from typing import Any, Iterable

OFFICE_LABELS = {"office", "commercial office"}
RETAIL_LABELS = {"retail"}
RESIDENTIAL_LABELS = {"residential"}


def normalize_type_group(property_type: str) -> str:
    label = (property_type or "").strip().lower()
    if label in RETAIL_LABELS:
        return "Retail"
    if label in RESIDENTIAL_LABELS:
        return "Residential"
    if label in OFFICE_LABELS:
        return "Office"
    return (property_type or "").strip() or "Unknown"


def owned_value(property_row: Any) -> float:
    pct = float(getattr(property_row, "ownership_percent", 100) or 100)
    return float(property_row.current_estimated_value_inr or 0) * (pct / 100.0)


def rental_yield(property_row: Any) -> float | None:
    value = float(property_row.current_estimated_value_inr or 0)
    rent = float(property_row.annual_rent_inr or 0)
    if value <= 0:
        return None
    return rent / value


INDIAN_STATES = {
    "maharashtra", "karnataka", "haryana", "uttar pradesh", "telangana", "tamil nadu", "gujarat",
    "west bengal", "rajasthan", "punjab", "kerala", "goa", "madhya pradesh", "bihar", "odisha",
}


def parse_city(location: str) -> str:
    """'Locality, City' -> City. 'Alibaug, Maharashtra' -> Alibaug (last part is a state)."""
    parts = [p.strip() for p in (location or "").split(",") if p.strip()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if parts[-1].lower() in INDIAN_STATES:
        return parts[-2]
    return parts[-1]


def city_of(p: Any) -> str:
    return (getattr(p, "city", None) or "").strip() or parse_city(p.location)


def owned_rent(property_row: Any) -> float:
    pct = float(getattr(property_row, "ownership_percent", 100) or 100)
    return float(property_row.annual_rent_inr or 0) * (pct / 100.0)


def serialize_property(p: Any) -> dict[str, Any]:
    yld = rental_yield(p)
    purchase = getattr(p, "purchase_price_inr", None)
    return {
        "property_id": p.property_id,
        "user_id": p.user_id,
        "property_type": p.property_type,
        "type_group": getattr(p, "type_group", None) or normalize_type_group(p.property_type),
        "sub_type": p.sub_type,
        "location": p.location,
        "city": city_of(p),
        "owned_rent_inr": owned_rent(p),
        "area_sqft": p.area_sqft,
        "current_estimated_value_inr": p.current_estimated_value_inr,
        "owned_value_inr": owned_value(p),
        "purchase_price_inr": purchase,
        "purchase_price_available": purchase is not None,
        "annual_rent_inr": p.annual_rent_inr,
        "rental_yield": yld,
        "occupancy_status": p.occupancy_status,
        "tenant_status": p.tenant_status,
        "ownership_percent": p.ownership_percent,
        "status": p.status,
    }


def compute_metrics(properties: Iterable[Any]) -> dict[str, Any]:
    rows = list(properties)
    if not rows:
        return {
            "property_count": 0,
            "total_portfolio_value_inr": 0,
            "total_annual_rent_inr": 0,
            "portfolio_yield": None,
            "by_type_group": {},
            "by_city": {},
            "occupancy": {},
            "highest_value": None,
            "lowest_value": None,
            "highest_rent": None,
            "non_income_assets": [],
            "missing_purchase_prices": True,
            "notes": [
                "Purchase prices are not in the seed data, so cost basis and historical appreciation cannot be calculated.",
                "There are no transaction dates, so time-based returns cannot be answered.",
            ],
        }

    total_value = sum(owned_value(p) for p in rows)
    total_rent = sum(owned_rent(p) for p in rows)
    by_type: dict[str, dict[str, float]] = defaultdict(lambda: {"value_inr": 0, "rent_inr": 0, "count": 0})
    by_city: dict[str, dict[str, float]] = defaultdict(lambda: {"value_inr": 0, "count": 0})
    occupancy: dict[str, int] = defaultdict(int)

    for p in rows:
        group = getattr(p, "type_group", None) or normalize_type_group(p.property_type)
        by_type[group]["value_inr"] += owned_value(p)
        by_type[group]["rent_inr"] += owned_rent(p)
        by_type[group]["count"] += 1
        city = city_of(p) or "Unknown"
        by_city[city]["value_inr"] += owned_value(p)
        by_city[city]["count"] += 1
        occupancy[p.occupancy_status or "Unknown"] += 1

    typed = {}
    for group, stats in by_type.items():
        share = (stats["value_inr"] / total_value) if total_value else 0
        typed[group] = {
            **stats,
            "share_of_value": share,
            "yield": (stats["rent_inr"] / stats["value_inr"]) if stats["value_inr"] else None,
        }

    cities = {
        city: {
            **stats,
            "share_of_value": (stats["value_inr"] / total_value) if total_value else 0,
        }
        for city, stats in by_city.items()
    }

    highest_value = max(rows, key=owned_value)
    lowest_value = min(rows, key=owned_value)
    highest_rent = max(rows, key=owned_rent) if total_rent > 0 else None

    missing_purchase = all(getattr(p, "purchase_price_inr", None) is None for p in rows)

    return {
        "property_count": len(rows),
        "total_portfolio_value_inr": total_value,
        "total_annual_rent_inr": total_rent,
        "portfolio_yield": (total_rent / total_value) if total_value else None,
        "by_type_group": typed,
        "by_city": cities,
        "occupancy": dict(occupancy),
        "highest_value": serialize_property(highest_value),
        "lowest_value": serialize_property(lowest_value),
        "highest_rent": serialize_property(highest_rent) if highest_rent else None,
        "non_income_assets": [
            {
                "property_id": p.property_id,
                "location": p.location,
                "occupancy_status": p.occupancy_status,
                "value_inr": owned_value(p),
            }
            for p in rows
            if owned_rent(p) == 0
        ],
        "missing_purchase_prices": missing_purchase,
        "notes": [
            "Office exposure groups 'Office' and 'Commercial Office' together.",
            "Yield uses current estimated value, not purchase price.",
            "Value and rent are scaled by ownership_percent (100 for every seed row).",
            "Purchase prices are blank in seed data; do not invent cost basis or appreciation.",
            "No dates are present; historical returns cannot be computed.",
        ],
    }


def make_hypothetical(index: int, data: dict[str, Any]) -> Any:
    """A property that exists only inside a what-if. Never touches the DB."""
    return SimpleNamespace(
        property_id=f"HYPO-{index}",
        user_id="",
        property_type=data["property_type"],
        type_group=normalize_type_group(data["property_type"]),
        sub_type=data.get("sub_type") or data["property_type"],
        location=data.get("location") or "Hypothetical",
        city=data.get("city") or parse_city(data.get("location") or ""),
        area_sqft=float(data["area_sqft"]),
        current_estimated_value_inr=float(data["current_estimated_value_inr"]),
        purchase_price_inr=None,
        annual_rent_inr=float(data.get("annual_rent_inr") or 0),
        occupancy_status=data.get("occupancy_status") or ("Tenanted" if data.get("annual_rent_inr") else "Vacant"),
        tenant_status="Yes" if data.get("annual_rent_inr") else "No",
        ownership_percent=100.0,
        status="Active",
    )


def apply_scenario(
    properties: list[Any],
    *,
    exclude_ids: list[str] | None = None,
    value_overrides: dict[str, float] | None = None,
    additions: list[dict[str, Any]] | None = None,
) -> list[Any]:
    """Return a copied list for what-if math. Never writes to the DB."""
    exclude = set(exclude_ids or [])
    overrides = value_overrides or {}
    projected = []
    for p in properties:
        if p.property_id in exclude:
            continue
        clone = _Clone(p)
        if clone.property_id in overrides:
            clone.current_estimated_value_inr = overrides[clone.property_id]
        projected.append(clone)
    for i, data in enumerate(additions or [], start=1):
        projected.append(make_hypothetical(i, data))
    return projected


def compare_metrics(actual: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    """Exact before/after differences so the model never subtracts numbers itself."""
    a_val, s_val = actual["total_portfolio_value_inr"], scenario["total_portfolio_value_inr"]
    a_rent, s_rent = actual["total_annual_rent_inr"], scenario["total_annual_rent_inr"]
    shares_a = {k: v["share_of_value"] for k, v in actual["by_type_group"].items()}
    shares_s = {k: v["share_of_value"] for k, v in scenario["by_type_group"].items()}
    groups = sorted(set(shares_a) | set(shares_s))
    return {
        "value_change_inr": s_val - a_val,
        "value_change_pct": ((s_val - a_val) / a_val) if a_val else None,
        "rent_change_inr": s_rent - a_rent,
        "yield_before": actual["portfolio_yield"],
        "yield_after": scenario["portfolio_yield"],
        "property_count_change": scenario["property_count"] - actual["property_count"],
        "type_share_before": {g: shares_a.get(g, 0.0) for g in groups},
        "type_share_after": {g: shares_s.get(g, 0.0) for g in groups},
    }


class _Clone:
    def __init__(self, src: Any):
        self.property_id = src.property_id
        self.user_id = src.user_id
        self.property_type = src.property_type
        self.type_group = getattr(src, "type_group", None) or normalize_type_group(src.property_type)
        self.sub_type = src.sub_type
        self.location = src.location
        self.city = city_of(src)
        self.area_sqft = src.area_sqft
        self.current_estimated_value_inr = src.current_estimated_value_inr
        self.purchase_price_inr = src.purchase_price_inr
        self.annual_rent_inr = src.annual_rent_inr
        self.occupancy_status = src.occupancy_status
        self.tenant_status = src.tenant_status
        self.ownership_percent = src.ownership_percent
        self.status = src.status
