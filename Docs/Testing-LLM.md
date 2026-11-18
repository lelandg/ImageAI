# Testing the LLM layer

ImageAI talks to language models through a small vendored package,
`core/chameleon_llm/`. This page shows how to test it. There are three tiers.
Each tier is one command. Run all commands from the repository root, with the
project's virtual environment active.

## The three tiers

| Tier | What it tests | Cost | Command |
|---|---|---|---|
| Unit and dialog | The package and the dialogs, with fake replies | Free | `python -m pytest` |
| Local servers | A real LM Studio or Ollama on your machine | Free | `python -m pytest -m local -v -rs` |
| Cloud (`live`) | The real OpenAI, Anthropic and Google APIs | A few cents | see below |

Add `-rs` to any run to print the reason for every skipped test.

### Running the cloud tier

The cloud tier spends real money. It stays off unless you turn it on.

PowerShell:

```powershell
$env:IMAGEAI_LIVE_TESTS = "1"
python -m pytest -m live -v -rs
Remove-Item Env:IMAGEAI_LIVE_TESTS
```

bash:

```bash
IMAGEAI_LIVE_TESTS=1 python -m pytest -m live -v -rs
```

The tests are in `tests/test_live_llm_params.py`. Expect a few cents of API
cost for a full run. Each provider's tests skip when that provider has no key.

## Environment variables

All of these are optional.

| Variable | Used by | Meaning |
|---|---|---|
| `IMAGEAI_LIVE_TESTS` | cloud tier | Set to `1` to allow paid API calls. Any other value skips them. |
| `IMAGEAI_LMSTUDIO_URL` | local tier | LM Studio address. Default `http://localhost:1234`. |
| `IMAGEAI_LMSTUDIO_MODEL` | local tier | LM Studio model key to test. Default: a loaded model, else the smallest downloaded chat model. |
| `IMAGEAI_OLLAMA_URL` | local tier | Ollama address. Default `http://localhost:11434`. |
| `IMAGEAI_OLLAMA_MODEL` | local tier | Ollama model name to test. Default: the smallest installed model that can complete text. |
| `LM_API_TOKEN` | local tier | LM Studio's own token variable. Set it only if you turned on authentication in LM Studio. |

## Where API keys come from

The cloud tier reads keys through the app's configuration
(`config.get_api_key()`). It never reads keys from the command line or from
the environment of the test command. To give a test a key, add the key in the
app's Settings first. Keys live in your user folder, never in the repository.

Vertex AI tests use your Google Cloud login, not a key. Run
`gcloud auth application-default login` once to set it up.

## Local tier details

You need LM Studio, Ollama, or both. Start the server and download a model
yourself. The tests never download or delete a model.

- **LM Studio.** If no chat model is loaded, the test loads the smallest
  downloaded one over LM Studio's REST API. When the tests finish, it unloads
  only a model it loaded itself. A model you had already loaded is left alone.
  Loading needs a recent LM Studio that offers `/api/v1/models/load`. On an
  older version, load a model by hand before you run the tests.
- **Ollama.** The tests use the smallest installed model. They do not load or
  unload anything.
- The image test runs only when the server says the model can read images.

## What each skip message means

| Message | Meaning | What to do |
|---|---|---|
| `live API tests disabled (set IMAGEAI_LIVE_TESTS=1)` | The cloud tier is off. | Nothing, unless you want to spend money. See the commands above. |
| `no anthropic API key configured` (also `openai`, `google`) | That provider has no key in the app's configuration. | Add the key in Settings. |
| `no Google Cloud application-default credentials ...` | The Vertex tests found no Google Cloud login. | Run `gcloud auth application-default login`. |
| `no curated <provider> model fits this test` | The built-in model list has no model of the kind the test needs. | Report it. The test needs updating. |
| `LM Studio is not running at <url>` | Nothing answered within 2 seconds. | Start LM Studio and its local server, or set `IMAGEAI_LMSTUDIO_URL`. |
| `LM Studio at <url> requires a token: set LM_API_TOKEN` | Authentication is on in LM Studio. | Set `LM_API_TOKEN`. |
| `LM Studio at <url> has no REST model listing ...` | The server answered 404 on both model-listing paths. | Check the URL. Update LM Studio. |
| `no chat model downloaded in LM Studio` | LM Studio has only embedding models, or none. | Download a chat model in LM Studio. |
| `load a model in LM Studio first ...` | This LM Studio cannot load models over REST, and none is loaded. | Load a model by hand. |
| `could not load <model> in LM Studio ...` | The load request failed, for example not enough memory. | Free memory, or choose a smaller model with `IMAGEAI_LMSTUDIO_MODEL`. |
| `IMAGEAI_LMSTUDIO_MODEL=... is not a chat model in LM Studio` | The model you named is not downloaded, or is not a chat model. | Fix the name. |
| `Ollama is not running at <url>, or has no models installed` | Nothing answered, or the server has no models. | Start Ollama and run `ollama pull <model>`, or set `IMAGEAI_OLLAMA_URL`. |
| `IMAGEAI_OLLAMA_MODEL=... is not installed in Ollama` | The model you named is not installed. | Fix the name. |
| `no Ollama model that can complete text is installed` | Every installed model is, for example, an embedding model. | Pull a chat model. |
| `model <name> does not report vision support` | The model cannot read images. | Nothing. This is expected for text-only models. |

A test that fails is not the same as a skip. A failure against a running
server, or with a configured key, means a real problem. Report it with the
full pytest output.
