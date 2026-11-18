"""Local-tier tests through the `lm_studio/` route against a real LM Studio server.

Run: python -m pytest -m local -v   (skips when the server does not answer)
"""

import pytest

from core import chameleon_llm
from core.llm_parsing import LLMResponseParser

pytestmark = pytest.mark.local

PREFIX = "lm_studio/"
TIMEOUT = 120


@pytest.fixture
def server(lmstudio):
    return lmstudio


def _ask(server, messages, **params):
    return chameleon_llm.completion(
        model=f"{PREFIX}{server.model}", api_base=server.base_url,
        messages=messages, timeout=TIMEOUT, **params)


def test_text_reply(server):
    r = _ask(server, [{"role": "user", "content": "Reply with the single word: pong"}],
             max_tokens=20, temperature=0)
    assert r.choices[0].message.content.strip() != ""
    assert r.choices[0].finish_reason in ("stop", "length")


def test_json_mode(server):
    r = _ask(server,
             [{"role": "user",
               "content": 'Reply with only this JSON object: {"ok": true}'}],
             max_tokens=100, temperature=0,
             response_format={"type": "json_object"})
    parsed = LLMResponseParser.parse_json_response(
        r.choices[0].message.content, dict)
    assert isinstance(parsed, dict), r.choices[0].message.content


def test_image_input(server, red_png_data_url):
    if server.vision is None:
        pytest.skip(f"the server did not report whether {server.model} supports vision")
    if not server.vision:
        pytest.skip(f"the server reports that {server.model} has no vision")
    r = _ask(server,
             [{"role": "user", "content": [
                 {"type": "text", "text": "What colour is this image? One word."},
                 {"type": "image_url", "image_url": {"url": red_png_data_url}}]}],
             max_tokens=40, temperature=0)
    assert r.choices[0].message.content.strip() != ""
