"""Tests for the local-tier fixture logic. No server needed; always runs."""

import pytest

from local_logic import (parse_listing, parse_ollama_tags, pick_lmstudio_model,
                         pick_ollama_model)

SKIP = pytest.skip.Exception
FAIL = pytest.fail.Exception


def _v1(*entries):
    return {"models": list(entries)}


def test_empty_list_skips():
    with pytest.raises(SKIP):
        pick_lmstudio_model(parse_listing(_v1()))


def test_only_embedding_models_skips():
    models = parse_listing(_v1({"key": "e", "type": "embedding"}))
    with pytest.raises(SKIP, match="only embedding"):
        pick_lmstudio_model(models)


def test_unrecognised_types_fail_and_name_them():
    models = parse_listing(_v1({"key": "a", "type": "chat-thing", "extra": 1}))
    with pytest.raises(FAIL) as err:
        pick_lmstudio_model(models)
    assert "chat-thing" in str(err.value)
    assert "extra" in str(err.value)


def test_missing_type_field_fails_not_skips():
    models = parse_listing(_v1({"key": "a"}))
    with pytest.raises(FAIL):
        pick_lmstudio_model(models)


def test_unknown_top_level_key_fails_and_names_keys():
    with pytest.raises(FAIL) as err:
        parse_listing({"things": [], "count": 0})
    assert "things" in str(err.value) and "count" in str(err.value)


def test_non_dict_body_fails():
    with pytest.raises(FAIL):
        parse_listing([1, 2])


def test_named_model_missing_fails():
    models = parse_listing(_v1({"key": "a", "type": "llm"}))
    with pytest.raises(FAIL, match="IMAGEAI_LMSTUDIO_MODEL"):
        pick_lmstudio_model(models, "nope")


def test_named_model_found():
    models = parse_listing(_v1({"key": "a", "type": "llm"},
                               {"key": "b", "type": "llm"}))
    assert pick_lmstudio_model(models, "b").key == "b"


def test_loaded_model_beats_larger_unloaded_one():
    models = parse_listing(_v1(
        {"key": "small", "type": "llm", "size_bytes": 1},
        {"key": "big", "type": "llm", "size_bytes": 99,
         "loaded_instances": [{"id": "big"}]}))
    assert pick_lmstudio_model(models).key == "big"


def test_smallest_chat_model_when_none_loaded():
    models = parse_listing(_v1(
        {"key": "big", "type": "llm", "size_bytes": 99},
        {"key": "small", "type": "llm", "size_bytes": 5},
        {"key": "emb", "type": "embedding", "size_bytes": 1}))
    assert pick_lmstudio_model(models).key == "small"


def test_vision_flag_read_when_present():
    models = parse_listing(_v1(
        {"key": "a", "type": "llm", "capabilities": {"vision": True}},
        {"key": "b", "type": "llm", "capabilities": {"vision": False}}))
    assert [m.vision for m in models] == [True, False]


def test_vision_unknown_when_absent():
    models = parse_listing(_v1({"key": "a", "type": "llm"}))
    assert models[0].vision is None


def test_v0_listing_marks_vision_by_type_and_loaded_by_state():
    models = parse_listing({"object": "list", "data": [
        {"id": "v", "type": "vlm", "state": "loaded"},
        {"id": "t", "type": "llm", "state": "not-loaded"}]})
    assert [(m.key, m.vision, m.loaded) for m in models] == [
        ("v", True, True), ("t", False, False)]


def test_ollama_picks_smallest_completion_model_and_reads_vision():
    caps = {"emb": ["embedding"], "small": ["completion", "vision"],
            "big": ["completion"]}
    name, vision = pick_ollama_model(
        ["big", "emb", "small"], {"big": 9, "emb": 1, "small": 4}, None, caps.get)
    assert (name, vision) == ("small", True)


def test_ollama_unreadable_capabilities_trusts_name_vision_unknown():
    assert pick_ollama_model(["a"], {}, None, lambda n: None) == ("a", None)


def test_ollama_named_model_missing_fails():
    with pytest.raises(FAIL, match="IMAGEAI_OLLAMA_MODEL"):
        pick_ollama_model(["a"], {}, "zzz", lambda n: ["completion"])


def test_ollama_no_completion_model_skips():
    with pytest.raises(SKIP):
        pick_ollama_model(["e"], {}, None, lambda n: ["embedding"])


def test_named_lmstudio_model_with_empty_list_fails():
    with pytest.raises(FAIL, match="IMAGEAI_LMSTUDIO_MODEL"):
        pick_lmstudio_model(parse_listing(_v1()), "foo")


