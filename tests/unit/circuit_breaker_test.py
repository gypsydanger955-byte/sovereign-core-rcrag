import time

import pytest

from src.rcrag.infrastructure.historian.circuit_breaker_decorator import (
    CircuitBreakerDecorator,
    CircuitBreakerOpenError,
)


class FlakyHistorian:
    def __init__(self):
        self.calls = 0
        self.fail_until = 0

    def ping(self):
        self.calls += 1
        if self.calls <= self.fail_until:
            raise RuntimeError("boom")
        return True


def test_circuit_breaker_opens_after_threshold():
    inner = FlakyHistorian()
    inner.fail_until = 3
    cb = CircuitBreakerDecorator(inner, failure_threshold=3, reset_timeout_s=0.5)

    # First 3 calls fail; breaker should open after third failure
    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb.ping()
    assert cb.state == "open"

    # While open and before timeout, further calls raise open error
    with pytest.raises(CircuitBreakerOpenError):
        cb.ping()


def test_circuit_breaker_half_open_after_timeout_and_recovery_to_closed():
    inner = FlakyHistorian()
    inner.fail_until = 2
    cb = CircuitBreakerDecorator(inner, failure_threshold=2, reset_timeout_s=0.2)

    # cause open
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.ping()
    assert cb.state == "open"

    # wait for half-open
    time.sleep(0.25)
    # first trial in half-open succeeds and should close
    res = cb.ping()
    assert res is True
    assert cb.state == "closed"

    # Subsequent calls normal
    assert cb.ping() is True
    assert cb.state == "closed"


def test_circuit_breaker_half_open_failure_reopens():
    inner = FlakyHistorian()
    inner.fail_until = 5
    cb = CircuitBreakerDecorator(inner, failure_threshold=2, reset_timeout_s=0.1)

    # cause open
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.ping()
    assert cb.state == "open"

    time.sleep(0.12)
    # next call still fails; should re-open
    with pytest.raises(RuntimeError):
        cb.ping()
    assert cb.state == "open"
