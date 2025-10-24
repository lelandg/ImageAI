# Veo 3 Tempo & Rhythm Prompting Research

**Research Date:** 2025-10-24
**Focus:** Prompting techniques for creating tempo-synchronized, rhythmic videos with Google's Veo 3/3.1

---

## Executive Summary

Google's Veo 3/3.1 video generation models have **limited explicit support for BPM or numerical tempo specifications**. However, the models respond well to **descriptive rhythm language**, **natural motion descriptors**, and **timestamp-based choreography**. Success with tempo-matched videos relies on:

1. **Descriptive rhythm language** (e.g., "upbeat," "pulsing," "bouncing") rather than BPM numbers
2. **Audio generation capabilities** that can create music with tempo descriptors
3. **Physics-based motion** that naturally produces bouncing, pulsing effects
4. **Timestamp prompting** (unofficial) for choreographing multi-shot sequences
5. **Reference images** for maintaining visual consistency across rhythm-synced shots

**Key Limitation:** Veo 3 does **not** support uploading pre-existing music tracks and auto-syncing visuals to the beat. Instead, it generates audio alongside video based on textual descriptions.

---

## 1. Tempo/Rhythm Prompting Techniques

### Descriptive Approach (Primary Method)

Veo 3 responds best to **qualitative rhythm descriptors** rather than quantitative BPM values:

**Tempo Descriptors:**
- "upbeat, driving electronic track"
- "slow, contemplative rhythm"
- "fast-paced, energetic movement"
- "mellow, soulful hip-hop beat"
- "sweeping orchestral score building to a crescendo"

**Rhythm Qualities:**
- "pulsating light"
- "rhythmic movement"
- "bouncing in place"
- "syncopated motion"
- "fluid, continuous motion"
- "energetic, high-energy actions"
- "graceful, flowing movement"

### Audio Generation with Tempo

When generating audio alongside video, describe the musical characteristics:

```
"A light orchestral score with woodwinds throughout with a cheerful,
optimistic rhythm, full of innocent curiosity"

"An upbeat electronic track with a heavy bassline and driving rhythm"

"SFX: rhythmic clatter of a train on tracks"
```

**Note:** Audio is described contextually, not with technical parameters like "120 BPM."

---

## 2. BPM-Specific Language

### Direct BPM References: Not Supported

Veo 3's official documentation contains **no evidence of BPM parameter support** in prompts or API calls.

### Workaround: External Music Generation

For precise BPM control, the community workflow is:

1. **Generate music separately** with BPM specification using tools like Soundverse
   - Example: "electronic beat with bass, 120 BPM, energetic and modern"
   - Example: "gentle piano with strings, 70 BPM, minor key with emotional depth"

2. **Generate video with Veo 3** using descriptive rhythm language matching the music

3. **Post-process** to combine video with the pre-generated music track

**Source:** Soundverse AI workflow for creating 3-minute AI films with Veo 3

### Tempo Language Mapping

Since BPM isn't supported, map tempo ranges to descriptive language:

| BPM Range | Descriptive Language |
|-----------|---------------------|
| 60-80     | "slow," "contemplative," "gentle," "mellow" |
| 80-100    | "moderate," "walking pace," "steady" |
| 100-120   | "upbeat," "energetic," "driving" |
| 120-140   | "fast," "intense," "high-energy," "rapid" |
| 140+      | "frenetic," "blazing," "explosive," "breakneck" |

---

## 3. Bouncy Movement Descriptors

### Physics-Based Bouncing

Veo 3 excels at **realistic physics simulation**, including natural bouncing motion:

**Prompt Pattern:**
```
"A low-angle medium shot frames a boxer from below as he bounces in
place before a match, lit by harsh overhead fluorescents."
```

**Physics Keywords:**
- "bouncing in place"
- "natural jump trajectory"
- "authentic momentum conservation in landing"
- "fluid dynamics in fabric movement"
- "falling, bouncing, and fluid motion remain physically accurate"

### Pulsing/Rhythmic Effects

