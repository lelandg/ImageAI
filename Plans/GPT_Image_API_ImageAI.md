# GPT Image API Integration Guide for ImageAI

## Model and Capabilities
- **Model**: `gpt-image-1`
- **Supported Sizes**: `1024x1024`, `1536x1024`, `1024x1536`
- **Transparency**: PNG or WEBP only (`background="transparent"` or include "transparent background" in prompt)
- **Quality**: `low | medium | high | auto`
- **Compression**: `output_compression` for JPEG/WEBP (0–100)
- **Edits**: Supported with optional mask (mask must have alpha)

---

## Provider Contract (ImageAI)

### `providers/openai.py`

```python
from openai import OpenAI
import base64, io
from PIL import Image

CLIENT = OpenAI()

def generate_image(prompt, out_sizes, transparent=False, quality="high", seed=None, fmt="png"):
    base_size = "1024x1024"  # choose closest supported size
    if transparent and fmt.lower() == "jpeg":
        fmt = "png"
    params = {
        "model": "gpt-image-1",
        "prompt": prompt if not transparent else f"{prompt}\nTransparent background.",
        "size": base_size,
        "quality": quality,
        "output_format": fmt.lower(),
    }
    if transparent:
        params["background"] = "transparent"
    if seed:
        params["seed"] = int(seed)
    resp = CLIENT.images.generate(**params)
    img = Image.open(io.BytesIO(base64.b64decode(resp.data[0].b64_json))).convert("RGBA")
    results = []
    for w,h in out_sizes:
        resized = img.resize((w,h), Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format=fmt.upper())
        results.append(((w,h), buf.getvalue()))
    return results
```

---

### `providers/base.py`
```python
supports = {
  "exact_export_sizes": True,
  "transparent_output": True,
  "seed": True,
  "edits": True,
  "masking": True
}
```

---

### CLI / GUI Additions
- **Flags**: `--transparent`, `--size`, `--fmt`, `--quality`, `--seed`
- **GUI Options**: Transparent checkbox, export sizes, file format dropdown
- **Disable JPEG when transparent is selected**

---

## Image Edits and Masking
```python
def edit_image(prompt, image_bytes, mask_png=None, size="1024x1024", fmt="png"):
    args = dict(model="gpt-image-1", prompt=prompt, size=size, output_format=fmt)
    if mask_png:
        args["image"] = [io.BytesIO(image_bytes)]
        args["mask"] = io.BytesIO(mask_png)
        resp = CLIENT.images.edit(**args)
    else:
        args["image"] = [io.BytesIO(image_bytes)]
        resp = CLIENT.images.edit(**args)
    return base64.b64decode(resp.data[0].b64_json)
```

---

## What You Might Be Missing
1. Transparent output flag end-to-end
2. Format guards (force PNG/WEBP if transparent)
3. Seed handling for scene continuity
4. ZIP export with deterministic filenames
5. Contact sheet generator for QA
6. Mask conversion helper (BW → RGBA alpha)

---

## API Call Summary
```python
client.images.generate(
  model="gpt-image-1",
  prompt="...",
  size="1024x1024",
  quality="high",
  background="transparent",
  output_format="png",
  output_compression=90,
  seed=12345
)
```

---

## Notes
- Square images are faster and cheaper
- Exact pixel exports require your post-resize step
- Use PIL `LANCZOS` for scaling
