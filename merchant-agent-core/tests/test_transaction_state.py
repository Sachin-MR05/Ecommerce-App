import pytest

from transaction.exceptions import InvalidTransactionStateError
from transaction.transaction_state import TERMINAL_STATES, TransactionState, TransactionStateMachine


def test_initial_state_is_initiated():
    machine = TransactionStateMachine()
    assert machine.state == TransactionState.INITIATED
    assert not machine.is_terminal()


def test_happy_path_transitions_are_allowed():
    machine = TransactionStateMachine()
    happy_path = [
        TransactionState.VALIDATING,
        TransactionState.VALIDATED,
        TransactionState.ORDER_CREATING,
        TransactionState.PAYMENT_PENDING,
        TransactionState.PAYMENT_PROCESSING,
        TransactionState.PAYMENT_SUCCESS,
        TransactionState.ORDER_CONFIRMED,
    ]
    for target in happy_path:
        machine.transition(target)

    assert machine.state == TransactionState.ORDER_CONFIRMED
    assert machine.is_terminal()


def test_payment_failure_path_transitions_deterministically():
    machine = TransactionStateMachine()
    for target in [
        TransactionState.VALIDATING,
        TransactionState.VALIDATED,
        TransactionState.ORDER_CREATING,
        TransactionState.PAYMENT_PENDING,
        TransactionState.PAYMENT_PROCESSING,
    ]:
        machine.transition(target)

    machine.transition(TransactionState.PAYMENT_FAILED)
    machine.transition(TransactionState.FAILED)

    assert machine.state == TransactionState.FAILED
    assert machine.is_terminal()


def test_validation_failure_short_circuits_to_failed():
    machine = TransactionStateMachine()
    machine.transition(TransactionState.VALIDATING)
    machine.transition(TransactionState.FAILED)
    assert machine.state == TransactionState.FAILED


@pytest.mark.parametrize(
    "start,invalid_target",
    [
        (TransactionState.INITIATED, TransactionState.PAYMENT_PENDING),
        (TransactionState.INITIATED, TransactionState.ORDER_CONFIRMED),
        (TransactionState.VALIDATED, TransactionState.PAYMENT_PROCESSING),
        (TransactionState.PAYMENT_PENDING, TransactionState.ORDER_CONFIRMED),
        (TransactionState.PAYMENT_SUCCESS, TransactionState.PAYMENT_PENDING),
        (TransactionState.ORDER_CONFIRMED, TransactionState.VALIDATING),
        (TransactionState.FAILED, TransactionState.VALIDATING),
    ],
)
def test_invalid_transitions_are_rejected(start, invalid_target):
    machine = TransactionStateMachine(initial=start)
    with pytest.raises(InvalidTransactionStateError):
        machine.transition(invalid_target)
    # Rejected transition must never mutate state.
    assert machine.state == start


def test_cancellation_only_allowed_before_payment_processing():
    machine = TransactionStateMachine()
    for target in [
        TransactionState.VALIDATING,
        TransactionState.VALIDATED,
        TransactionState.ORDER_CREATING,
        TransactionState.PAYMENT_PENDING,
    ]:
        machine.transition(target)

    machine.transition(TransactionState.CANCELLED)
    assert machine.state == TransactionState.CANCELLED
    assert machine.is_terminal()


def test_terminal_states_have_no_outgoing_transitions():
    for state in TERMINAL_STATES:
        machine = TransactionStateMachine(initial=state)
        assert machine.is_terminal()
        for target in TransactionState:
            assert not machine.can_transition(target)
