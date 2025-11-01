import threading
import time
from typing import Any, Callable, Optional

try:
    # Phase 1 likely provides this base decorator
    from src.rcrag.infrastructure.historian.decorator import HistorianDecorator  # type: ignore
except Exception:  # pragma: no cover - fallback for standalone run
    class HistorianDecorator:  # minimal fallback
        def __init__(self, inner: Any) -> None:
            self.inner = inner

        def __getattr__(self, name: str) -> Any:
            return getattr(self.inner, name)

class CircuitBreakerOpenError(RuntimeError):
    pass


class CircuitBreakerDecorator(HistorianDecorator):
    """
    Decorates a HistorianPort implementation with a circuit breaker.
    Applies breaker to all callable, public methods of the historian.
    """

    def __init__(
        self,
        inner: Any,
        *,
        failure_threshold: int = 5,
        reset_timeout_s: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        super().__init__(inner)
        self._failure_threshold = max(1, int(failure_threshold))
        self._reset_timeout_s = float(reset_timeout_s)
        self._half_open_max_calls = max(1, int(half_open_max_calls))

        self._state = "closed"  # closed | open | half_open
        self._failure_count = 0
        self._opened_at: Optional[float] = None
        self._half_open_inflight = 0

        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def _transition_to_open(self) -> None:
        self._state = "open"
        self._opened_at = time.monotonic()
        self._half_open_inflight = 0

    def _transition_to_half_open_if_timeout_elapsed(self) -> None:
        now = time.monotonic()
        if self._opened_at is None:
            self._opened_at = now
        if (now - self._opened_at) >= self._reset_timeout_s:
            self._state = "half_open"
            self._half_open_inflight = 0

    def _transition_to_closed(self) -> None:
        self._state = "closed"
        self._failure_count = 0
        self._opened_at = None
        self._half_open_inflight = 0

    def _record_failure(self) -> None:
        self._failure_count += 1
        if self._state == "half_open":
            # immediate open on failure in half-open
            self._transition_to_open()
        elif self._failure_count >= self._failure_threshold:
            self._transition_to_open()

    def _before_call(self) -> None:
        # Evaluate state and possibly transition
        if self._state == "open":
            self._transition_to_half_open_if_timeout_elapsed()
            if self._state == "open":
                raise CircuitBreakerOpenError("Circuit breaker is open")

        if self._state == "half_open":
            if self._half_open_inflight >= self._half_open_max_calls:
                # limit concurrent test calls
                raise CircuitBreakerOpenError("Circuit breaker is half-open; trial limit reached")
            self._half_open_inflight += 1

    def _after_call_success(self) -> None:
        if self._state == "half_open":
            # Successful trial -> close circuit
            self._transition_to_closed()
        # In closed state, success resets failure count
        if self._state == "closed":
            self._failure_count = 0

    def _after_call_failure(self) -> None:
        self._record_failure()

    def _finally(self) -> None:
        if self._state == "half_open" and self._half_open_inflight > 0:
            self._half_open_inflight -= 1

    def _call_with_circuit(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            self._before_call()
        try:
            result = func(*args, **kwargs)
        except Exception:
            with self._lock:
                self._after_call_failure()
                self._finally()
            raise
        else:
            with self._lock:
                self._after_call_success()
                self._finally()
            return result

    def __getattr__(self, name: str) -> Any:
        # wrap callable public methods
        attr = getattr(self.inner, name)
        if callable(attr) and not name.startswith("_"):
            def wrapped(*args: Any, **kwargs: Any) -> Any:
                return self._call_with_circuit(attr, *args, **kwargs)
            return wrapped
        return attr
