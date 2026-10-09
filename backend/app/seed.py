from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import Session

from app.analytics import normalize_type_group, parse_city
from app.config import settings
from app.models import Property, User


def _empty(value: str | None):
    if value is None:
        return None
    text = str(value).strip()
    return None if text == "" else text


def seed_from_csv(db: Session, data_dir: Path | None = None) -> None:
    folder = data_dir or settings.data_dir
    if db.query(User).count() > 0:
        return

    with open(folder / "users.csv", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            db.add(
                User(
                    user_id=row["user_id"],
                    name=row["name"],
                    city=row["city"],
                    preferences=row["preferences"],
                    preferred_locations=row["preferred_locations"],
                    portfolio_value_preference_inr=row["portfolio_value_preference_inr"],
                )
            )

    with open(folder / "properties.csv", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            purchase = _empty(row.get("purchase_price_inr"))
            db.add(
                Property(
                    property_id=row["property_id"],
                    user_id=row["user_id"],
                    property_type=row["property_type"],
                    type_group=normalize_type_group(row["property_type"]),
                    sub_type=row["sub_type"],
                    location=row["location"],
                    city=parse_city(row["location"]),
                    area_sqft=float(row["area_sqft"]),
                    current_estimated_value_inr=float(row["current_estimated_value_inr"]),
                    purchase_price_inr=float(purchase) if purchase is not None else None,
                    annual_rent_inr=float(row["annual_rent_inr"] or 0),
                    occupancy_status=row["occupancy_status"],
                    tenant_status=row["tenant_status"],
                    ownership_percent=float(row["ownership_percent"] or 100),
                    status=row["status"] or "Active",
                )
            )
    db.commit()


def backfill_city(db: Session) -> None:
    """Fill the city column for rows created before it existed."""
    changed = False
    for prop in db.query(Property).filter((Property.city.is_(None)) | (Property.city == "")):
        prop.city = parse_city(prop.location)
        changed = True
    if changed:
        db.commit()
