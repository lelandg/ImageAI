"""LLMHandler.setup_llm hands back the vendored chameleon_llm package."""
import logging

from gui.llm_utils import LLMHandler


def _console_handlers():
    return [h for h in logging.getLogger("chameleon_llm").handlers
            if getattr(h, "_imageai_console", False)]


def test_setup_llm_returns_package_with_completion():
    ok, mod = LLMHandler.setup_llm(enable_console_logging=False)
    assert ok is True
    assert callable(mod.completion)
    assert mod.__name__ == "core.chameleon_llm"


def test_setup_llm_attaches_console_handler_to_chameleon_llm_logger():
    LLMHandler.setup_llm(enable_console_logging=True)
    assert len(_console_handlers()) == 1


def test_setup_llm_does_not_stack_handlers():
    for _ in range(3):
        LLMHandler.setup_llm(enable_console_logging=True)
    assert len(_console_handlers()) == 1


def test_setup_llm_sets_no_attributes_on_package():
    ok, mod = LLMHandler.setup_llm(enable_console_logging=False)
    assert not hasattr(mod, "drop_params")


def test_temporary_litellm_aliases_still_resolve():
    from gui.llm_utils import LiteLLMHandler
    assert LiteLLMHandler is LLMHandler
    assert LLMHandler.setup_litellm is LLMHandler.setup_llm