**Light/Visual Pulsing:**
```
"Medium shot, two astronauts inside a dimly lit cockpit, warning lights
pulsing across their helmets."

"Weathered skin etched with intricate, bioluminescent circuit-like
tattoos that pulse with a soft, cyan light."
```

**Movement Pulsing:**
```
"Colorful geometric shapes pulsate and rotate to the rhythm of a
chill lo-fi beat"

"Crowd waving hands in sync with the beat"

"Dancer leaps with natural physics, fabric flowing with momentum"
```

### Rhythm-Aligned Action

**Music Video Examples:**
```
"A hip-hop artist rapping on stage, crowd waving hands in sync with
the beat"

"Crowd dancing to the bass drop, bodies moving in rhythmic unison"

"Fast-paced, rhythmic jump cut effect where actions happen in sync
with implied timing"
```

---

## 4. Camera Movement vs Subject Movement

### Best Practices

**Separate camera motion from subject action** for clarity:

**Good:**
```
"A dancer performs a graceful pirouette on a stage. The camera pulls
back slowly to reveal the full theater."
```

**Less Effective:**
```
"A dancer performs a graceful pirouette while the camera pulls back to
reveal the full theater."
```

**Rationale:** Separating motion instructions helps the model parse intent accurately.

### Camera Movement for Rhythm

**Camera motion types** that can enhance rhythmic feeling:

- `"static"` - no motion, let subject movement dominate
- `"slow_push_in"` - gradual intensification
- `"continuous_slow_zoom_out"` - expanding perspective
- `"dolly_in"` - smooth forward motion
- `"panning_left_to_right"` - sweeping lateral movement
- `"smooth_gimbal_movement"` - fluid, stabilized motion

**For rhythmic videos:** Consider static or minimal camera movement to let subject motion and editing create the rhythm.

### Subject Movement for Tempo

**Movement keywords:**
- "energetic movement" - high-energy, dynamic actions
- "graceful movement" - smooth, flowing motion
- "fluid movement" - seamless, continuous motion
- "sharp, staccato movements" - quick, punctuated actions
- "slow, deliberate gestures" - controlled, measured motion

**Music video workflow:** Focus subject movement on beat-aligned actions (jumping, clapping, gesturing) and use camera as a supporting element.

---

## 5. Duration Considerations (8-Second Constraint)

### Veo 3.0/3.1 Duration Limit

**Fixed duration:** 8 seconds per generation (technical constraint)

**Impact on rhythm establishment:**
- **Challenge:** 8 seconds ≈ 16 beats at 120 BPM, limiting rhythmic pattern complexity
- **Opportunity:** Focus on establishing clear, simple rhythmic motifs
- **Solution:** Use multi-shot sequencing with timestamp prompting

### Calculating Beat Counts

At common BPM values, 8 seconds provides:

| BPM | Beats in 8s | Bars (4/4) |
|-----|-------------|------------|
| 60  | 8           | 2 bars     |
| 90  | 12          | 3 bars     |
| 120 | 16          | 4 bars     |
| 140 | ~18.7       | ~4.7 bars  |
| 160 | ~21.3       | ~5.3 bars  |

**Recommendation:** Design rhythmic prompts for **2-4 bar phrases** that loop or extend naturally.

### Multi-Shot Rhythm Continuity

**Timestamp Prompting** (unofficial community technique):

```
[00:00-00:02] Wide shot. A DJ raises both hands as purple stage lights
              pulse in rhythm. Audio: Deep bass kick drops.

[00:02-00:04] Medium shot. The crowd jumps in unison, arms raised,
              bodies bouncing to the beat.

[00:04-00:06] Close-up. DJ's hands twist knobs in sync with the rhythm,
              fingers moving rapidly.

[00:06-00:08] Wide shot. Entire venue lit by strobing lights, crowd
              pulsing as one mass.
```

**Note:** This technique appears in guides but isn't officially documented. Test in your implementation.

---

## 6. Examples and Best Practices

### Community-Validated Music Video Workflow

**Source:** TikTok creator @ai.with.whit, Beatstorapon.com

**Process:**
1. **Write scene-specific prompts** matching lyrical content
   - Include: character descriptions, outfits, camera angles, emotion
   - Example: "Singer with raw, no-makeup look performs under streetlight,
              graffiti-covered alley, intimate close-up, melancholic"

