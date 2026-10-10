from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.db import ensure_columns
from app.models import Property
from app.seed import backfill_city


def test_old_database_gets_new_columns_and_city_backfill():
    engine = create_engine("sqlite://")
    with engine.begin() as c:  # a properties table as it existed before the city column
        c.execute(text("CREATE TABLE properties (property_id VARCHAR(16) PRIMARY KEY, user_id VARCHAR(16), property_type VARCHAR(64), type_group VARCHAR(32), sub_type VARCHAR(64), location VARCHAR(200), area_sqft FLOAT, current_estimated_value_inr FLOAT, purchase_price_inr FLOAT, annual_rent_inr FLOAT, occupancy_status VARCHAR(32), tenant_status VARCHAR(32), ownership_percent FLOAT, status VARCHAR(16))"))
        c.execute(text("INSERT INTO properties VALUES ('P006','U002','Residential','Residential','Villa','Alibaug, Maharashtra',4200,78000000,NULL,0,'Self-occupied','No',100,'Active')"))
    ensure_columns(engine)
    assert "city" in {col["name"] for col in inspect(engine).get_columns("properties")}
    session = sessionmaker(bind=engine)()
    backfill_city(session)
    assert session.get(Property, "P006").city == "Alibaug"


def test_access_key_column_is_added_to_an_existing_conversations_table_without_touching_rows():
    """Simulates a database created before per-conversation keys existed."""
    from app.db import ensure_columns
    from app.models import Base

    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text(
            "CREATE TABLE conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id VARCHAR(16), title VARCHAR(200), "
            "needs_attention BOOLEAN, attention_reason VARCHAR(400), attention_kind VARCHAR(20), active_scenario JSON, "
            "last_mentioned_property_ids JSON, created_at DATETIME, updated_at DATETIME)"
        ))
        c.execute(text("INSERT INTO conversations (user_id, title, needs_attention, last_mentioned_property_ids) VALUES ('U001','keep me',1,'[\"P001\"]')"))
        c.execute(text("INSERT INTO conversations (user_id, title, needs_attention, last_mentioned_property_ids) VALUES ('U002','me too',0,'[]')"))
    ensure_columns(engine)
    ensure_columns(engine)  # idempotent: a second start must not fail
    cols = {col["name"]: col for col in inspect(engine).get_columns("conversations")}
    assert "access_key_hash" in cols and cols["access_key_hash"]["nullable"] is True
    with engine.connect() as c:
        rows = c.execute(text("SELECT id, user_id, title, needs_attention, access_key_hash FROM conversations ORDER BY id")).all()
    assert [tuple(r) for r in rows] == [(1, "U001", "keep me", 1, None), (2, "U002", "me too", 0, None)]
