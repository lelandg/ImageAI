# Implementation Plan: Google Cloud Authentication

## 1. Overview

This plan outlines the steps to add support for Google Cloud authentication (via Application Default Credentials) as an alternative to the existing API key method for Google image generation. This allows users to authenticate using their Google Cloud account (`gcloud auth application-default login`) instead of managing API keys.

The OpenAI provider will remain unchanged.

## 2. Prerequisites for User

The `README.md` must be updated to inform users that for the "Google Cloud Account" method, they must first:
1.  Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install).
2.  Authenticate by running the command: `gcloud auth application-default login`.

## 3. Phase 1: Backend & Core Logic Refactoring

### 3.1. Update Dependencies
-   Modify `requirements.txt` to add the Google Cloud AI Platform library:
    ```
    google-cloud-aiplatform
    ```

### 3.2. Abstract Generation Logic
-   In `main.py`, create a new helper function or class to manage which client to use.
-   The goal is to have a single point of entry for generation that can handle both auth methods.

### 3.3. Refactor Client Initialization
-   Modify `make_client()` to accept an `auth_mode` parameter (`'api-key'` or `'gcloud'`).
-   If `auth_mode` is `'api-key'`, it should return the existing `genai.Client`.
-   If `auth_mode` is `'gcloud'`, it should initialize and return a client from the `google.cloud.aiplatform.gapic.PredictionServiceClient`. It will also require initializing the SDK with `aiplatform.init()`.

### 3.4. Refactor Generation Call
-   Modify `generate_any()` to handle the two different clients.
-   The method signature for `google-cloud-aiplatform` is different from `google-genai`. The function must abstract this, calling the correct method on the client object it receives.
-   **Crucially, it must return the results in the same `(texts, image_bytes_list)` tuple format** that the rest of the application expects.

## 4. Phase 2: CLI Integration

### 4.1. Add CLI Argument
-   In `main.py`, add a new argument to the `argparse` setup:
    ```python
    parser.add_argument("--auth-mode", choices=["api-key", "gcloud"], default="api-key", help="Google authentication mode to use.")
    ```

### 4.2. Update CLI Logic
-   In `run_cli()`, read the `args.auth_mode`.
-   Pass the `auth_mode` to the refactored client and generation functions.
-   If `auth_mode` is `'gcloud'`, the `--api-key` and `--api-key-file` arguments should be ignored. Add logic to print a warning if they are used together.

## 5. Phase 3: GUI Integration

### 5.1. Update Settings Tab UI
-   In `_init_settings()`, add a `QComboBox` or `QButtonGroup` to allow the user to select "Authentication Mode":
    -   `API Key` (default)
    -   `Google Cloud Account`
-   The visibility/enabled state of the API key input field (`self.api_key_edit`) should depend on this selection.
    -   If "API Key" is selected, the key input is enabled.
    -   If "Google Cloud Account" is selected, the key input is disabled.
-   Add a non-editable `QLabel` to display the detected Google Cloud Project ID when "Google Cloud Account" is selected. This provides user feedback. You can get this by running `gcloud config get-value project`.
-   Add a "Check Status" button that runs `gcloud auth list` to help the user verify their login.

### 5.2. Persist UI State
-   When the authentication mode is changed in the GUI, save the choice to `config.json` (e.g., `{"auth_mode": "gcloud"}`).
-   Load this value when the application starts to set the initial state of the Settings tab.

### 5.3. Update GUI Generation Logic
-   In `_on_generate()`, read the configured `auth_mode` from the settings.
-   Pass this `auth_mode` to the `GenWorker` thread.
-   The `GenWorker` must use the `auth_mode` to initialize the correct client before performing the generation task.

## 6. Phase 4: Documentation

-   Update `README.md` with the following:
    -   A new section explaining the two authentication modes for Google.
    -   Clear instructions for the new "Google Cloud Account" mode, including the `gcloud` CLI installation and login command as mentioned in the "Prerequisites" section of this plan.
    -   Documentation for the new `--auth-mode` CLI flag.
