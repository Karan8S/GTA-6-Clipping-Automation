"""Channel growth-optimized scheduling for YouTube Shorts.

Enforces healthy channel growth practices:
- Maximum 2 Shorts per day to prevent audience fatigue and self-cannibalization.
- Strategic peak-traffic time slots (Midday lunch break & Prime evening).
- Generates RFC 3339 / ISO 8601 UTC timestamps required by YouTube Data API v3 (`publishAt`).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger("streamclip.publish.scheduler")


@dataclass
class ScheduleSlot:
    """Individual scheduled publishing slot."""
    index: int
    local_datetime: datetime
    utc_datetime: datetime
    publish_at_iso: str
    slot_label: str

    def __str__(self) -> str:
        local_str = self.local_datetime.strftime("%Y-%m-%d %I:%M %p %Z")
        return f"Slot {self.index + 1}: {local_str} (UTC: {self.publish_at_iso}) — {self.slot_label}"


class ChannelGrowthScheduler:
    """Calculates healthy YouTube Shorts release schedules (2 shorts/day max)."""

    DEFAULT_PEAK_TIMES = ["13:00", "19:00"]  # 1:00 PM (Midday) and 7:00 PM (Prime Evening)
    SLOT_LABELS = {
        "13:00": "Peak Midday (Lunch Hour Engagement)",
        "19:00": "Prime Evening (Peak Screen Time)",
    }

    def __init__(
        self,
        shorts_per_day: int = 2,
        timezone_str: str = "Asia/Kolkata",
        peak_times: Optional[List[str]] = None,
        start_days_ahead: int = 1,
    ):
        self.shorts_per_day = max(1, min(shorts_per_day, 4))
        self.timezone_str = timezone_str
        try:
            self.tz = ZoneInfo(timezone_str)
        except Exception:
            logger.warning("Invalid timezone %s, defaulting to UTC", timezone_str)
            self.tz = timezone.utc
            self.timezone_str = "UTC"

        self.peak_times = peak_times or self.DEFAULT_PEAK_TIMES
        # Sort peak times chronologically
        self.peak_times.sort()
        self.start_days_ahead = start_days_ahead

    def generate_plan(
        self,
        num_shorts: int,
        base_datetime: Optional[datetime] = None,
    ) -> List[ScheduleSlot]:
        """Generate a schedule plan distributing num_shorts at <= 2 shorts/day."""
        if num_shorts <= 0:
            return []

        now = base_datetime or datetime.now(self.tz)
        if now.tzinfo is None:
            now = now.replace(tzinfo=self.tz)
        else:
            now = now.astimezone(self.tz)

        # Start on target day (e.g. tomorrow)
        current_date = now.date() + timedelta(days=self.start_days_ahead)
        slots: List[ScheduleSlot] = []

        slot_times_to_use = self.peak_times[:self.shorts_per_day]
        if not slot_times_to_use:
            slot_times_to_use = self.DEFAULT_PEAK_TIMES[:self.shorts_per_day]

        current_slot_idx = 0
        while len(slots) < num_shorts:
            for time_str in slot_times_to_use:
                if len(slots) >= num_shorts:
                    break

                h, m = map(int, time_str.split(":"))
                slot_time = time(hour=h, minute=m)
                local_dt = datetime.combine(current_date, slot_time, tzinfo=self.tz)

                # Ensure slot is at least 15 minutes into the future
                utc_dt = local_dt.astimezone(timezone.utc)
                publish_at_iso = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                label = self.SLOT_LABELS.get(time_str, f"Optimal Slot ({time_str})")

                slots.append(
                    ScheduleSlot(
                        index=current_slot_idx,
                        local_datetime=local_dt,
                        utc_datetime=utc_dt,
                        publish_at_iso=publish_at_iso,
                        slot_label=label,
                    )
                )
                current_slot_idx += 1

            current_date += timedelta(days=1)

        return slots

    def format_plan_table(self, slots: List[ScheduleSlot]) -> str:
        """Format schedule plan as a readable summary."""
        lines = [
            "==================================================================",
            f"YOUTUBE SHORTS HEALTHY GROWTH SCHEDULE ({self.shorts_per_day} Shorts/Day)",
            f"Target Timezone: {self.timezone_str}",
            "==================================================================",
        ]
        for s in slots:
            lines.append(f"• {s}")
        lines.append("==================================================================")
        return "\n".join(lines)
