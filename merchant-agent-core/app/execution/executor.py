from __future__ import annotations

import logging
from typing import Optional

from app.agent.agent_state import AgentState
from app.audit.audit_event import AuditEventType
from app.audit.audit_service import AuditService
from app.failure_handling.failure_handler import FailureHandler
from app.failure_handling.idempotency import DuplicateOperationInProgressError, IdempotencyStatus
from app.planning.decision import Decision
from app.tools.tool_client import ToolClient, ToolClientError
from app.tools.tool_schema import ToolCallResult, ToolDefinition

logger = logging.getLogger(__name__)


class ExecutorError(Exception):
    """A tool call could not be executed as decided."""


class UnknownToolError(ExecutorError):
    """The planner selected a tool that isn't in the request's available tool definitions."""


class InvalidToolArgumentsError(ExecutorError):
    """The supplied arguments don't satisfy the tool's declared input schema."""


# Tool names whose execution represents a payment/order operation and
# therefore get idempotency protection + PAYMENT_*/ORDER_CREATED audit
# events. Kept here (rather than in tool_schema.py's KNOWN_TOOL_NAMES,
# which is documentation-only) because this is Failure Handling/Audit
# Service policy, not a wire contract.
PAYMENT_TOOL_NAMES: frozenset[str] = frozenset({"verify_payment"})
ORDER_TOOL_NAMES: frozenset[str] = frozenset({"create_order"})
IDEMPOTENCY_PROTECTED_TOOLS: frozenset[str] = PAYMENT_TOOL_NAMES | ORDER_TOOL_NAMES

# Best-effort, response-shape-agnostic lookup for a transaction/order
# identifier in a tool's result data, for audit traceability only. Never
# required - absence just means the audit trail for that event has no
# transaction_id.
_TRANSACTION_ID_KEYS: tuple[str, ...] = ("transactionId", "orderId", "id")


