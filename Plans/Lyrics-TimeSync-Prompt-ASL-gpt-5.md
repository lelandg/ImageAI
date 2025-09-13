# Time‑Synchronized Lyrics Prompt (Audio + MIDI + Lyrics → SRT/LRC/JSON)

**Purpose:** Use this prompt in your local app when you send audio, MIDI, and lyrics. The assistant must return **only the time‑synchronized lyrics** in the requested format. (Your app filters out lines wrapped in `[]` before sending; if any remain, ignore them.)

---

## ✅ What you (the assistant) will receive
- **Audio** (e.g., WAV/MP3): full mix; if stems are provided, prefer the **vocal** stem.
- **MIDI** (optional but preferred): includes **tempo map** and **time signature**.
- **Lyrics** (UTF‑8 text): plain lines; **any lines wrapped in `[]` are to be ignored**.

---

## 🎯 Your tasks
1. **Align lyrics to time** using:
   - The **MIDI tempo map** (downbeats, measures) to build a beat grid.
   - **Forced alignment** against the audio to locate word/line boundaries (snap to nearby beats when `ADJUST_TO_BEATS=true`).
2. **Produce only the requested output format** (no commentary, no headers).
3. **Preserve lyric text** exactly as provided (except: ignore any lines wrapped in `[]` if any slip through).
4. **Ensure validity**:
   - Timestamps must be **monotonic**, **non‑overlapping**, and **within the audio duration**.
   - Start times \< end times; end of last line \<= track length.
   - Use **normalized whitespace**; trim leading/trailing spaces.

---

## ⚙️ Parameters (set by the user app)
- **OUTPUT_FORMAT:** `srt` | `lrc` | `json` (default: `srt`)
- **LINE_GROUPING:** `line` | `phrase` | `caption` (default: `line`)
  - `line` = one caption per lyric line.
  - `phrase` = merge short lines into natural phrases.
  - `caption` = wrap to ~`MAX_LINE_CHARS`.
- **MAX_LINE_CHARS:** integer, default `42` (for `caption` mode)
- **CAPTION_DURATION_RANGE_MS:** `[min_ms, max_ms]`, default `[1200, 6000]`
- **GAP_MIN_MS:** minimum gap between captions, default `50`
- **ADJUST_TO_BEATS:** `true` | `false` (default: `true`)
- **BEAT_SNAP_FRACTION:** `"1/16"` (snap to nearest 1/16 note when adjusting)
- **LEADING_SILENCE_MS:** integer, default `0`
- **TRAILING_SILENCE_MS:** integer, default `0`

> If any of these are omitted, use the defaults above.

---

## 📤 Output specifications (choose exactly one via `OUTPUT_FORMAT`)

### 1) `srt`
- Index starts at 1.
- Timestamp format: `HH:MM:SS,mmm` (e.g., `00:01:02,345`).
- **Output only SRT blocks**; no extra text.

**Example (dummy times):**
```
1
00:00:000 --> 00:03:200
When the night feels endless and I’m wide awake

2
00:03:200 --> 00:05:400
I shuffle numbers like cards
```

### 2) `lrc`
- Use extended LRC with millisecond tags: `[mm:ss.xxx]`.
- One line per lyric line; no indices.

**Example (dummy times):**
```
[00:00.000]When the night feels endless and I’m wide awake
[00:03.200]I shuffle numbers like cards
```

### 3) `json`
- Emit a **single JSON array**, no trailing text:
```json
[
  {"i":1, "start_ms":0, "end_ms":3200, "text":"When the night feels endless and I’m wide awake"},
  {"i":2, "start_ms":3200, "end_ms":5400, "text":"I shuffle numbers like cards"}
]
```

---

## 🧠 Alignment guidance (internal)
- Derive an initial **beat grid** from MIDI (tempo map, time signature, barlines).
- Estimate line timings by **phonetic/energy alignment** to audio; then **optionally snap** to nearest beat or subdivision (`BEAT_SNAP_FRACTION`), staying within ±120 ms of true boundary.
- Respect `CAPTION_DURATION_RANGE_MS` and `GAP_MIN_MS` by expanding/contracting to nearby quiet regions.
- If the vocal is buried, weight spectral bands (1–5 kHz) and onsets; if a vocal stem is present, prefer it.

---

## 🧪 Example using the attached ASL (“Do Math”, bracketed lines are ignored)

### Raw lyrics sample (with tags; your app filters lines in `[]` before sending)
```
[Verse 1]
When the night feels endless and I’m wide awake
I shuffle numbers like cards
I hum a rhythm, let the numbers dance
And suddenly it’s not so hard

[Chorus]
I’m doin’ math, I do math, I do math
I’m tap-tap-tappin’ in my head
I’m doin’ math, I do math, I do math
I’m countin’ sheep with sums instead
```

### The same sample (effective input after filtering)
```
When the night feels endless and I’m wide awake
I shuffle numbers like cards
I hum a rhythm, let the numbers dance
And suddenly it’s not so hard
I’m doin’ math, I do math, I do math
I’m tap-tap-tappin’ in my head
I’m doin’ math, I do math, I do math
I’m countin’ sheep with sums instead
```

### Expected **SRT** output (dummy timings for illustration only)
```
1
00:00:000 --> 00:03:200
When the night feels endless and I’m wide awake

2
00:03:200 --> 00:05:400
I shuffle numbers like cards

3
00:05:400 --> 00:08:100
I hum a rhythm, let the numbers dance

4
00:08:100 --> 00:10:600
And suddenly it’s not so hard

5
00:10:600 --> 00:12:800
I’m doin’ math, I do math, I do math

6
00:12:800 --> 00:14:900
I’m tap-tap-tappin’ in my head

7
00:14:900 --> 00:17:100
I’m doin’ math, I do math, I do math

8
00:17:100 --> 00:20:000
I’m countin’ sheep with sums instead
```

---

## 📥 How your app should call this (template)
**User message to assistant (single prompt):**
```
You will receive:
- Audio file: <filename.wav or .mp3> (attached)
- MIDI file: <filename.mid> (attached)  # optional but recommended
- Lyrics (UTF-8 text): provided below (lines in [] should be ignored if any remain)

Parameters:
OUTPUT_FORMAT=srt
LINE_GROUPING=line
MAX_LINE_CHARS=42
CAPTION_DURATION_RANGE_MS=[1200,6000]
GAP_MIN_MS=50
ADJUST_TO_BEATS=true
BEAT_SNAP_FRACTION="1/16"
LEADING_SILENCE_MS=0
TRAILING_SILENCE_MS=0

Task:
Return only the time-synchronized lyrics in the requested OUTPUT_FORMAT. 
Do not include any extra commentary, headers, or code fences.

Lyrics:
<PASTE LYRICS HERE>
```

> **Note:** If audio and MIDI disagree (e.g., rubato/vocal pickups), prefer **audio alignment** and use MIDI only for beat guidance.

---

## 🧩 Troubleshooting
- If the vocal line starts before bar 1, allow **negative musical offsets** but clamp **timestamps to ≥ 0 ms**.
- If a lyric line is too short, merge with adjacent line when `LINE_GROUPING=phrase` or `caption`.
- Normalize curly quotes/apostrophes as-is; **do not alter text content**.

---

## ✅ One-line “minimal” prompt (if you need a compact version)
```
Align these lyrics to the attached audio using the attached MIDI tempo map; ignore any lines wrapped in []; output only SRT with monotonic, non-overlapping timestamps snapped to the nearest 1/16 note (±120 ms), durations 1.2–6.0 s, min gap 50 ms, and preserve the text exactly; no commentary.
```
