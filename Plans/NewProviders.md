# New Providers and Feature Suggestions (Aug 30, 2025)

This document proposes high‑quality image generation providers and concrete feature ideas (including image editing) that fit the current ImageAI app architecture (google and optional OpenAI today). You can copy/paste parts of this into new provider adapters and UI controls.

Selection criteria: High image quality, reliable APIs, clear terms, supports edits (mask/outpaint) where possible, and sustainable availability.


## 1) Provider Shortlist (Top Quality, API‑friendly)

- Google Vertex AI — Imagen 3 family (and ImageFX portal)
  - Capabilities: text‑to‑image, image‑to‑image, masking/inpainting, guidance, safety controls.
  - Notable models: Imagen 3 (Standard, Ultra tiers as available). Google’s public Generative Image API is evolving; Vertex AI SDK provides enterprise‑grade access and quotas.
  - API/docs: https://cloud.google.com/vertex-ai/docs/generative-ai/model-reference/imagen
  - Pros: Excellent photorealism and typography improvements vs older baselines; enterprise reliability and safety.
  - Cons: Requires GCP project/billing; some features are gated to Vertex vs AISTUDIO.

- OpenAI Images API (gpt-image-1 / DALL·E 3 via Images API)
  - Capabilities: text‑to‑image, image edits with masks, variations, size/aspect options.
  - API/docs: https://platform.openai.com/docs/guides/images
  - Pros: High quality, simple API, strong upscalers; good for concept art and photorealistic composites.
  - Cons: Content policy restrictions; edits sometimes stricter.

- Stability AI — Stable Diffusion SDXL / SD3 / 3.5 (Hosted API)
  - Capabilities: txt2img, img2img, inpainting/outpainting, ControlNet‑like guidance, upscaling, face restoration.
  - API/docs: https://api.stability.ai/ and https://platform.stability.ai/
  - Pros: Powerful, fast, flexible; large community ecosystem; granular controls (CFG, steps, seeds, schedulers).
  - Cons: Quality varies by checkpoints/settings; more tuning required.

- Adobe Firefly Services (GenStudio APIs)
  - Capabilities: text‑to‑image, Generative Fill (mask inpaint/outpaint), background removal, photo enhancement, vector fill, upscaling; strong safety/commercial usage posture.
  - API/docs: https://developer.adobe.com/firefly-services/
  - Pros: Enterprise‑friendly licensing, strong inpainting/outpainting (“Generative Fill”) and upscaling.
  - Cons: Requires Adobe developer account and entitlement; rate limits/quotas apply.

- Together AI (as an aggregation layer for top community SOTA like FLUX.1, SDXL variants)
  - Capabilities: txt2img, sometimes img2img/masking depending on model; good route to access Black Forest Labs FLUX models and others with one API.
  - API/docs: https://www.together.ai/docs
  - Pros: One API for multiple best‑in‑class models; competitive pricing.
  - Cons: Feature parity (edits/masks) depends on underlying model.

- Replicate (broad model marketplace: FLUX.1, SDXL, Playground v2.5, custom checkpoints)
  - Capabilities: txt2img, img2img, inpainting, upscalers, control adapters vary by model.
  - API/docs: https://replicate.com/docs
  - Pros: Quick evaluation of many high‑quality models; easy to swap.
  - Cons: Varies widely by model; need to pick vetted, actively maintained runners.

- Leonardo.Ai API
  - Capabilities: txt2img, img2img, inpainting/outpainting, tiling, upscaling, style presets, consistency tools.
  - API/docs: https://docs.leonardo.ai/
  - Pros: Polished platform for production pipelines; strong style controls.
  - Cons: Account gating/quotas; proprietary features.

- AWS Bedrock — Amazon Titan Image Generator (G1, latest)
  - Capabilities: txt2img, inpainting (mask), background removal, redaction, some safety filters.
  - API/docs: https://docs.aws.amazon.com/bedrock/
  - Pros: Enterprise integration, IAM/security, regional controls.
  - Cons: Image quality behind top community SOTA in some cases; regional availability.

Notes on others:
- Midjourney: Excellent quality but no general‑purpose public API for direct integration; primarily Discord‑based and limited partner APIs. Consider out of scope for now.
- Ideogram: Very good text rendering; API availability has been limited/partnered. Track and revisit if public API is stable.
- Black Forest Labs (FLUX.1): High quality; access via Together, Replicate, or enterprise agreements.

Research references to keep tracking:
- LMSYS “LLM” Arena (for general model ecosystem trends): https://lmarena.ai/
- Replicate model explorer leaderboards and community adoption; Papers With Code image synthesis leaderboards.


