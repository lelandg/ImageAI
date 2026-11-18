# Testing the LLM layer

ImageAI talks to language models through a small vendored package,
`core/chameleon_llm/`. This page shows how to test it. There are three tiers.
Each tier is one command. Run all commands from the repository root, with the
project's virtual environment active.

## The three tiers

| Tier | What it tests | Cost | Command |
|---|---|---|---|
| Unit and dialog | The package and the dialogs, with fake replies | Free | `python -m pytest -m "not local and not live"` |
| Local servers | A real LM Studio or Ollama on your machine | Free | `python -m pytest -m local -v -rs` |
| Cloud (`live`) | The real OpenAI, Anthropic and Google APIs | A few cents | see below |

Add `-rs` to any run to print the reason for every skipped test.

A bare `python -m pytest` also runs the local tier. When LM Studio is running,
that can load a model into memory. Use the unit-and-dialog command above when
you want only the free, offline tests.

On some Windows machines, running all the GUI test directories in one
process can crash the Python interpreter. Run one directory per process to
avoid it, for example `python -m pytest tests/gui -m "not local and not live"`,
then `python -m pytest tests/video -m "not local and not live"`, and so on.

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
| `LM_API_TOKEN` | local tier | LM Studio's own token variable. Set it only if you turned on authentication in LM Studio. The tests send it with the REST calls and with every completion. |

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
| `LM Studio is not running at <url>` | The connection was refused, or nothing accepted it within 2 seconds. | Start LM Studio and its local server, or set `IMAGEAI_LMSTUDIO_URL`. |
| `no chat model downloaded in LM Studio (...)` | LM Studio lists no models, or only embedding models. | Download a chat model in LM Studio. |
| `load a model in LM Studio first ...` | This LM Studio cannot load models over REST, and none is loaded. | Load a model by hand. |
| `Ollama is not running at <url>` | The connection was refused, or nothing accepted it within 2 seconds. | Start Ollama, or set `IMAGEAI_OLLAMA_URL`. |
| `Ollama has no models installed` | Ollama answers but lists no models. | Run `ollama pull <model>`. |
| `no Ollama model that can complete text is installed ...` | Ollama reported capabilities for every model and none can complete text. | Pull a chat model. |
| `the server did not report whether <model> supports vision` | The server does not say if the model reads images. | Nothing, or use a model whose server reports it. |
| `the server reports that <model> has no vision` | The model is text-only. | Nothing. This is expected. |

## Failures you may see

A skip means there is nothing to test. A failure means a server answered but
did something unexpected, so the test could not do its job. These are the
failures the fixtures raise on purpose.

| Message starts with | Meaning | What to do |
|---|---|---|
| `LM Studio at <url> accepted the connection but the request to <path> failed` (also `Ollama at <url> ...`) | The server accepted the connection, then timed out reading or broke off the reply. The message names the error. | Check that the server is not busy or stuck. Check the URL. |
| `LM Studio at <url> answered HTTP 401` (or 403) | Authentication is on in LM Studio. | Set `LM_API_TOKEN`. |
| `LM Studio at <url> answered HTTP <code>` | The model listing returned an error. | Read the text after the code. |
| `LM Studio at <url> returned a non-JSON body` | Something else may be using the port. | Check the URL. |
| `Something answers at <url> but it is not a recognised LM Studio REST API` | Both listing paths returned 404. | Check the URL. Update LM Studio. |
| `LM Studio answered 200 but the body has no recognisable model list` | The reply has no `models` or `data` array. The message lists the keys it saw. | Report the keys. The test code needs updating. |
| `LM Studio lists models but none is recognised as a chat model` | The `type` values are not the ones the tests know. The message lists them. | Report the values. The test code needs updating. |
| `IMAGEAI_LMSTUDIO_MODEL=... is not a chat model` | The model you named is not a downloaded chat model. This fails even when LM Studio lists no models. | Fix the name. |
| `loading <model> in LM Studio failed` | The load request failed, for example not enough memory. | Free memory, or pick a smaller model with `IMAGEAI_LMSTUDIO_MODEL`. |
| `LM Studio accepted the load ... but reported status` or `... does not show as loaded afterwards` | The load did not take effect. | Check LM Studio's own log. |
| `IMAGEAI_OLLAMA_MODEL=... is not installed in Ollama` | The model you named is not installed. | Fix the name. |
| `Ollama at <url> answered HTTP <code>` or `returned a non-JSON body` | The model listing returned an error. | Read the text after the code. Check the URL. |
| `Ollama answered 200 but the body has no 'models' list` | The reply is not an Ollama model listing. The message lists the keys it saw. | Check the URL. |
| `LM Studio lists N entries but none has a 'key' or 'id' field` | The listing uses field names the tests do not know. The message lists them. | Report the keys. The test code needs updating. |

If LM Studio cannot unload a model the tests loaded, you get a warning, not a
failure. Unload that model by hand.

A test that fails for any other reason is not the same as a skip. A failure against a running
server, or with a configured key, means a real problem. Report it with the
full pytest output.