2. **Describe audio-visual synchronization explicitly**
   - "Crowd cheering in sync with the hook"
   - "Performer gestures on the word 'freedom,' raising fist"
   - "Bass drop coincides with camera zoom"

3. **Leverage Veo 3's automatic lip-sync**
   - Veo 3 "analyzes the song's tempo and energy" to coordinate visual cuts
   - Automatically aligns lip movements when prompts imply singing/rapping

4. **Specify energy level matching tempo**
   - Fast track: "high-energy," "intense," "rapid movements"
   - Slow track: "contemplative," "smooth," "flowing gestures"

### Prompt Templates for Rhythmic Videos

**Template 1: Bouncing Subject**
```
[Shot type], [subject] bounces [motion descriptor] [location/context].
[Lighting]. Audio: [rhythmic sound description].

Example:
Medium shot, a basketball player bounces energetically on the court
before a game, anticipation visible. Harsh overhead gym lights.
Audio: rhythmic dribbling, crowd murmur building.
```

**Template 2: Pulsing Visual Effects**
```
[Shot type], [subject/scene] with [pulsing element] that pulses
[intensity/color/pattern]. [Style]. Audio: [matching audio rhythm].

Example:
Wide shot, a futuristic cityscape with neon signs that pulse in
cyan and magenta waves. Cyberpunk aesthetic. Audio: electronic
synth arpeggios with driving rhythm.
```

**Template 3: Crowd/Group Rhythm**
```
[Shot type], [group] [synchronized action] in sync with [music element].
[Camera movement]. Audio: [beat description].

Example:
Wide shot, a concert crowd jumps and raises hands in unison with
the beat. Camera slowly pushes forward through the crowd.
Audio: heavy bass kick with 4-on-the-floor rhythm, cheering.
```

**Template 4: Music Video Lyric Sync**
```
[Shot type], [character] [action matching lyric] while [environment/mood].
[Lighting/style]. Audio: [vocal line], [background music].

Example:
Close-up, hip-hop artist gestures toward camera on the word "truth,"
intense expression. Urban rooftop at golden hour. Audio: "Speaking
nothing but the truth," mellow hip-hop beat underneath.
```

### JSON Prompting for Advanced Control

**Community discovery (July 2025):** JSON-structured prompts provide superior results.

**Basic Structure:**
```json
{
  "scene": "A lone DJ performs at an underground rave",
  "style": "Cinematic with vibrant neon lighting",
  "camera": "Slow dolly-in from wide to medium shot",
  "lighting": "Pulsing purple and blue strobes synchronized with beat",
  "audio": {
    "music": "Driving techno beat with heavy bass, energetic rhythm",
    "sfx": "Crowd cheering, bass thump"
  },
  "character": {
    "appearance": "DJ wearing all black, headphones, focused expression",
    "action": "Hands moving rhythmically over turntables, bobbing to beat"
  },
  "technical": {
    "duration_seconds": 8,
    "aspect_ratio": "16:9"
  }
}
```

**Advanced with Dialogue Timing:**
```json
{
  "scene": "Concert stage, hip-hop artist performing",
  "camera": "Medium shot, static",
  "lighting": "Spotlight from above, dramatic shadows",
  "audio": {
    "dialogue": [{
      "actorId": "rapper_main",
      "line": "We rise together, never fall",
      "delivery": "enthusiastic"
    }],
    "music": "Upbeat hip-hop beat, heavy bass, energetic"
  },
  "character": {
    "actorId": "rapper_main",
    "appearance": "Streetwear, confident stance",
    "action": "Raises fist on 'rise,' gestures downward on 'fall'"
  }
}
```

**Note:** JSON prompting is an **unofficial community convention**, not documented API syntax. It works by providing structured clarity but may be processed as text.

---

## 7. Reference Video/Image Usage

### Reference Image Capabilities

**Veo 3.1 feature:** "Ingredients to video" with up to **3 reference images** per shot

