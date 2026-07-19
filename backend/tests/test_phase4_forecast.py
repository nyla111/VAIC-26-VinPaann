from datetime import date

from app.routes.logistics import _parse_order_date, _vehicles_needed


def test_forecast_date_parser_accepts_iso_datetime_and_date():
    assert _parse_order_date("2026-07-20T08:30:00") == date(2026, 7, 20)
    assert _parse_order_date("2026-07-21") == date(2026, 7, 21)
    assert _parse_order_date("not-a-date") is None


def test_vehicles_needed_uses_largest_prepared_vehicles_first():
    assert _vehicles_needed(9000, [5000, 4000, 2000]) == 2
    assert _vehicles_needed(12000, [5000, 4000]) == 2
    assert _vehicles_needed(0, [5000]) == 0
