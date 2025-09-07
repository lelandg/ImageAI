# HuggingFace Authentication Guide for Local SD

## Why Authentication is Needed

Some Stable Diffusion models on HuggingFace require authentication:
- **Gated models**: Models that require accepting terms (e.g., Stable Diffusion 2.x)
- **Private models**: Your own private models or organization models
- **Rate limits**: Authenticated users get higher download rate limits

## How to Authenticate

### Method 1: Through the GUI

1. Open ImageAI GUI
2. Go to **Settings** tab
3. Select **local_sd** as the provider
4. In the **HuggingFace Authentication** section:
   - Click **Login to HuggingFace**
   - Paste your token in the field that appears
   - Click **Save Token**

### Method 2: Through the CLI

```bash
# Login to HuggingFace
python download_models.py login

# You'll be prompted for your token (hidden input)
# The token will be saved for future use
```

### Method 3: Using HuggingFace CLI (if installed)

```bash
# Install huggingface-hub if not already installed
pip install huggingface-hub

# Login using the official CLI
huggingface-cli login
```

## Getting Your HuggingFace Token

1. Go to https://huggingface.co/settings/tokens
2. Sign up or log in to your HuggingFace account
3. Click **New token**
4. Give it a name (e.g., "ImageAI")
5. Select **Read** permission (minimum required)
6. Click **Generate token**
7. Copy the token (starts with `hf_`)

## Authentication Status

The GUI shows your authentication status:
- ✓ **Logged in as: [username]** - Successfully authenticated
- ⚠ **Invalid token** - Token exists but is invalid
- **Not logged in** - No authentication (can still download public models)

## Downloading Models

### Public Models (No Auth Required)
Most models work without authentication:
- runwayml/stable-diffusion-v1-5
- CompVis/stable-diffusion-v1-4
- Most community models

### Gated Models (Auth Required)
Some models require accepting terms:
- stabilityai/stable-diffusion-2-1
- stabilityai/stable-diffusion-xl-base-1.0
- Some newer Stability AI models

When downloading a gated model:
1. Ensure you're logged in to HuggingFace
2. Go to the model page on HuggingFace
3. Accept the license terms if prompted
4. Then download through ImageAI

## Troubleshooting

### "401 Unauthorized" Error
- You need to authenticate with HuggingFace
- Run `python download_models.py login` or use the GUI

### "403 Forbidden" Error
- You're authenticated but haven't accepted the model's terms
- Visit the model page on HuggingFace and accept the license

### Token Not Working
- Ensure your token starts with `hf_`
- Check that it has at least **Read** permission
- Try generating a new token

## Security Notes

- Your token is stored locally in `~/.huggingface/token`
- Never share your token or commit it to version control
- The token is used only for downloading models
- You can revoke tokens at any time from HuggingFace settings