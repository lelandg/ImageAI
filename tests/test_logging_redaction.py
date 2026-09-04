"""Guard tests: API keys never reach a log line or a traceback."""
import atexit
import io
import json
import logging

import pytest

import core.paths as paths_mod
from core.logging_config import SecretRedactionFilter, redact_secrets, setup_logging

FAKE_GOOGLE_KEY = "AIzaSyFAKE_KEY_1234567890abcdefghij"
FAKE_OPENAI_KEY = "sk-FAKEKEY1234567890abcdefghijklmnop"
FAKE_HF_KEY = "hf_FAKEtokenABCDEFGHIJKLMNOPQRSTUV"
URL = f"https://example.invalid/v1/models?key={FAKE_GOOGLE_KEY}"


@pytest.fixture
def isolated_paths(tmp_path, monkeypatch):
    """Point DataPaths at tmp_path so setup_logging never touches the real
    user directories. Same pattern as tests/test_paths.py."""
    dest = tmp_path / "settings_root"
    dest.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {"settings": str(dest)}}))
    monkeypatch.setattr(paths_mod, "_INSTANCE", paths_mod.DataPaths(config_path=cfg))
    return dest


@pytest.fixture
def clean_root_logger():
    """Restore the root logger after a setup_logging call."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    yield root
    root.handlers = saved_handlers
    root.setLevel(saved_level)


@pytest.fixture
def capture():
    """A private logger that writes through the filter into a StringIO."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    handler.addFilter(SecretRedactionFilter())
    logger = logging.getLogger("test.redaction")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers = [handler]
    yield logger, stream
    logger.handlers = []


def test_query_key_parameter_is_masked(capture):
    logger, stream = capture
    logger.error("request failed: %s" % URL)
    text = stream.getvalue()
    assert "?key=***" in text
    assert FAKE_GOOGLE_KEY not in text
    assert "AIza" not in text


def test_traceback_with_key_is_masked(capture):
    logger, stream = capture
    try:
        raise RuntimeError(f"403 from {URL}")
    except RuntimeError:
        logger.error("boom", exc_info=True)
    text = stream.getvalue()
    assert "Traceback" in text
    assert "RuntimeError" in text
    assert "AIza" not in text
    assert "key=***" in text


def test_plain_message_is_unchanged(capture):
    logger, stream = capture
    logger.info("Sprite export finished: 12 frames, 64x64 cells")
    assert stream.getvalue() == "INFO - Sprite export finished: 12 frames, 64x64 cells\n"


def test_message_with_args_is_masked(capture):
    logger, stream = capture
    logger.info("%s", URL)
    text = stream.getvalue()
    assert "?key=***" in text
    assert FAKE_GOOGLE_KEY not in text


def test_bare_google_and_openai_keys_are_masked(capture):
    logger, stream = capture
    logger.warning("google=%s openai=%s", FAKE_GOOGLE_KEY, FAKE_OPENAI_KEY)
    text = stream.getvalue()
    assert text == "WARNING - google=*** openai=***\n"


def test_short_prefixes_are_not_masked(capture):
    logger, stream = capture
    logger.info("task-1 sk-1 AIza")
    assert stream.getvalue() == "INFO - task-1 sk-1 AIza\n"


def test_a_later_unfiltered_handler_keeps_exc_info_and_prints_the_masked_traceback():
    """Every handler shares one LogRecord. The filter must not clear
    ``exc_info``: a handler added after the filtered one (pytest ``caplog``,
    a handler attached after ``setup_logging``) still needs the exception,
    and it must print the redacted ``exc_text``, not a fresh render."""
    filtered_stream, later_stream = io.StringIO(), io.StringIO()
    filtered = logging.StreamHandler(filtered_stream)
    filtered.setFormatter(logging.Formatter("%(message)s"))
    filtered.addFilter(SecretRedactionFilter())
    later = logging.StreamHandler(later_stream)
    later.setFormatter(logging.Formatter("%(message)s"))
    seen = []

    class Spy(logging.Filter):
        def filter(self, record):
            seen.append(record.exc_info)
            return True

    later.addFilter(Spy())
    logger = logging.getLogger("test.redaction.shared")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers = [filtered, later]
    try:
        try:
            raise RuntimeError(f"403 from {URL}")
        except RuntimeError:
            logger.error("boom", exc_info=True)
    finally:
        logger.handlers = []

    assert seen and seen[0] is not None and seen[0][0] is RuntimeError
    for text in (filtered_stream.getvalue(), later_stream.getvalue()):
        assert "Traceback" in text and "RuntimeError" in text
        assert "key=***" in text
        assert FAKE_GOOGLE_KEY not in text


def test_bearer_token_and_hf_key_are_masked():
    text = f"Authorization: bearer {FAKE_OPENAI_KEY} hf={FAKE_HF_KEY}"
    assert redact_secrets(text) == "Authorization: Bearer *** hf=***"
    assert redact_secrets("Bearer abc.def-ghi") == "Bearer ***"


def test_sprite_stage_named_key_is_not_masked():
    assert redact_secrets("stage key=done") == "stage key=done"


def test_message_whose_str_raises_does_not_escape_the_logging_call(capture):
    """Handler.handle does not guard filter(). The filter must swallow the
    error so the stdlib path handles the record."""
    logger, stream = capture

    class Bad:
        def __str__(self):
            raise ValueError("no str for you")

    logger.error(Bad())
    logger.info("still alive")
    assert "still alive" in stream.getvalue()


def test_setup_logging_installs_the_filter_on_every_handler(isolated_paths, clean_root_logger):
    root = clean_root_logger
    setup_logging(log_to_file=False)
    assert root.handlers, "setup_logging attached no handler"
    for handler in root.handlers:
        kinds = [type(f) for f in handler.filters]
        assert SecretRedactionFilter in kinds, f"{handler!r} has no redaction filter"


def test_setup_logging_under_pytest_does_not_register_the_log_copy(
    isolated_paths, clean_root_logger, monkeypatch
):
    """The atexit copy overwrites ./imageai_current.log in the repo. A pytest
    process must never register the copy."""
    registered = []
    monkeypatch.setattr(atexit, "register", lambda fn, *a, **k: registered.append(fn))
    log_file = setup_logging(log_to_file=True)
    assert log_file is not None
    assert log_file.parent == isolated_paths / "logs"
    assert registered == []