**Applications for rhythm/tempo:**
1. **Character consistency** across multiple rhythm-synced shots
   - Maintain same dancer/performer appearance through sequence
   - Example: Generate 8-second dance clip, use final frame as reference for next clip

2. **Style consistency** for music video aesthetics
   - Reference image of album art, lighting style, color palette
   - Ensures visual cohesion across beat-synced segments

3. **Environment consistency** for multi-shot sequences
   - Same stage, club, or location across multiple clips
   - Reference image of venue for all performance shots

### First/Last Frame Conditioning

**Veo 3.1 capability:** Specify **starting and ending frames**, model interpolates between them

**Rhythmic application:**
```
First frame: Dancer with arms down, feet together
Last frame: Dancer with arms raised, legs apart in jump
Prompt: "Dancer performs energetic jump with natural physics,
         bouncing motion, upbeat rhythm"

Result: 8-second clip interpolates the jump with realistic physics
        and bouncing motion
```

**Benefit:** Ensures specific poses at beat-critical moments while letting AI handle the motion between.

### Reference Video: Not Directly Supported

**Current limitation:** Veo 3/3.1 does **not support reference video input** for motion/rhythm matching.

**Workaround:**
1. Extract keyframes from reference video at important beat moments
2. Use these as reference images for character/style
3. Describe the motion in text prompts
4. Use first/last frame to control motion start/end points

**Community expectation:** Reference video support may come in future versions, but not available as of October 2024.

---

## 8. Technical Implementation Recommendations

### For Your Video Generation System

Based on this research, here are actionable implementation strategies:

#### Strategy 1: Tempo Descriptor Mapping

**Implementation:**
```python
def map_bpm_to_descriptors(bpm: int) -> dict:
    """Map BPM to Veo 3-compatible descriptive language."""
    if bpm < 80:
        return {
            "tempo": "slow",
            "energy": "contemplative, gentle, mellow",
            "movement": "smooth, flowing, graceful",
            "camera": "slow_push_in or static"
        }
    elif bpm < 100:
        return {
            "tempo": "moderate",
            "energy": "steady, balanced, walking pace",
            "movement": "natural, measured, deliberate",
            "camera": "dolly_in or panning"
        }
    elif bpm < 120:
        return {
            "tempo": "upbeat",
            "energy": "energetic, driving, lively",
            "movement": "bouncing, rhythmic, dynamic",
            "camera": "smooth_gimbal_movement"
        }
    elif bpm < 140:
        return {
            "tempo": "fast",
            "energy": "intense, high-energy, rapid",
            "movement": "sharp, quick, pulsing",
            "camera": "dynamic movement or fast zoom"
        }
    else:
        return {
            "tempo": "very fast",
            "energy": "frenetic, explosive, blazing",
            "movement": "rapid-fire, staccato, intense",
            "camera": "aggressive movement or quick cuts"
        }
```

#### Strategy 2: Lyric-to-Visual Prompt Generation

**Implementation approach:**
```python
def generate_lyric_synced_prompt(
    lyric_line: str,
    bpm: int,
    character_ref: str,
    scene_setting: str
) -> str:
    """Generate Veo 3 prompt for lyric-synced video."""

    tempo_desc = map_bpm_to_descriptors(bpm)

    # Extract key action words from lyrics
    action_words = extract_action_verbs(lyric_line)

    # Build prompt
    prompt = f"""Medium shot, {character_ref} performs in {scene_setting}.

On the lyric "{lyric_line}", character {describe_gesture_for_words(action_words)}.

Movement: {tempo_desc['movement']}, matching the {tempo_desc['energy']} rhythm.
Camera: {tempo_desc['camera']}.
Lighting: Dramatic with pulsing accents synchronized to the beat.

Audio: Vocal line "{lyric_line}", {tempo_desc['energy']} {tempo_desc['tempo']} beat underneath.
"""

    return prompt.strip()
```

#### Strategy 3: Multi-Shot Timestamp Sequencing

