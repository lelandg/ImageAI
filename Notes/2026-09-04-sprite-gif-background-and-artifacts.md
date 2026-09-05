# Sprite GIF background proposal and rock_3 artifact diagnosis

Investigated: 2026-09-04 18:05 (local environment clock).

Scope: inspect current capability and propose implementation; diagnose saved artifacts. No application code, project settings, source images, frames, or exports changed. No generation API calls, commits, or pushes.

## Solid background GIF

The Sprite exporter currently always writes a transparent GIF. `core/sprite/exporters/gif.py:88` has no background argument; line 111 unconditionally sets transparency index 255. `gui/sprite/export_dialog.py:146` does not supply a background option. Both actual rock_3 GIFs decode with transparency index 255 (HD 256x256, pixel 64x64, nine frames each).

Proposed implementation:

1. Add **GIF background: Transparent / Solid color** to Export, with a color picker and validated hex field. Remember the choice; retain Transparent as the default.
2. Pass optional RGB background through `ExportRequest`, `format_gif()`, and `export_gif()`. Also cover the separate `core/sprite/exporters/engine_presets.py` GIF writer.
3. For solid output, alpha-composite source RGBA frames onto the chosen color **before** palette quantization. Reserve an exact palette entry for that background and omit the GIF transparency flag. Preserve aspect ratio, canvas size, timing, direction, repetition, and disposal behavior.
4. Record mode/color in the JSON sidecar and export log. Leave the editable transparent source frames untouched.
5. Extend existing exporter, GUI export, and engine-preset tests. Decode every exported frame to verify opacity, exact background color, soft-edge compositing within palette precision, timing, and absence of trails; preserve transparent-export regressions and test remembered settings/invalid colors.

Relevant tests: `tests/sprite/test_exporters.py`, `tests/sprite/gui/test_export_dialog.py`, `tests/sprite/test_engine_presets.py`.

## Latest project and visible artifacts

Latest modified Sprite project under the configured G: sprite directory:

`G:\ImageAI\Images\sprites\rock_3_20260903_100335\project.iasprite.json`

Action: `rock_out`, ID `92f1f6989035454080287cc5e8383732`. Inspected its original character, generated plate, extracted video frames, keyed/cleanup/alpha/stabilized/profile PNGs, GIFs, sidecars, and `imageai_current.log`.

### Detached black marks come from the source artwork

The black strokes around the guitar are visible in `source/character.png`, before plate or video generation. They remain in `source/plate.png` and extracted frame `0001.png`. They are decorative motion marks in the supplied artwork, not marks invented by GIF encoding. They are particularly conspicuous in extracted frames 1 and 9; frame 7 lacks those large strokes. The video changes their appearance across poses, which makes them look like intermittent artifacts.

Chroma removal retains those dark pixels as foreground. Saved cleanup settings are `despeckle_px=0`, `choke_px=0`, `feather_px=0`; keyed and cleanup masks retain the same detached-pixel counts. With 8-connected components at alpha >=128, excluding the largest component, frame 1 has 2,299 detached pixels and frame 9 has 777 before downscaling. These counts include both unwanted marks and potentially legitimate disconnected detail; they are not an automatic deletion mask.

A deterministic, in-memory call to the actual `key_frame()` function on extracted frame 1 reproduced 1,193 visible pixels in the motion-mark region (x=748..847, y=140..254). An assertion that this region was empty failed as expected: `FAIL (expected): stray marks remain in keyed frame`.

Best remedy for future generation: clean the motion marks out of the character reference before building the plate, and request no motion lines, floating symbols, particles, or detached strokes. Prompt wording alone cannot guarantee their absence. For existing frames, selective mask/retouch cleanup is more precise than aggressively eroding the whole character.

### Edge processing amplifies colored flecks

The plate generator returned muted green (`#77BB5F` measured in the plate sidecar) despite a requested `#00FF00`. Keying correctly auto-sampled the clip as `#75BA5D`, recorded in `stages/<action>/key/key.json`. Color drift alone therefore does not explain the black marks.