class Executor:
    """Executes a validated TOOL_CALL Decision against the Java Tool Layer
    via ToolClient, and records the outcome on the AgentState.

    Never decides which tool to use - that belongs to the planner/LLM. This
    class only validates that the chosen tool/arguments are legitimate,
    delegates, and captures the result.

    failure_handler and audit_service are optional (default to no
    integration) so existing callers/tests that construct
    `Executor(tool_client)` keep working unchanged. When supplied, the
    Executor never lets either one change control flow beyond what's
    documented below - failure_handler only classifies/decides recovery
    and protects against duplicate payment/order execution; audit_service
    only records what happened.
    """

    def __init__(
        self,
        tool_client: ToolClient,
        failure_handler: Optional[FailureHandler] = None,
        audit_service: Optional[AuditService] = None,
    ):
        self._tool_client = tool_client
        self._failure_handler = failure_handler
        self._audit_service = audit_service

    def execute(self, decision: Decision, state: AgentState) -> ToolCallResult:
        tool_definition = self._require_known_tool(decision.tool_name, state.available_tools)
        self._validate_arguments(tool_definition, decision.arguments)

        state.record_tool_call(decision.tool_name, decision.arguments)
        logger.info("Executing tool '%s' for session %s", decision.tool_name, state.session_id)

        request_id = state.request_id or state.session_id
        tool_name = decision.tool_name

        idempotency_key: Optional[str] = None
        if self._failure_handler is not None and tool_name in IDEMPOTENCY_PROTECTED_TOOLS:
            cached = self._check_idempotency(tool_name, decision.arguments, request_id, state)
            if cached is not None:
                return cached
            idempotency_key = self._failure_handler.idempotency_key_for(tool_name, None, decision.arguments)

        self._audit_tool_call_started(tool_name, decision.arguments, request_id)

        try:
            result = self._tool_client.execute_tool(tool_name, decision.arguments, user_id=state.user_id)
        except ToolClientError as exc:
            logger.error("Tool '%s' execution failed: %s", tool_name, exc)
            state.record_tool_error(str(exc))
            self._handle_transport_failure(exc, tool_name, request_id, idempotency_key)
            raise ExecutorError(str(exc)) from exc

        state.record_tool_result(result)
        transaction_id = _extract_transaction_id(result.data)
        self._audit_tool_outcome(tool_name, result, request_id, transaction_id)
        self._finish_idempotency(idempotency_key, result)

        return result

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    def _check_idempotency(
        self, tool_name: str, arguments: dict, request_id: str, state: AgentState
    ) -> Optional[ToolCallResult]:
        """Returns a cached result if this exact operation already ran to
        completion, so the caller returns early without re-invoking the
        tool. Raises ExecutorError if the same operation is already
        in-flight (concurrent duplicate)."""
        assert self._failure_handler is not None
        key = self._failure_handler.idempotency_key_for(tool_name, None, arguments)
        try:
            record = self._failure_handler.begin_protected_operation(key, None, tool_name)
        except DuplicateOperationInProgressError as exc:
            logger.warning("Duplicate in-flight operation for tool '%s': %s", tool_name, exc)
            raise ExecutorError(str(exc)) from exc

        if record.status == IdempotencyStatus.IN_PROGRESS:
            return None  # first time seeing this key - proceed normally

        logger.info(
            "Idempotent replay for tool '%s' (status=%s) - returning existing result instead of re-executing",
            tool_name,
            record.status.value,
        )
        if self._audit_service is not None:
            event_type = AuditEventType.TOOL_SUCCESS if record.status == IdempotencyStatus.SUCCEEDED else AuditEventType.TOOL_FAILURE
            self._audit_service.record_event(
                event_type,
                component="Executor",
                operation=tool_name,
                status=record.status.value,
                request_id=request_id,
                metadata={"idempotent_replay": True},
            )

        if record.status == IdempotencyStatus.SUCCEEDED and record.result is not None:
            # record.result is whatever ToolClient.execute_tool returned for
            # the original call (today, a contracts.tool_response.ToolResponse -
            # duck-type compatible with ToolCallResult's success/data/
            # error_code/error_message surface used throughout this module).
            state.record_tool_result(record.result)
            return record.result

        error_message = record.error or f"Operation '{tool_name}' previously failed"
        state.record_tool_error(error_message)
        raise ExecutorError(error_message)

    def _finish_idempotency(self, idempotency_key: Optional[str], result: ToolCallResult) -> None:
        if idempotency_key is None or self._failure_handler is None:
            return
        if result.success:
            self._failure_handler.complete_protected_operation(idempotency_key, result)
        else:
            self._failure_handler.fail_protected_operation(idempotency_key, result.error_message or "tool reported failure")

    # ------------------------------------------------------------------
    # Failure classification (delegates the decision; never retries here
    # itself - the agent loop/caller acts on the recovery decision)
    # ------------------------------------------------------------------

    def _handle_transport_failure(
        self, exc: ToolClientError, tool_name: str, request_id: str, idempotency_key: Optional[str]
    ) -> None:
        if idempotency_key is not None and self._failure_handler is not None:
            self._failure_handler.fail_protected_operation(idempotency_key, str(exc))

        standard_error = None
        if self._failure_handler is not None:
            recovery = self._failure_handler.handle_tool_client_exception(
                exc, component="Executor", attempt=1, request_id=request_id
            )
            standard_error = recovery.standard_error

        if self._audit_service is not None:
            self._audit_service.record_event(
                AuditEventType.TOOL_FAILURE,
                component="Executor",
                operation=tool_name,
                status="FAILED",
                request_id=request_id,
                error_code=standard_error.error_code if standard_error else None,
                error_message=str(exc),
            )
            if tool_name in PAYMENT_TOOL_NAMES:
                self._audit_service.record_event(
                    AuditEventType.PAYMENT_FAILED,
                    component="Executor",
                    operation=tool_name,
                    status="FAILED",
                    request_id=request_id,
                    error_message=str(exc),
                )

    # ------------------------------------------------------------------
    # Audit helpers
    # ------------------------------------------------------------------

    def _audit_tool_call_started(self, tool_name: str, arguments: dict, request_id: str) -> None:
        if self._audit_service is None:
            return
        self._audit_service.record_event(
            AuditEventType.TOOL_CALL,
            component="Executor",
            operation=tool_name,
            status="STARTED",
            request_id=request_id,
        )
        if tool_name in PAYMENT_TOOL_NAMES:
            self._audit_service.record_event(
                AuditEventType.PAYMENT_INITIATED,
                component="Executor",
                operation=tool_name,
                status="STARTED",
                request_id=request_id,
            )

    def _audit_tool_outcome(
        self, tool_name: str, result: ToolCallResult, request_id: str, transaction_id: Optional[str]
    ) -> None:
        if self._audit_service is None:
            return

        if result.success:
            self._audit_service.record_event(
                AuditEventType.TOOL_SUCCESS,
                component="Executor",
                operation=tool_name,
                status="SUCCESS",
                request_id=request_id,
                transaction_id=transaction_id,
            )
            if tool_name in PAYMENT_TOOL_NAMES:
                self._audit_service.record_event(
                    AuditEventType.PAYMENT_SUCCESS,
                    component="Executor",
                    operation=tool_name,
                    status="SUCCESS",
                    request_id=request_id,
                    transaction_id=transaction_id,
                )
            if tool_name in ORDER_TOOL_NAMES:
                self._audit_service.record_event(
                    AuditEventType.ORDER_CREATED,
                    component="Executor",
                    operation=tool_name,
                    status="SUCCESS",
                    request_id=request_id,
                    transaction_id=transaction_id,
                )
            return

        error = getattr(result, "error", None)
        recovery_error_code = error.code if error else result.error_code
        recovery_error_message = error.message if error else result.error_message

        if self._failure_handler is not None and error is not None:
            self._failure_handler.handle_tool_error(
                error, component="Executor", attempt=1, transaction_id=transaction_id, request_id=request_id
            )

        self._audit_service.record_event(
            AuditEventType.TOOL_FAILURE,
            component="Executor",
            operation=tool_name,
            status="FAILED",
            request_id=request_id,
            transaction_id=transaction_id,
            error_code=recovery_error_code,
            error_message=recovery_error_message,
        )
        if tool_name in PAYMENT_TOOL_NAMES:
            self._audit_service.record_event(
                AuditEventType.PAYMENT_FAILED,
                component="Executor",
                operation=tool_name,
                status="FAILED",
                request_id=request_id,
                transaction_id=transaction_id,
                error_code=recovery_error_code,
                error_message=recovery_error_message,
            )

    def _require_known_tool(self, tool_name: str, available_tools: list[ToolDefinition]) -> ToolDefinition:
        for tool in available_tools:
            if tool.name == tool_name:
                return tool
        raise UnknownToolError(f"Tool '{tool_name}' is not among the tools available for this request")

    def _validate_arguments(self, tool: ToolDefinition, arguments: dict) -> None:
        required = tool.input_schema.get("required", []) if isinstance(tool.input_schema, dict) else []
        missing = [name for name in required if name not in arguments]
        if missing:
            raise InvalidToolArgumentsError(
                f"Tool '{tool.name}' is missing required argument(s): {', '.join(missing)}"
            )


def _extract_transaction_id(data) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    for key in _TRANSACTION_ID_KEYS:
        if key in data and data[key] is not None:
            return str(data[key])
    return None
