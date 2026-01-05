"""Scheduler - Time-based playback scheduling"""

import json
import logging
from pathlib import Path
from datetime import datetime, date, time as dtime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from .exceptions import SchedulerError

logger = logging.getLogger(__name__)


class ScheduleMode(Enum):
    """Scheduling mode"""
    MANUAL = "manual"       # Manual control only
    CONTINUOUS = "continuous"  # Loop continuously
    SCHEDULED = "scheduled"   # Follow schedule rules


@dataclass
class ScheduleRule:
    """A scheduling rule"""
    id: str
    days: List[str]  # mon, tue, wed, thu, fri, sat, sun
    times: List[str]  # HH:MM format
    enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScheduleException:
    """An exception to the schedule (e.g., holiday)"""
    date: str  # YYYY-MM-DD format
    times: List[str]  # Override times for this date (empty = no playback)
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Schedule:
    """Complete schedule configuration"""
    enabled: bool = True
    mode: ScheduleMode = ScheduleMode.MANUAL
    rules: List[ScheduleRule] = field(default_factory=list)
    exceptions: List[ScheduleException] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "mode": self.mode.value,
            "rules": [r.to_dict() for r in self.rules],
            "exceptions": [e.to_dict() for e in self.exceptions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Schedule":
        schedule = cls()
        schedule.enabled = data.get("enabled", True)
        schedule.mode = ScheduleMode(data.get("mode", "manual"))

        for rule_data in data.get("rules", []):
            schedule.rules.append(ScheduleRule(**rule_data))

        for exc_data in data.get("exceptions", []):
            schedule.exceptions.append(ScheduleException(**exc_data))

        return schedule


# Day name mapping
DAY_MAP = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6
}

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class PlaybackScheduler:
    """Manages time-based playback scheduling"""

    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        self.schedule_file = self.config_path / "schedule.json"

        self._scheduler = BackgroundScheduler()
        self._schedule = Schedule()
        self._on_trigger: Optional[Callable] = None
        self._on_stop: Optional[Callable] = None

        self._running = False
        self._next_trigger: Optional[datetime] = None

    def load_schedule(self) -> Schedule:
        """Load schedule from file"""
        if self.schedule_file.exists():
            try:
                with open(self.schedule_file, 'r') as f:
                    data = json.load(f)
                self._schedule = Schedule.from_dict(data)
                logger.info("Schedule loaded from file")
            except Exception as e:
                logger.error(f"Error loading schedule: {e}")
                self._schedule = Schedule()
        else:
            logger.info("No schedule file found, using defaults")

        return self._schedule

    def save_schedule(self):
        """Save schedule to file"""
        self.config_path.mkdir(parents=True, exist_ok=True)
        with open(self.schedule_file, 'w') as f:
            json.dump(self._schedule.to_dict(), f, indent=2)
        logger.info("Schedule saved to file")

    def set_schedule(self, schedule: Schedule):
        """Set the schedule configuration"""
        self._schedule = schedule
        self.save_schedule()
        self._rebuild_jobs()

    def get_schedule(self) -> Schedule:
        """Get current schedule"""
        return self._schedule

    def start(self):
        """Start the scheduler"""
        if self._running:
            return

        self.load_schedule()
        self._rebuild_jobs()
        self._scheduler.start()
        self._running = True
        logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler"""
        if not self._running:
            return

        self._scheduler.shutdown(wait=False)
        self._running = False
        logger.info("Scheduler stopped")

    def _rebuild_jobs(self):
        """Rebuild all scheduler jobs based on current schedule"""
        # Remove all existing jobs
        self._scheduler.remove_all_jobs()

        if not self._schedule.enabled:
            logger.info("Schedule disabled, no jobs created")
            return

        if self._schedule.mode == ScheduleMode.MANUAL:
            logger.info("Manual mode, no scheduled jobs")
            return

        if self._schedule.mode == ScheduleMode.CONTINUOUS:
            # In continuous mode, we trigger immediately and let it loop
            logger.info("Continuous mode enabled")
            if self._on_trigger:
                # Trigger once on start
                self._scheduler.add_job(
                    self._on_trigger,
                    trigger=DateTrigger(run_date=datetime.now()),
                    id="continuous_start"
                )
            return

        # Scheduled mode - create jobs for each rule
        for rule in self._schedule.rules:
            if not rule.enabled:
                continue

            self._create_rule_jobs(rule)

        self._update_next_trigger()
        logger.info(f"Created jobs for {len(self._schedule.rules)} rules")

    def _create_rule_jobs(self, rule: ScheduleRule):
        """Create scheduler jobs for a rule"""
        # Convert day names to cron day_of_week format
        days = []
        for day in rule.days:
            day_lower = day.lower()[:3]
            if day_lower in DAY_MAP:
                days.append(str(DAY_MAP[day_lower]))

        if not days:
            return

        day_of_week = ",".join(days)

        # Create job for each time
        for time_str in rule.times:
            try:
                hour, minute = time_str.split(":")
                job_id = f"rule_{rule.id}_{time_str.replace(':', '')}"

                self._scheduler.add_job(
                    self._trigger_playback,
                    trigger=CronTrigger(
                        day_of_week=day_of_week,
                        hour=int(hour),
                        minute=int(minute),
                    ),
                    id=job_id,
                    replace_existing=True,
                )
                logger.debug(f"Created job {job_id}: {day_of_week} at {time_str}")

            except Exception as e:
                logger.error(f"Error creating job for {rule.id} at {time_str}: {e}")

    def _trigger_playback(self):
        """Called when a scheduled trigger fires"""
        # Check for exceptions on today's date
        today = date.today().isoformat()

        for exc in self._schedule.exceptions:
            if exc.date == today:
                if not exc.times:
                    logger.info(f"Playback skipped due to exception: {exc.reason}")
                    return
                # Check if current time is in exception times
                # (This is handled by having separate jobs for exceptions)

        logger.info("Scheduled playback triggered")

        if self._on_trigger:
            try:
                self._on_trigger()
            except Exception as e:
                logger.error(f"Error in trigger callback: {e}")

        self._update_next_trigger()

    def _update_next_trigger(self):
        """Update the next trigger time"""
        jobs = self._scheduler.get_jobs()

        if not jobs:
            self._next_trigger = None
            return

        # Find the earliest next run time
        next_times = []
        for job in jobs:
            if job.next_run_time:
                next_times.append(job.next_run_time)

        if next_times:
            self._next_trigger = min(next_times)
        else:
            self._next_trigger = None

    def get_next_trigger(self) -> Optional[datetime]:
        """Get the next scheduled trigger time"""
        self._update_next_trigger()
        return self._next_trigger

    def get_triggers_today(self) -> List[str]:
        """Get all trigger times for today"""
        today_triggers = []
        today = datetime.now().date()
        today_day = DAY_NAMES[today.weekday()]

        # Check for exceptions first
        today_iso = today.isoformat()
        for exc in self._schedule.exceptions:
            if exc.date == today_iso:
                return exc.times  # Return exception times (may be empty)

        # Collect all times for today from rules
        for rule in self._schedule.rules:
            if not rule.enabled:
                continue

            if today_day in [d.lower()[:3] for d in rule.days]:
                today_triggers.extend(rule.times)

        # Sort and deduplicate
        today_triggers = sorted(set(today_triggers))
        return today_triggers

    def set_on_trigger(self, callback: Callable):
        """Set callback for when schedule triggers playback"""
        self._on_trigger = callback

    def set_on_stop(self, callback: Callable):
        """Set callback for when schedule stops playback"""
        self._on_stop = callback

    def add_rule(self, rule: ScheduleRule) -> str:
        """Add a new rule"""
        self._schedule.rules.append(rule)
        self.save_schedule()
        self._rebuild_jobs()
        return rule.id

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID"""
        for i, rule in enumerate(self._schedule.rules):
            if rule.id == rule_id:
                del self._schedule.rules[i]
                self.save_schedule()
                self._rebuild_jobs()
                return True
        return False

    def update_rule(self, rule_id: str, rule: ScheduleRule) -> bool:
        """Update an existing rule"""
        for i, existing in enumerate(self._schedule.rules):
            if existing.id == rule_id:
                self._schedule.rules[i] = rule
                self.save_schedule()
                self._rebuild_jobs()
                return True
        return False

    def add_exception(self, exception: ScheduleException):
        """Add a schedule exception"""
        self._schedule.exceptions.append(exception)
        self.save_schedule()

    def remove_exception(self, date_str: str) -> bool:
        """Remove an exception by date"""
        for i, exc in enumerate(self._schedule.exceptions):
            if exc.date == date_str:
                del self._schedule.exceptions[i]
                self.save_schedule()
                return True
        return False

    def set_mode(self, mode: ScheduleMode):
        """Set scheduling mode"""
        self._schedule.mode = mode
        self.save_schedule()
        self._rebuild_jobs()

    def enable(self):
        """Enable scheduling"""
        self._schedule.enabled = True
        self.save_schedule()
        self._rebuild_jobs()

    def disable(self):
        """Disable scheduling"""
        self._schedule.enabled = False
        self.save_schedule()
        self._rebuild_jobs()

    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status for API"""
        next_trigger = self.get_next_trigger()
        return {
            "enabled": self._schedule.enabled,
            "mode": self._schedule.mode.value,
            "running": self._running,
            "next_trigger": next_trigger.isoformat() if next_trigger else None,
            "triggers_today": self.get_triggers_today(),
            "rules_count": len(self._schedule.rules),
        }

    def shutdown(self):
        """Shutdown scheduler"""
        self.stop()
        logger.info("Scheduler shutdown complete")
