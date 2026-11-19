"""Unit tests for ChannelGrowthScheduler."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest

from src.publish.scheduler import ChannelGrowthScheduler, ScheduleSlot


def test_scheduler_two_shorts_per_day():
    scheduler = ChannelGrowthScheduler(
        shorts_per_day=2,
        timezone_str="Asia/Kolkata",
        peak_times=["13:00", "19:00"],
        start_days_ahead=1,
    )
    base_time = datetime(2026, 11, 20, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    plan = scheduler.generate_plan(num_shorts=4, base_datetime=base_time)

    assert len(plan) == 4

    # Day 1
    assert plan[0].local_datetime.strftime("%Y-%m-%d %H:%M") == "2026-11-21 13:00"
    assert plan[0].publish_at_iso == "2026-11-21T07:30:00Z"
    assert "Midday" in plan[0].slot_label

    assert plan[1].local_datetime.strftime("%Y-%m-%d %H:%M") == "2026-11-21 19:00"
    assert plan[1].publish_at_iso == "2026-11-21T13:30:00Z"
    assert "Evening" in plan[1].slot_label

    # Day 2
    assert plan[2].local_datetime.strftime("%Y-%m-%d %H:%M") == "2026-11-22 13:00"
    assert plan[2].publish_at_iso == "2026-11-22T07:30:00Z"

    assert plan[3].local_datetime.strftime("%Y-%m-%d %H:%M") == "2026-11-22 19:00"
    assert plan[3].publish_at_iso == "2026-11-22T13:30:00Z"


def test_scheduler_odd_number_of_shorts():
    scheduler = ChannelGrowthScheduler(
        shorts_per_day=2,
        timezone_str="UTC",
        peak_times=["12:00", "18:00"],
        start_days_ahead=1,
    )
    base_time = datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc)
    plan = scheduler.generate_plan(num_shorts=3, base_datetime=base_time)

    assert len(plan) == 3
    # Day 1 (2 shorts)
    assert plan[0].publish_at_iso == "2026-11-21T12:00:00Z"
    assert plan[1].publish_at_iso == "2026-11-21T18:00:00Z"
    # Day 2 (1 short)
    assert plan[2].publish_at_iso == "2026-11-22T12:00:00Z"


def test_scheduler_empty_plan():
    scheduler = ChannelGrowthScheduler()
    assert scheduler.generate_plan(0) == []
    assert scheduler.generate_plan(-2) == []


def test_scheduler_table_formatting():
    scheduler = ChannelGrowthScheduler()
    plan = scheduler.generate_plan(2)
    table = scheduler.format_plan_table(plan)
    assert "HEALTHY GROWTH SCHEDULE" in table
    assert "Slot 1:" in table
    assert "Slot 2:" in table
