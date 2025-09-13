# Strict Lyric Timing Output Contract (ALWAYS-Parseable)
**Version:** 1.0 • **Date:** 2025-09-12  
**Purpose:** Eliminate fragmentation, reordering, and unit/field inconsistency. Force a *single* JSON format that your parser can always consume.

---

## 🔐 Hard Rules (non‑negotiable)
1. **Output Format:** Return **exactly one** JSON object (no code fences, no comments, no prose).
2. **Schema:** Top‑level keys are **exactly**: `version`, `units`, `line_count`, `lyrics`. No others.
3. **Units:** Always `"ms"` (milliseconds). Times are **integers** in milliseconds.
4. **One‑to‑One Mapping:** **Exactly one entry per lyric line** (after the client filters out lines wrapped in `[]`).  
   - **Do not split** a single input line into fragments.  
   - **Do not merge** multiple input lines into one.  
5. **Order Preservation:** Maintain **exact input order**. `lyrics[i].line_index == i+1`.
6. **No Reordering:** Bridges, outros, etc. must stay in the same position as the input.
7. **No Extra Fields:** Inside each lyric item, only: `line_index`, `start_ms`, `end_ms`, `text`.
8. **Time Validity:** `0 <= start_ms < end_ms <= TRACK_DURATION_MS` (rounded).  
   - If alignment truly fails for a line, set both to **null** (still valid JSON) and keep order.
9. **Whitespace & Text:** Preserve **exact text** of each line (after the client’s bracket-filter). Trim leading/trailing whitespace. No additional punctuation.
10. **Deterministic Rounding:** Compute times in seconds internally if needed, but **round to nearest millisecond** before emitting integers (`round(x * 1000)`), not floor/ceil.

---

## ✅ JSON Shape (canonical)
```json
{
  "version": "1.0",
  "units": "ms",
  "line_count": <integer>,
  "lyrics": [
    {"line_index": 1, "start_ms": <integer|null>, "end_ms": <integer|null>, "text": "<first line>"},
    {"line_index": 2, "start_ms": <integer|null>, "end_ms": <integer|null>, "text": "<second line>"},
    ...
  ]
}
```

### Field Semantics
- `version`: Must be the string `"1.0"`.
- `units`: Must be the string `"ms"`.
- `line_count`: Must equal `lyrics.length` and the number of input lines received **after** bracket-filtering.
- `lyrics[i].line_index`: 1‑based index in **input order**; must equal `i+1`.
- `lyrics[i].start_ms` / `end_ms`: integers (milliseconds) or `null` if unalignable. If not `null`, must satisfy `0 <= start_ms < end_ms`.
- `lyrics[i].text`: the exact line text (after bracketed lines are removed by the client). Empty lines must be **omitted**.

---

## 🧭 Operational Constraints (how alignment must behave)
- **Fragmentation is prohibited.** Even for karaoke effects, **do not** split into word/phrase fragments. One JSON object per input line.
- **Quantization (optional):** If MIDI is provided, you may internally snap to the nearest subdivision but emit the **final integer ms** values only.
- **Pickups / Negative Offsets:** Clamp to `0` for `start_ms` if pre‑roll occurs. Ensure end times remain within track length.
- **Rubato / Tempo Drift:** Prefer **audio** alignment for anchors; MIDI is guidance only.
- **Confidence:** Not emitted. (If needed downstream, compute separately; this contract avoids optional fields.)

---

