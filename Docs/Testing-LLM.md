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
| `IMAGEAI_LMSTUDIO_MODEL` | local tier | LM Studio model key to test, or the id of one loaded instance of a model (for example `name:2`). A model key uses that model's first loaded instance; an instance id uses that instance. Default: a loaded model, else the smallest downloaded chat model. |
| `IMAGEAI_OLLAMA_URL` | local tier | Ollama address. Default `http://localhost:11434`. |
| `IMAGEAI_OLLAMA_MODEL` | local tier | Ollama model name to test. Default: the smallest installed model that can complete text. |
| `LM_API_TOKEN` | local tier | LM Studio's own token variable. Set it only if you turned on authentication in LM Studio. The tests send it with the REST calls and with every completion. |

## Where API keys come from

The cloud tier reads keys through the app's configuration
(`config.get_api_key()`). It never reads keys from the command line or from
the environment of the test command. Keys live in your user folder, never in
the repository.

**The cloud tier finds a key only when it is stored in your operating
system's keyring.** Every test run redirects `config.json` to an empty
temporary folder (`tests/conftest.py::_sandboxed_user_data_dir`), so that a
test can never overwrite your real settings. A key that exists only in
`config.json` is therefore invisible to the tests, and that provider's tests
skip with `no <provider> API key configured`. Settings stores a key in the
keyring whenever the `keyring` package is installed and the system has a
keyring service. It falls back to `config.json` only when the keyring is not
available.

To give the cloud tier a key:

1. Check whether the key is already in the keyring. This prints `in keyring`
   or `NOT in keyring`, never the key. Replace `openai` with `anthropic` or
   `google` for the other providers. The command is the same in PowerShell
   and bash:

   ```
   python -c "import keyring; print('in keyring' if keyring.get_password('ImageAI', 'openai_api_key') else 'NOT in keyring')"
   ```

2. If it prints `in keyring`, you are done.
3. If it prints `NOT in keyring`, or fails with `No module named 'keyring'`,
   install the requirements into the virtual environment
   (`python -m pip install -r requirements.txt`), start the app, open
   Settings, type the key in again and save. Then run the command from step 1
   again. It must print `in keyring`.
4. If step 1 still prints `NOT in keyring`, your system has no keyring service
   (this can happen on a Linux machine without a desktop session). The cloud
   tier cannot read your keys on that machine.

The Google key from step 1 is used for the `gemini/` tests only. It is always
the stored API key, never a Google Cloud access token.

Vertex AI tests use your Google Cloud login, not a key. Run
`gcloud auth application-default login` once to set it up.

## What the unit tier proves about credentials

These rules are tested offline, with a recorder in place of the real client.
If you change routing or key handling, these are the tests to read first.

| Rule | Test file |
|---|---|
| A provider's key is not sent when the model id carries another provider's route prefix (`ollama/...` under Google, `anthropic/...` under OpenAI). | `tests/test_llm_params.py` |
| With Google Cloud login, no call sends the access token as a Gemini API key; Gemini models use `vertex_ai/` with the saved project, also when the model id already says `gemini/`. | `tests/video/test_google_cloud_auth_routes.py`, `tests/video/test_style_analyzer_routes.py`, `tests/test_styles_analyzer_google_auth.py`, `tests/test_llm_params.py` |
| The Google key is passed with each request and never written to `GEMINI_API_KEY`; two objects with different Google settings do not change each other's route, in either creation order. | `tests/video/test_google_cloud_auth_routes.py` |
| In API-key mode a missing Google key stays on `gemini/` and is never sent to Vertex; a key stored in Settings is found through `get_api_key`; Google Cloud login never looks a key up. | `tests/video/test_google_cloud_auth_routes.py`, `tests/gui/test_llm_dialogs_workspace.py` |
| A base URL is logged without user info, query or fragment, at every log level. | `tests/chameleon_llm/test_cleartext_warning.py` |

Tests that need the saved Settings replace `core.llm_params._saved_settings`.
Unpatched, it reads the sandboxed, empty `config.json`, which means API-key
mode and no project.

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
- **`top_k`.** LM Studio receives `top_k`. Ollama does not: its
  OpenAI-compatible endpoint has no such field, so the package drops it on the
  `ollama/` routes and logs a WARNING that names it.

## What each skip message means

| Message | Meaning | What to do |
|---|---|---|
| `live API tests disabled (set IMAGEAI_LIVE_TESTS=1)` | The cloud tier is off. | Nothing, unless you want to spend money. See the commands above. |
| `no anthropic API key configured` (also `openai`, `google`) | That provider has no key in the keyring. A key saved only in `config.json` does not count. | Follow "Where API keys come from" above. |
| `no Google Cloud application-default credentials ...` | The Vertex tests found no Google Cloud login. | Run `gcloud auth application-default login`. |
| `no curated <provider> model fits this test` | The built-in model list has no model of the kind the test needs. | Report it. The test needs updating. |
| `LM Studio is not running at <url>` | The connection was refused, or nothing accepted it within 2 seconds. No other connection error skips. | Start LM Studio and its local server, or set `IMAGEAI_LMSTUDIO_URL`. |
| `no chat model downloaded in LM Studio (...)` | LM Studio lists no models, or only embedding models. | Download a chat model in LM Studio. |
| `load a model in LM Studio first ...` | This LM Studio cannot load models over REST, and none is loaded. | Load a model by hand. |
| `Ollama is not running at <url>` | The connection was refused, or nothing accepted it within 2 seconds. No other connection error skips. | Start Ollama, or set `IMAGEAI_OLLAMA_URL`. |
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
| `LM Studio at <url> accepted the connection but the request to <path> failed` (also `Ollama at <url> ...`) | The request failed for a reason other than a refused connection or a connect timeout. Usually the server accepted the connection, then timed out reading, reset it or closed it before replying. A TLS error, a proxy error and a host name that does not resolve also end here. The message names the error. | Check that the server is not busy or stuck. Check the URL. |
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
