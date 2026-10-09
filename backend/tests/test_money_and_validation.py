import pytest

from app import portfolio
from app.portfolio import InputError, parse_inr


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("₹14 Cr", 140_000_000), ("12 crore", 120_000_000), ("4.2 crores", 42_000_000), ("50 lakh", 5_000_000),
        ("₹1,20,00,000", 12_000_000), ("Rs. 75 lakhs", 7_500_000), (1500000, 1_500_000), ("2500000", 2_500_000), (None, None), ("", None),
    ],
)
def test_parse_inr(raw, expected):
    assert parse_inr(raw) == expected


@pytest.mark.parametrize("bad", ["lots", "12 zorks", True, "nan", float("inf")])
def test_parse_inr_rejects(bad):
    with pytest.raises(InputError):
        parse_inr(bad)


def test_add_resolves_city_from_existing_property(db):
    r = portfolio.add_property(db, "U004", {"property_type": "Retail", "location": "Indiranagar", "area_sqft": 3000, "current_estimated_value_inr": "4.2 crore"})
    assert r["ok"] and r["property"]["city"] == "Bengaluru"
    assert r["property"]["location"] == "Indiranagar, Bengaluru"
    assert any("Bengaluru" in a for a in r["assumptions"]) and any("Vacant" in a for a in r["assumptions"])


def test_add_asks_city_when_user_is_ncr_and_locality_unknown(db):
    r = portfolio.add_property(db, "U003", {"property_type": "Office", "location": "Sector 99", "area_sqft": 2000, "current_estimated_value_inr": "5 Cr"})
    assert r["ok"] is False and "city" in r["message"].lower()


def test_state_suffix_gives_town_not_state(db):
    assert [p for p in portfolio.search_properties(db, "U002") if p["property_id"] == "P006"][0]["city"] == "Alibaug"


@pytest.mark.parametrize(
    "overrides",
    [{"area_sqft": 0}, {"area_sqft": -5}, {"current_estimated_value_inr": -1}, {"current_estimated_value_inr": 12},  # '12' instead of '12 Cr'
     {"annual_rent_inr": -100}, {"property_type": "Spaceship"}, {"occupancy_status": "Haunted"}],
)
def test_add_rejects_bad_input_and_saves_nothing(db, overrides):
    payload = {"property_type": "Retail", "location": "Bandra, Mumbai", "area_sqft": 1000, "current_estimated_value_inr": "3 Cr", **overrides}
    before = len(portfolio.user_properties(db, "U001"))
    r = portfolio.add_property(db, "U001", payload)
    assert r["ok"] is False and r["needs_clarification"] is True
    assert len(portfolio.user_properties(db, "U001")) == before


def test_add_blocks_tenanted_without_rent_until_confirmed(db):
    payload = {"property_type": "Retail", "location": "Bandra, Mumbai", "area_sqft": 900, "current_estimated_value_inr": "3 Cr", "occupancy_status": "Tenanted"}
    first = portfolio.add_property(db, "U001", payload)
    assert first["ok"] is False and first["can_confirm"]
    assert portfolio.add_property(db, "U001", payload, confirmed=True)["ok"] is True


def test_add_blocks_duplicates_and_absurd_price_per_sqft(db):
    dup = {"property_type": "Retail", "location": "Bandra West, Mumbai", "area_sqft": portfolio.user_properties(db, "U001")[0].area_sqft, "current_estimated_value_inr": "12 Cr"}
    assert portfolio.add_property(db, "U001", dup)["duplicate_of"] == "P001"
    silly = {"property_type": "Retail", "location": "Bandra, Mumbai", "area_sqft": 100000, "current_estimated_value_inr": "1 Cr"}
    assert "per sq ft" in portfolio.add_property(db, "U001", silly)["message"]


def test_update_returns_previous_value_and_keeps_tenant_status_in_sync(db):
    r = portfolio.update_property(db, "U002", location_hint="bandra", updates={"current_estimated_value_inr": "14 Cr"})
    assert r["ok"] and r["previous"]["current_estimated_value_inr"] == 64_000_000
    assert r["property"]["current_estimated_value_inr"] == 140_000_000
    r2 = portfolio.update_property(db, "U002", property_id="P004", updates={"occupancy_status": "Vacant"})
    assert r2["ok"] and r2["property"]["tenant_status"] == "No"


def test_update_rejects_negative_zero_and_conflicts(db):
    assert portfolio.update_property(db, "U002", property_id="P004", updates={"current_estimated_value_inr": -5})["ok"] is False
    assert portfolio.update_property(db, "U002", property_id="P005", updates={"occupancy_status": "Vacant"})["can_confirm"]  # still has rent
    assert portfolio.update_property(db, "U002", location_hint="nowhere", updates={"current_estimated_value_inr": "1 Cr"})["ok"] is False


def test_update_ambiguous_returns_candidates_and_changes_nothing(db):
    r = portfolio.update_property(db, "U002", location_hint="mumbai", updates={"current_estimated_value_inr": "9 Cr"})
    assert r["ok"] is False and len(r["candidates"]) == 2
    assert [p["current_estimated_value_inr"] for p in portfolio.search_properties(db, "U002", property_ids=["P004", "P005"])] == [64_000_000, 51_000_000]


def test_cannot_touch_another_users_property(db):
    assert portfolio.update_property(db, "U001", property_id="P007", updates={"current_estimated_value_inr": "1 Cr"})["ok"] is False


def test_scenario_delta_additions_and_unknown_ids(db):
    base = portfolio.metrics_for_user(db, "U001")
    r = portfolio.scenario_for_user(db, "U001", exclude_ids=["P001"], additions=[{"property_type": "Residential", "area_sqft": 1000, "current_estimated_value_inr": "5 Cr"}])
    assert r["ok"] and r["persisted"] is False
    assert r["delta"]["value_change_inr"] == pytest.approx(-120_000_000 + 50_000_000)
    assert r["delta"]["property_count_change"] == 0
    assert portfolio.metrics_for_user(db, "U001") == base  # nothing written
    bad = portfolio.scenario_for_user(db, "U001", exclude_ids=["P999"])
    assert bad["ok"] is False and bad["unknown_ids"] == ["P999"]
    assert portfolio.scenario_for_user(db, "U001")["ok"] is False  # empty scenario