**Implementation:**
```python
def create_timestamp_sequence(
    shots: list[dict],  # [{"duration": 2, "action": "...", "camera": "..."}, ...]
    total_duration: int = 8
) -> str:
    """Create timestamp-based multi-shot prompt (unofficial technique)."""

    current_time = 0
    timestamp_prompts = []

    for shot in shots:
        start = current_time
        end = min(current_time + shot["duration"], total_duration)

        timestamp_prompts.append(
            f"[{start:02d}:00-{end:02d}:00] {shot['shot_type']}, "
            f"{shot['action']}. {shot['camera']}. "
            f"Audio: {shot['audio']}."
        )

        current_time = end
        if current_time >= total_duration:
            break

    return "\n\n".join(timestamp_prompts)
```

#### Strategy 4: Reference Image Chain for Continuity

**Implementation:**
```python
def generate_sequence_with_continuity(
    base_character_ref: str,
    shots: list[dict],
    bpm: int
) -> list[dict]:
    """Generate sequence using last frame as next shot's reference."""

    results = []
    current_ref_image = base_character_ref

    for i, shot in enumerate(shots):
        prompt = generate_lyric_synced_prompt(
            shot["lyric"],
            bpm,
            current_ref_image,
            shot["setting"]
        )

        # Generate video with Veo 3
        result = veo3_generate(
            prompt=prompt,
            reference_images=[current_ref_image],
            duration=8
        )

        # Extract last frame as reference for next shot
        current_ref_image = extract_last_frame(result.video_url)

        results.append({
            "shot_index": i,
            "video": result.video_url,
            "prompt": prompt,
            "next_reference": current_ref_image
        })

    return results
```

#### Strategy 5: JSON Prompt Builder

**Implementation:**
```python
def build_json_prompt(
    scene: str,
    character: dict,
    audio: dict,
    camera: str,
    lighting: str,
    bpm: int
) -> str:
    """Build JSON-structured prompt for Veo 3 (community technique)."""

    tempo_desc = map_bpm_to_descriptors(bpm)

    prompt_dict = {
        "scene": scene,
        "style": "Cinematic music video aesthetic",
        "camera": camera,
        "lighting": f"{lighting}, with pulsing accents synchronized to {tempo_desc['tempo']} rhythm",
        "audio": {
            "music": f"{audio.get('music', 'Background music')}, {tempo_desc['energy']} rhythm",
            "sfx": audio.get('sfx', ''),
        },
        "character": {
            "appearance": character.get('appearance', ''),
            "action": f"{character.get('action', '')}, moving with {tempo_desc['movement']} to match the beat"
        },
        "technical": {
            "duration_seconds": 8,
            "aspect_ratio": "16:9"
        }
    }

    # Convert to formatted JSON string
    return json.dumps(prompt_dict, indent=2)
```

---

## 9. Key Limitations and Workarounds

### Limitation 1: No Direct BPM Input

**Limitation:** Cannot specify "120 BPM" in prompts
**Workaround:** Use tempo descriptor mapping (see Strategy 1)
**Example:** Instead of "120 BPM," use "upbeat, energetic rhythm with driving beat"

### Limitation 2: No Pre-Existing Audio Upload

**Limitation:** Cannot upload existing music track for auto-sync
**Workaround:**
1. Generate music separately with BPM control (Soundverse, etc.)
2. Generate video with matching tempo descriptors
3. Combine in post-production

### Limitation 3: 8-Second Duration Constraint

**Limitation:** Each generation limited to 8 seconds (Veo 3.0/3.1)
**Workaround:**
- Use timestamp prompting for multi-shot sequences within 8s
- Generate multiple 8s clips and stitch together
- Use last frame of clip N as reference image for clip N+1

### Limitation 4: Timestamp Prompting Unofficial

**Limitation:** `[00:00-00:02]` syntax not officially documented
**Workaround:**
- Test thoroughly in your implementation
- Have fallback to standard prompts if timestamp syntax fails
- Monitor Google's documentation for official timestamp support

### Limitation 5: No Reference Video Support

**Limitation:** Cannot provide reference video for motion/rhythm matching
**Workaround:**
- Extract keyframes from reference video
- Use keyframes as reference images
- Describe motion in text prompts
- Use first/last frame conditioning for specific poses

---

## 10. Recommended Prompt Patterns for Your System

Based on this research, here are the most effective prompt patterns for tempo-matched video generation:

