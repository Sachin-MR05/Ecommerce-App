from __future__ import annotations

import logging

from app.agent.agent_state import AgentState, AgentStatus
from app.execution.executor import Executor, ExecutorError
from app.planning.decision import Decision, DecisionAction
from app.planning.planner import Planner, PlannerError

logger = logging.getLogger(__name__)


class AgentLoop:
    """The core think -> act -> observe loop.

    Knows nothing about HTTP, FastAPI, or how AgentState was created - it
    only drives Planner/Executor against a given AgentState until a
    terminal status is reached or AGENT_MAX_ITERATIONS is hit. The LLM
    determines the next action each iteration; the loop never assumes a
    fixed operation sequence.
    """

    def __init__(self, planner: Planner, executor: Executor, max_iterations: int):
        self._planner = planner
        self._executor = executor
        self._max_iterations = max_iterations

    def run(self, state: AgentState) -> AgentState:
        logger.info("Agent loop started for session %s", state.session_id)

        while True:
            iteration = state.increment_iteration()
            if iteration > self._max_iterations:
                logger.warning(
                    "Session %s exceeded max iterations (%d)", state.session_id, self._max_iterations
                )
                state.fail(
                    "I wasn't able to complete this request within the allowed number of steps. "
                    "Please try rephrasing your request or breaking it into smaller steps."
                )
                return state

            logger.info("Session %s - iteration %d", state.session_id, iteration)
            state.status = AgentStatus.THINKING

            try:
                decision = self._planner.decide(state)
            except PlannerError as exc:
                logger.error("Session %s - planning failed: %s", state.session_id, exc)
                state.fail("I couldn't determine the next step for this request. Please try again.")
                return state

            if decision.action == DecisionAction.FINAL_RESPONSE:
                state.add_message("assistant", decision.response)
                state.complete(decision.response)
                logger.info("Session %s completed", state.session_id)
                return state

            if decision.action == DecisionAction.ASK_USER:
                state.add_message("assistant", decision.clarification_question)
                state.wait_for_user(decision.clarification_question)
                logger.info("Session %s waiting for user clarification", state.session_id)
                return state

            if decision.action == DecisionAction.TOOL_CALL:
                state.status = AgentStatus.TOOL_CALL
                self._run_tool_call(decision, state)
                continue

            # Unreachable in practice - Decision validates its own shape -
            # but fail safely rather than loop forever on an unexpected action.
            state.fail(f"Received an unsupported decision action: {decision.action}")
            return state

    def _run_tool_call(self, decision: Decision, state: AgentState) -> None:
        state.add_message(
            "assistant", f"Calling tool '{decision.tool_name}' with arguments {decision.arguments}"
        )

        try:
            result = self._executor.execute(decision, state)
        except ExecutorError as exc:
            logger.error("Session %s - tool execution failed: %s", state.session_id, exc)
            # Let the agent observe the failure and decide what to do next on
            # the following iteration, rather than aborting the whole request.
            state.add_message("tool", f"Tool call failed: {exc}")
            return

        state.status = AgentStatus.OBSERVING
        observation = (
            f"Tool '{decision.tool_name}' result: success={result.success}, data={result.data}, "
            f"error_code={result.error_code}, error_message={result.error_message}"
        )
        state.add_message("tool", observation)
