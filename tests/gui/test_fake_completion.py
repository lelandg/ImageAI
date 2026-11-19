"""The dialog tests' FakeCompletion rejects what the real completion would (I1, final review)."""
import pytest

from core.chameleon_llm import BadRequestError
from tests.gui.conftest import FakeCompletion

MSGS = [{"role": "user", "content": "hi"}]


def test_accepts_a_routed_call_with_accepted_params():
    fake = FakeCompletion()
    fake(model="anthropic/test-model", messages=MSGS, temperature=0.2,
         max_tokens=10, api_key="k", timeout=5, max_retries=0)
    assert fake.violations == []


def test_wrong_route_raises_and_is_recorded():
    fake = FakeCompletion()
    with pytest.raises(BadRequestError):
        fake(model="claude-test-model", messages=MSGS)
    assert fake.violations and "claude-test-model" in fake.violations[0]


def test_unaccepted_param_raises_and_is_recorded():
    fake = FakeCompletion()
    with pytest.raises(AssertionError) as info:
        fake(model="anthropic/test-model", messages=MSGS, seed=7)
    assert "seed" in str(info.value)
    assert fake.violations


def test_none_valued_params_are_ignored_like_the_real_call():
    fake = FakeCompletion()
    fake(model="anthropic/test-model", messages=MSGS, seed=None)
    assert fake.violations == []


def test_any_name_is_accepted_with_an_api_base():
    fake = FakeCompletion()
    fake(model="lmstudio-community/test-model", messages=MSGS,
         api_base="http://localhost:1234/v1", top_k=40)
    assert fake.violations == []
