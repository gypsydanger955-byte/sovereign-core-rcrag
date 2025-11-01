import pytest

from src.rcrag.application.policies import InvalidLifecycleTransition, LifecyclePolicy


def test_valid_state_transitions():
    p = LifecyclePolicy()
    assert p.validate_state_transition("proposal", "execution_report")[0]
    assert p.validate_state_transition("execution_report", "fact")[0]
    assert p.validate_state_transition("proposal", "proposal")[0]


def test_invalid_state_transitions():
    p = LifecyclePolicy()
    with pytest.raises(InvalidLifecycleTransition):
        p.validate_state_transition("proposal", "fact")
    with pytest.raises(InvalidLifecycleTransition):
        p.validate_state_transition("execution_report", "proposal")


def test_valid_status_transitions():
    p = LifecyclePolicy()
    assert p.validate_status_transition("pending", "active")[0]
    assert p.validate_status_transition("active", "superseded")[0]
    assert p.validate_status_transition("active", "disputed")[0]
    assert p.validate_status_transition("active", "rejected")[0]
    assert p.validate_status_transition("pending", "pending")[0]


def test_invalid_status_transitions():
    p = LifecyclePolicy()
    with pytest.raises(InvalidLifecycleTransition):
        p.validate_status_transition("pending", "rejected")
    with pytest.raises(InvalidLifecycleTransition):
        p.validate_status_transition("superseded", "active")
