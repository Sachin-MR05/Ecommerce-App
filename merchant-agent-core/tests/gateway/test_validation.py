from app.gateway.validation import validate_incoming_message


def test_valid_request_passes():
    assert validate_incoming_message("s1", "u1", "I want to buy 2 iPhones", "web") is None


def test_empty_message_is_rejected():
    error = validate_incoming_message("s1", "u1", "", "web")
    assert error is not None
    assert error.code == "EMPTY_MESSAGE"


def test_whitespace_only_message_is_rejected():
    error = validate_incoming_message("s1", "u1", "   ", "web")
    assert error is not None
    assert error.code == "EMPTY_MESSAGE"


def test_missing_session_id_is_rejected():
    error = validate_incoming_message(None, "u1", "hello", "web")
    assert error is not None
    assert error.code == "MISSING_SESSION_ID"


def test_missing_user_id_is_rejected():
    error = validate_incoming_message("s1", None, "hello", "web")
    assert error is not None
    assert error.code == "MISSING_USER_ID"


def test_message_too_long_is_rejected():
    error = validate_incoming_message("s1", "u1", "x" * 5000, "web")
    assert error is not None
    assert error.code == "MESSAGE_TOO_LONG"


def test_invalid_channel_is_rejected():
    error = validate_incoming_message("s1", "u1", "hello", "carrier-pigeon")
    assert error is not None
    assert error.code == "INVALID_CHANNEL"


def test_default_channel_is_allowed_when_omitted():
    assert validate_incoming_message("s1", "u1", "hello", None) is None
