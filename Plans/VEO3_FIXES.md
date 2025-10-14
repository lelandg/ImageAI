# 🧩 Fixing Veo-3 Integration in ImageAI

## 1. Root Cause
The Veo 3.0 generation completes successfully but fails during video download (`403 Forbidden`).  
This happens because the Gemini API now requires authentication headers when downloading generated files.

---

## 2. Correct Download Method

Use authenticated requests when fetching the video file:

```python
download_url = result["response"]["video"]["uri"]
headers = {
    "Authorization": f"Bearer {self.api_key}",
    "Accept": "application/octet-stream"
}
resp = httpx.get(download_url, headers=headers, follow_redirects=True)
```

If using an API key instead of OAuth:

```python
params = {"key": self.api_key}
resp = httpx.get(download_url, params=params)
```

⚠️ Gemini v1beta prefers `Authorization: Bearer` for `/download` endpoints.

---

## 3. Required API Scopes

Ensure your Google Cloud project has these scopes enabled:

```
https://www.googleapis.com/auth/generative-language.retriever
https://www.googleapis.com/auth/generative-language.video
```

The service account must have `Vertex AI User` or a role with `generativelanguage.files.download` permission.

---

## 4. Update Your `veo_client.py`

Locate around line 435:

```python
resp = self.client.get(download_url)
```

Replace with:

```python
try:
    headers = {"Authorization": f"Bearer {self.api_key}"}
    resp = self.client.get(download_url, headers=headers, follow_redirects=True)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(resp.content)
except httpx.HTTPStatusError as e:
    self.logger.error(f"Download failed ({e.response.status_code}): {e.response.text}")
    raise
```

---

## 5. Optional Enhancements

| Feature | Gemini API Method | Implementation |
|----------|-------------------|----------------|
| Text-to-video | `models/veo-3.0-generate-001:predictLongRunning` | existing |
| Image-to-video | `image_input { mime_type: image/png, data: ... }` | existing |
| Dialogue scenes | `prompt_parts` list with timestamps | new feature |
| Extended durations | `duration: "5s"` (max 60s) | optional |
| Resolution control | `aspect_ratio`, `resolution: "1080p"` | supported |
| Metadata | parse `response["video"]["metadata"]` | logging |

---

## 6. CLI Verification

Run:
```bash
curl -H "Authorization: Bearer $GEMINI_TOKEN"      "https://generativelanguage.googleapis.com/v1beta/files/0f71cg9j32hq:download?alt=media"      -o output.mp4
```

If this works, credentials are valid.

---

## 7. Summary of Code Fixes

| File | Change | Purpose |
|------|---------|---------|
| `core/video/veo_client.py` | Add `Authorization` header on download | Fix 403 error |
| `core/video/veo_client.py` | Catch `HTTPStatusError` and log body | Diagnostics |
| `core/video/veo_client.py` | Support OAuth token refresh | Reliability |
| `gui/video/video_project_tab.py` | Validate video file post-download | UI consistency |
| `.env` | Add `GEMINI_API_KEY` or `GEMINI_OAUTH_TOKEN` | Auth setup |

---

## 8. Example Response Handling

```python
if "video" in operation["response"]:
    video_uri = operation["response"]["video"]["uri"]
    output_path = Path(project_dir) / "output.mp4"
    self.download_video(video_uri, output_path)
else:
    raise RuntimeError("No video URI in operation response.")
```

---

## 9. Testing Plan
1. Generate 2‑second clip from text‑only prompt.  
2. Generate image‑to‑video clip with seed.  
3. Verify `.mp4` saved successfully.  
4. Confirm proper error message on invalid token.

---

✅ **Fix Summary:** Add authenticated download headers and ensure correct API scopes.  
🔗 Based on official Gemini API docs: [https://ai.google.dev/gemini-api/docs/video](https://ai.google.dev/gemini-api/docs/video)
