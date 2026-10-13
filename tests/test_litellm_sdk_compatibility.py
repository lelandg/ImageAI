"""Exercise real LiteLLM/OpenAI SDK calls without network or user credentials."""
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("content", ["fixture completion", ""])
def test_direct_completion_preserves_response_shape(content):
    # Isolate the fixture tokenizer and SDK globals from the rest of the suite.
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}}
    env["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    result = subprocess.run(
        [sys.executable, "-c",
         "import runpy,sys; runpy.run_path(sys.argv[1], run_name='__main__')",
         str(Path(__file__).resolve()), content],
        cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, timeout=45, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _sdk_smoke(content):
    import json
    import socket
    from unittest.mock import patch

    import httpx
    import tiktoken
    from openai import OpenAI

    from core.llm_params import LLMParams, build_completion_kwargs

    def no_network(*args, **kwargs):
        raise AssertionError("SDK compatibility test must not use the network")

    # Token counts are not under test. A deterministic tokenizer avoids a
    # download of OpenAI's tokenizer data on a fresh offline machine.
    encoding = tiktoken.Encoding(
        name="offline-fixture", pat_str=r"(?s).",
        mergeable_ranks={bytes([i]): i for i in range(256)}, special_tokens={},
    )
    with (patch.object(socket.socket, "connect", no_network),
          patch.object(socket, "getaddrinfo", no_network),
          patch.object(tiktoken, "get_encoding", return_value=encoding)):
        import litellm

        received = []

        def reply(request):
            received.append(json.loads(request.content))
            return httpx.Response(200, json={
                "id": "chatcmpl-offline-fixture", "object": "chat.completion",
                "created": 0, "model": "gpt-4o",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": content}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            })

        messages = [{"role": "user", "content": "offline fixture"}]
        kwargs = build_completion_kwargs(
            "openai", "gpt-4o", messages,
            LLMParams(temperature=0.4, max_tokens=20),
        )
        with (httpx.Client(transport=httpx.MockTransport(reply)) as http_client,
              OpenAI(api_key="offline-fixture", base_url="https://sdk-fixture.invalid/v1",
                     http_client=http_client) as client):
            response = litellm.completion(**kwargs, client=client, api_key="offline-fixture")

        assert len(received) == 1
        assert received[0]["messages"] == messages
        assert received[0]["temperature"] == 0.4
        assert response.choices[0].message.content == content
        assert response.choices[0].finish_reason == "stop"


if __name__ == "__main__":
    _sdk_smoke(sys.argv[-1])
