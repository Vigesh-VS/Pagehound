import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config

PACIFIC = ZoneInfo("America/Los_Angeles")

MESSAGES = {
    "daily_budget": "The demo has used up today's free AI quota. It resets at midnight Pacific time.",
    "reserve": "The remaining quota is held for new visitors. Please come back tomorrow.",
    "user_share": "You've used your share of today's quota. Your share shrinks as more people join.",
    "user_rpm": "You're asking too fast. Please wait a moment.",
    "global_rpm": "The demo is busy right now. Please try again in a few seconds.",
    "uploads": "You've reached today's upload limit.",
    "guest_cap": "You've used today's guest questions. Sign in with Google to keep going.",
}


def day_key():
    return datetime.now(PACIFIC).strftime("%Y-%m-%d")


@dataclass
class Decision:
    ok: bool
    reason: str = ""
    message: str = ""
    retry_after: int = 0
    status: dict = field(default_factory=dict)


class QuotaManager:
    def __init__(self, budget, reserve_fraction, global_rpm, user_rpm, uploads_per_day):
        self.budget = budget
        self.pool = int(budget * (1 - reserve_fraction))
        self.global_rpm = global_rpm
        self.user_rpm = user_rpm
        self.uploads_per_day = uploads_per_day
        self.lock = threading.Lock()
        self._reset()

    def _reset(self):
        self.day = day_key()
        self.used = {}
        self.late = set()
        self.uploads = {}
        self.total = 0
        self.global_hits = deque()
        self.user_hits = {}

    def _roll(self):
        if day_key() != self.day:
            self._reset()

    @staticmethod
    def _prune(hits, now):
        while hits and now - hits[0] > 60:
            hits.popleft()

    def _share(self, user):
        users = len(self.used) + (0 if user in self.used else 1)
        return self.pool / max(users, 1)

    def _room(self, user):
        if user not in self.used or user in self.late:
            return self.budget - self.total
        return self.pool - self.total

    def _remaining(self, user):
        left = self._share(user) - self.used.get(user, 0)
        return max(0, int(min(left, self._room(user))))

    def _status(self, user):
        return {
            "your_used": self.used.get(user, 0),
            "your_remaining": self._remaining(user),
            "your_share": int(self._share(user)),
            "total_used": self.total,
            "budget": self.budget,
            "active_users": len(self.used),
        }

    def status(self, user):
        with self.lock:
            self._roll()
            return self._status(user)

    def _deny(self, reason, user, retry_after=0):
        return Decision(False, reason, MESSAGES[reason], retry_after, self._status(user))

    def check_and_consume(self, user, cap=None):
        with self.lock:
            self._roll()
            now = time.time()

            if self.total >= self.budget:
                return self._deny("daily_budget", user)

            if cap is not None and self.used.get(user, 0) >= cap:
                return self._deny("guest_cap", user)

            is_new = user not in self.used
            if is_new and self.total >= self.pool:
                self.late.add(user)

            if not is_new and user not in self.late and self.total >= self.pool:
                return self._deny("reserve", user)

            if self.used.get(user, 0) >= self._share(user):
                return self._deny("user_share", user)

            hits = self.user_hits.setdefault(user, deque())
            self._prune(hits, now)
            self._prune(self.global_hits, now)
            if len(hits) >= self.user_rpm:
                return self._deny("user_rpm", user, int(60 - (now - hits[0])) + 1)
            if len(self.global_hits) >= self.global_rpm:
                return self._deny("global_rpm", user, int(60 - (now - self.global_hits[0])) + 1)

            self.used[user] = self.used.get(user, 0) + 1
            self.total += 1
            hits.append(now)
            self.global_hits.append(now)
            return Decision(True, status=self._status(user))

    def refund(self, user):
        with self.lock:
            if self.used.get(user, 0) > 0:
                self.used[user] -= 1
                self.total -= 1
                if self.used[user] == 0:
                    del self.used[user]
                    self.late.discard(user)

    def consume_upload(self, user, limit=None):
        with self.lock:
            self._roll()
            count = self.uploads.get(user, 0)
            if count >= (limit or self.uploads_per_day):
                return False
            self.uploads[user] = count + 1
            return True


quota = QuotaManager(
    config.DAILY_BUDGET,
    config.RESERVE_FRACTION,
    config.GLOBAL_RPM,
    config.USER_RPM,
    config.UPLOADS_PER_DAY,
)