## 2) Feature Suggestions To Add (Cross‑Provider)

Prioritize features that many providers support so the UI stays consistent. Map to your current main.py (provider switch + GUI tabs).

A) Image Editing & Variations
- Masked inpainting (user loads an image + mask PNG; prompt to fill). Most of the shortlist supports this: Google/Vertex Imagen (mask), OpenAI Images (edit with mask), Stability (inpaint), Adobe Firefly (Generative Fill).
- Outpainting (expand canvas with prompt). Supported by Adobe Firefly, Stability (outpaint workflows), and some community models.
- Image‑to‑Image strength slider (keep composition, change style) with denoise strength.
- Variations/Batch generation with seed control and seed locking.

B) Quality Controls
- Sampler/steps/CFG scale (where relevant; Stability‑style models).
- Resolution/aspect ratios; safe defaults with auto‑upscaling if large.
- High‑fidelity upscaling pass (ESRGAN/CodeFormer where available; Firefly/Adobe, Stability upscalers).

C) Guidance/Consistent Characters
- Reference image(s) as guidance; weight controls.
- Negative prompts (where supported) and safety category toggles.
- Style presets (photoreal, cinematic, watercolor, anime, product render, logo) as reusable presets per provider.

D) Utilities
- Save metadata sidecar (you already do this) with enough fields for reproducibility: provider, model, seed, steps, CFG/strength, guidance images used, mask path, upscale factor.
- Quick re‑roll and “search history” filters by prompt/seed/provider.
- Tiled/Repeatable patterns for textures (where supported).
- Simple crop/mask painter in‑app (optional later) for inpainting.


## 3) Concrete API Notes Per Provider (copy/paste checklists)

Google (Vertex AI Imagen 3)
- Auth: Use Google Cloud credentials; for local dev, Application Default Credentials or explicit JSON key; for hosted, service account.
- Endpoints: Generative image with text prompt, image‑to‑image, and mask.
- Params: prompt, negative_prompt (if available), safety, image_dimensions, guidance.
- Notes: For this repo, add a provider adapter `providers/google_vertex.py` and a new provider key like `provider="google-vertex"` to keep legacy `google` backward‑compatible.

OpenAI Images API
- Auth: OPENAI_API_KEY.
- Endpoints: images/generations, images/edits (with mask), images/variations.
- Params: prompt, image (for edits), mask, size (1024x1024 etc.), n, quality, background removal via edits where applicable.
- Notes: Your main.py already tries to import OpenAI. Add an adapter that calls Images endpoints and normalizes byte/format to your `auto_save_images`.

Stability AI
- Auth: STABILITY_API_KEY.
- Endpoints: v1/generation/... for SDXL/SD3; inpaint, img2img supported. Upscalers available.
- Params: prompt, negative_prompt, steps, sampler, cfg_scale, seed, clip_guidance_preset, denoise, mask, init_image.
- Notes: Surface advanced controls under an “Advanced” accordion in the UI.

Adobe Firefly Services
- Auth: OAuth2 (Adobe Developer Console), org/entitlement needed.
- Endpoints: Text‑to‑image and Generative Fill (mask) endpoints.
- Params: prompt, mask, reference images, size, style presets, content safety settings.
- Notes: Great for commercial/safety‑sensitive users; implement only when credentials available and hide behind feature flag.

Together AI (Flux/SDXL access)
- Auth: TOGETHER_API_KEY.
- Endpoints: Model‑specific; many expose txt2img, some img2img/masks.
- Params: prompt, seed, guidance, steps, image/mask depending on model.
- Notes: Provide a curated whitelist of models known for quality (e.g., flux‑schnell for drafts, flux‑dev for quality, SDXL high‑quality runners).

Replicate
- Auth: REPLICATE_API_TOKEN.
- Endpoints: Model‑specific; pass input dict; poll for result URLs.
- Params: Vary widely; wrap via adapters per curated model (e.g., FLUX.1, SDXL inpainting, upscale runners).
- Notes: Cache model/version IDs in settings with human names; handle async polling in your worker thread.

Leonardo.Ai
- Auth: LEONARDO_API_KEY.
- Endpoints: Generations, Edits/Inpaint, Upscale.
- Params: prompt, image/mask, style, guidance, seed, tiling.
- Notes: Good for style presets and batch variations.

AWS Bedrock — Titan Image Generator
- Auth: AWS credentials/IAM; Bedrock runtime client.
- Endpoints: InvokeModel for Titan Image; supports mask inpaint, background removal.
- Params: prompt, mask, cfg, steps, dimensions, seed.
- Notes: Enterprise route; expose in settings if AWS creds detected.


