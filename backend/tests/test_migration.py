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