### Pattern A: Simple Rhythmic Scene

**Use case:** Single-shot video with bouncing/pulsing movement

**Template:**
```
{shot_type}, {subject} {rhythmic_action} {location}. {subject} moves
with {tempo_descriptor} {movement_quality}. {lighting_with_pulse}.
Audio: {music_description_with_tempo}, {sfx}.
```

**Example (120 BPM):**
```
Medium shot, a street dancer performs in an urban plaza. Dancer bounces
energetically with upbeat, dynamic movements, body pulsing to the rhythm.
Colorful stage lights pulse in sync with the beat. Audio: driving
electronic track with heavy bass and energetic rhythm, crowd cheering.
```

### Pattern B: Lyric-Synced Performance

**Use case:** Music video shot matching specific lyric line

**Template:**
```
{shot_type}, {character} performs "{lyric_line}" in {setting}. On the
word "{key_word}", {character} {specific_gesture}. {character} moves
with {tempo_descriptor} {movement_quality}. {camera_movement}. {lighting}.
Audio: "{lyric_line}", {music_description}.
```

**Example (90 BPM):**
```
Close-up, hip-hop artist performs "We rise above the hate" in a graffiti
alley. On the word "rise", artist raises fist triumphantly. Artist moves
with moderate, steady gestures matching contemplative rhythm. Camera slowly
pushes in. Dramatic side lighting with shadows. Audio: "We rise above the
hate", mellow hip-hop beat with soulful rhythm.
```

### Pattern C: Multi-Shot Timestamp Sequence

**Use case:** Choreographed sequence across 8 seconds

**Template:**
```
[00:00-{time1}] {shot1_description}. Audio: {audio1}.

[{time1}-{time2}] {shot2_description}. Audio: {audio2}.

[{time2}-00:08] {shot3_description}. Audio: {audio3}.
```

**Example (140 BPM, fast):**
```
[00:00-00:02] Wide shot, DJ raises hands as purple stage lights explode
in rhythm. Audio: Bass drop hits hard.

[00:02-00:05] Medium shot, crowd jumps in unison, arms raised, bodies
pulsing rapidly to the intense beat. Audio: Fast, high-energy techno
rhythm continues.

[00:05-00:08] Close-up, DJ's hands move rapidly over equipment, fingers
dancing with frenetic energy. Audio: Beat builds to crescendo.
```

### Pattern D: JSON-Structured Advanced Prompt

**Use case:** Maximum control with structured approach

**Template:**
```json
{
  "scene": "{scene_description}",
  "style": "Cinematic music video",
  "camera": "{camera_movement}",
  "lighting": "{lighting} with pulsing accents synchronized to {tempo} rhythm",
  "audio": {
    "music": "{genre} with {tempo_descriptor} rhythm, {energy_descriptor}",
    "sfx": "{sound_effects}",
    "dialogue": [
      {
        "actorId": "{character_id}",
        "line": "{lyric_or_dialogue}",
        "delivery": "{delivery_style}"
      }
    ]
  },
  "character": {
    "actorId": "{character_id}",
    "appearance": "{visual_description}",
    "action": "{action_description}, moving with {movement_quality} to match the beat"
  },
  "technical": {
    "duration_seconds": 8,
    "aspect_ratio": "16:9"
  }
}
```

---

## 11. Additional Resources

### Official Documentation
- **Google Cloud Veo 3.1 Prompting Guide:** https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1
- **DeepMind Veo Prompt Guide:** https://deepmind.google/models/veo/prompt-guide/
- **Vertex AI Video Generation Guide:** https://cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide

### Community Resources
- **Skywork AI Veo 3 Guides:** https://skywork.ai/blog/ (multiple in-depth guides)
- **Superprompt Veo 3 Best Practices:** https://superprompt.com/blog/veo3-prompting-best-practices
- **Replicate Veo 3 Blog:** https://replicate.com/blog (image conditioning, prompting tips)

