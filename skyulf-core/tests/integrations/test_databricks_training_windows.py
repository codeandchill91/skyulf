"""Data selection calendars must be independent of outer splits and job schedules."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pandas as pd
import pytest

from skyulf.integrations.databricks.local_retraining import split_labeled_snapshot
from skyulf.integrations.databricks.local_workflow import _monthly_training_spec, _training_spec


def _config(**changes):
    """Default to ordinary date-free sources; callers select calendar behavior explicitly."""
    config = {
        "training_table": "workspace.test.labels",
        "training_version": 0,
        "record_key_columns": ["id"],
        "input_columns": ["x"],
        "target_column": "target",
        "max_rows": 100,
        "max_input_mb": 1,
        "split_strategy": "random",
        "training_window_mode": "full_snapshot",
    }
    return {**config, **changes}


def _spark():
    """Only history lookup is needed to pin a monthly source version."""
    spark = Mock()
    spark.sql.return_value.select.return_value.orderBy.return_value.first.return_value = {
        "version": 9
    }
    return spark


@pytest.mark.parametrize("strategy", ["random", "temporal"])
def test_rolling_calendar_uses_named_zone_and_includes_holdout_month(strategy):
    """Business month rollover must follow the chosen calendar, not UTC or execution day."""
    config = _config(
        split_strategy=strategy,
        training_window_mode="rolling_calendar",
        event_column="event",
        monthly_lookback_months=4,
        window_timezone="Europe/Vilnius",
    )
    # Already January in Vilnius, still December in UTC.
    spec = _monthly_training_spec(_spark(), config, datetime(2026, 12, 31, 22, 30, tzinfo=UTC))
    assert spec.start is not None and spec.cutoff is not None
    assert spec.start.isoformat() == "2026-09-01T00:00:00+03:00"
    assert spec.cutoff.isoformat() == "2027-01-01T00:00:00+02:00"
    if strategy == "temporal":
        assert spec.holdout_start is not None
        assert spec.holdout_start.isoformat() == "2026-12-01T00:00:00+02:00"
    else:
        assert spec.holdout_start is None and spec.test_size == 0.2
    assert spec.version == 9


def test_random_split_can_select_a_fixed_event_window():
    """Selecting recent observations must not force temporal train/test splitting."""
    config = _config(
        training_window_mode="fixed_window",
        event_column="event",
        start="2026-01-01T00:00:00+00:00",
        cutoff="2026-02-01T00:00:00+00:00",
    )
    spec = _training_spec(config)
    frame = pd.DataFrame(
        {
            "id": range(20),
            "x": range(20),
            "target": range(20),
            "event": pd.date_range("2026-01-01", periods=20, tz="UTC"),
        }
    )
    train, holdout, _ = split_labeled_snapshot(frame, spec)
    assert len(train) == 16 and len(holdout) == 4
    assert set(train.x).isdisjoint(holdout.x)
    first = _monthly_training_spec(_spark(), config, datetime(2026, 3, 15, tzinfo=UTC))
    later = _monthly_training_spec(_spark(), config, datetime(2026, 4, 20, tzinfo=UTC))
    assert first.start == later.start == spec.start
    assert first.cutoff == later.cutoff == spec.cutoff


@pytest.mark.parametrize(
    "changes",
    [
        {"training_window_mode": "unknown"},
        {
            "training_window_mode": "rolling_calendar",
            "event_column": "event",
            "monthly_lookback_months": 4,
        },
        {
            "training_window_mode": "rolling_calendar",
            "event_column": "event",
            "monthly_lookback_months": 4,
            "window_timezone": "not/a-zone",
        },
        {"training_window_mode": "full_snapshot", "event_column": "event"},
        {"training_window_mode": "full_snapshot", "window_timezone": "UTC"},
    ],
)
def test_invalid_selection_policy_fails_before_history(changes):
    """A monthly job cannot invent source dates, silently shift calendars or ignore typos."""
    spark = _spark()
    with pytest.raises(ValueError):
        _monthly_training_spec(spark, _config(**changes), datetime(2026, 9, 25, tzinfo=UTC))
    spark.sql.assert_not_called()


@pytest.mark.parametrize(
    "instant,start,holdout,cutoff",
    [
        (
            "2024-04-15T12:00:00+00:00",
            "2023-12-01T00:00:00+02:00",
            "2024-02-01T00:00:00+02:00",
            "2024-04-01T00:00:00+03:00",
        ),
        (
            "2026-11-15T12:00:00+00:00",
            "2026-07-01T00:00:00+03:00",
            "2026-09-01T00:00:00+03:00",
            "2026-11-01T00:00:00+02:00",
        ),
        (
            "2026-12-31T22:30:00+00:00",
            "2026-09-01T00:00:00+03:00",
            "2026-11-01T00:00:00+02:00",
            "2027-01-01T00:00:00+02:00",
        ),
    ],
)
def test_two_month_holdout_preserves_calendar_boundaries(instant, start, holdout, cutoff):
    """Holdout months belong to total lookback across leap years, DST and local rollover."""
    spec = _monthly_training_spec(
        _spark(),
        _config(
            training_window_mode="rolling_calendar",
            split_strategy="temporal",
            event_column="event",
            monthly_lookback_months=4,
            holdout_months=2,
            window_timezone="Europe/Vilnius",
        ),
        datetime.fromisoformat(instant),
    )
    assert spec.start is not None and spec.holdout_start is not None and spec.cutoff is not None
    assert spec.start.isoformat() == start
    assert spec.holdout_start.isoformat() == holdout
    assert spec.cutoff.isoformat() == cutoff


@pytest.mark.parametrize("value", [None, True, 1.5, "2", 0, -1, 4, 121])
def test_invalid_rolling_holdout_fails_before_source_history(value):
    """Temporal holdout requires an exact integer leaving at least one training month."""
    spark = _spark()
    with pytest.raises(ValueError, match="holdout_months"):
        _monthly_training_spec(
            spark,
            _config(
                training_window_mode="rolling_calendar",
                split_strategy="temporal",
                event_column="event",
                monthly_lookback_months=4,
                holdout_months=value,
                window_timezone="UTC",
            ),
            datetime(2026, 9, 25, tzinfo=UTC),
        )
    spark.sql.assert_not_called()


@pytest.mark.parametrize("instant", ["2026-03-29T04:00:00+03:00", "2026-10-25T04:00:00+02:00"])
@pytest.mark.parametrize("lag", [0, 48, 87600])
def test_result_lag_uses_elapsed_utc_hours_without_event_column(instant, lag):
    """Result maturity is independent of event windows and DST wall-clock changes."""
    now = datetime.fromisoformat(instant)
    spec = _monthly_training_spec(
        _spark(),
        _config(
            filter_unavailable_results=True,
            result_available_at_column="confirmed_at",
            result_availability_lag_hours=lag,
        ),
        now,
    )
    assert spec.result_cutoff == now.astimezone(UTC) - timedelta(hours=lag)
    assert spec.event_column is None


@pytest.mark.parametrize("value", [None, True, 1.5, "2", -1, 87601])
def test_invalid_result_lag_fails_before_source_history(value):
    """Bad result lag cannot cause external reads or silently coerce a different cutoff."""
    spark = _spark()
    with pytest.raises(ValueError, match="result_availability_lag_hours"):
        _monthly_training_spec(
            spark,
            _config(
                filter_unavailable_results=True,
                result_available_at_column="confirmed_at",
                result_availability_lag_hours=value,
            ),
            datetime(2026, 9, 25, tzinfo=UTC),
        )
    spark.sql.assert_not_called()


@pytest.mark.parametrize(
    "field,value", [("holdout_months", 1), ("result_availability_lag_hours", 0)]
)
def test_inactive_window_controls_require_null(field, value):
    """Inactive controls must not be silently ignored in date-free workflows."""
    with pytest.raises(ValueError, match=field):
        _training_spec(_config(**{field: value}))


def test_manual_training_keeps_explicit_result_cutoff_with_lag():
    """A manual replay must preserve its saved cutoff regardless of the scheduled lag."""
    spec = _training_spec(
        _config(
            filter_unavailable_results=True,
            result_available_at_column="confirmed_at",
            result_availability_lag_hours=48,
            result_cutoff="2026-09-01T00:00:00+00:00",
        )
    )
    assert spec.result_cutoff == datetime(2026, 9, 1, tzinfo=UTC)


@pytest.mark.parametrize("engine", ["pandas", "polars"])
def test_lagged_result_cutoff_is_inclusive_and_event_window_half_open(engine):
    """A mature label at cutoff participates, a later label and cutoff event cannot."""
    spec = _monthly_training_spec(
        _spark(),
        _config(
            training_window_mode="rolling_calendar",
            split_strategy="temporal",
            event_column="event",
            monthly_lookback_months=4,
            holdout_months=2,
            window_timezone="UTC",
            filter_unavailable_results=True,
            result_available_at_column="confirmed_at",
            result_availability_lag_hours=48,
        ),
        datetime(2026, 9, 3, tzinfo=UTC),
    )
    assert spec.result_cutoff is not None
    frame = pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "x": [1, 2, 3, 4, 5],
            "target": [2, 4, 6, 8, 10],
            "event": pd.to_datetime(
                ["2026-05-01", "2026-06-01", "2026-07-01", "2026-08-31", "2026-08-31"], utc=True
            ),
            "confirmed_at": [spec.result_cutoff] * 4
            + [spec.result_cutoff + timedelta(microseconds=1)],
        }
    )
    train, holdout, excluded = split_labeled_snapshot(frame, spec, engine=engine)
    assert train.x.tolist() == [1, 2]
    assert holdout.x.tolist() == [3, 4]
    assert excluded == 1
    frame.loc[4, "event"] = spec.cutoff
    with pytest.raises(ValueError, match="outside the pinned window"):
        split_labeled_snapshot(frame, spec, engine=engine)
