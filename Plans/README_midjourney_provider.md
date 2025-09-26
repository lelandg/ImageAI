# Midjourney Provider (REST + Manual Handoff)

**File:** `providers    /midjourney_rest_provider.py`  
**Generated:** 2025-09-22T01:46:21.992165Z

## What this adds
- Safe provider with no Discord automation and no human-verification bypass.
- Two modes: REST proxy or Manual Discord handoff.

## Wire-up steps
1. Copy file into `providers/` and register in provider registry.
2. Add config keys `MIDJOURNEY_REST_BASE_URL`, `MIDJOURNEY_REST_API_KEY`.
3. Update Image tab UI to include provider option and fields from `parameter_schema()`.
4. Manual mode: show slash command copy + open Discord/account buttons.
5. REST mode: enable generate/upscale/variation/describe/video features.
6. Add compliance tooltip about Midjourney ToS and Discord rules.

## Known limits
- No Discord/web automation.
- Proxy support is unofficial, opt-in only.

i found using midjourney with proxy is not allowed in tos. remove proxy/username, and all related features.
  Midjourney will be "manual only", to generate prompts. Not generate images.
  Also, just copy prompt to clipboard, inform user the first time, then open browser as shown in @Sample/