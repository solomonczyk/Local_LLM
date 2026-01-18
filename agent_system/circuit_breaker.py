import time
from typing import Any, Dict, Optional


class CircuitBreaker:
    """Simple circuit breaker for repeated failures."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60, success_threshold: int = 1):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = "CLOSED"
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None

        self.total_calls = 0
        self.total_failures = 0
        self.total_blocked = 0
        self.state_changes = []

    def _record_state_change(self, old_state: str, new_state: str, reason: str) -> None:
        self.state_changes.append({"timestamp": time.time(), "from": old_state, "to": new_state, "reason": reason})
        if len(self.state_changes) > 10:
            self.state_changes.pop(0)

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            if self.last_failure_time and time.time() - self.last_failure_time >= self.recovery_timeout:
                old_state = self.state
                self.state = "HALF_OPEN"
                self.success_count = 0
                self._record_state_change(old_state, "HALF_OPEN", "Recovery timeout elapsed")
                return True
            self.total_blocked += 1
            return False

        if self.state == "HALF_OPEN":
            return True

        return False

    def record_success(self) -> None:
        self.total_calls += 1

        if self.state == "HALF_OPEN":
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                old_state = self.state
                self.state = "CLOSED"
                self.failure_count = 0
                self._record_state_change(old_state, "CLOSED", f"{self.success_count} successful calls")
        elif self.state == "CLOSED":
            self.failure_count = 0

    def record_failure(self, error: Exception = None) -> None:
        self.total_calls += 1
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == "HALF_OPEN":
            old_state = self.state
            self.state = "OPEN"
            self._record_state_change(old_state, "OPEN", f"Failure in HALF_OPEN: {error}")
        elif self.state == "CLOSED":
            if self.failure_count >= self.failure_threshold:
                old_state = self.state
                self.state = "OPEN"
                self._record_state_change(
                    old_state, "OPEN", f"Failure threshold reached ({self.failure_count}/{self.failure_threshold})"
                )

    def get_status(self) -> Dict[str, Any]:
        time_until_retry = None
        if self.state == "OPEN" and self.last_failure_time:
            elapsed = time.time() - self.last_failure_time
            time_until_retry = max(0, self.recovery_timeout - elapsed)

        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_blocked": self.total_blocked,
            "time_until_retry": round(time_until_retry, 1) if time_until_retry else None,
            "config": {
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "success_threshold": self.success_threshold,
            },
            "recent_state_changes": self.state_changes[-3:],
        }