def test_named_lmstudio_model_with_embedding_only_list_fails():
    models = parse_listing(_v1({"key": "e", "type": "embedding"}))
    with pytest.raises(FAIL, match="IMAGEAI_LMSTUDIO_MODEL"):
        pick_lmstudio_model(models, "foo")


def test_entries_without_key_or_id_fail_and_name_entry_keys():
    with pytest.raises(FAIL) as err:
        parse_listing(_v1({"name": "a", "type": "llm"}))
    assert "name" in str(err.value) and "type" in str(err.value)


def test_ollama_body_without_models_fails():
    with pytest.raises(FAIL, match="no 'models' list"):
        parse_ollama_tags({"error": "x"})


def test_ollama_empty_models_skips():
    with pytest.raises(SKIP, match="no models installed"):
        parse_ollama_tags({"models": []})


def test_ollama_named_model_with_empty_models_fails():
    with pytest.raises(FAIL, match="IMAGEAI_OLLAMA_MODEL"):
        parse_ollama_tags({"models": []}, "foo")


def test_ollama_named_model_missing_fails_in_parse():
    with pytest.raises(FAIL, match="IMAGEAI_OLLAMA_MODEL"):
        parse_ollama_tags({"models": [{"name": "a", "size": 1}]}, "foo")


def test_ollama_tags_parse_names_and_sizes():
    assert parse_ollama_tags({"models": [{"name": "a", "size": 7}]}) == (["a"], {"a": 7})


# --- M5: only "nothing accepted the connection" counts as not running --------

requests = pytest.importorskip("requests")


def _decide(server, base, path, exc):
    """("skip" | "fail", message). Explicit, because a skip raised inside
    ``pytest.raises(FAIL)`` would report the test as skipped, not failed."""
    from local_logic import fail_or_skip_request_error
    try:
        fail_or_skip_request_error(server, base, path, exc)
    except SKIP as outcome:
        return "skip", str(outcome)
    except FAIL as outcome:
        return "fail", str(outcome)
    raise AssertionError("fail_or_skip_request_error returned without deciding")


def _refused(os_error):
    """requests' error for a refused connection, built as urllib3 builds it:
    ConnectionError(MaxRetryError(reason=NewConnectionError)) from the OSError."""
    from urllib3.exceptions import MaxRetryError, NewConnectionError
    new = NewConnectionError(None, f"Failed to establish a new connection: {os_error}")
    new.__cause__ = os_error
    return requests.ConnectionError(MaxRetryError(None, "/api/tags", new))


def _closed_after_accept(inner):
    """requests' error when the server accepts, then drops the connection."""
    from urllib3.exceptions import ProtocolError
    return requests.ConnectionError(ProtocolError("Connection aborted.", inner))


def _remote_disconnected():
    import http.client
    return http.client.RemoteDisconnected(
        "Remote end closed connection without response")


@pytest.mark.parametrize("exc", [
    _refused(ConnectionRefusedError(111, "Connection refused")),
    _refused(ConnectionRefusedError(
        10061, "No connection could be made because the target machine "
               "actively refused it")),
    _refused(OSError(111, "Connection refused")),      # errno only, base class
    requests.ConnectTimeout("no answer within the connect timeout"),
], ids=["refused-posix", "refused-windows", "refused-errno", "connect-timeout"])
def test_unreachable_server_skips(exc):
    outcome, msg = _decide("LM Studio", "http://h:1", "/api/v1/models", exc)
    assert outcome == "skip", msg
    assert "LM Studio is not running at http://h:1" in msg


@pytest.mark.parametrize("exc", [
    _closed_after_accept(_remote_disconnected()),
    _closed_after_accept(ConnectionResetError(104, "Connection reset by peer")),
    _closed_after_accept(ConnectionAbortedError(
        10053, "An established connection was aborted")),
    requests.exceptions.SSLError("certificate verify failed"),
    requests.exceptions.ProxyError("proxy said no"),
    requests.ConnectionError("no cause attached"),
], ids=["closed-before-reply", "reset", "aborted", "ssl", "proxy", "unexplained"])
def test_connection_error_from_an_answering_server_fails(exc):
    """A ConnectionError is not proof that nothing is listening: a server that
    accepts and then resets, or a TLS failure, must not become a green skip."""
    outcome, msg = _decide("Ollama", "http://h:2", "/api/tags", exc)
    assert outcome == "fail", msg
    assert "Ollama at http://h:2" in msg and "/api/tags" in msg
    assert type(exc).__name__ in msg


