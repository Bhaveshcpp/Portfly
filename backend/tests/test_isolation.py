from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.portfolio import add_property, search_properties, update_property
from app.seed import seed_from_csv


def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    seed_from_csv(db, Path(__file__).resolve().parents[2] / "data")
    return db


def test_user_cannot_see_another_portfolio():
    db = session()
    rahul = search_properties(db, "U001")
    priya = search_properties(db, "U002")
    assert {p["property_id"] for p in rahul} == {"P001", "P002", "P003"}
    assert {p["property_id"] for p in priya} == {"P004", "P005", "P006"}


def test_update_scoped_to_user():
    db = session()
    result = update_property(
        db,
        "U002",
        property_id="P001",
        updates={"current_estimated_value_inr": 1},
    )
    assert result["ok"] is False


def test_add_requires_fields_and_stays_on_user():
    db = session()
    missing = add_property(db, "U004", {"property_type": "Retail"})
    assert missing["ok"] is False
    created = add_property(
        db,
        "U004",
        {
            "property_type": "Retail",
            "location": "Indiranagar, Bengaluru",
            "area_sqft": 3000,
            "current_estimated_value_inr": 42_000_000,
        },
    )
    assert created["ok"] is True
    assert created["property"]["user_id"] == "U004"
    ids = {p["property_id"] for p in search_properties(db, "U001")}
    assert created["property"]["property_id"] not in ids