Using a diagnostic magenta-like threshold of R > G+25, B > G+25, alpha >=128:

| Frame | Extracted clip | Saved key stage | Saved alpha stage |
| --- | ---: | ---: | ---: |
| 1 | 305 | 305 | 598 |
| 9 | 109 | 109 | 370 |

`key_pass()` applies despill; `alpha_pass()` then unmixes the key color from partially transparent edges (`core/sprite/keying.py:370`). Controlled in-memory replay with current code produced 604 versus 305 magenta-like pixels in frame 1 with edge decontamination enabled versus disabled, and 375 versus 109 in frame 9. Thus some colored pixels already exist in the video, and edge decontamination adds more. The slight replay/saved difference also means the current implementation should not be described as a byte-identical reconstruction of the older output.

Practical experiment in Processing: disable **Edge decontaminate**, use a small **despeckle** value, and select **Run pipeline** before reviewing/exporting again. In-memory despeckle values 1/2/3 reduced frame 1 detached pixels from 2,299 to 2,158/1,675/460, but did not eliminate all marks. Morphological opening can remove legitimate narrow detail, so inspect hair, fingers, and guitar strings. This experiment was not applied to the saved project.

Potential implementation follow-up: review the ordering and assumptions of despill versus edge unmixing with real clip fixtures. Add an optional previewable detached-component cleanup with size/distance controls and selective protection, rather than unconditionally retaining only the largest component.

### Stale processing is a separate issue

The last logged GIF export at 11:59 warned for both profiles that **stabilize output is stale; run the pipeline from the Processing panel**. Export continued. Rerunning processing is necessary for current settings/code to reach the exported frames. This warning is not the origin of the motion marks: they are already in the original character image.

A solid background will make transparency edges easier to judge and avoid binary-alpha cutout edges when composited before quantization. It will not remove foreground motion marks or colored foreground specks.

## Verification and remaining work

### Follow-up: preserve the input background

The requested design now has three background choices:

- **Keep original background:** bypass background removal, despill, edge decontamination, and alpha cleanup. Preserve the complete input frame/canvas and aspect ratio; resize only when requested. Avoid automatic border cropping, subject stabilization, and transparent profile padding. GIF palette conversion can still slightly change colors.
- **Transparent:** retain input alpha when available; otherwise remove the background using chroma keying or ML matting.
- **Replace with solid color:** obtain foreground alpha using existing input alpha or background removal, then composite onto the selected color before quantization. An opaque final GIF can therefore still need background removal when replacing an existing background.

There is already a Processing method labeled `none (source has alpha)` (`gui/sprite/processing_panel.py:299`). Its implementation also accepts opaque inputs: a real `key_frame()` call with `KeySettings(method='none')` returned pixel-identical RGBA for extracted frame 1. However, this is only the keying stage: `stabilize_runner()` still applies solid-border auto-cropping to opaque frames, and output profiles use transparent canvas padding. The existing dropdown is not a complete preserve-input guarantee.

For **new generation**, Keep original background must also bypass chroma-plate creation and the unconditional chroma prompt injection in both Omni and Veo paths (`core/sprite/generation/video_route.py`). Use the original character/reference background and request its preservation while retaining appropriate loop conditioning. Provider generation can still drift visually; pixel preservation is guaranteed only for the processing/export of already supplied frames, subject to requested resizing and GIF palette conversion.

For the existing rock_3 clip, bypassing keying preserves the green background already baked into that clip, not the original character image's white background. Recovering the original white appearance requires a new generation from that reference or background replacement.

Verified via direct image inspection, Pillow GIF decoding, connected-component measurements, source/sidecar/log inspection, and controlled calls to the real keyer. No fix or permanent regression test was implemented because the request was for a proposal and explanation.

`Docs/CodeMap.md` reports last updated 2026-08-11 and predates these Sprite modules. A refresh would help subsequent implementation; references here were checked directly against current source.