def _loopback_get(port):
    """One GET to 127.0.0.1 with proxies ignored; returns the exception raised."""
    session = requests.Session()
    session.trust_env = False
    try:
        session.get(f"http://127.0.0.1:{port}/api/tags", timeout=5)
    except requests.RequestException as exc:
        return exc
    finally:
        session.close()
    raise AssertionError("the request unexpectedly succeeded")


def test_real_refused_connection_skips():
    """The exception requests really raises for a closed loopback port."""
    import socket
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    exc = _loopback_get(port)  # nothing listens on the port any more
    outcome, msg = _decide("Ollama", f"http://127.0.0.1:{port}", "/api/tags", exc)
    assert outcome == "skip", f"{msg} ({exc!r})"
    assert "Ollama is not running" in msg


def test_real_connection_closed_after_accept_fails():
    """A loopback server that accepts and closes before replying is a failure."""
    import socket
    import threading

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def _accept_and_close():
        conn, _ = server.accept()
        conn.recv(65536)
        conn.close()

    thread = threading.Thread(target=_accept_and_close, daemon=True)
    thread.start()
    try:
        exc = _loopback_get(port)
    finally:
        thread.join(timeout=5)
        server.close()
    assert isinstance(exc, requests.ConnectionError)
    outcome, msg = _decide("Ollama", f"http://127.0.0.1:{port}", "/api/tags", exc)
    assert outcome == "fail", f"{msg} ({exc!r})"
    assert "/api/tags" in msg


@pytest.mark.parametrize("exc", [
    requests.ReadTimeout("answered, then went quiet"),
    requests.exceptions.ChunkedEncodingError("broken body"),
    requests.exceptions.TooManyRedirects("loop"),
])
def test_answering_server_error_fails(exc):
    from local_logic import fail_or_skip_request_error
    with pytest.raises(FAIL) as err:
        fail_or_skip_request_error("Ollama", "http://h:2", "/api/tags", exc)
    msg = str(err.value)
    assert "Ollama at http://h:2" in msg and "/api/tags" in msg
    assert type(exc).__name__ in msg


def test_named_model_found_is_returned_after_the_upfront_check():
    models = parse_listing(_v1({"key": "a", "type": "llm", "size_bytes": 9},
                               {"key": "b", "type": "llm", "size_bytes": 1}))
    assert pick_lmstudio_model(models, "a").key == "a"


# --- Codex P2-3: the LM Studio token also authenticates completions ----------

@pytest.mark.parametrize("value,expected", [
    (None, None), ("", None), ("  ", None), ("tok-test", "tok-test")])
def test_lmstudio_token(monkeypatch, value, expected):
    from local_logic import lmstudio_token
    if value is None:
        monkeypatch.delenv("LM_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("LM_API_TOKEN", value)
    assert lmstudio_token() == expected


def test_lmstudio_completions_pass_the_server_token(monkeypatch):
    import test_local_lmstudio as lm
    from types import SimpleNamespace
    seen = {}
    monkeypatch.setattr(lm.chameleon_llm, "completion",
                        lambda **kw: seen.update(kw) or "ok")
    server = SimpleNamespace(model="m", base_url="http://h/v1", api_key="tok-test")
    lm._ask(server, [{"role": "user", "content": "x"}])
    assert seen["api_key"] == "tok-test"


# --- the requested loaded instance is the one the tests use -------------------

def _two_instances():
    return parse_listing(_v1({
        "key": "a", "type": "llm", "size_bytes": 9,
        "loaded_instances": [{"id": "a"}, {"id": "a:2"}]}))


def test_requested_second_instance_is_used():
    from local_logic import instance_to_use
    pick = pick_lmstudio_model(_two_instances(), "a:2")
    assert pick.key == "a"
    assert instance_to_use(pick, "a:2") == "a:2"


@pytest.mark.parametrize("wanted", [None, "", "a"])
def test_first_instance_is_the_default(wanted):
    """No selection, or a selection by model key, keeps the first instance."""
    from local_logic import instance_to_use
    pick = pick_lmstudio_model(_two_instances(), wanted or None)
    assert instance_to_use(pick, wanted) == "a"


def test_request_for_an_instance_that_is_not_loaded_falls_back_to_the_first():
    from local_logic import instance_to_use
    pick = pick_lmstudio_model(_two_instances(), "a")
    assert instance_to_use(pick, "a:9") == "a"
