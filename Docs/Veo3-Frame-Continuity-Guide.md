# Veo 3 Frame-to-Frame Continuity Guide

**Purpose**: Create seamless video sequences where each clip starts with the previous clip's ending frame but transitions according to its own video prompt.

**Created**: 2025-10-19
**Applies to**: ImageAI Video Tab with Veo 3 provider

---

## Table of Contents

1. [Overview](#overview)
2. [The Continuity Challenge](#the-continuity-challenge)
3. [How Frame-to-Frame Continuity Works](#how-frame-to-frame-continuity-works)
4. [Three Approaches to Continuity](#three-approaches-to-continuity)
5. [Step-by-Step Workflows](#step-by-step-workflows)
6. [Technical Implementation](#technical-implementation)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [Examples](#examples)

---

## Overview

Frame-to-frame continuity is the technique of creating video clips where each clip starts with the exact ending frame of the previous clip, ensuring smooth visual transitions between scenes. This is particularly powerful when combined with Veo 3.1's "Frames to Video" capability, which allows you to specify both a **start frame** (where the video begins) and an **end frame** (where the video ends), with a **video prompt** describing the transition.

### What You'll Learn

- How to extract the last frame from Clip 1 and use it as the start frame for Clip 2
- How to have Clip 2 transition from Clip 1's ending to Clip 2's intended scene
- Three different approaches: Manual, Auto-Link, and Reference Images
- Best practices for prompts, aspect ratios, and visual consistency

---

## The Continuity Challenge

### Without Frame Continuity

When you generate videos independently, you get **jump cuts** between clips:

```
Clip 1: "Person walking in rain" → generates video from start frame
        Last frame: Person mid-stride in rain

Clip 2: "Person in moonlit clearing" → generates video from start frame
        First frame: Person standing in clearing

Result: JUMP CUT - Person instantly teleports from rain to clearing
```

### With Frame Continuity

When you use frame-to-frame continuity, transitions are smooth:

```
Clip 1: "Person walking in rain" → generates video
        Last frame: Person mid-stride in rain

Clip 2: Start frame = Clip 1's last frame
        Video prompt: "Person walks from rain into moonlit clearing"
        End frame: Person standing in moonlit clearing

Result: SMOOTH TRANSITION - Person seamlessly walks from rain to clearing
```

---

## How Frame-to-Frame Continuity Works

### The Three Key Elements

For each video clip, you can specify:

1. **Start Frame** (required): The image where the video begins
2. **Video Prompt** (required): Description of motion/action/transition
3. **End Frame** (optional): The image where the video ends

### Veo 3.1 "Frames to Video"

When you provide both a start frame and an end frame, Veo 3.1 uses its "Frames to Video" capability:

- **Interpolates** smoothly between the two frames
- **Follows the video prompt** for motion, camera movement, and action
- **Maintains visual consistency** throughout the transition
- **Duration**: 4, 6, or 8 seconds (fixed options)

### The Continuity Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ CLIP 1                                                      │
│ Start Frame: [person-in-rain.png]                          │
│ Video Prompt: "Person walking through heavy rain"          │
│ End Frame: [Optional - can leave empty]                    │
│ ↓                                                           │
│ Generate Video → clip1.mp4                                 │
│ System extracts: first_frame.png, last_frame.png          │
└─────────────────────────────────────────────────────────────┘
                         ↓
            (Use Clip 1's last_frame.png)
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ CLIP 2                                                      │
│ Start Frame: clip1_last_frame.png ← From Clip 1            │
│ Video Prompt: "Person walks toward moonlit clearing"       │
│ End Frame: [moonlit-clearing.png] ← Your scene goal        │
│ ↓                                                           │
│ Generate Video → clip2.mp4                                 │
│ (Veo 3.1 interpolates from Clip 1's end to your goal)     │
└─────────────────────────────────────────────────────────────┘
```

**Result**: Clip 2 starts exactly where Clip 1 ended, then smoothly transitions to Clip 2's desired scene based on the video prompt.

---

## Three Approaches to Continuity

ImageAI provides three ways to achieve frame-to-frame continuity, each with different levels of control and automation.

### Approach 1: Manual Frame Selection

**Best for**: Maximum control, specific artistic vision

**How it works**:
1. Generate Clip 1, system extracts last frame
2. Manually select Clip 1's last frame as Clip 2's start frame
3. Generate or load Clip 2's end frame
4. Write Clip 2's video prompt describing the transition
5. Generate Clip 2 video

**Pros**:
- Complete control over every frame
- Can review and adjust before committing
- Flexibility to use any frame as start/end

**Cons**:
- More manual steps
- Requires clicking through UI for each clip

---

### Approach 2: Auto-Link End Frames

**Best for**: Quick seamless sequences, automated workflows

**How it works**:
1. Enable "Auto-link end frames" in project settings
2. Generate all start frames for your clips first
3. When generating videos, system automatically:
   - Uses next clip's start frame as current clip's end frame
   - Veo 3.1 interpolates from current start to next start
4. Result: Each clip transitions directly to the next clip's starting point

**Pros**:
- One checkbox enables continuity for entire project
- Minimal manual intervention
- Perfect for sequential storytelling

**Cons**:
- Less control over intermediate frames
- Must have next clip's start frame ready

**Example**:
```
Auto-link enabled:

Clip 1: Start frame A → End frame = Clip 2's start frame B
        Video: Transitions from A to B

Clip 2: Start frame B → End frame = Clip 3's start frame C
        Video: Transitions from B to C

Result: A → B → C seamless sequence
```

---

### Approach 3: Reference Images for Style Continuity

**Best for**: Character/environment consistency across transitions

**How it works**:
1. Add up to 3 reference images per scene (or globally)
2. Reference images guide Veo 3 for:
   - Character appearance
   - Environment style
   - Lighting mood
3. Use reference images along with start/end frames
4. Veo 3 maintains visual consistency based on references

**Pros**:
- Maintains character/environment consistency
- Works with or without frame continuity
- Up to 3 references per scene for multi-aspect consistency

**Cons**:
- Doesn't guarantee exact frame matching
- More of a "style guide" than frame continuity

**Use case**:
- Reference 1: Main character's appearance
- Reference 2: Environment/location style
- Reference 3: Lighting/color palette
- Start frame: Clip 1's last frame
- End frame: Target scene for Clip 2

Result: Smooth transition with consistent character and environment

---

## Step-by-Step Workflows

### Workflow 1: Basic Manual Continuity

**Goal**: Create 2 clips with smooth transition

#### Step 1: Generate Clip 1

1. Open Video Project tab
2. Create Scene 1:
   - **Prompt**: "Person walking through heavy rain, dark clouds overhead"
   - Click **Generate** → Creates start frame image
3. Click **Generate Video** button for Scene 1
   - System generates clip1.mp4
   - **Automatically extracts**: `scene1_first_frame.png` and `scene1_last_frame.png`
   - Check the scene row - you'll see both frames extracted

#### Step 2: Use Clip 1's Last Frame for Clip 2

4. Create Scene 2:
   - **Start Frame**: Click the start frame button → "Select from scene images"
   - Navigate to Scene 1 → Select `scene1_last_frame.png`
   - This is now Scene 2's start frame (matches Clip 1's ending)

#### Step 3: Create Clip 2's End Frame

5. Still in Scene 2:
   - **Video Prompt**: "Person walks from rain into sunlit moonlit clearing, mist rising"
   - **End Prompt**: "Person standing in moonlit clearing, serene atmosphere"
   - Click **Generate** on end frame → Creates end frame image

#### Step 4: Generate Clip 2 Video

6. Click **Generate Video** for Scene 2
   - Veo 3.1 sees: Start frame (Clip 1's last frame) + End frame + Video prompt
   - Generates smooth transition video from rain → clearing

#### Result

- Clip 1 ends with person in rain
- Clip 2 starts with person in rain (same frame)
- Clip 2 transitions to person in clearing
- Final concatenated video: Seamless rain → clearing transition

---

### Workflow 2: Auto-Link for Full Project

**Goal**: Create 4-clip sequence with complete continuity

#### Step 1: Enable Auto-Link

1. Open project settings in Video tab
2. Check ☑ **"Auto-link end frames"**
3. Save settings

#### Step 2: Create All Scenes and Start Frames

4. Create 4 scenes with prompts:
   - Scene 1: "Person in city street at dawn"
   - Scene 2: "Person entering forest path"
   - Scene 3: "Person by mountain stream"
   - Scene 4: "Person watching sunrise from peak"

5. Generate start frames for ALL scenes first:
   - Click "Generate" on each scene's start frame
   - Wait for all 4 start frames to complete

#### Step 3: Generate Videos in Order

6. Generate videos sequentially (important: do in order):
   - Generate Scene 1 video
     - System auto-links: Scene 1 end frame = Scene 2 start frame
     - Video transitions from Scene 1 start → Scene 2 start

   - Generate Scene 2 video
     - System auto-links: Scene 2 end frame = Scene 3 start frame
     - Video transitions from Scene 2 start → Scene 3 start

   - Generate Scene 3 video
     - System auto-links: Scene 3 end frame = Scene 4 start frame
     - Video transitions from Scene 3 start → Scene 4 start

   - Generate Scene 4 video
     - No auto-link (last scene)
     - Can manually add end frame or leave as single-frame video

#### Step 4: Verify Continuity

7. Play videos in sequence:
   - Scene 1 ends where Scene 2 starts ✓
   - Scene 2 ends where Scene 3 starts ✓
   - Scene 3 ends where Scene 4 starts ✓

8. Export final concatenated video → No jump cuts!

---

### Workflow 3: Reference Images + Frame Continuity

**Goal**: Maintain character consistency while using frame continuity

#### Step 1: Set Up Global Reference Images

1. In Video Project, go to **Reference Images** section
2. Add up to 3 global references:
   - **Reference 1**: Portrait of main character
   - **Reference 2**: Environment style example
   - **Reference 3**: Lighting/color mood reference
3. Mark as **"Use for all scenes"**

#### Step 2: Create First Scene with References

4. Create Scene 1:
   - **Prompt**: "Character walking in rain, wearing red coat"
   - Generate start frame (Veo uses references for consistency)
   - Generate video → System extracts last frame

#### Step 3: Create Scene 2 with Frame + References

5. Create Scene 2:
   - **Start Frame**: Select Scene 1's last frame
   - **Video Prompt**: "Character walks from rain into warm café interior"
   - **End Prompt**: "Character sitting at café table, smiling"
   - Generate end frame (Veo uses references for character consistency)
   - Global references ensure character looks the same

#### Step 4: Generate and Verify

6. Generate Scene 2 video:
   - Start frame = Scene 1's end (frame continuity)
   - References = Character appearance (style continuity)
   - End frame = Café scene goal
   - Result: Smooth transition with consistent character

#### Benefits

- **Frame continuity**: No jump cuts between clips
- **Character consistency**: References keep character recognizable
- **Environment consistency**: References maintain style across scenes

---

### Workflow 4: Mixed Approach (Strategic Continuity)

**Goal**: Use continuity strategically, not for every transition

#### Rationale

Not every transition needs frame-to-frame continuity. Use it strategically:
- **Continuous action**: Person walking from A to B
- **Cause and effect**: Lightning strikes, then rain starts
- **Emotional flow**: Character's expression changes

Skip continuity for:
- **Scene changes**: Different location/time
- **Cut-aways**: Establishing shots
- **Parallel action**: Different characters

#### Example Project

**Scene 1**: Wide shot of city (no end frame, single-frame video)

**Scene 2**: Character walking in city
- Start frame: Generate fresh
- End frame: Use Scene 3's start frame (auto-link)
- Reason: Continuous walking action

**Scene 3**: Character entering building
- Start frame: Auto-linked from Scene 2
- End frame: Generate (interior shot)
- Reason: Complete the entrance action

**Scene 4**: Interior establishing shot (no end frame, new angle)

**Scene 5**: Character at desk
- Start frame: Generate fresh
- No end frame
- Reason: Scene change, no action continuity needed

#### Result

Strategic use of continuity where it matters, clean cuts where appropriate.

---

## Technical Implementation

### Scene Data Model

Each scene in ImageAI has these frame-related fields:

```python
class Scene:
    # Start frame (required for video)
    prompt: str                    # Start frame description
    images: List[ImageVariant]     # Generated start frame variants
    approved_image: Path           # Selected start frame for video

    # Video generation
    video_prompt: str              # Description of motion/action
    video_clip: Path               # Generated video

    # Frame extraction (automatic after video generation)
    first_frame: Path              # Extracted from video start
    last_frame: Path               # Extracted from video end

    # Veo 3.1 End Frame (optional)
    end_prompt: str                # End frame description
    end_frame_images: List         # Generated end frame variants
    end_frame: Path                # Selected end frame for video
    end_frame_auto_linked: bool    # True if using next scene's start

    # Veo 3 Reference Images (up to 3)
    reference_images: List[ReferenceImage]  # Scene-specific references
    use_global_references: bool    # Use project-level references
```

### How Video Generation Works

#### Without End Frame (Veo 3 - Current Behavior)

```python
# Scene has only start frame
if scene.end_frame is None:
    config = VeoGenerationConfig(
        model=VeoModel.VEO_3_GENERATE,
        prompt=scene.video_prompt,
        image=scene.approved_image,  # Start frame only
        duration=scene.duration_sec,
        aspect_ratio=project.style['aspect_ratio']
    )
    video = veo_client.generate_video(config)
```

Result: Animates the start frame according to video prompt.

#### With End Frame (Veo 3.1 - New Behavior)

```python
# Scene has both start and end frames
if scene.end_frame is not None:
    config = VeoGenerationConfig(
        model=VeoModel.VEO_3_GENERATE,
        prompt=scene.video_prompt,
        image=scene.approved_image,        # Start frame
        last_frame=scene.end_frame,        # End frame
        duration=scene.duration_sec,
        aspect_ratio=project.style['aspect_ratio']
    )
    video = veo_client.generate_video(config)
```

Result: Interpolates smoothly from start frame to end frame following video prompt.

#### With Reference Images

```python
# Scene uses reference images for consistency
config = VeoGenerationConfig(
    model=VeoModel.VEO_3_GENERATE,
    prompt=scene.video_prompt,
    image=scene.approved_image,
    last_frame=scene.end_frame,  # Optional
    reference_images=[ref.path for ref in scene.reference_images],  # Max 3
    duration=scene.duration_sec,
    aspect_ratio=project.style['aspect_ratio']
)
video = veo_client.generate_video(config)
```

Result: Video maintains visual consistency with reference images while interpolating frames.

### Auto-Link Logic

```python
def apply_auto_link(scene_index: int, scenes: List[Scene], auto_link_enabled: bool):
    """Apply auto-linking if enabled and next scene exists."""

    if not auto_link_enabled:
        return

    current_scene = scenes[scene_index]

    # Only auto-link if current scene has no manual end frame
    if current_scene.end_frame is not None:
        return

    # Check if next scene exists
    if scene_index + 1 >= len(scenes):
        return

    next_scene = scenes[scene_index + 1]

    # Use next scene's start frame as current scene's end frame
    if next_scene.approved_image is not None:
        current_scene.end_frame = next_scene.approved_image
        current_scene.end_frame_auto_linked = True
        logger.info(f"Auto-linked Scene {scene_index} end frame to Scene {scene_index+1} start frame")
```

### Frame Extraction (Automatic)

After video generation, ImageAI automatically extracts frames:

```python
def extract_frames_from_video(video_path: Path, scene_id: str) -> Tuple[Path, Path]:
    """Extract first and last frames from generated video."""

    import cv2

    cap = cv2.VideoCapture(str(video_path))

    # Extract first frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret, first = cap.read()
    first_frame_path = project_dir / f"{scene_id}_first_frame.png"
    cv2.imwrite(str(first_frame_path), first)

    # Extract last frame
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count - 1)
    ret, last = cap.read()
    last_frame_path = project_dir / f"{scene_id}_last_frame.png"
    cv2.imwrite(str(last_frame_path), last)

    cap.release()

    return first_frame_path, last_frame_path
```

These extracted frames become available for:
- Using as next scene's start frame
- Using as reference images
- Verification/review

---

## Best Practices

### 1. Aspect Ratio Consistency

**Critical**: Start and end frames MUST have the same aspect ratio.

```
✓ Good:
Start frame: 1920x1080 (16:9)
End frame: 1280x720 (16:9)  ← Same aspect ratio

✗ Bad:
Start frame: 1920x1080 (16:9)
End frame: 1080x1080 (1:1)  ← Different aspect ratio = ERROR
```

**Solution**: ImageAI validates aspect ratios before video generation and shows warnings.

### 2. Video Prompt Quality

When using start + end frames, your video prompt should describe the **transition**, not just the end state:

```
✗ Bad: "Person in moonlit clearing"
        (Describes destination, not journey)

✓ Good: "Person walks from rain through mist into moonlit clearing, camera follows"
        (Describes motion and transition)
```

### 3. Generate Start Frames First

When using auto-link:
1. Create all scenes
2. Generate ALL start frames first
3. Then generate videos in order

This ensures auto-link has next scene's start frame available.

### 4. Duration Considerations

Veo 3 supports **only 4, 6, or 8 seconds**:
- **4 seconds**: Quick transitions
- **6 seconds**: Standard, good for most transitions
- **8 seconds**: Longer, more gradual transitions

ImageAI automatically snaps to nearest valid duration.

### 5. Reference Images

When using reference images with frame continuity:
- **Max 3 references** per scene
- Use for: Character, Environment, Lighting
- References guide style, not exact frame matching
- Combine with start/end frames for best results

### 6. Testing Transitions

Before generating full project:
1. Test 2-3 scenes first
2. Verify continuity looks good
3. Adjust video prompts if needed
4. Then generate remaining scenes

### 7. Manual End Frames Override Auto-Link

If you manually set an end frame, it takes precedence over auto-link:

```
Scene 2:
- Auto-link enabled: Would use Scene 3's start frame
- You manually set end frame: Uses your manual frame instead
- Auto-link indicator: Shows it's manual, not auto-linked
```

### 8. Review Before Concatenation

Before exporting final video:
1. Play each scene video individually
2. Check that transitions look smooth
3. Verify no unexpected jump cuts
4. Adjust and regenerate if needed

---

## Troubleshooting

### Issue 1: Jump Cut Despite Using Continuity

**Symptoms**: Scene 2 starts with Scene 1's last frame, but there's still a visible jump.

**Causes**:
1. Video prompt doesn't describe transition
2. Aspect ratios don't match
3. Lighting/style too different between frames

**Solutions**:
- Review video prompt - should describe motion/transition
- Check aspect ratios match exactly
- Use reference images for style consistency
- Consider using intermediate scene

### Issue 2: Character Looks Different

**Symptoms**: Character appearance changes between clips despite using frame continuity.

**Causes**:
1. No reference images for character consistency
2. Start/end frames have different character poses/angles
3. Lighting changes too dramatic

**Solutions**:
- Add character reference image (global or scene-specific)
- Use reference images for all scenes with same character
- Keep lighting consistent in prompts
- Consider gradual lighting changes

### Issue 3: Auto-Link Not Working

**Symptoms**: Auto-link checkbox enabled, but end frames not auto-linking.

**Causes**:
1. Next scene doesn't have start frame yet
2. Current scene already has manual end frame
3. Generating videos out of order

**Solutions**:
- Generate all start frames first
- Clear manual end frame if you want auto-link
- Generate videos in sequential order (Scene 1, then 2, then 3...)

### Issue 4: Aspect Ratio Mismatch Error

**Symptoms**: Error when generating video: "Start and end frames have different aspect ratios"

**Causes**:
1. Start frame and end frame generated with different aspect ratio settings
2. Manually loaded end frame has different aspect ratio
3. Previous scene video has different aspect ratio

**Solutions**:
- Regenerate end frame with correct aspect ratio
- Check project settings - all scenes should use same aspect ratio
- If using extracted frame as start frame, ensure original video had correct aspect ratio

### Issue 5: Extracted Frames Not Appearing

**Symptoms**: After video generation, first_frame and last_frame not showing in UI.

**Causes**:
1. Frame extraction failed
2. Video file corrupted
3. FFmpeg/cv2 not installed

**Solutions**:
- Check logs for frame extraction errors
- Verify video plays correctly
- Ensure cv2 (OpenCV) is installed: `pip install opencv-python`
- Manually extract frames using external tool if needed

---

## Examples

### Example 1: Nature Transformation Sequence

**Goal**: Show season change from summer to winter.

#### Scene 1: Summer
- **Start Prompt**: "Lush green forest, sunlight streaming through leaves, vibrant colors"
- **Generate start frame**
- **Video Prompt**: "Camera slowly pans through forest, leaves gently swaying"
- **No end frame** (single-frame video)
- Duration: 6 seconds

#### Scene 2: Autumn Transition
- **Start Frame**: Scene 1's last frame (or generate fresh autumn start)
- **Video Prompt**: "Forest gradually transitions from green to golden autumn colors, leaves start falling"
- **End Prompt**: "Same forest now with golden and orange autumn foliage, some leaves on ground"
- **Generate end frame**
- Duration: 8 seconds

#### Scene 3: Winter
- **Start Frame**: Scene 2's end frame (auto-link enabled)
- **Video Prompt**: "Snow begins falling gently, covering the autumn forest, transition to winter"
- **End Prompt**: "Forest now covered in snow, winter atmosphere"
- **Generate end frame**
- Duration: 8 seconds

#### Result
Smooth seasonal transition: Summer → Autumn → Winter with natural progression.

---

### Example 2: Character Journey with References

**Goal**: Character walks from dark alley to bright street, maintaining appearance.

#### Setup
**Global References**:
- Ref 1: Character portrait (face, clothing)
- Ref 2: Urban environment style
- Ref 3: Cinematic lighting mood

#### Scene 1: Dark Alley
- **Start Prompt**: "Character in dark narrow alley, dim streetlight, dramatic shadows"
- **Generate start frame** (uses references)
- **Video Prompt**: "Character walks cautiously down dark alley, camera follows from behind"
- **No end frame**
- Duration: 6 seconds

#### Scene 2: Transition to Street
- **Start Frame**: Scene 1's last frame (manual selection)
- **Video Prompt**: "Character walks from dark alley into bright city street, light gradually increases"
- **End Prompt**: "Character emerging onto busy city street, bright daylight, people around"
- **Generate end frame** (uses references for character consistency)
- Duration: 8 seconds

#### Scene 3: City Street
- **Start Frame**: Scene 2's end frame (auto-link)
- **Video Prompt**: "Character walks confidently through busy street, camera follows, urban life around"
- Duration: 6 seconds

#### Result
- Frame continuity: Character's position flows naturally
- Reference images: Character looks the same throughout
- Smooth lighting transition: Dark → bright

---

### Example 3: Action Sequence

**Goal**: Chase scene with continuous action.

#### Scene 1: Chase Start
- **Start Prompt**: "Character running through warehouse, looking back, urgent expression"
- **Video Prompt**: "Character runs between warehouse shelves, camera tracks, dramatic lighting"
- Duration: 4 seconds (quick cut)

#### Scene 2: Door Exit
- **Start Frame**: Scene 1's last frame (auto-link)
- **Video Prompt**: "Character bursts through warehouse door into loading dock, momentum carries forward"
- **End Prompt**: "Character on loading dock, door swinging behind, ready to jump"
- Duration: 4 seconds

#### Scene 3: Jump
- **Start Frame**: Scene 2's end frame (auto-link)
- **Video Prompt**: "Character leaps from loading dock onto moving vehicle, action shot"
- Duration: 6 seconds

#### Result
Continuous action sequence with no breaks, feels like one shot.

---

### Example 4: Emotional Journey

**Goal**: Character's emotional state changes through scenes.

#### Scene 1: Sadness
- **Start Prompt**: "Person sitting alone on park bench, sad expression, overcast day"
- **Video Prompt**: "Person sits quietly, head down, wind blows gently"
- Duration: 6 seconds

#### Scene 2: Realization
- **Start Frame**: Generate fresh (new angle, same park)
- **Video Prompt**: "Person looks up, sees something off-frame, expression changes to hope"
- **End Prompt**: "Person standing, slight smile forming, posture more upright"
- Duration: 6 seconds

#### Scene 3: Joy
- **Start Frame**: Scene 2's end frame (manual selection to maintain pose)
- **Video Prompt**: "Person walks forward with growing confidence and smile, sun breaks through clouds"
- **End Prompt**: "Person in bright sunlight, full smile, reaching toward something"
- Duration: 8 seconds

#### Result
Emotional arc with strategic continuity for key moments, fresh angles for variety.

---

## Summary

### Key Takeaways

1. **Frame continuity** eliminates jump cuts by using previous clip's last frame as next clip's start frame
2. **Veo 3.1** enables smooth transitions from start frame → end frame with video prompt
3. **Three approaches**: Manual (control), Auto-Link (speed), References (consistency)
4. **Video prompts** should describe transitions, not just destinations
5. **Aspect ratios** must match between start and end frames
6. **Strategic use** is better than using continuity everywhere

### Quick Reference

| Scenario | Best Approach | Key Settings |
|----------|--------------|--------------|
| Full seamless sequence | Auto-Link | Enable auto-link checkbox |
| Specific artistic control | Manual | Select frames individually |
| Character consistency | References + Manual | Add character references |
| Quick action sequence | Auto-Link + 4-sec clips | Short durations, auto-link |
| Mixed pacing | Manual | Continuity where needed only |

### Next Steps

1. **Experiment**: Try 2-scene test with manual continuity first
2. **Test auto-link**: Enable for simple 3-4 scene project
3. **Add references**: Try character reference images for consistency
4. **Review**: Watch transitions, adjust prompts as needed
5. **Scale up**: Apply to larger projects once comfortable

---

**Document Status**: Complete guide for Veo 3 frame-to-frame continuity
**Last Updated**: 2025-10-19
**Related Docs**:
- `Veo3.1-FramesToVideo.md` - Feature implementation plan
- `veo_3_inspirational_continuity.md` - Inspirational short guide
- `Video-Tab-Guide.md` - Complete Video Tab documentation

**Questions?** Check the troubleshooting section or refer to Veo 3 API documentation.