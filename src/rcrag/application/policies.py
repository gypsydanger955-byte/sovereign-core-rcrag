from dataclasses import dataclass
from typing import Literal, Tuple


class InvalidLifecycleTransition(Exception):
    pass


State = Literal["proposal", "execution_report", "fact"]
Status = Literal["pending", "active", "superseded", "disputed", "rejected"]


@dataclass(frozen=True)
class LifecyclePolicy:
    """
    Validates lifecycle state and status transitions.

    State transitions: proposal -> execution_report -> fact
    Status transitions: pending -> active -> (superseded|disputed|rejected)
    """

    def validate_state_transition(self, from_state: State, to_state: State) -> Tuple[bool, str]:
        order = {"proposal": 0, "execution_report": 1, "fact": 2}
        if from_state == to_state:
            return True, "no-op"
        if order.get(to_state, 99) == order.get(from_state, -1) + 1:
            return True, "ok"
        raise InvalidLifecycleTransition(f"Invalid state transition {from_state} -> {to_state}")

    def validate_status_transition(self, from_status: Status, to_status: Status) -> Tuple[bool, str]:
        if from_status == to_status:
            return True, "no-op"
        if from_status == "pending" and to_status == "active":
            return True, "ok"
        if from_status == "active" and to_status in ("superseded", "disputed", "rejected"):
            return True, "ok"
        raise InvalidLifecycleTransition(f"Invalid status transition {from_status} -> {to_status}")