### Workflow Examples
- **Music Video Creation (Hip-Hop):** https://beatstorapon.com/blog/veo3-democratizing-high-quality-music-video-creation-for-rap-hip-hop-artists/
- **Full AI Film Workflow:** https://www.soundverse.ai/blog/article/how-to-create-a-3-minute-ai-short-film-using-midjourney-veo-3-soundverse-and-topaz-video-ai-no-code-no-budget

### JSON Prompting
- **Veo 3 JSON Guide:** https://www.imagine.art/blogs/veo-3-json-prompting-guide
- **Advanced JSON Techniques:** https://ademyuce.tr/en/veo-3-json-prompt-guide/

---

## 12. Conclusion and Recommendations

### What Works Well

1. **Descriptive tempo language** - Use "upbeat," "energetic," "driving" instead of BPM
2. **Physics-based bouncing** - Leverage realistic physics for natural rhythmic motion
3. **Pulsing visual effects** - Lights, colors, and visual elements can pulse rhythmically
4. **Audio generation** - Veo 3 can generate matching music/sfx alongside video
5. **Lyric/action synchronization** - Explicitly describe what happens on specific words
6. **Reference images** - Maintain character/style consistency across rhythm-synced clips
7. **JSON prompting** - Structured approach provides clearer results (unofficial)

### What Doesn't Work

1. **Direct BPM specification** - No support for "120 BPM" in prompts
2. **Pre-existing audio upload** - Cannot provide existing music track for auto-sync
3. **Reference video** - Cannot provide video for motion/rhythm matching
4. **Precise beat timing** - No frame-level control over beat hits
5. **Duration > 8s** - Stuck with 8-second constraint (Veo 3.0/3.1)

### Implementation Strategy for Your System

For a lyric-synced video generation system with tempo matching:

1. **Map BPM to descriptors** (Strategy 1) - Convert numerical BPM to qualitative language
2. **Generate tempo-matched prompts** (Strategy 2) - Build prompts with matching energy/movement
3. **Use multi-shot sequencing** (Strategy 3) - Break longer songs into 8s segments
4. **Chain clips with reference frames** (Strategy 4) - Maintain visual continuity
5. **Optionally use JSON structure** (Strategy 5) - For maximum prompt clarity
6. **Generate music separately** - Use Soundverse or similar for precise BPM control
7. **Post-process combination** - Merge Veo 3 video with separate audio track

### Future Developments to Watch

- Official timestamp/sequencing support
- Reference video input for motion matching
- Longer duration support (>8 seconds)
- Direct audio upload and auto-sync
- BPM/tempo parameter support
- Enhanced multi-shot consistency features

---

## Appendix: Quick Reference

### Tempo Descriptor Quick Map

```
60-80 BPM   → "slow, contemplative, gentle, flowing"
80-100 BPM  → "moderate, steady, balanced, measured"
100-120 BPM → "upbeat, energetic, driving, bouncing"
120-140 BPM → "fast, intense, high-energy, pulsing"
140+ BPM    → "very fast, frenetic, explosive, rapid-fire"
```

### Movement Quality Keywords

```
Slow:     smooth, flowing, graceful, deliberate
Moderate: natural, measured, rhythmic, steady
Fast:     energetic, dynamic, bouncing, sharp
V. Fast:  rapid, staccato, intense, explosive
```

### Camera Movement for Rhythm

```
Static               → Let subject motion dominate
Slow push/pull       → Gradual intensification
Dolly in/out         → Smooth, controlled motion
Panning              → Sweeping lateral rhythm
Smooth gimbal        → Fluid, stabilized tracking
Dynamic/aggressive   → High-energy, fast tempo
```

### Prompt Building Checklist

- [ ] Shot type specified (wide, medium, close-up)
- [ ] Subject/character described
- [ ] Rhythmic action/movement included
- [ ] Tempo descriptor matching BPM
- [ ] Movement quality keywords
- [ ] Camera movement (if needed)
- [ ] Lighting with "pulsing" elements
- [ ] Audio description (music + sfx)
- [ ] Lyric line (if applicable)
- [ ] Specific gesture on key word (if applicable)

---

**End of Research Report**

Generated: 2025-10-24
For: ImageAI Video Project - Veo 3 Integration
Next Steps: Implement prompt generation strategies in video generation system
