from types import SimpleNamespace

from app.services.order_views import can_view_order


def make_order(**overrides):
    values = {
        "id": 1,
        "user_id": 10,
        "assigned_provider_id": None,
        "assigned_vehicle_id": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_enterprise_can_only_read_its_own_orders():
    own_order = make_order(user_id=10)
    other_order = make_order(user_id=11)
    enterprise = {"id": 10, "role": "enterprise"}

    assert can_view_order(own_order, enterprise)
    assert not can_view_order(other_order, enterprise)


def test_logistics_can_read_explicit_provider_assignment():
    order = make_order(user_id=10, assigned_provider_id=21)

    assert can_view_order(order, {"id": 21, "role": "logistics"})
    assert not can_view_order(order, {"id": 22, "role": "logistics"})


def test_logistics_legacy_vehicle_assignment_remains_visible():
    order = make_order(assigned_vehicle_id="65C-123.45")
    vehicles = {
        "65C-123.45": SimpleNamespace(provider_id=21),
    }

    assert can_view_order(order, {"id": 21, "role": "logistics"}, vehicles)
    assert not can_view_order(order, {"id": 22, "role": "logistics"}, vehicles)


def test_admin_can_read_all_orders():
    assert can_view_order(make_order(user_id=None), {"id": 1, "role": "admin"})
