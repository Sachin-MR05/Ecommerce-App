from app.agent.agent_state import AgentState, AgentStatus
from app.tools.tool_schema import ToolCallResult


def test_state_initialization_has_sane_defaults():
    state = AgentState.create(user_request="find headphones")

    assert state.session_id
    assert state.user_request == "find headphones"
    assert state.iteration == 0
    assert state.status == AgentStatus.INITIALIZED
    assert state.messages == []
    assert state.tool_results == []
    assert state.final_response is None
    assert state.error is None


def test_create_uses_provided_session_id_and_user_id():
    state = AgentState.create(user_request="find headphones", session_id="abc-123", user_id=42)

    assert state.session_id == "abc-123"
    assert state.user_id == 42


def test_create_generates_session_id_when_not_provided():
    state_one = AgentState.create(user_request="find headphones")
    state_two = AgentState.create(user_request="find headphones")

    assert state_one.session_id != state_two.session_id


def test_increment_iteration_counts_up():
    state = AgentState.create(user_request="find headphones")

    assert state.increment_iteration() == 1
    assert state.increment_iteration() == 2
    assert state.iteration == 2


def test_record_tool_call_and_result_tracks_history():
    state = AgentState.create(user_request="find headphones")

    state.record_tool_call("search_products", {"keyword": "headphones"})
    assert state.selected_tool == "search_products"
    assert state.tool_arguments == {"keyword": "headphones"}
    assert len(state.tool_results) == 1
    assert state.tool_results[0].tool_name == "search_products"

    result = ToolCallResult(success=True, data=[{"id": 1}])
    state.record_tool_result(result)
    assert state.tool_results[-1].result is result


def test_record_tool_error_attaches_to_latest_call():
    state = AgentState.create(user_request="find headphones")
    state.record_tool_call("search_products", {"keyword": "headphones"})

    state.record_tool_error("tool service unavailable")

    assert state.tool_results[-1].error == "tool service unavailable"


def test_complete_sets_status_and_final_response():
    state = AgentState.create(user_request="find headphones")

    state.complete("Here are three matching products.")

    assert state.status == AgentStatus.COMPLETED
    assert state.final_response == "Here are three matching products."


def test_fail_sets_status_and_error():
    state = AgentState.create(user_request="find headphones")

    state.fail("tool service unavailable")

    assert state.status == AgentStatus.FAILED
    assert state.error == "tool service unavailable"


def test_wait_for_user_sets_status_and_response():
    state = AgentState.create(user_request="order shoes")

    state.wait_for_user("Which size would you like?")

    assert state.status == AgentStatus.WAITING_FOR_USER
    assert state.final_response == "Which size would you like?"


def test_add_message_appends_in_order():
    state = AgentState.create(user_request="find headphones")

    state.add_message("user", "find headphones")
    state.add_message("assistant", "Calling search_products")

    assert [m.role for m in state.messages] == ["user", "assistant"]
    assert [m.content for m in state.messages] == ["find headphones", "Calling search_products"]
