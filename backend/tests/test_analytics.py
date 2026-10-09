from types import SimpleNamespace

from app.analytics import apply_scenario, compute_metrics, normalize_type_group, owned_value


def prop(**kwargs):
    defaults = dict(
        property_id="P001",
        user_id="U001",
        property_type="Retail",
        type_group="Retail",
        sub_type="High-street",
        location="Bandra West, Mumbai",
        area_sqft=1000,
        current_estimated_value_inr=10_000_000,
        purchase_price_inr=None,
        annual_rent_inr=1_000_000,
        occupancy_status="Tenanted",
        tenant_status="Yes",
        ownership_percent=100,
        status="Active",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_office_labels_group_together():
    assert normalize_type_group("Office") == "Office"
    assert normalize_type_group("Commercial Office") == "Office"
    assert normalize_type_group("Retail") == "Retail"


def test_metrics_totals_and_yield():
    rows = [
        prop(property_id="A", current_estimated_value_inr=100, annual_rent_inr=10),
        prop(property_id="B", current_estimated_value_inr=50, annual_rent_inr=0, occupancy_status="Vacant"),
    ]
    m = compute_metrics(rows)
    assert m["total_portfolio_value_inr"] == 150
    assert m["total_annual_rent_inr"] == 10
    assert abs(m["portfolio_yield"] - 10 / 150) < 1e-9
    assert m["missing_purchase_prices"] is True


def test_ownership_scales_value():
    assert owned_value(prop(current_estimated_value_inr=100, ownership_percent=50)) == 50


def test_scenario_does_not_mutate_source():
    original = prop(property_id="P001", current_estimated_value_inr=120)
    projected = apply_scenario([original], exclude_ids=["P001"])
    assert original.current_estimated_value_inr == 120
    assert projected == []
    bumped = apply_scenario([original], value_overrides={"P001": 140})
    assert original.current_estimated_value_inr == 120
    assert bumped[0].current_estimated_value_inr == 140