## 4) Implementation Blueprint For This Repo

Minimal architecture to add providers without touching core UI too much:

- Provider enum/selector
  - Today: PROVIDER_NAME = "google" with special‑case logic. Extract into a simple provider registry dict: { name: adapter }.

- Adapter interface (pseudo‑code)
  - def make_client(api_key) -> object
  - def generate_text_to_image(client, model, prompt, options) -> list[bytes]
  - def edit_image(client, model, prompt, image: bytes, mask: Optional[bytes], options) -> list[bytes]
  - def image_to_image(client, model, prompt, init_image: bytes, strength: float, options) -> list[bytes]
  - def upscale(client, image: bytes, factor: int, options) -> bytes (optional)

- UI additions
  - Tabs or toggles in “Generate” panel: [Text-to-Image] [Image-to-Image] [Edit (Mask)] [Upscale]. Only enable if provider supports it.
  - Controls: seed, batch size, size/aspect ratio, guidance/CFG, steps (when applicable), negative prompt.
  - File pickers for init image and mask; preview thumbnails.

- Metadata
  - Extend sidecar to save: { provider, model, mode: "txt2img|img2img|edit|upscale", seed, steps, cfg, strength, negative_prompt, width, height, references, timestamp }.

- Safety/filters
  - Add a global “Safe Mode” toggle mapping to provider flags (OpenAI policies, Google safety settings, Adobe content filters).

- Error handling
  - Normalize provider errors to user‑friendly messages; include provider response id for support tickets.


## 5) Curated Model Picks (Starter Set)

- Google Vertex Imagen 3: "imagen-3.0" (choose Standard vs higher tiers per availability)
- OpenAI Images: "gpt-image-1" (edits, variations)
- Stability: "stable-diffusion-xl-1024-v1-0" for quality; "sd3"/"sd3.5" where available for advanced users
- Together AI: "black-forest-labs/FLUX.1-dev" for quality; "FLUX.1-schnell" for drafts; curated SDXL inpainting runners
- Replicate: Pin exact versions for FLUX.1 dev and SDXL inpainting; add an "4x-UltraSharp"/ESRGAN upscale runner
- Adobe Firefly: Text to Image, Generative Fill (no public model name string; expose as provider features)
- Leonardo: "Leonardo Vision XL" or latest recommended flagship in docs
- AWS Bedrock: "amazon.titan-image-generator" latest


## 6) Phased Rollout Plan

Phase 1 (Low Risk, quick wins)
- Add OpenAI Images edits/variations (you already conditionally import OpenAI) and Stability txt2img/inpaint.
- UI: Add mode switch (txt2img/img2img/edit). Add seed and batch controls. Save metadata.

Phase 2
- Add Google Vertex Imagen 3 (separate from current Google GenAI image preview model) with mask editing.
- Add Replicate or Together AI with a curated, locked list of models (FLUX.1 dev, SDXL inpaint, an upscaler).

Phase 3
- Add Adobe Firefly and Leonardo for commercial workflows. Add upscale pass option.
- Optional: In‑app simple mask painter.


## 7) Configuration Keys (Environment/Settings)

- OPENAI_API_KEY
- STABILITY_API_KEY
- GOOGLE_APPLICATION_CREDENTIALS or Vertex ADC
- TOGETHER_API_KEY
- REPLICATE_API_TOKEN
- LEONARDO_API_KEY
- AWS credentials (for Bedrock): AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
- ADOBE credentials (OAuth flow / service integration)


## 8) Security/Compliance Notes

- Respect each provider’s content policy; surface a Safe Mode toggle.
- Do not log image bytes or prompts unless user opts in; scrub PII in telemetry.
- Cache only final images and minimal metadata, as you do via sidecars.


## 9) Useful Links (Quick Access)

- Google Vertex Imagen: https://cloud.google.com/vertex-ai/docs/generative-ai/model-reference/imagen
- OpenAI Images: https://platform.openai.com/docs/guides/images
- Stability AI: https://platform.stability.ai/
- Adobe Firefly Services: https://developer.adobe.com/firefly-services/
- Together AI: https://www.together.ai/docs
- Replicate: https://replicate.com/docs
- Leonardo AI: https://docs.leonardo.ai/
- AWS Bedrock: https://docs.aws.amazon.com/bedrock/
- LMSYS Arena (general ecosystem): https://lmarena.ai/


---
If you want me to implement any subset, reply with the providers/modes you want first (e.g., “Add Stability txt2img + inpaint with seed/CFG controls”, or “Add OpenAI Images edits/variations”), and I’ll wire up the provider adapter, UI toggles, and metadata fields accordingly.