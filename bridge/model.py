from dataclasses import dataclass
import math
import time


class SourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Window:
    bucket: str
    name: str
    used: float
    minutes: int | None
    resets_at: int | None
    blocked: bool = False

    @property
    def remaining(self):
        return max(0, min(100, 100 - self.used))

    @property
    def label(self):
        if self.minutes == 10080:
            return "WEEKLY"
        if self.minutes is None:
            return self.name.upper()
        if self.minutes % 1440 == 0:
            return f"{self.minutes // 1440} DAY"
        if self.minutes % 60 == 0:
            return f"{self.minutes // 60} HOUR"
        return f"{self.minutes} MIN"


@dataclass(frozen=True)
class Snapshot:
    windows: tuple[Window, ...]
    fetched_at: float
    allowed: bool
    plan: str | None


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def normalize(data, now=None):
    if not isinstance(data, dict):
        raise SourceError("Account limits response is not an object")
    multi = data.get("rateLimitsByLimitId")
    if isinstance(multi, dict):
        buckets = list(multi.items())
    else:
        legacy = data.get("rateLimits")
        buckets = [(legacy.get("limitId") or "codex", legacy)] if isinstance(legacy, dict) else []
    buckets.sort(key=lambda item: (item[0] != "codex", item[0]))
    windows = []
    plan = None
    allowed = data.get("ordinaryUsageAllowed") is not False
    for key, bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        plan = plan or bucket.get("planType")
        blocked = bool(bucket.get("rateLimitReachedType") or bucket.get("spendControlReached"))
        for field in ("primary", "secondary"):
            raw = bucket.get(field)
            if not isinstance(raw, dict):
                continue
            used = raw.get("usedPercent")
            if not number(used) or not 0 <= used <= 100:
                continue
            minutes = raw.get("windowDurationMins")
            if type(minutes) is not int or minutes <= 0:
                minutes = None
            reset = raw.get("resetsAt")
            if type(reset) is not int or reset <= 0:
                reset = None
            windows.append(Window(str(key), field, float(used), minutes, reset, blocked))
    if not windows:
        raise SourceError("Codex returned no usable quota windows; sign in with ChatGPT")
    return Snapshot(tuple(windows), time.time() if now is None else now, allowed, plan)


def freshness(snapshot, now, error=False, stale_seconds=150):
    if snapshot is None:
        return "NO DATA"
    if error or now - snapshot.fetched_at > stale_seconds:
        return "STALE"
    if not snapshot.allowed:
        return "BLOCKED"
    return "LIVE"


def countdown(reset, now):
    if reset is None:
        return "RESET UNKNOWN"
    seconds = reset - now
    if seconds <= 0:
        return "AWAITING RESET"
    minutes = math.ceil(seconds / 60)
    if minutes >= 1440:
        return f"RESET {minutes // 1440}D {minutes % 1440 // 60:02}H"
    return f"RESET {minutes // 60}H {minutes % 60:02}M"
