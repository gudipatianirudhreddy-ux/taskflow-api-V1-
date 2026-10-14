from datetime import datetime, timezone

import pytest

from app.date_utils import (
    current_local_datetime,
    format_stored_due_date,
    normalize_due_date_input,
)


def test_date_only_is_midnight_in_app_timezone_then_stored_as_utc():
    # Asia/Kolkata is UTC+05:30; local midnight maps to the previous UTC date.
    assert normalize_due_date_input("2026-10-20") == datetime(2026, 10, 19, 18, 30)


def test_naive_datetime_is_interpreted_in_app_timezone():
    assert normalize_due_date_input("2026-10-20T18:30:00") == datetime(2026, 10, 20, 13, 0)


def test_z_suffix_is_supported():
    assert normalize_due_date_input("2026-10-20T13:00:00Z") == datetime(2026, 10, 20, 13, 0)


def test_explicit_offset_is_converted_to_utc():
    assert normalize_due_date_input("2026-10-20T18:30:00+05:30") == datetime(2026, 10, 20, 13, 0)


def test_none_is_preserved():
    assert normalize_due_date_input(None) is None


@pytest.mark.parametrize("value", ["", "tomorrow", "not-a-date", "2026-13-42"])
def test_invalid_values_raise(value):
    with pytest.raises(ValueError):
        normalize_due_date_input(value)


def test_stored_utc_datetime_is_serialized_with_z():
    assert format_stored_due_date(datetime(2026, 10, 20, 13, 0)) == "2026-10-20T13:00:00Z"


def test_aware_value_is_converted_to_utc_for_serialization():
    value = datetime(2026, 10, 20, 18, 30, tzinfo=timezone.utc)
    assert format_stored_due_date(value) == "2026-10-20T18:30:00Z"


def test_current_time_has_application_timezone():
    assert current_local_datetime().utcoffset() is not None
