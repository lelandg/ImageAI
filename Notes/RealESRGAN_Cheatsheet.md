# Real-ESRGAN Cheatsheet

## Conversation Summary

**Q:** I'm using Real-ESRGAN AI for upscaling. Does it have parameters? Does it do anything else?  
**A:** Real-ESRGAN is focused on upscaling, artifact reduction, and limited restoration. It has CLI parameters like `--model_name`, `--netscale`, `--outscale`, `--tile`, `--face_enhance`, etc. It can also integrate GFPGAN for face restoration and has special models for anime. It does not do unrelated tasks like colorization or style transfer.  

**Q:** Yes → (user asked for models and use cases)  
**A:** Provided table of available models with best uses.  

**Q:** Yes → (user asked for CLI commands)  
**A:** Provided copy-paste commands for each model.  

**Q:** Yes → (user asked for cheatsheet including entire thread)  
**A:** This file.

---

## Real-ESRGAN Models

| Model name | Scale | Training target | Best for |
| RealESRGAN_x4plus | ×4 | General photos, natural images | Default choice. High-quality upscale of most photos |
| RealESRNet_x4plus | ×4 | Artifact reduction | Better at compressed/old JPEGs, less sharp than ESRGAN |
| RealESRGAN_x4plus_anime_6B | ×4 | Anime-style drawings | Anime, manga, line art. Preserves clean edges |
| RealESRGAN_x2plus | ×2 | General photos | Use when only modest upscale needed. Less resource intensive |
| RealESRGAN_x4plus_face | ×4 | Human faces (with GFPGAN) | Upscaling portraits. Integrates face enhancement |
| RealESRGANv2-anime | ×4 | Anime (improved v2 model) | Faster, cleaner anime upscaling, less detail loss |

**Notes**  
- All models allow arbitrary scaling via `--outscale` (e.g. ×1.5, ×6).  
- `--face_enhance` integrates GFPGAN.  
- `RealESRNet` specializes in denoising / artifact removal.  
- Anime models trained on animation datasets for clean lines.  
- Video requires frame-by-frame processing.  

---

## CLI Commands

| Purpose | Command |
| General photos (default) | `python inference_realesrgan.py -n RealESRGAN_x4plus -i input.png --outscale 4 -o output.png` |
| Artifact reduction | `python inference_realesrgan.py -n RealESRNet_x4plus -i input.png --outscale 4 -o output.png` |
| Anime / manga | `python inference_realesrgan.py -n RealESRGAN_x4plus_anime_6B -i input.png --outscale 4 -o output.png` |
| 2× upscale | `python inference_realesrgan.py -n RealESRGAN_x2plus -i input.png --outscale 2 -o output.png` |
| Human faces (GFPGAN) | `python inference_realesrgan.py -n RealESRGAN_x4plus -i input.png --outscale 4 --face_enhance -o output.png` |
| Anime v2 model | `python inference_realesrgan.py -n RealESRGANv2-anime -i input.png --outscale 4 -o output.png` |

---

## Useful Parameters

| Flag | Function |
| --model_name | Selects pretrained model (see table above) |
| --netscale | Base model scale factor (usually 2 or 4) |
| --outscale | Arbitrary output scale (e.g. 1.5, 3, 6) |
| --tile | Tile size to avoid GPU OOM |
| --tile_pad | Padding between tiles to reduce seams |
| --pre_pad | Padding before feeding image, improves borders |
| --face_enhance | Enable GFPGAN face restoration |
| --alpha_upsampler | Upsample transparent PNGs correctly |
| --suffix | Add suffix to output filename |
| --gpu-id | Select GPU device |
| --fp32 / --half | Force 32-bit or half-precision inference |

---

## Capabilities Beyond Basic Upscaling
- Artifact reduction (`RealESRNet`).  
- Face restoration (GFPGAN with `--face_enhance`).  
- Anime/cartoon upscaling (anime models).  
- Alpha channel support (`--alpha_upsampler realesrgan`).  
- Arbitrary scaling factors.  
- Video upscaling via frame-by-frame processing.  

---

## Limitations
- No colorization, depth estimation, or style transfer.  
- No native temporal consistency for video.  