## 🧪 JSON Schema (Draft 2020‑12)
Use this to validate every response before returning it.
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["version", "units", "line_count", "lyrics"],
  "properties": {
    "version": { "type": "string", "const": "1.0" },
    "units": { "type": "string", "const": "ms" },
    "line_count": { "type": "integer", "minimum": 0 },
    "lyrics": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["line_index", "start_ms", "end_ms", "text"],
        "properties": {
          "line_index": { "type": "integer", "minimum": 1 },
          "start_ms": { "type": ["integer","null"], "minimum": 0 },
          "end_ms":   { "type": ["integer","null"], "minimum": 0 },
          "text":     { "type": "string", "minLength": 1 }
        }
      }
    }
  },
  "allOf": [
    {
      "if": {"properties": {"lyrics": {"minItems": 1}}},
      "then": {
        "properties": {
          "line_count": {
            "const": {"$data": "1/lyrics/length"}
          }
        }
      }
    }
  ]
}
```

> **Additional validator checks (pseudo):**
> - For each item `i`: assert `lyrics[i].line_index == i+1`.
> - For each item: if both times are not null ⇒ `0 <= start_ms < end_ms`.
> - Global: end of last line ≤ TRACK_DURATION_MS.

---

## 📦 Assistant Prompt (drop‑in)
Use this as the exact instruction your app sends with the assets (audio, optional MIDI, and the already‑filtered lyrics text).

**SYSTEM**
```
You are “Lyric Timing Aligner — Strict v1.0”. Output must be a single JSON object that conforms exactly to the “Strict Lyric Timing Output Contract v1.0”. Do not include any commentary or code fences. Do not split or merge lines. Preserve input order. Use integer milliseconds (units=ms). Round to nearest millisecond.
```

**USER**
```
TASK: Align each lyric line to the attached audio (MIDI optional). Return exactly one JSON object per the Strict Lyric Timing Output Contract v1.0.

ASSETS:
- audio: <attach final mixed audio file>
- midi: <attach matching MIDI file>  # optional
- lyrics_text_utf8 (already filtered; lines in [] were removed on client):
<PASTE LYRICS HERE, one line per lyric; omit blank lines>

CONSTRAINTS:
- One JSON entry per input line, in exact order.
- start_ms/end_ms integers in milliseconds (or null if truly unalignable).
- No other fields beyond the contract.
- Ensure 0 <= start_ms < end_ms <= TRACK_DURATION_MS (if not null).
- Rounding rule: round(x * 1000) to nearest millisecond.

OUTPUT:
- Emit only the JSON object, with top-level keys [version, units, line_count, lyrics]. Nothing else.
```

---

## 🧷 Example (short excerpt; dummy timings)
**Input lines (after client filtering of `[Verse]`, `[Chorus]`, etc.):**
```
When the night feels endless and I’m wide awake
I shuffle numbers like cards
```

**Valid output (parseable, non‑fragmented, ordered, ms):**
```json
{
  "version": "1.0",
  "units": "ms",
  "line_count": 2,
  "lyrics": [
    {"line_index": 1, "start_ms": 3128, "end_ms": 7420, "text": "When the night feels endless and I’m wide awake"},
    {"line_index": 2, "start_ms": 7850, "end_ms": 10420, "text": "I shuffle numbers like cards"}
  ]
}
```

**Invalid (will be rejected by validator):**
- Uses seconds instead of ms:
```json
{ "version": "1.0", "units": "ms", "line_count": 1, "lyrics": [{"line_index":1,"start_ms":3.128,"end_ms":7.420,"text":"..."}]} 
```
- Fragmented (two entries for one input line): ❌
- Reordered lines: ❌
- Extra fields (`confidence`, `bar_beat`, etc.): ❌

---

## 🛠 Integration Tips
- Run the JSON Schema above with a validator (Ajv, `jsonschema`, etc.) before accepting output.
- If any item returns `null` times, keep your scene logic robust (e.g., fallback to beat grid or neighbor interpolation), but parsing will still succeed.
- For consistent visuals, apply a post-pass that enforces a minimum caption duration/gap by expanding to nearby low‑energy frames; **do not** ask the assistant to split lines.

---

## 🧩 Optional: Minimal “Compact Contract” (if you want an even stricter envelope)
If you want to forbid `null`, require successful alignment:
```json
{
  "version": "1.0",
  "units": "ms",
  "line_count": <n>,
  "lyrics": [
    {"line_index": 1, "start_ms": <int>, "end_ms": <int>, "text": "<...>"}
  ]
}
```
In this mode, reject any response that contains `null` and re‑request alignment with stronger guidance (e.g., supply a vocal stem).
