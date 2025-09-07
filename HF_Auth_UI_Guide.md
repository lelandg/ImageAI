# HuggingFace Authentication UI Guide

## What You'll See in Settings → local_sd

### HuggingFace Authentication Section

```
┌─ HuggingFace Authentication ─────────────────────────┐
│                                                       │
│ ⚠ Not logged in - Authentication required for some   │
│    models                                             │
│                                                       │
│ Token: [____________________________] [Save Token]   │
│                                                       │
│ Don't have a token? [Get Token from HuggingFace]     │
│                                                       │
│ ℹ️ Some models (like SD 2.1) require authentication. │
│    Create a free READ token on HuggingFace.          │
│                                                       │
└───────────────────────────────────────────────────────┘
```

### Key Features

1. **Get Token Button** (NEW!)
   - Styled as a blue link
   - Opens https://huggingface.co/settings/tokens in your browser
   - Shows pointer cursor on hover
   - Located right below the token input

2. **Clear Status Messages**
   - ⚠ Not logged in - Shows when no token is saved
   - ✓ Logged in as: [username] - Shows when authenticated (green, bold)
   - ⚠ Invalid token - Shows when token is expired/wrong

3. **Simple Flow**
   - Click "Get Token from HuggingFace" → Opens token page
   - Create token on HuggingFace
   - Paste token in field
   - Click "Save Token"
   - Done!

### When Logged In

```
┌─ HuggingFace Authentication ─────────────────────────┐
│                                                       │
│ ✓ Logged in as: YourUsername                         │
│                                                       │
│ [Logout]                                              │
│                                                       │
│ ℹ️ Some models (like SD 2.1) require authentication. │
│    Create a free READ token on HuggingFace.          │
│                                                       │
└───────────────────────────────────────────────────────┘
```

- Token input is hidden when logged in
- Logout button appears
- Can download gated models

## Quick Steps

1. **Click** "Get Token from HuggingFace" button
2. **Sign up/Login** to HuggingFace (free)
3. **Create** a new READ token
4. **Copy** the token (starts with hf_)
5. **Paste** in the Token field
6. **Click** "Save Token"
7. **Success!** You can now download all models

## Models That Need Authentication

- stabilityai/stable-diffusion-2-1
- stabilityai/stable-diffusion-xl-base-1.0
- Most Stability AI models
- Private/organization models

## Troubleshooting

- **401 Error**: You need to authenticate
- **403 Error**: Accept the model's license on HuggingFace first
- **Browser won't open**: Copy link manually: https://huggingface.co/settings/tokens