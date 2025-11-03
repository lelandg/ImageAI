# Video Project FAQ

*Last Updated: 2025-11-02 14:42:25*

A comprehensive guide to creating videos with ImageAI's Video Project feature.

---

## Table of Contents

1. [Getting Started](#getting-started)
   - [Walk me through how to generate a video](#walk-me-through-how-to-generate-a-video-i-have-no-idea-where-to-begin)
2. [Project Management](#project-management)
   - [What is "New"?](#what-is-new)
   - [Do I type in a name and save after a video is made?](#do-i-type-in-a-name-and-save-after-a-video-is-made)
3. [Input and Content](#input-and-content)
   - [It says to input lyrics, but didn't you say it doesn't have audio?](#it-says-to-input-lyrics-but-didnt-you-say-it-doesnt-have-audio)
4. [Workflow Features](#workflow-features)
   - [How to use Workflow Guide?](#how-to-use-workflow-guide)
   - [How to use Storyboard?](#how-to-use-storyboard)
   - [Auto-generate video prompts?](#auto-generate-video-prompts)
5. [Advanced Features](#advanced-features)
   - [Auto-link refs?](#auto-link-refs)
   - [Enable Prompt Flow?](#enable-prompt-flow)
   - [How do I upload images and video?](#how-do-i-upload-images-and-video)
6. [Video Effects](#video-effects)
   - [What's Ken Burns Effect?](#whats-ken-burns-effect)
   - [Transitions?](#transitions)
   - [Smooth Transitions?](#smooth-transitions)
7. [Complete Walkthrough Example](#complete-walkthrough-example)

---

## Getting Started

### Walk me through how to generate a video. I have no idea where to begin.

Creating a video in ImageAI follows a structured workflow. Here's a step-by-step guide:

#### **Step 1: Open Video Project Tab**
1. Launch ImageAI
2. Navigate to the **Video Project** tab (look for the 🎬 icon)
3. The interface has three main areas:
   - **Left**: Workflow Guide (step-by-step instructions)
   - **Center**: Main workspace with input/storyboard
   - **Right**: Reference images and settings

#### **Step 2: Create or Open a Project**
Click **"New"** to start a new project. You'll be prompted to:
- Enter a project name (e.g., "My First Video")
- Choose a location to save project files
- The project will create a folder structure for all assets

#### **Step 3: Input Your Text/Lyrics**
In the **Text Input** area, paste or type your content. Three formats are supported:

**Format 1: Plain Text** (simplest)
```
My country, 'tis of thee
Sweet land of liberty
Of thee I sing
```

**Format 2: Timestamped Lyrics** (precise timing)
```
[00:00.50] My country, 'tis of thee
[00:03.20] Sweet land of liberty
[00:06.10] Of thee I sing
```

**Format 3: Structured Sections** (organized)
```
# Verse 1
My country, 'tis of thee
Sweet land of liberty

# Chorus
Of thee I sing
```

#### **Step 4: Generate Storyboard**
1. Click **"Generate Storyboard"** button
2. The system will:
   - Parse your text into individual scenes (one per line)
   - Calculate scene durations based on timing
   - Create initial image generation prompts
3. Review the storyboard table showing each scene

#### **Step 5: Enhance Prompts (Optional but Recommended)**
1. In the **LLM Provider** dropdown, select an AI provider:
   - **OpenAI** (GPT-4, GPT-3.5) - Excellent quality
   - **Anthropic** (Claude 3) - Creative descriptions
   - **Google** (Gemini) - Good balance
   - **Ollama** (Local) - Free but requires local setup
2. Choose a **Prompt Style** (Cinematic, Artistic, Photorealistic, etc.)
3. Click **"Enhance Prompts"** to use AI to improve descriptions
4. This transforms simple text like "sweet land" into rich descriptions like:
   - *"Wide cinematic shot of rolling green hills at golden hour, American flag waving gently, warm nostalgic lighting, photorealistic style"*

#### **Step 6: Generate Video Prompts**
1. Select your **Image Provider** (Gemini, OpenAI, etc.)
2. Click **"Generate Video Prompts"**
3. The system will:
   - Generate enhanced prompts for Veo video generation
   - Add camera movements (pan, zoom, tilt)
   - Include continuity instructions between scenes
4. Review and edit the generated video prompts

#### **Step 7: Generate Visuals**
You have two options:

**Option A: Generate Images** (faster, cheaper)
1. Click **"Generate Images"** button
2. Select number of variants per scene (1-4)
3. Wait for image generation (30 seconds to a few minutes)
4. Review thumbnails and select your favorite for each scene

**Option B: Generate Video Clips with Veo** (higher quality, more expensive)
1. Click **"Generate Video Clips"**
2. Veo will create 4-8 second video clips with motion
3. Generation takes 1-6 minutes per scene
4. Review and approve video clips

#### **Step 8: Add Audio (Optional)**
1. Click **"Browse"** next to **Audio Track**
2. Select an MP3, WAV, or M4A file
3. The audio will be linked (not copied) to your project
4. Adjust volume with the slider if needed

#### **Step 9: Export Video**
1. Click **"Render Video"** button
2. Choose output format:
   - **Slideshow (FFmpeg)**: Images with Ken Burns effect and transitions
   - **Veo Video**: Concatenated video clips
3. Wait for rendering (1-10 minutes depending on length)
4. Your video is saved in the project's `exports/` folder!

**That's it!** You've created your first video. The Workflow Guide on the left will track your progress through these steps.

---

## Project Management

### What is "New"?

The **"New"** button creates a brand new video project from scratch. Here's what happens:

1. **Project Creation Dialog**: Opens a dialog where you:
   - Enter a project name (e.g., "Summer Vacation 2025")
   - Choose where to save the project folder
   - Optionally set initial configuration

2. **Folder Structure**: Creates organized directories:
   ```
   My Project/
   ├── project.iaproj.json      # Project settings and scene data
   ├── assets/
   │   ├── scene-001/           # Images for first scene
   │   ├── scene-002/           # Images for second scene
   │   └── reference/           # Reference images
   ├── exports/                 # Rendered videos
   └── logs/                    # Generation logs
   ```

3. **Clean Slate**: Starts with:
   - Empty text input area
   - No scenes in storyboard
   - Default settings
   - Fresh workflow guide

**When to use "New":**
- Starting a completely different video project
- Want to try different lyrics/content
- Need a fresh start without old settings

**Tip**: You can have multiple projects. Use "Open" to switch between them later.

---

### Do I type in a name and save after a video is made?

**Short answer**: No, you name the project **before** making the video, and it auto-saves throughout the process.

**Detailed explanation**:

#### When You Name the Project
- When clicking **"New"**, you're immediately prompted for a project name
- This creates the project folder and saves the initial project file
- Example: Naming it "My Country Video" creates folder `My Country Video/`

#### Auto-Save Behavior
The project automatically saves after major actions:
- ✅ After generating storyboard
- ✅ After enhancing prompts
- ✅ After generating each image/video
- ✅ After approving variants
- ✅ After adding audio
- ✅ After exporting video

You'll see a brief "Project saved" notification in the status bar.

#### Manual Save
You can also manually save anytime:
- Click **"Save"** button in the toolbar
- Or use keyboard shortcut: **Ctrl+S** (Windows/Linux) or **Cmd+S** (Mac)

#### Renaming a Project
To rename an existing project:
1. Click **"Project Settings"** button (gear icon)
2. Change the **Project Name** field
3. Click **"Save"** - the folder remains the same, but internal name updates

**Important**: The project file (`.iaproj.json`) stores everything:
- Your input text
- All scene data and prompts
- Image/video file paths
- Audio track links
- Settings and configuration

So you can close ImageAI, come back later, and click **"Open"** to resume exactly where you left off!

---

## Input and Content

### It says to input lyrics, but didn't you say it doesn't have audio?

Great question! This is a common point of confusion. Let me clarify:

#### What "Lyrics" Means Here
The **"Input Lyrics"** field is just a label - it accepts **any text**, not just song lyrics:
- 📝 **Lyrics** (song/poem lines)
- 📖 **Story narration** ("Once upon a time...")
- 🎬 **Script lines** (dialogue or scene descriptions)
- 📋 **Plain descriptions** ("Sunset over mountains", "Cat playing with yarn")
- 🗣️ **Quotes or phrases** (motivational quotes, proverbs)

Think of it as: **"What do you want your video to visualize?"**

#### Why It Says "Lyrics"
The feature was originally designed for music videos, hence "lyrics." But it works for any sequential text content!

#### Audio is Optional
You have **two separate options**:

**Option 1: Silent Video**
- Input text → Generate images/videos → Export video
- Result: Silent video with visual scenes
- Great for: Social media posts, presentations, silent storytelling

**Option 2: Video with Audio**
- Input text → Generate images/videos → Add audio file → Export video
- Result: Video synchronized with music/narration
- Great for: Music videos, lyric videos, narrated stories

#### How They Work Together

**Scenario A: Lyrics WITH Audio**
```
Input text:         [00:00] Sweet land of liberty
                    [00:04] Of thee I sing

Add audio file:     sweet-land.mp3

Result:             Video shows visuals synced to the music track,
                    with optional text overlays of the lyrics
```

**Scenario B: Descriptive Text WITHOUT Audio**
```
Input text:         Sunset over calm ocean
                    Waves gently rolling in
                    Seagulls flying overhead

No audio file

Result:             Silent video showing these three scenes
                    Can add music later in video editor
```

**Scenario C: Story WITH Narration**
```
Input text:         Once upon a time in a small village
                    There lived a curious young explorer
                    Who dreamed of distant lands

Add audio file:     narration.mp3 (your voice reading the story)

Result:             Video shows scenes while your narration plays
```

#### Best Practices

**For Music Videos:**
1. Paste the lyrics as they appear in the song
2. Use timestamped format if you want precise sync
3. Add your audio track (MP3, WAV, etc.)
4. The video will match the music's timing

**For Other Content:**
1. Write descriptive phrases (one per scene)
2. Don't worry about timestamps unless you have audio
3. Choose a timing preset (Fast/Medium/Slow) for scene durations
4. Leave audio empty for silent video

**Pro Tip**: You can always add audio later! Generate the video first, then:
- Use video editing software (DaVinci Resolve, Premiere, etc.) to add music
- Or regenerate in ImageAI with an audio file added

The "lyrics" field is really just **"your text content"** - call it whatever you like! 🎵📝🎬

---

## Workflow Features

### How to use Workflow Guide?

The **Workflow Guide** is your step-by-step companion throughout the video creation process. It appears on the **left side** of the Video Project workspace and acts like a smart checklist.

#### What It Does

**1. Shows Your Progress**
- Displays all workflow steps with status indicators:
  - ○ **Not Started** (empty circle)
  - ◐ **In Progress** (half-filled circle)
  - ● **Completed** (filled circle)
  - ─ **Skipped** (optional steps you skipped)

**2. Tracks Current Step**
- Current step is **highlighted in blue**
- Title is **bold** for easy identification
- Shows percentage complete at the top (e.g., "Progress: 60%")

**3. Provides Contextual Help**
- Hover over any step to see a tooltip with description
- Click on a step to see detailed help text
- Shows estimated time for each step (e.g., "~2-5 minutes")

#### The Workflow Steps

The guide follows this sequence:

| Step | Title | Required? | Description |
|------|-------|-----------|-------------|
| 1 | **Input Text/Lyrics** | Required | Add your content that will become video scenes |
| 2 | **MIDI File** | Optional | Upload MIDI for precise music synchronization |
| 3 | **Audio Track** | Optional | Add background music or narration |
| 4 | **Generate Storyboard** | Required | Parse text into scenes with timing |
| 5 | **Enhance Prompts** | Optional | Use AI to improve scene descriptions |
| 6 | **Generate Media** | Required | Create images or video clips |
| 7 | **Review & Approve** | Required | Select best variants for each scene |
| 8 | **Export Video** | Required | Render final video output |

#### How to Use It

**Following the Guide (Recommended for Beginners)**
1. Start at Step 1 (Input Text)
2. Complete each step in order
3. Watch the progress bar fill as you go
4. Skip optional steps if you don't need them

**Jumping Around (For Experienced Users)**
- Click any **completed** step to review it
- You can go back and edit previous steps
- Changes will update dependent steps automatically

**Getting Help for Current Step**
1. Look at the **"Current Step"** panel below the step list
2. Read the description of what you need to do
3. Click **"? Show Help"** button for detailed instructions
4. Follow the action button prompt (e.g., "Generate Storyboard")

**Using Action Buttons**
Each step shows relevant action buttons:
- **Step 1 (Input Text)**: "Continue" button appears when you've entered text
- **Step 4 (Generate Storyboard)**: "Generate Storyboard" button activates
- **Step 5 (Enhance Prompts)**: Shows LLM provider selection and "Enhance" button
- **Step 6 (Generate Media)**: "Generate Images" or "Generate Video Clips" options

**Skipping Optional Steps**
For optional steps (MIDI, Audio, Enhance Prompts):
- Click **"Skip"** button to mark as skipped
- The guide moves to the next required step
- You can always go back later if you change your mind

#### Example Usage Flow

```
Start Video Project
↓
1. ● Input Text/Lyrics [COMPLETED]
   - You pasted your lyrics
↓
2. ─ MIDI File [SKIPPED]
   - Clicked "Skip" - no MIDI file available
↓
3. ◐ Audio Track [IN PROGRESS] ← YOU ARE HERE
   - Current step highlighted
   - Panel shows: "Upload audio file (MP3, WAV, etc.)"
   - Action: Click "Browse" to select audio
↓
4. ○ Generate Storyboard [NOT STARTED]
   - Waiting for you to complete audio
   - Or skip audio to proceed
```

#### Pro Tips

**Resume Anytime**: The guide remembers your progress. If you:
- Close ImageAI and reopen the project
- Switch to another project and come back
- The guide automatically detects what's done and picks up where you left off

**Non-Linear Workflow**: You don't HAVE to follow in order:
- Generate storyboard first, add audio later
- Skip prompt enhancement initially, enhance later after seeing results
- Generate images, go back and adjust prompts, regenerate

**Status Indicators**: Watch for:
- **Green checkmark** in status bar = step auto-completed successfully
- **Red X** = error occurred (click "Show Help" for troubleshooting)
- **Yellow warning** = optional action recommended but not required

**Help Text Details**: Each step's help includes:
- What this step does
- Why it's important (or why it's optional)
- What happens if you skip it
- Best practices and tips

The Workflow Guide is designed to eliminate confusion and ensure you don't miss critical steps. Use it as much or as little as you need!

---

### How to use Storyboard?

The **Storyboard** is the heart of your video project - it's where you see, edit, and manage all your scenes. Think of it as a timeline view showing everything that will appear in your final video.

#### Where to Find It

After clicking **"Generate Storyboard"**, a table appears in the center workspace showing all your scenes.

#### Storyboard Table Columns

| Column | Description | Editable? |
|--------|-------------|-----------|
| **#** | Scene number (1, 2, 3...) | No (auto) |
| **Source** | Original text from your input | No |
| **Prompt** | Description for image generation | **Yes** ✏️ |
| **Duration** | Length of scene in seconds (e.g., 4.5s) | **Yes** 🔢 |
| **Thumbnails** | Preview images (if generated) | Visual only |
| **Actions** | Buttons for operations | Clickable |

#### Viewing and Understanding Scenes

**Scene Information Display**
Each row shows:
- Original text you entered
- Current generation prompt (enhanced or basic)
- How long this scene will appear in video
- Preview thumbnails of generated images (after generation)

**Duration Indicators**
- Green text = Good duration (3-8 seconds)
- Orange text = Short duration (< 3 seconds)
- Red text = Very long duration (> 10 seconds)

Total video duration shown at bottom: "Total Duration: 2:45"

#### Editing Scene Prompts

**Direct Editing**
1. **Double-click** the prompt cell
2. Edit the text directly
3. Press **Enter** to save or **Esc** to cancel
4. Changes are auto-saved

**Prompt Enhancement**
1. Right-click on a scene row
2. Select "Enhance This Prompt" from context menu
3. Choose LLM provider and style
4. System generates improved description
5. Accept or continue editing manually

**Best Practices for Prompts**
- Be specific: "elderly man on porch, golden hour lighting" vs. "old person outside"
- Include style keywords: "cinematic", "photorealistic", "oil painting style"
- Mention camera angles: "wide shot", "close-up", "bird's eye view"
- Add mood/atmosphere: "nostalgic", "dramatic", "peaceful", "energetic"

Example Transformation:
```
Before: "Sweet land of liberty"
After:  "Sweeping aerial view of American farmland at sunset,
         golden wheat fields, small rural town in distance,
         warm nostalgic lighting, cinematic composition"
```

#### Adjusting Scene Duration

**Method 1: Direct Edit**
1. Click the duration cell (shows "4.5s")
2. Enter new duration in seconds (e.g., "6.0")
3. Press Enter to save

**Method 2: Duration Slider**
1. Click on the scene to select it
2. Use the duration slider in the sidebar
3. Drag left (shorter) or right (longer)
4. Duration updates in real-time

**Method 3: MIDI Sync** (if using MIDI file)
- Durations auto-calculated from MIDI timing
- Scenes snap to musical measures/beats
- Manual adjustments override auto-sync

**Tips for Good Duration**:
- **Still images**: 3-6 seconds (too short feels rushed, too long gets boring)
- **Veo video clips**: 4-8 seconds (Veo's native duration range)
- **Complex scenes**: 5-8 seconds (give viewers time to absorb details)
- **Transition scenes**: 2-4 seconds (quick cuts between locations)

#### Reordering Scenes

**Drag and Drop** (easiest):
1. Click and hold on a scene row's number column
2. Drag up or down
3. Drop between other scenes
4. Scene numbers automatically renumber

**Cut/Paste**:
1. Right-click on scene → **"Cut"**
2. Click where you want to move it
3. Right-click → **"Paste"**

**Move Up/Down Buttons**:
- Select a scene
- Click ⬆️ "Move Up" or ⬇️ "Move Down" buttons
- Scene shifts one position

#### Managing Multiple Variants

After generating images, each scene can have multiple variants (typically 3-4 per scene).

**Viewing Variants**:
- Thumbnails appear in the "Thumbnails" column
- Hover over a thumbnail for larger preview
- Click thumbnail to open full-size view

**Selecting Best Variant**:
1. Click a thumbnail to view full-size
2. Navigate between variants with arrow buttons
3. Click **"Approve"** button (or green checkmark ✓)
4. Selected variant gets a green border
5. Only approved variants are used in final video

**Regenerating a Scene**:
1. Right-click on scene → **"Regenerate Images"**
2. System generates new variants with same prompt
3. Previous variants are kept (not deleted)
4. Select new favorite or stick with original

#### Scene Actions Menu

Right-click any scene to see options:

| Action | What It Does |
|--------|-------------|
| **Edit Prompt** | Open prompt in text editor |
| **Enhance Prompt** | Use AI to improve description |
| **Copy Prompt** | Copy to clipboard |
| **Duplicate Scene** | Create copy of this scene |
| **Delete Scene** | Remove from storyboard |
| **Regenerate Images** | Generate new variants |
| **Set as Reference** | Use image as style reference for other scenes |
| **Move Up/Down** | Change scene order |

#### Storyboard Toolbar Buttons

At the top of the storyboard:

- **📝 Add Scene**: Insert blank scene (type prompt manually)
- **🗑️ Delete Selected**: Remove checked scenes
- **📋 Copy All Prompts**: Copy all prompts to clipboard (useful for backup)
- **♻️ Regenerate All**: Re-generate images for all scenes
- **💾 Export Storyboard**: Save as PDF or spreadsheet for review

#### Working with the Storyboard

**Typical Workflow**:
1. **Generate Initial Storyboard**: Creates scenes from your text
2. **Review Prompts**: Read through, check for accuracy
3. **Enhance if Desired**: Use AI to improve descriptions
4. **Adjust Durations**: Make sure timing feels right
5. **Generate Images/Videos**: Create visuals
6. **Review Thumbnails**: Look at all variants
7. **Approve Favorites**: Select best for each scene
8. **Fine-tune**: Edit prompts, regenerate if needed
9. **Final Review**: Watch preview or check total duration
10. **Export Video**: Render final output

**Keyboard Shortcuts**:
- **Ctrl+C**: Copy selected scene prompt
- **Ctrl+V**: Paste prompt
- **Delete**: Remove selected scene
- **↑/↓ Arrow Keys**: Navigate between scenes
- **Enter**: Edit selected scene prompt
- **Space**: Toggle variant selection

The storyboard is your command center - spend time here getting everything just right before final export!

---

### Auto-generate video prompts?

**"Auto-generate video prompts"** is a powerful feature that transforms your storyboard's image prompts into **video-optimized prompts** specifically designed for Veo video generation.

#### What Are Video Prompts?

**Image Prompts** (what you start with):
- Describe a **static scene**
- Focus on composition, lighting, subjects
- Example: *"Elderly man on wooden porch, golden hour lighting, American flag"*

**Video Prompts** (what you need for Veo):
- Describe **motion and camera movement**
- Include continuity between scenes
- Add temporal elements (how things change over time)
- Example: *"Camera slowly zooms in on elderly man on wooden porch, gentle breeze moves the American flag, warm golden hour light shifts as clouds pass, man takes a sip of coffee, subtle facial expression of nostalgia, 6 seconds"*

#### Why You Need Video Prompts

Veo (Google's video generation AI) creates **moving video clips**, not just still images. To get good results, prompts need:

1. **Camera Movement**: Pan, tilt, zoom, tracking shots
2. **Subject Motion**: What moves and how
3. **Continuity**: Connection between consecutive scenes
4. **Timing**: Match scene durations (4-8 seconds for Veo)
5. **Style Consistency**: Maintain visual style throughout

#### How to Use Auto-Generate

**Step 1: Generate Your Storyboard**
- Input your text/lyrics
- Click "Generate Storyboard"
- Optional: Enhance prompts with LLM for better base descriptions

**Step 2: Access Video Prompt Generation**
1. Look for the **"Generate Video Prompts"** button
2. Located in the storyboard toolbar or workflow guide
3. Ensure you have at least one scene in your storyboard

**Step 3: Configure Settings**

Before generating, set:

**LLM Provider Selection**:
- Choose which AI will generate prompts:
  - **OpenAI GPT-4**: Best quality, most creative camera movements
  - **Anthropic Claude**: Excellent at continuity and storytelling
  - **Google Gemini**: Good understanding of Veo's capabilities
  - **Ollama (Local)**: Free but lower quality

**Style Preset**:
- **Cinematic**: Film-like camera movements, dramatic shots
- **Documentary**: Natural, observational camera work
- **Music Video**: Dynamic cuts, rhythm-based movement
- **Artistic**: Creative, unconventional camera techniques

**Continuity Options**:
- **Enable Auto-Link**: Automatically reference previous scene's ending in next scene's beginning
- **Character Consistency**: Maintain same character appearance across scenes
- **Environment Consistency**: Keep location/setting details consistent

**Step 4: Generate**
1. Click **"Generate Video Prompts"**
2. System processes all scenes in batch (efficient, one API call)
3. Progress bar shows completion
4. Each scene's prompt is replaced with video-optimized version

**Step 5: Review Results**

Each video prompt now includes:

**Camera Direction**:
- "Camera starts wide, slowly pushes in"
- "Tracking shot following the subject"
- "Overhead crane shot descending"

**Motion Description**:
- "Character walks from left to right"
- "Wind gently rustles leaves"
- "Clouds move across the sky"

**Temporal Changes**:
- "Lighting gradually shifts from warm to cool"
- "Subject's expression changes from sad to hopeful"

**Scene Duration**:
- Adjusted to valid Veo durations (4, 6, or 8 seconds)
- Respects MIDI timing if available

**Continuity References**:
- "Continuing from previous scene's farmhouse, camera pulls back..."
- "Same character as before, now seen from behind..."

#### Example Transformation

**Before (Image Prompt)**:
```
Scene 1: "Elderly man on porch, American flag, golden hour"
Scene 2: "Farmland, wheat fields, sunset"
Scene 3: "Small town main street, evening"
```

**After (Video Prompts with Auto-Link)**:
```
Scene 1: "Slow dolly-in shot on elderly man sitting peacefully on
wooden porch. American flag waves gently in breeze on porch post.
Golden hour sunlight creates long shadows. Man gazes thoughtfully
at distant horizon. Duration: 6 seconds. Cinematic composition."

Scene 2: "Aerial shot rising from farmhouse porch (continuing from
previous scene) revealing vast wheat fields in golden hour light.
Camera sweeps forward over gently swaying wheat. Same warm color
palette as Scene 1. Distant farmhouses visible. Setting sun on
horizon. Duration: 6 seconds."

Scene 3: "Tracking shot gliding down quiet small-town main street.
Evening light matches previous sunset scene. Old brick buildings,
vintage storefronts. A few people walking. American flags on lamp
posts echo Scene 1. Camera moves steadily forward, slight upward
tilt at end. Duration: 6 seconds."
```

Notice how Scene 2 references Scene 1's ending, and Scene 3 maintains visual continuity!

#### Advanced Options

**Manual Override**:
- After auto-generation, you can still edit any prompt
- Changes won't affect other scenes unless you regenerate

**Per-Scene Regeneration**:
- Right-click a scene → "Regenerate Video Prompt"
- Only that scene's prompt is regenerated
- Useful for fine-tuning one scene

**Custom Instructions**:
- Add a "System Prompt" field with global instructions
- Example: "All scenes should have vintage 1960s film aesthetic"
- Applied to all auto-generated prompts

**Camera Movement Library**:
Some systems include preset camera movements:
- **Push In**: Camera moves toward subject (emotional intensity)
- **Pull Back**: Reveals more of scene (context, isolation)
- **Pan Left/Right**: Follows action or shows environment
- **Tilt Up/Down**: Reveals scale or shifts focus
- **Orbit**: Circles around subject (360° view)
- **Tracking**: Follows moving subject smoothly

#### Best Practices

**Do Auto-Generate When**:
- ✅ You want professional-looking camera work
- ✅ You need consistency between scenes
- ✅ You're new to video prompt writing
- ✅ You want to save time vs. manual writing

**Edit Manually When**:
- ✏️ Auto-generated camera movement doesn't match your vision
- ✏️ You want specific technical shots (Dutch angle, whip pan, etc.)
- ✏️ Continuity references are incorrect
- ✏️ Duration doesn't match your music

**Tips for Best Results**:
1. **Start with enhanced image prompts**: Better input = better video prompts
2. **Use MIDI timing if available**: Ensures durations work with music
3. **Review continuity**: Make sure scene transitions make sense
4. **Test generate one scene first**: Check quality before batch generation
5. **Keep reference images**: Upload example frames for style consistency

#### Troubleshooting

**Problem**: Generated prompts are too generic
- **Solution**: Use GPT-4 or Claude instead of Gemini/local models
- **Solution**: Add more detail to your original image prompts first

**Problem**: Camera movements are too fast/jarring
- **Solution**: Add instruction: "Slow, smooth camera movements only"
- **Solution**: Manually edit to "gentle" or "gradual" movements

**Problem**: Continuity breaks between scenes
- **Solution**: Enable "Auto-Link Refs" option
- **Solution**: Manually add continuity in system prompt

**Problem**: Veo generation fails with these prompts
- **Solution**: Prompts may be too long (Veo has character limit)
- **Solution**: Simplify by removing some details

Auto-generation is a huge time-saver! Even if you edit the results, it provides an excellent starting point for video-optimized prompts.

---

## Advanced Features

### Auto-link refs?

**"Auto-link refs"** (short for "auto-link references") is a continuity feature that helps create visual consistency between consecutive scenes by automatically referencing elements from previous scenes.

#### What Problem Does It Solve?

When generating videos scene-by-scene, each scene is created independently. This can lead to:
- ❌ Character appearance changes (different clothing, age, features)
- ❌ Location inconsistencies (different architecture, colors)
- ❌ Style shifts (realistic → cartoon → painting)
- ❌ Jarring transitions (no visual connection between scenes)

**Auto-link refs** solves this by making each scene aware of what came before it.

#### How It Works

**Without Auto-Link** (each scene is isolated):
```
Scene 1: "Man on porch" → Generates older man, blue shirt, gray hair
Scene 2: "Man walking" → Generates younger man, red shirt, brown hair
Scene 3: "Man in town" → Generates different man, green shirt, no hair
```
Result: Looks like three different people! 😕

**With Auto-Link Refs Enabled**:
```
Scene 1: "Man on porch" → Generates older man, blue shirt, gray hair
Scene 2: "Man walking" → References Scene 1's man → Same man, blue shirt, gray hair
Scene 3: "Man in town" → References Scene 2's man → Consistent appearance maintained
```
Result: Same character throughout! 👍

#### Types of References

The system can auto-link several types of elements:

**1. Character References**
- Appearance (age, gender, clothing, hair, features)
- Props they're holding
- Body language/posture

**2. Environment References**
- Location (same house, town, landscape)
- Lighting conditions (maintain time of day)
- Weather (if it's raining in Scene 1, continue in Scene 2)

**3. Style References**
- Art style (photorealistic, animated, oil painting)
- Color palette (warm sunset tones, cool blue night)
- Camera characteristics (vintage film grain, modern crisp)

**4. Objects/Props**
- Vehicles (same car throughout)
- Buildings (architectural details)
- Background elements (flags, trees, furniture)

#### How to Enable Auto-Link Refs

**Method 1: Global Setting** (Recommended)
1. In the **Video Project Settings**
2. Find **"Continuity"** section
3. Check ☑️ **"Auto-link references between scenes"**
4. Choose what to link:
   - ☑️ Characters
   - ☑️ Environment
   - ☑️ Style
   - ☑️ Props/Objects

**Method 2: During Video Prompt Generation**
1. When clicking **"Generate Video Prompts"**
2. Dialog appears with options
3. Enable **"Auto-link references"** checkbox
4. System automatically includes continuity in prompts

**Method 3: Per-Scene Manual**
1. Right-click on a scene in storyboard
2. Select **"Link to Previous Scene"**
3. Choose what to reference from dropdown
4. Manually edit prompt to include reference

#### What Gets Added to Prompts

Auto-link refs work by modifying your video prompts to include explicit continuity instructions.

**Example 1: Character Continuity**

Original Scene 2 Prompt:
```
"Man walking down country road at sunset"
```

With Auto-Link Refs:
```
"Same elderly man from previous scene (gray hair, denim overalls,
weathered face) now walking down country road at sunset. Maintains
same character appearance and clothing. Continues the nostalgic mood."
```

**Example 2: Environment Continuity**

Original Scene 3 Prompt:
```
"Downtown main street in evening"
```

With Auto-Link Refs:
```
"Downtown main street of the same small rural town from previous scene.
Same architectural style, warm evening lighting matching earlier sunset.
Continuing same color palette and atmosphere."
```

**Example 3: Style Continuity**

Original Scene 4 Prompt:
```
"Children playing in park"
```

With Auto-Link Refs:
```
"Children playing in park, shot in same cinematic style as previous
scenes: photorealistic, warm golden hour lighting, vintage 1960s
film aesthetic, Kodachrome color palette."
```

#### Advanced: Reference Images

For even better continuity, combine auto-link refs with **reference images**:

**How It Works**:
1. Generate Scene 1's image/video
2. System saves Scene 1's image as reference
3. When generating Scene 2, includes reference image
4. AI sees the visual style and matches it

**Example Workflow**:
```
Scene 1: Generate → Beautiful sunset image created
         ↓
Scene 2: Auto-link refs + Use Scene 1 image as reference
         → Generates scene matching Scene 1's lighting and style
         ↓
Scene 3: Auto-link refs + Use Scene 2 image as reference
         → Continues the consistent look
```

This creates a **visual through-line** across your entire video!

#### Configuration Options

**Continuity Strength**:
- **Weak** (25%): Subtle hints, allows variation
- **Medium** (50%): Balanced consistency and creativity
- **Strong** (75%): Very consistent, less variation
- **Strict** (100%): Maximum consistency, may reduce creativity

**Linking Strategy**:
- **Previous Scene Only**: Each scene references the one before it
- **First Scene Reference**: All scenes reference Scene 1 (ensures everyone matches start)
- **Key Frame References**: Scenes reference designated "anchor" scenes (Scene 1, 5, 10...)

**Selective Linking**:
Choose which elements to link per scene:
```
Scene 2: Link character ☑️, environment ☐
Scene 3: Link character ☑️, environment ☑️, style ☐
Scene 4: Link character ☐, environment ☐, style ☑️
```

#### When to Use Auto-Link Refs

**✅ Use When**:
- You have recurring characters
- Scenes are part of one continuous narrative
- Maintaining location/environment across multiple scenes
- Creating a cohesive visual style throughout video
- Generating long videos (20+ scenes)

**❌ Don't Use When**:
- Each scene is intentionally different (montage of unrelated clips)
- You want variety in each scene
- Scenes jump between different times/places
- Creating abstract/experimental video
- Very short video (3-5 scenes) where variation is fine

#### Troubleshooting

**Problem**: References are too strict, scenes look repetitive
- **Solution**: Lower continuity strength to 25-50%
- **Solution**: Disable some reference types (keep character, unlink environment)
- **Solution**: Manually edit prompts to add variety

**Problem**: References not working, scenes still inconsistent
- **Solution**: Increase continuity strength to 75-100%
- **Solution**: Use reference images in addition to text descriptions
- **Solution**: Be more specific in Scene 1 (details to carry forward)

**Problem**: Scene 5 references Scene 4, but Scene 4 was wrong
- **Solution**: Regenerate Scene 4 first
- **Solution**: Change linking strategy to reference Scene 1 instead
- **Solution**: Manually edit Scene 5 prompt to fix incorrect reference

**Problem**: Auto-linked prompts are too long for Veo
- **Solution**: Enable "Concise Mode" to shorten references
- **Solution**: Manually trim prompts after generation

#### Pro Tips

**1. Set Up Scene 1 Carefully**: This becomes the anchor for everything else. Make sure:
- Character appearance is exactly what you want
- Environment is well-defined
- Style is clearly established

**2. Use Reference Library**: Create a reference library of:
- Character design sheets (different angles of main character)
- Location reference images
- Style guide images
You can then link to these throughout

**3. Mix Auto and Manual**:
- Let auto-link handle basics (character, environment)
- Manually add creative elements unique to each scene

**4. Test Early**: Generate first 3 scenes to see if continuity works. Adjust settings before generating all 50 scenes!

**5. Anchor Points**: For long videos, designate certain scenes as "anchors":
- Scene 1: Main character introduced
- Scene 10: New location established
- Scene 20: Style shift (flashback, dream sequence)
Later scenes can reference these anchors

Auto-link refs is powerful but can be confusing at first. Start with default settings, then tune as needed!

---

### Enable Prompt Flow?

**"Enable Prompt Flow"** is an advanced workflow option that changes how scene prompts are generated from a **static batch process** to a **dynamic, flowing sequence** that considers narrative progression and emotional arc.

#### Static vs. Flow Mode

**Static Mode (Default)**:
```
Scene 1: [Generate prompt based on Line 1]
Scene 2: [Generate prompt based on Line 2]
Scene 3: [Generate prompt based on Line 3]
```
Each scene is generated independently using only its source text.

**Flow Mode**:
```
Scene 1: [Generate based on Line 1]
         ↓ (considers Scene 1's ending)
Scene 2: [Generate based on Line 2 + Scene 1 context]
         ↓ (considers Scene 1-2 arc)
Scene 3: [Generate based on Line 3 + Scenes 1-2 context]
```
Each scene is aware of what came before, creating narrative momentum.

#### What Prompt Flow Does

**1. Narrative Continuity**
Ensures the story flows logically:
- Scene 1 establishes setting → Scene 2 continues in that setting
- Scene 2 ends with character looking right → Scene 3 shows what they're looking at
- Scene 5 is climax → Scene 6 is resolution

**2. Emotional Arc**
Tracks and maintains emotional progression:
- Scenes gradually build tension
- Mood shifts feel natural (sad → contemplative → hopeful)
- Intensity increases or decreases appropriately

**3. Visual Progression**
Creates visual storytelling through camera work:
- Wide establishing shot → Medium shots → Close-ups
- Gradual time of day changes (dawn → morning → noon)
- Progressive reveals (hint at something → show partially → full reveal)

**4. Temporal Awareness**
Understands passage of time:
- Early scenes: Morning light
- Middle scenes: Afternoon
- Later scenes: Evening/night
- Or maintains consistent time if story is one moment

#### How to Enable Prompt Flow

**Step 1: Access Settings**
1. In Video Project workspace
2. Click **"Advanced Settings"** or **"Workflow Options"**
3. Find **"Prompt Generation"** section

**Step 2: Enable Flow**
- Toggle **"Enable Prompt Flow"** switch to ON
- Choose flow mode:
  - **Linear**: Simple A → B → C progression
  - **Narrative Arc**: Follows story structure (exposition → rising action → climax → resolution)
  - **Emotional**: Focuses on mood progression
  - **Cinematic**: Emphasizes visual storytelling techniques

**Step 3: Configure Flow Parameters**

**Context Window**:
- How many previous scenes to consider
- Options: 1 (previous only), 3 (short context), 5 (medium), All (full context)
- Longer context = more consistent but slower generation

**Arc Type**:
- **Three Act**: Setup → Confrontation → Resolution
- **Hero's Journey**: Classic narrative structure (12 stages)
- **Episodic**: Each section is semi-independent
- **Custom**: Define your own beat sheet

**Emotional Curve**:
- **Rising**: Gradually build intensity
- **Falling**: Start intense, gradually calm
- **Wave**: Alternating high and low
- **Custom**: Draw your own curve on graph

**Step 4: Generate with Flow**
1. Click **"Generate Storyboard"** or **"Enhance Prompts"**
2. System processes scenes **sequentially** (not batch)
3. Each scene sees results of previous generation
4. Progress shown: "Processing Scene 5/20 (considering Scenes 1-4...)"

#### Example: With and Without Flow

**Input Lyrics**:
```
[00:00] My country, 'tis of thee
[00:05] Sweet land of liberty
[00:10] Of thee I sing
[00:15] Land where my fathers died
[00:20] Land of the pilgrims' pride
[00:25] From every mountainside
[00:30] Let freedom ring
```

**Without Prompt Flow** (each scene independent):
```
Scene 1: Wide shot of American flag waving
Scene 2: Beautiful landscape with fields
Scene 3: Person singing with emotion
Scene 4: Historical cemetery scene
Scene 5: Pilgrims landing on shore
Scene 6: Mountain range panorama
Scene 7: Liberty bell ringing
```
Problem: Scenes jump around randomly, no visual coherence

**With Prompt Flow** (narrative progression):
```
Scene 1: "Wide establishing shot of rural American farmland at dawn,
         American flag visible on distant farmhouse. Peaceful, still."

Scene 2: "Camera slowly pushes in toward farmhouse from Scene 1,
         revealing wheat fields in morning light. Same warm color
         palette. Sense of tranquility."

Scene 3: "Close-up of elderly man on farmhouse porch (continuing
         location), gazing at fields. Nostalgic expression. Golden
         hour lighting beginning."

Scene 4: "Slow pan across weathered cemetery near the farmhouse,
         old gravestones from 1700s-1800s. Maintaining golden hour
         lighting. Respectful, commemorative mood."

Scene 5: "Transition to historical reenactment style: Pilgrims
         in period clothing near coastline (ancestor of man from
         Scene 3 suggested). Sepia-toned. Maintaining emotional
         reverence."

Scene 6: "Camera rises, revealing modern America: same farmland
         from Scene 1 but now aerial view, with mountains in
         distance. Full daylight. Sense of scope and continuity."

Scene 7: "Final shot: Return to man from Scene 3, now standing,
         looking toward mountains. He smiles softly. Church bell
         rings in distance (audio). Sunset light. Emotional
         resolution."
```

Notice how it creates a **coherent narrative journey** rather than disconnected scenes!

#### Flow Types Explained

**1. Linear Flow**
- Each scene naturally leads to the next
- Camera and subject position maintain spatial logic
- Time progresses realistically
- Best for: Documentaries, walkthroughs, journeys

**2. Narrative Arc Flow**
- Follows classic story structure:
  - **Act 1** (Scenes 1-3): Establish world, character, situation
  - **Act 2** (Scenes 4-6): Conflict, challenges, build tension
  - **Act 3** (Scenes 7-8): Climax, resolution
- Best for: Story-driven content, music videos with narrative

**3. Emotional Flow**
- Maps scenes to emotional intensity curve
- Varies pacing to match emotion (fast cuts when excited, slow when calm)
- Lighting and color shift with mood
- Best for: Emotional songs, poetry, artistic pieces

**4. Cinematic Flow**
- Uses film grammar (establishing shot → master → coverage → close-ups)
- Applies rules like 180° rule, eyeline matching
- Creates professional film-like progression
- Best for: High-production-value content, mimicking movies

#### Advanced Configuration

**Custom Beat Sheet**:
Define exactly what each section should do:
```
Scenes 1-3: Establish main character in their world
Scene 4: Introduce conflict/tension
Scenes 5-7: Escalate challenge
Scene 8: Turning point
Scenes 9-10: Resolution
Scene 11: Denouement (aftermath)
```

**Emotion Tags**:
Tag input lines with emotions, flow respects these:
```
[00:00] My country, 'tis of thee  #pride #nostalgia
[00:05] Sweet land of liberty     #hope #freedom
[00:10] Of thee I sing            #joy #celebration
```
System generates prompts matching these emotions and transitions smoothly.

**Camera Language**:
Specify camera progression:
```
Scenes 1-2: Wide shots (establish)
Scenes 3-5: Medium shots (develop)
Scenes 6-8: Close-ups (intimacy)
Scene 9: Wide shot (conclusion)
```

#### Performance Considerations

**Pros**:
- ✅ Much more cohesive final video
- ✅ Professional storytelling quality
- ✅ Easier for viewers to follow
- ✅ Emotional impact is stronger

**Cons**:
- ❌ Slower generation (sequential, not parallel)
- ❌ More LLM API calls (higher cost)
- ❌ If one scene fails, affects subsequent scenes
- ❌ Less flexibility to regenerate individual scenes

**Best Practice**:
- Use flow mode for **final generation**
- Use static mode for **initial testing/iterations**

#### When to Use Prompt Flow

**✅ Use Prompt Flow For**:
- Music videos with storytelling
- Narrative content (story, journey, process)
- Emotional arcs (sad to happy, chaos to peace)
- Professional/commercial projects
- Content where viewer immersion matters

**❌ Don't Use Prompt Flow For**:
- Montages (intentionally disconnected clips)
- Abstract/experimental video
- Quick social media clips
- Testing/iteration (too slow)
- When each scene is meant to be standalone

#### Troubleshooting

**Problem**: Flow makes all scenes too similar
- **Solution**: Reduce context window from 5 to 2
- **Solution**: Add "variety" instruction to system prompt
- **Solution**: Use episodic arc type instead of linear

**Problem**: Later scenes don't make sense (inherited bad context)
- **Solution**: Regenerate problematic scene, flow will recalculate subsequent scenes
- **Solution**: Add "reset point" at certain scenes to start fresh context

**Problem**: Generation is very slow
- **Solution**: Use faster LLM (GPT-3.5 instead of GPT-4)
- **Solution**: Reduce context window
- **Solution**: Disable flow for testing, enable only for final generation

**Pro Tip**: Combine with Auto-Link Refs for maximum continuity!
- **Prompt Flow**: Handles narrative/emotional progression
- **Auto-Link Refs**: Handles visual consistency
- Together: Professional, cohesive video

Prompt Flow is a power-user feature - start simple, then experiment with different arc types to find what works for your content!

---

### How do I upload images and video?

ImageAI's Video Project supports uploading your own images and videos to use alongside or instead of AI-generated content. This is useful for:
- Adding real photos/footage to your video
- Using specific reference images for style
- Mixing generated and real content
- Incorporating existing brand assets

#### Types of Uploads

**1. Reference Images** (for style/character consistency)
**2. Scene Images** (direct use in video)
**3. Background Videos** (b-roll footage)
**4. End Frames** (custom final shot)

#### Method 1: Reference Images

Reference images guide AI generation without appearing directly in the video.

**How to Upload**:
1. Look for **"Reference Images"** panel (usually on right side)
2. Click **"Add Reference"** button
3. Browse to select image files (JPG, PNG, WebP)
4. Drag and drop also supported

**Organizing References**:
- **Character Refs**: Photos of people who should appear in scenes
- **Style Refs**: Images showing the artistic style you want
- **Environment Refs**: Locations/settings to match
- **Object Refs**: Specific props, vehicles, buildings

**Using References**:
1. Upload reference image
2. Select scene in storyboard
3. Click scene's **"Link Reference"** button
4. Choose which reference to use
5. When generating, AI tries to match the reference

**Example**:
```
Reference Image: Photo of your grandpa in the 1960s
Scene Prompt: "Elderly man on porch at sunset"
Result: Generated image resembles your grandpa's appearance
```

**Best Practices**:
- High resolution (1024x1024 minimum)
- Clear subject (not blurry or cluttered)
- Good lighting on reference
- Multiple angles for character refs

#### Method 2: Direct Scene Images

Use your own images directly as scenes in the video.

**How to Upload**:
1. In storyboard, click on a scene row
2. Click **"Upload Image"** button (or right-click → "Upload Custom Image")
3. Select image file
4. Image replaces generated content for that scene

**Supported Formats**:
- JPG/JPEG
- PNG (transparency supported)
- WebP
- TIFF
- BMP

**Resolution Requirements**:
- Minimum: 1280x720 (720p)
- Recommended: 1920x1080 (1080p)
- Maximum: 3840x2160 (4K)
- Aspect ratio should match project (typically 16:9)

**Processing**:
- Images are automatically resized to match project resolution
- Aspect ratio is maintained (black bars added if needed)
- Or choose to crop/fill to exact dimensions

**Example Use Cases**:
- Opening title card with your logo
- Real photo for Scene 1, AI-generated for rest
- Family photos interspersed with generated scenes
- Diagrams, charts, infographics

#### Method 3: Video Clips

Upload existing video footage to include in your project.

**How to Upload**:
1. In storyboard, select a scene
2. Click **"Upload Video Clip"** instead of generating
3. Browse to video file
4. Clip replaces that scene

**Supported Formats**:
- MP4 (H.264 codec)
- MOV (QuickTime)
- AVI
- MKV
- WebM

**Duration Handling**:
- Video longer than scene duration: Automatically trimmed to fit
- Video shorter than scene duration: Extended with freeze frame or looped
- Option to adjust scene duration to match video length

**Mixing Generated and Uploaded**:
```
Scene 1: [AI Generated] - Sunset landscape
Scene 2: [Uploaded Video] - Real drone footage of mountains
Scene 3: [AI Generated] - Close-up of character
Scene 4: [Uploaded Video] - Your actual hometown footage
Scene 5: [AI Generated] - Final emotional scene
```

**Audio Handling**:
- Uploaded videos can include audio
- Choose to keep video's audio or use project's audio track
- Audio mix options: overlay, replace, or mute

#### Method 4: Batch Upload

Upload multiple files at once.

**How to Batch Upload**:
1. Click **"Import Media"** button in toolbar
2. Select multiple files (Ctrl+Click or Shift+Click)
3. Or drag and drop multiple files into workspace
4. System creates a scene for each image/video

**Automatic Organization**:
- Files are sorted alphabetically (001_intro.jpg, 002_scene.jpg...)
- Each file becomes one scene
- Durations calculated based on project settings
- You can reorder after import

**Smart Import**:
If you have a folder structure:
```
My Video Assets/
├── 01_intro.jpg
├── 02_scene.mp4
├── 03_outro.jpg
└── references/
    ├── character.jpg
    └── style.jpg
```
System automatically:
- Imports 01-03 as scenes
- Detects `references/` folder and adds those as reference images

#### Upload Manager

The **Upload Manager** tracks all imported media.

**Accessing Upload Manager**:
1. Click **"Manage Media"** button
2. View all uploaded files in one place
3. See which scenes use which media
4. Replace, remove, or reorganize

**Media Info**:
- File name and location
- Resolution and aspect ratio
- File size
- Where it's used in project
- Status (linked, missing, modified)

**Operations**:
- **Replace**: Swap one image/video for another
- **Relink**: If file moved, update path
- **Remove**: Delete from project (file stays on disk)
- **Export**: Copy all used media to project folder (for portability)

#### Advanced: Image Sequences

Upload a sequence of images to create animation.

**How to Use**:
1. Prepare numbered images (frame_001.jpg, frame_002.jpg, etc.)
2. Click **"Import Sequence"**
3. Select first file in sequence
4. System auto-detects remaining files
5. Creates video clip at specified frame rate (24fps default)

**Use Cases**:
- Stop-motion animation
- Time-lapse photography
- Hand-drawn animation frames
- Rendered 3D animation

#### Working with Uploaded Media

**Editing Uploaded Images**:
1. Right-click uploaded image in scene
2. Select **"Edit Image"**
3. Opens basic editor:
   - Crop
   - Rotate
   - Adjust brightness/contrast
   - Apply filters
4. Save changes

**Effects on Uploaded Media**:
- **Ken Burns Effect**: Works on uploaded images (zoom and pan)
- **Transitions**: Apply between uploaded and generated scenes
- **Color Grading**: Adjust uploaded media to match generated style
- **Overlays**: Add text, graphics on top

#### Best Practices

**1. Resolution Consistency**:
- Match all uploaded images to project resolution (1920x1080)
- Upscale small images before importing (use ImageAI's upscale feature)
- Downscale huge images to save storage

**2. Aspect Ratio**:
- Stick to 16:9 for consistency (1920x1080, 1280x720, 3840x2160)
- Or crop images to match before upload
- Avoid mixing 4:3 and 16:9 (creates black bars)

**3. Style Matching**:
- If mixing real photos with AI-generated:
  - Apply filters to make photos look more stylized
  - Or generate AI scenes in photorealistic style
- Use color grading to unify look

**4. File Organization**:
- Store media in project folder for easy backup
- Use descriptive filenames
- Keep originals separate from edited versions

**5. Performance**:
- Large video files slow down editing
- Create proxies (lower-res versions) for editing
- Use final quality only for export

#### Troubleshooting

**Problem**: Uploaded image looks wrong in video
- **Solution**: Check aspect ratio - might be stretched or cropped
- **Solution**: Re-upload at correct resolution

**Problem**: Uploaded video doesn't play smoothly
- **Solution**: Convert to MP4 with H.264 codec
- **Solution**: Reduce frame rate to 24fps or 30fps

**Problem**: Can't find uploaded files after reopening project
- **Solution**: Files were moved/renamed on disk
- **Solution**: Use Upload Manager → Relink to update paths
- **Solution**: Always use "Copy to Project" option when importing

**Problem**: Uploaded images look grainy/low quality
- **Solution**: Upload higher resolution sources
- **Solution**: Use ImageAI's upscale tool before importing

**Keyboard Shortcuts**:
- **Ctrl+I**: Import media
- **Ctrl+Shift+I**: Import as reference
- **Delete**: Remove selected media
- **Alt+Drag**: Copy media to another scene

Uploading your own media gives you full creative control - mix AI generation with real footage for best results!

---

## Video Effects

### What's Ken Burns Effect?

The **Ken Burns Effect** is a video technique that adds motion to still images by slowly zooming and panning across them. It's named after documentarian Ken Burns, who popularized this style in his historical films.

#### What It Does

Instead of a static image on screen, Ken Burns creates the illusion of camera movement:
- **Zoom In**: Gradually closer to the subject (emotional intensity)
- **Zoom Out**: Gradually revealing more of scene (context)
- **Pan**: Camera slides left, right, up, or down
- **Combination**: Zoom + Pan simultaneously

This transforms a boring still photo into dynamic, engaging video footage.

#### Why Use It?

**Engagement**: Static images are boring to watch. Even subtle movement keeps viewers interested.

**Storytelling**: Camera movement guides viewer's attention:
- Zoom in on a face → intimacy, emotion
- Pan across landscape → sense of journey
- Pull back from detail → reveal bigger picture

**Professional Look**: Mimics real camera work, making slideshow videos look cinematic.

**Focus Direction**: Draw attention to specific parts of image:
- Start wide, zoom to important detail
- Pan from one subject to another
- Reveal surprise element by zooming out

#### How It's Applied in ImageAI

When you export a video using the **Slideshow** renderer with images (not video clips):

**Default Behavior**:
- Each image displays for its scene duration (e.g., 4 seconds)
- Ken Burns effect is automatically applied
- Movement is subtle and smooth (not jarring)

**What Happens**:
```
Scene 1 Image: Landscape photo
Effect Applied: Starts zoomed in 10%, slowly zooms out to 100% over 4 seconds
                While zooming, subtle pan from left to right

Scene 2 Image: Portrait photo
Effect Applied: Starts at 100%, gradually zooms in to 110% over 5 seconds
                Focuses on subject's face

Scene 3 Image: Wide scene
Effect Applied: Pans slowly from right to left, no zoom
```

#### Configuration Options

You can control Ken Burns behavior in **Video Export Settings**:

**Enable/Disable**:
- ☑️ **"Apply Ken Burns Effect"**: ON by default
- Uncheck to use static images (no movement)

**Movement Style**:
- **Subtle**: 5-10% zoom/pan (barely noticeable, professional)
- **Moderate**: 10-20% movement (clearly visible)
- **Dramatic**: 20-30%+ (obvious effect, artistic)

**Direction Presets**:
- **Auto**: System chooses based on image composition
- **Zoom In**: Always zoom closer
- **Zoom Out**: Always reveal more
- **Pan Left**: Slide left across image
- **Pan Right**: Slide right across image
- **Pan Up**: Vertical movement upward
- **Pan Down**: Vertical movement downward
- **Orbit**: Circular motion around center

**Speed**:
- **Slow**: Full effect over entire scene duration
- **Medium**: Effect completes halfway through scene
- **Fast**: Effect completes in first 25% of scene, then holds

#### Per-Scene Customization

For fine control, set Ken Burns per scene:

1. Select scene in storyboard
2. Click **"Effects"** button
3. Configure Ken Burns for just that scene:
   - Start position (top-left, center, bottom-right, etc.)
   - End position (where camera ends up)
   - Zoom amount (100-150% typical)
   - Easing (linear, ease-in, ease-out, ease-in-out)

**Example Custom Setup**:
```
Scene 1: Landscape
- Start: Centered at 110% zoom
- End: Bottom-right at 100% zoom
- Effect: Reveals sky while zooming out

Scene 2: Portrait
- Start: Top-left at 100%
- End: Center at 120% zoom
- Effect: Focuses on subject's face

Scene 3: Group photo
- Start: Left side at 110%
- End: Right side at 105%
- Effect: Pans across showing each person
```

#### Smart Auto-Detection

ImageAI can analyze images and automatically choose best movement:

**How It Works**:
1. Image is analyzed for subjects, faces, focal points
2. Ken Burns movement is calculated to:
   - Start showing full image
   - End focused on main subject
3. Or vice versa (start on detail, pull back to context)

**Example**:
- Image: Person on left side, mountain on right
- Auto-detected: Pan from person → mountain (left to right)
- Duration: 5 seconds, slow pan with slight zoom in

**Override**: If auto-detection is wrong, manually adjust

#### Technical Details

**Implementation**:
Ken Burns is achieved through FFmpeg's `zoompan` filter:
```
zoompan=z='min(zoom+0.001,1.5)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080
```
This creates smooth zoom-in effect over 125 frames (5 seconds at 25fps).

**Performance**:
- Applying Ken Burns increases render time slightly
- Effect is rendered during export, not stored per-image
- No quality loss (operates on full-resolution images)

#### Best Practices

**1. Subtlety is Key**:
- Viewers shouldn't be distracted by movement
- 5-15% zoom is usually enough
- Slow, gradual movements feel natural

**2. Match Content**:
- **Calm scenes**: Slow zoom out
- **Intense scenes**: Faster zoom in
- **Transitions**: Pan direction matches next scene (pan right if next scene is to the right)

**3. Vary Directions**:
- Don't zoom in on every scene (gets predictable)
- Mix zoom in, zoom out, pans
- Occasional static shot for variety

**4. Respect Composition**:
- Don't zoom past important elements
- Pan direction should follow visual flow
- Start and end on "clean" frames (not cutting off faces)

**5. Duration Matters**:
- Short scene (2-3s): Minimal movement or none
- Medium scene (4-6s): Standard zoom/pan
- Long scene (7-10s): Can have more dramatic movement

#### Advanced Techniques

**Reveal Effect**:
- Zoom out from tight close-up to wide shot
- Creates surprise as context is revealed
- Example: Zoom out from flower → garden → house → entire estate

**Focus Pull**:
- Start at 120% zoom, slowly zoom out to 100%
- Then hold briefly, zoom in to 110%
- Creates "breathing" effect mimicking real camera focus

**Match Cut**:
- Scene 1 ends panning right
- Scene 2 starts from right, pans left
- Creates seamless visual flow between scenes

**Motivated Movement**:
- Image has road leading off to right → Pan right
- Subject looking up → Pan up (show what they see)
- Creates visual storytelling

#### Alternatives to Ken Burns

If Ken Burns doesn't fit your style:

**Static with Transitions**:
- No Ken Burns effect
- Rely entirely on transitions between scenes
- Clean, simple look

**Parallax Effect**:
- Separate image into layers (foreground, midground, background)
- Move layers at different speeds
- Creates 3D depth illusion
- More complex but impressive

**Morph Transitions**:
- Instead of moving within image, morph to next image
- Smooth blend between scenes
- Different feeling than Ken Burns

#### Disabling Ken Burns

If you prefer completely static images:

1. Open **Export Settings**
2. Uncheck **"Apply Ken Burns Effect"**
3. Choose how to handle static images:
   - Simply display (no movement)
   - Apply subtle fade in/out instead
   - Use transitions only

Or disable per-scene:
1. Right-click scene
2. Select **"Disable Effects"**
3. That scene will be static while others have Ken Burns

#### Examples in Use

**Music Video - Nostalgic Song**:
- All scenes use slow zoom-outs
- Creates feeling of memory/reflection
- Combined with vintage color grading

**Travel Montage**:
- Photos of locations with pan effects
- Pans mimic journey (left to right across map)
- Faster movement for dynamic feel

**Documentary Style**:
- Historical photos with slow zoom-ins
- Focuses on details (faces, artifacts)
- Ken Burns' actual documentary technique

**Product Showcase**:
- Photos of product with rotate + zoom
- Shows all angles
- Professional, engaging

Ken Burns Effect is one of the most important tools for making still-image videos look professional and engaging!

---

### Transitions?

**Transitions** are effects applied between scenes to smoothly move from one shot to the next. Instead of abrupt cuts, transitions create visual flow and can convey meaning, mood, and pacing.

#### Why Transitions Matter

**Without Transitions** (hard cuts):
```
Scene 1: [Man on porch]
[CUT - instant switch]
Scene 2: [Wheat field]
[CUT]
Scene 3: [Town street]
```
Feels jarring, disjointed (though sometimes intentional for style)

**With Transitions**:
```
Scene 1: [Man on porch]
[FADE to black, FADE from black]
Scene 2: [Wheat field]
[CROSSFADE/DISSOLVE]
Scene 3: [Town street]
```
Smooth, professional, guides viewer's eye

#### Types of Transitions in ImageAI

**1. Cut (No Transition)**
- Instant switch from one scene to next
- **When to use**: Fast pacing, music video cuts, modern style
- **Duration**: 0 seconds
- **Example**: Scene 1 shows person, Scene 2 shows different person

**2. Crossfade / Dissolve**
- Scene 1 fades out while Scene 2 fades in simultaneously
- Most common transition
- **When to use**: Smooth storytelling, time passage, location changes
- **Duration**: 0.5 - 1.5 seconds typically
- **Example**: Sunset crossfades to sunrise (time passing)

**3. Fade to Black**
- Scene fades to completely black screen
- Brief pause, then next scene fades in
- **When to use**: Chapter breaks, major scene changes, dramatic pauses
- **Duration**: 0.5s out + 0.5s black + 0.5s in = 1.5s total
- **Example**: End of verse → fade to black → start of chorus

**4. Fade to White**
- Same as fade to black but with white
- **When to use**: Flashbacks, dream sequences, heavenly/ethereal moments
- **Duration**: Same as fade to black
- **Example**: Memory scene → bright white → return to present

**5. Wipe**
- Scene 2 "pushes" Scene 1 off screen
- Direction: left, right, up, down, diagonal
- **When to use**: Retro style, energetic feel, spatial transitions
- **Duration**: 0.5 - 1.0 seconds
- **Example**: Moving from room to room (wipe left as character walks)

**6. Slide**
- Scene 2 slides into frame while Scene 1 slides out
- **When to use**: Geographic movement, map transitions, modern style
- **Duration**: 0.3 - 0.8 seconds
- **Example**: Panning across multiple locations

**7. Zoom Transition**
- Scene 1 zooms in until blurry, Scene 2 zooms out into focus
- **When to use**: Emphasis, surprise reveals, focus changes
- **Duration**: 0.5 - 1.0 seconds
- **Example**: Zoom into detail → zoom out revealing it's part of larger scene

**8. Blur Transition**
- Scene 1 blurs out, Scene 2 blurs in from blur
- **When to use**: Dreamy feel, confusion, disorientation, soft style
- **Duration**: 0.5 - 1.0 seconds
- **Example**: Waking up, blurry vision clearing

**9. Glitch/Digital Transition** (Advanced)
- Pixelated, corrupted effect between scenes
- **When to use**: Tech themes, cyberpunk, edgy/modern style
- **Duration**: 0.1 - 0.3 seconds (fast)
- **Example**: Switching between digital interface screens

#### How to Apply Transitions

**Global Transitions** (all scenes use same type):

1. Open **Export Settings** dialog
2. Find **"Transitions"** section
3. Select transition type from dropdown
4. Set duration (slider: 0.1s - 2.0s)
5. All scenes will use this transition

**Per-Scene Transitions** (customize each):

1. In storyboard, click between two scenes (the "seam")
2. A transition editor appears
3. Choose transition type for this specific transition
4. Set duration
5. Preview (if available)
6. Apply

**Example Storyboard with Custom Transitions**:
```
Scene 1: Man on porch
   ↓ [Crossfade - 1.0s]
Scene 2: Wheat field
   ↓ [Cut - 0s]
Scene 3: Town street
   ↓ [Fade to Black - 1.5s]
Scene 4: Nighttime scene
   ↓ [Crossfade - 0.8s]
Scene 5: Final shot
```

#### Transition Duration

How long should transitions be?

**Short (0.2 - 0.5s)**:
- Fast pacing
- Music with quick cuts
- Modern, energetic style
- When scenes are visually similar

**Medium (0.5 - 1.0s)**:
- Standard, professional look
- Most common choice
- Works for most content
- Balanced, not rushed

**Long (1.0 - 2.0s)**:
- Dramatic, slow pacing
- Emotional moments
- Emphasizing change
- Artistic style

**Very Long (2.0s+)**:
- Rare, very specific use
- Extremely slow, meditative pace
- Often with fade to black
- Major chapter divisions

#### Transition Timing vs. Scene Duration

Important consideration:

```
Scene 1: 4 seconds
Transition: 1 second crossfade
Scene 2: 5 seconds

Actual timing:
0:00-0:04 → Scene 1 (visible)
0:03-0:04 → Scene 1 + 2 overlap (crossfade starts)
0:04-0:05 → Scene 1 + 2 overlap (crossfade continues)
0:05-0:09 → Scene 2 (visible alone)
```

**Overlap means**:
- Total video duration is NOT sum of all scene durations
- Transitions "borrow" time from adjacent scenes
- If Scene 1 is 4s with 1s crossfade, viewer sees ~3.5s of Scene 1 alone

**Adjusting for This**:
- Option 1: Increase scene durations to compensate
- Option 2: Use shorter transitions
- Option 3: Accept that some content will be partially visible

ImageAI handles this automatically - you set scene durations, system adjusts for transitions.

#### Transition Best Practices

**1. Consistency**:
- Use same transition type throughout (usually crossfade)
- Or establish patterns (crossfade for time passage, cut for same scene)
- Don't randomly mix all types (looks amateurish)

**2. Match Tone**:
- Dramatic/emotional: Fade to black, long crossfades
- Energetic/fun: Fast cuts, wipes, slides
- Professional/corporate: Clean crossfades, no gimmicks
- Artistic: Blur, long fades, creative transitions

**3. Music Sync**:
- Time transitions to musical beats
- Cut or transition at:
  - Start of measure
  - Chorus entry
  - Drum hits
  - Lyric emphasis
- MIDI timing helps align perfectly

**4. Visual Logic**:
- Similar scenes: Short crossfade
- Different locations: Longer crossfade or fade to black
- Time passing: Fade to black/white
- Spatial movement: Wipe/slide in direction of movement

**5. Less is More**:
- Subtle transitions are professional
- Obvious, flashy transitions distract from content
- Save dramatic transitions for key moments
- Most of video should use simple crossfades or cuts

#### Advanced Transition Techniques

**Motivated Transitions**:
- Scene 1 ends with bright light (sun, lamp, etc.)
- Transition: Fade to white through that light source
- Scene 2 starts emerging from white
- **Effect**: Seamless, story-driven transition

**Match Cut**:
- Scene 1 ends with circular object (wheel, clock face)
- Cut to Scene 2 starting with similar circular shape (moon, plate)
- No transition effect, but visual similarity makes cut smooth

**L-Cut and J-Cut** (audio-based):
- **L-Cut**: Scene 2's audio starts before Scene 2's video appears
- **J-Cut**: Scene 1's video continues while Scene 2's audio begins
- Creates overlap that feels natural

**Directional Flow**:
- Subject exits frame right in Scene 1
- Transition wipes right
- Subject enters frame left in Scene 2
- **Effect**: Continuous motion across transition

**Color Match**:
- Scene 1 ends with dominant blue color
- Crossfade to Scene 2 starting with similar blue
- Makes transition nearly invisible
- Requires color grading

#### Disabling Transitions

For pure cuts throughout:

1. Export Settings → Transitions
2. Select **"None (Cuts Only)"**
3. All scenes instantly cut to next

Or disable specific transitions:
1. Click transition in storyboard
2. Set duration to **0 seconds**
3. That transition becomes a hard cut

#### Transition Presets

ImageAI includes preset collections:

**Classic Film**:
- All crossfades
- 1.0s duration
- Occasional fade to black for chapters

**Music Video**:
- Mix of cuts (70%) and fast crossfades (30%)
- 0.2-0.5s durations
- Synced to beat grid if MIDI available

**Documentary**:
- Mostly cuts
- Occasional crossfades for time/location changes
- Fade to black between major sections

**Artistic**:
- Varied transitions
- Blur, fade to white, long crossfades
- 1.0-2.0s durations
- Slow, meditative pacing

**Apply Preset**:
1. Export Settings → Transitions
2. Click **"Load Preset"**
3. Choose preset
4. Applies to all transitions
5. Customize individual transitions after if needed

#### Troubleshooting

**Problem**: Transitions look choppy/jerky
- **Cause**: Low frame rate or video rendering issue
- **Solution**: Export at 30fps or 60fps instead of 24fps
- **Solution**: Use shorter transition duration

**Problem**: Transition cuts off important content
- **Cause**: Transition overlaps with key moment in scene
- **Solution**: Increase scene duration
- **Solution**: Move transition start point earlier
- **Solution**: Use shorter transition duration

**Problem**: Can't see transition effect
- **Cause**: Scene images are too similar (crossfade of similar colors invisible)
- **Solution**: Use cut instead
- **Solution**: Add fade to black between scenes

**Problem**: Transitions don't align with music
- **Cause**: Manual timing vs. musical timing
- **Solution**: Enable MIDI sync
- **Solution**: Manually adjust scene durations to match beats
- **Solution**: Use transition timing calculator (measures music BPM)

**Pro Tip**: Preview transitions before final export. Click "Preview" button to see a quick render of first 30 seconds with transitions applied. Adjust if needed.

Transitions are subtle but crucial for professional-looking videos. When done right, viewers don't notice them - the video just flows naturally!

---

### Smooth Transitions?

**Smooth Transitions** is an enhanced transition system that goes beyond basic crossfades to create seamless, nearly invisible transitions between scenes using advanced techniques.

#### What Makes Transitions "Smooth"?

Regular transitions are mechanical:
- Timer-based (always 1.0s, regardless of content)
- Same effect regardless of what's in the scenes
- Crossfade is applied uniformly across frame

**Smooth Transitions** are intelligent:
- Content-aware (analyzes both scenes)
- Adaptive timing (duration varies based on visual similarity)
- Seamless blending (matches motion, color, composition)

#### How Smooth Transitions Work

**Step 1: Analysis**
Before creating transition, system analyzes:
- **Color Palette**: Dominant colors in Scene 1's end vs. Scene 2's start
- **Brightness**: Overall luminance levels
- **Composition**: Subject placement and framing
- **Motion**: Ken Burns direction (if applied)
- **Content Similarity**: How visually related the scenes are

**Step 2: Optimization**
Based on analysis, system chooses best transition method:
- Similar colors → Shorter, subtler crossfade
- Different colors → Longer crossfade or color-matched intermediate
- Matching motion → Directional transition that follows motion
- Dissimilar content → Fade to black or white

**Step 3: Rendering**
Transition is created with:
- **Optical Flow**: Warps pixels to create smooth motion between frames
- **Color Grading**: Adjusts colors mid-transition for consistency
- **Easing**: Non-linear timing (starts slow, speeds up, slows down)

#### Types of Smooth Transitions

**1. Motion-Matched Crossfade**
- Analyzes Ken Burns movement in both scenes
- Creates transition that continues motion flow
- Example:
  ```
  Scene 1: Ken Burns zooming in
  Transition: Continues zoom motion while crossfading
  Scene 2: Starts at similar zoom level, continues
  ```
- **Result**: Camera appears to move continuously across transition

**2. Color-Interpolated Fade**
- Instead of direct crossfade, gradually shifts color palette
- Intermediate frames blend color spaces
- Example:
  ```
  Scene 1: Warm sunset (orange/red tones)
  Transition: Gradual shift through amber → yellow
  Scene 2: Daylight (blue/white tones)
  ```
- **Result**: No jarring color shift

**3. Morphing Transition**
- Identifies similar features in both scenes (faces, buildings, horizon lines)
- Warps Scene 1's features to match Scene 2's position
- Crossfades while morphing
- Example:
  ```
  Scene 1: Person centered, looking left
  Transition: Person's position morphs from center to right side
  Scene 2: Person on right, looking forward
  ```
- **Result**: Subject appears to move smoothly during transition

**4. Directional Flow Transition**
- Adds directional movement to crossfade
- Direction based on visual flow in scenes
- Example:
  ```
  Scene 1: Road leading off to right
  Transition: Crossfade with rightward slide/wipe
  Scene 2: Arriving at destination on right
  ```
- **Result**: Enhances sense of journey

**5. Depth-Based Transition**
- Separates scenes into depth layers (foreground, midground, background)
- Transitions layers at different speeds
- Creates parallax effect
- Example:
  ```
  Scene 1: Tree in foreground, mountains in background
  Transition: Tree fades out quickly, mountains linger longer
  Scene 2: New foreground fades in fast, background fades gradually
  ```
- **Result**: 3D-like transition depth

**6. Adaptive Duration Transition**
- System automatically determines best transition length
- Similar scenes: 0.3s (quick, barely noticeable)
- Different scenes: 1.2s (longer, gives time to adjust)
- Very different scenes: 2.0s with fade to black

#### Enabling Smooth Transitions

**Method 1: Global Enable** (Recommended)
1. Open **Export Settings**
2. Find **"Transitions"** section
3. Check ☑️ **"Enable Smooth Transitions"**
4. Choose intelligence level:
   - **Basic**: Color matching only
   - **Standard**: Color + motion matching
   - **Advanced**: Full analysis with morphing
   - **Maximum**: All techniques + AI enhancement

**Method 2: Per-Transition**
1. Click on transition between two scenes
2. Transition editor opens
3. Enable **"Smooth"** toggle
4. System analyzes just those two scenes
5. Apply optimized transition

**Settings**:
- **Aggressiveness**: How much to alter for smoothness
  - Low (25%): Subtle improvements
  - Medium (50%): Balanced
  - High (75%): Obvious smoothing
  - Maximum (100%): Prioritizes smoothness over all else
- **Optical Flow**: Enable motion warping (slower render, smoother result)
- **Color Matching**: Enable color interpolation

#### Technical Implementation

Smooth transitions use advanced video processing:

**Optical Flow Analysis**:
```python
# Simplified concept
last_frame_scene1 = get_last_frame(scene1)
first_frame_scene2 = get_first_frame(scene2)

# Calculate pixel motion vectors
flow = optical_flow(last_frame_scene1, first_frame_scene2)

# Generate intermediate frames following motion
for t in range(transition_frames):
    alpha = easing_function(t / transition_frames)
    frame = warp_and_blend(last_frame_scene1, first_frame_scene2, flow, alpha)
    output_frame(frame)
```

**Color Space Interpolation**:
```python
# Convert to LAB color space (perceptually uniform)
lab1 = rgb_to_lab(scene1_colors)
lab2 = rgb_to_lab(scene2_colors)

# Interpolate in LAB space
for t in range(transition_frames):
    lab_blend = lerp(lab1, lab2, t / transition_frames)
    rgb_blend = lab_to_rgb(lab_blend)
    apply_color_grade(frame, rgb_blend)
```

This creates perceptually smoother color transitions than raw RGB blending.

#### Comparison: Regular vs. Smooth

**Regular Crossfade**:
```
Frame 10 (Scene 1): 100% visible
Frame 11: 90% Scene 1 + 10% Scene 2
Frame 12: 80% Scene 1 + 20% Scene 2
...
Frame 20 (Scene 2): 100% visible
```
Linear blend, same timing regardless of content.

**Smooth Transition**:
```
Analysis: Scenes have similar colors, different motion
Decision: Use motion-matched crossfade with adaptive duration

Frame 10 (Scene 1): 100% visible, zooming in
Frame 11: 98% Scene 1 + 2% Scene 2, zoom continues
Frame 12: 95% Scene 1 + 5% Scene 2, zoom starts to shift direction
Frame 13: 88% Scene 1 + 12% Scene 2, zoom now matches Scene 2's motion
Frame 14: 75% Scene 1 + 25% Scene 2
...
Frame 18: 10% Scene 1 + 90% Scene 2
Frame 19: 2% Scene 1 + 98% Scene 2, Scene 2 fully established
Frame 20 (Scene 2): 100% visible
```
Non-linear blend, motion-aware, adaptive timing.

#### When to Use Smooth Transitions

**✅ Use Smooth Transitions For**:
- Professional/commercial videos
- Narrative storytelling where flow matters
- Videos with many scenes (50+ scenes)
- Slow-paced, cinematic content
- When scenes are visually related (same location, continuous story)

**❌ Don't Use Smooth Transitions For**:
- Intentionally jarring style (music videos with fast cuts)
- Abstract/experimental content
- When hard cuts are creative choice
- Very short videos (5-10 scenes) where it won't be noticed
- Low-powered rendering (smooth transitions are slower)

#### Performance Considerations

**Rendering Time**:
- Regular transitions: ~1 second to render per transition
- Smooth transitions: ~5-30 seconds per transition
- Advanced smooth (optical flow): ~1-2 minutes per transition

For a 50-scene video:
- Regular: ~1 minute total transition rendering
- Smooth: ~5-10 minutes
- Advanced smooth: ~30-60 minutes

**Memory Usage**:
- Smooth transitions need more RAM (analyzing frames)
- Minimum 8GB RAM recommended
- 16GB+ for advanced smooth with high-res (1080p+)

**Quality vs. Speed**:
Use quality presets:
- **Draft**: Fast, basic smoothing (color only)
- **Preview**: Medium quality, most features enabled
- **Final**: Full quality, all features, slowest

#### Advanced Options

**Transition Templates**:
Create and save custom smooth transition styles:

```
My Cinematic Template:
- Motion-matched crossfades (aggressive)
- Color interpolation enabled
- Adaptive duration (0.5s - 1.5s range)
- Optical flow enabled
- Easing: Ease-in-out (cubic)

My Documentary Template:
- Basic smooth crossfades
- Color matching only
- Fixed 0.8s duration
- No optical flow (faster render)
- Easing: Linear
```

**Per-Scene Transition Override**:
Some transitions need special handling:

```
Scene 5 → Scene 6: Dream sequence
Override: Fade to white instead of smooth crossfade
Reason: Jarring cut is intentional for dream effect

Scene 10 → Scene 11: Same location, different time
Override: Advanced smooth with morphing
Reason: Want seamless time passage effect
```

**Transition AI Assist**:
Experimental feature using AI to generate custom transitions:

1. AI analyzes scene content (objects, people, mood)
2. Generates transition specific to these scenes
3. Can create creative transitions (swirl into black hole, shatter like glass)
4. Much slower but impressive results

#### Troubleshooting

**Problem**: Smooth transitions make video look blurry
- **Cause**: Optical flow creating artifacts
- **Solution**: Reduce optical flow strength to 50%
- **Solution**: Disable optical flow for this transition

**Problem**: Transitions are jerky despite being "smooth"
- **Cause**: Frame rate mismatch
- **Solution**: Ensure project is 30fps or 60fps (not 24fps)
- **Solution**: Increase transition duration to 1.0s+

**Problem**: Color shifts look wrong during transition
- **Cause**: Color space interpolation mismatch
- **Solution**: Disable color matching
- **Solution**: Manually color grade scenes before export

**Problem**: Smooth transitions too slow to render
- **Cause**: High-quality settings with many scenes
- **Solution**: Use "Draft" quality preset
- **Solution**: Disable optical flow
- **Solution**: Render overnight or use faster computer

**Problem**: Transitions don't look any different than regular
- **Cause**: Scenes are too different (smoothing can't help)
- **Solution**: Use fade to black instead
- **Solution**: Increase aggressiveness setting
- **Solution**: Manually adjust scenes to be more visually similar

#### Best Practices

**1. Consistency in Footage**:
- Smooth transitions work best when scenes are related
- Same lighting conditions
- Similar color palettes
- Continuous location

**2. Test First**:
- Generate 3-4 scenes
- Apply smooth transitions
- Render preview
- Check if it looks better than regular
- If not, regular transitions may be fine

**3. Selective Application**:
- Use smooth for most transitions
- Use regular/cuts for intentionally jarring moments
- Reserve fade to black for major breaks

**4. Combine with Ken Burns**:
- Smooth transitions + Ken Burns = professional look
- Motion-matched transitions complement Ken Burns perfectly

**5. Audio Sync**:
- Smooth transitions can slightly alter timing
- Double-check audio still syncs after applying
- Adjust scene durations if needed

**Example Settings for Different Styles**:

**Wedding Video**:
- Smooth transitions: Advanced
- Motion matching: ON
- Color interpolation: ON
- Adaptive duration: 0.8s - 1.5s
- Result: Romantic, flowing

**Corporate Presentation**:
- Smooth transitions: Standard
- Motion matching: OFF (prefer stability)
- Color interpolation: ON (brand consistency)
- Fixed duration: 0.5s
- Result: Professional, clean

**Travel Vlog**:
- Smooth transitions: Standard
- Motion matching: ON
- Color interpolation: Subtle (50%)
- Adaptive duration: 0.3s - 1.0s
- Result: Dynamic, energetic

Smooth transitions are powerful but not always necessary. Use them when you want maximum polish and professional quality!

---

## Complete Walkthrough Example

Let's create a complete video project from start to finish, demonstrating all features.

### Project: "My Country, 'Tis of Thee" - A Patriotic Music Video

**Goal**: Create a 2-minute 45-second music video with AI-generated images, custom audio, and professional transitions.

---

#### Phase 1: Project Setup

**Step 1.1: Create New Project**
1. Launch ImageAI
2. Click **Video Project** tab
3. Click **"New Project"** button
4. Enter name: `My Country Video`
5. Choose save location: `C:\Users\YourName\Videos\ImageAI Projects\`
6. Click **"Create"**

**Result**: Project folder created with structure:
```
My Country Video/
├── project.iaproj.json
├── assets/
├── exports/
└── logs/
```

**Step 1.2: Configure Settings**
1. Click **"Project Settings"** (gear icon)
2. Set project resolution: **1920x1080 (1080p HD)**
3. Set aspect ratio: **16:9**
4. Set frame rate: **30 fps**
5. Click **"Save"**

---

#### Phase 2: Input Content

**Step 2.1: Prepare Lyrics**
Open a text editor and prepare timestamped lyrics:

```
[00:00.50] My country, 'tis of thee
[00:04.20] Sweet land of liberty
[00:08.00] Of thee I sing

[00:12.50] Land where my fathers died
[00:16.30] Land of the pilgrims' pride
[00:20.10] From every mountainside
[00:24.00] Let freedom ring

[00:28.50] My native country, thee
[00:32.20] Land of the noble free
[00:36.00] Thy name I love

[00:40.50] I love thy rocks and rills
[00:44.20] Thy woods and templed hills
[00:48.00] My heart with rapture thrills
[00:52.00] Like that above

[00:56.50] Let music swell the breeze
[01:00.20] And ring from all the trees
[01:04.00] Sweet freedom's song

[01:08.50] Let mortal tongues awake
[01:12.20] Let all that breathe partake
[01:16.00] Let rocks their silence break
[01:20.00] The sound prolong

[01:24.50] Our fathers' God, to Thee
[01:28.20] Author of liberty
[01:32.00] To Thee we sing

[01:36.50] Long may our land be bright
[01:40.20] With freedom's holy light
[01:44.00] Protect us by Thy might
[01:48.00] Great God, our King
```

**Step 2.2: Input Lyrics**
1. Copy the lyrics above
2. In ImageAI Video Project workspace, paste into **"Text Input"** area
3. System auto-detects format: **"Timestamped"** ✓

**Step 2.3: Add Audio Track**
1. Locate your audio file (e.g., `my_country_audio.mp3`)
2. Click **"Browse"** next to Audio Track
3. Select `my_country_audio.mp3`
4. File path appears: `C:\Music\my_country_audio.mp3`
5. Set volume: **80%** (slider)
6. Fade in: **2.0 seconds**
7. Fade out: **3.0 seconds**

**Step 2.4: MIDI Sync (Optional)**
If you have a MIDI file for precise timing:
1. Click **"Browse"** next to MIDI File
2. Select `my_country.mid`
3. System displays: "120 BPM, 4/4 time, 2:48 duration"
4. Enable **"Sync to MIDI beats"** checkbox
5. Set sync mode: **"Measure"** (snap to musical measures)

---

#### Phase 3: Generate Storyboard

**Step 3.1: Create Storyboard**
1. Click **"Generate Storyboard"** button
2. Wait ~5 seconds for processing
3. Storyboard table appears with 24 scenes (one per lyric line)

**Step 3.2: Review Initial Prompts**
System generated basic prompts:

| Scene | Source Text | Initial Prompt | Duration |
|-------|-------------|----------------|----------|
| 1 | My country, 'tis of thee | "My country America" | 3.7s |
| 2 | Sweet land of liberty | "Beautiful American landscape with freedom theme" | 3.8s |
| 3 | Of thee I sing | "Person singing patriotic song" | 4.0s |
| ... | ... | ... | ... |

**Step 3.3: Check Total Duration**
- Bottom of storyboard shows: **"Total Duration: 2:47.5"**
- Close to our 2:45 target ✓

---

#### Phase 4: Enhance Prompts with AI

**Step 4.1: Configure LLM**
1. In **"LLM Provider"** dropdown, select: **"OpenAI"**
2. In **"LLM Model"** dropdown, select: **"gpt-4"**
3. API key already saved in settings ✓
4. In **"Prompt Style"** dropdown, select: **"Cinematic"**

**Step 4.2: Batch Enhance**
1. Click **"Enhance Prompts"** button
2. Progress dialog appears: "Batch enhancing 24 scenes..."
3. Watch progress: "Processing scenes 1-24 in 1 API call..."
4. Wait ~45 seconds
5. Complete! "✓ Enhanced 24 prompts"

**Step 4.3: Review Enhanced Prompts**
Scene 1 transformed from:
```
Before: "My country America"

After:  "Cinematic wide establishing shot of rural American farmland
         at golden hour. Weathered red barn with faded American flag,
         gentle breeze, warm nostalgic lighting. Rolling hills in
         background, dirt road winding through wheat fields. Norman
         Rockwell aesthetic, photorealistic, 1960s Americana."
```

Scene 2 transformed:
```
Before: "Beautiful American landscape with freedom theme"

After:  "Sweeping aerial drone shot rising over vast open landscape.
         Patchwork of green farmland, small white churches with
         steeples, winding rivers. Soft morning mist, warm sunlight
         breaking through. Eagle soaring across frame. Sense of
         freedom and vastness. Cinematic 16:9, Kodachrome colors."
```

Much better! Every scene now has rich, detailed descriptions.

**Step 4.4: Manual Tweaks** (Optional)
1. Review Scene 12 prompt, seems generic
2. Double-click prompt cell to edit
3. Add: "...elderly African American woman and young Hispanic boy together, representing diversity..."
4. Press Enter to save

---

#### Phase 5: Generate Video Prompts

**Step 5.1: Enable Video Generation**
1. Click **"Generate Video Prompts"** button
2. Dialog appears with options:
   - Enable **"Auto-link references"** ☑️
   - Enable **"Add camera movements"** ☑️
   - Enable **"Continuity between scenes"** ☑️
3. Click **"Generate"**

**Step 5.2: Wait for Processing**
- Progress: "Analyzing scene 1/24..."
- "Adding camera movements..."
- "Linking scene 2 to scene 1..."
- Total time: ~60 seconds
- Complete! "✓ Generated video-optimized prompts for 24 scenes"

**Step 5.3: Review Video Prompts**
Scene 1 now includes camera movement:
```
"Cinematic wide establishing shot of rural American farmland at
 golden hour, starting from distant aerial view. Camera slowly
 descends and pushes forward toward weathered red barn with faded
 American flag gently waving in breeze. Warm nostalgic lighting
 with lens flare. Rolling hills in background, dirt road winding
 through golden wheat fields. Norman Rockwell aesthetic,
 photorealistic, 1960s Americana. Camera movement: Aerial descent
 + forward dolly, 4 seconds duration."
```

Scene 2 links to Scene 1:
```
"Continuing from previous farmland scene, camera completes approach
 to barn from Scene 1, then rises again into sweeping aerial shot
 revealing broader landscape. Patchwork of green farmland matching
 previous scene's color palette, small white churches with steeples,
 winding rivers. Same golden hour lighting. Eagle soaring across
 frame from left to right. Maintains warm Kodachrome colors. Camera
 movement: Pull back + rise, 4 seconds duration."
```

Excellent continuity!

---

#### Phase 6: Add Reference Images (Optional)

**Step 6.1: Upload Style Reference**
1. Open **"Reference Images"** panel (right side)
2. Click **"Add Reference"**
3. Select file: `norman_rockwell_example.jpg` (painting example)
4. Tag as: **"Style Reference"**
5. Description: "Norman Rockwell painting style - warm, nostalgic Americana"

**Step 6.2: Link Reference to Scenes**
1. Select all scenes (Ctrl+A in storyboard)
2. Right-click → **"Link Reference to Selected"**
3. Choose `norman_rockwell_example.jpg`
4. All scenes will now try to match this style

---

#### Phase 7: Generate Images

**Step 7.1: Configure Image Provider**
1. In **"Image Provider"** dropdown, select: **"Google Gemini"**
2. In **"Model"** dropdown, select: **"imagen-4.0-generate-001"**
3. Set **"Variants per Scene"**: **3** (generates 3 options per scene)
4. Quality: **"High"**

**Step 7.2: Start Generation**
1. Click **"Generate Images"** button
2. Confirmation: "Generate 72 images total (24 scenes × 3 variants)?"
3. Estimated cost: **"~$1.44"** (at $0.02 per image)
4. Click **"Yes, Generate"**

**Step 7.3: Monitor Progress**
- Progress bar: "Generating Scene 1/24..."
- Scene 1 completed: 3 thumbnails appear
- Scene 2 generating...
- Continue for ~15 minutes (generation is parallel, ~3 scenes at a time)

**Step 7.4: Review Results**
- All scenes now show 3 thumbnail variants
- Hover over thumbnail to see larger preview
- Some are great, some are okay

---

#### Phase 8: Select and Refine

**Step 8.1: Approve Best Variants**
Go through each scene:

1. **Scene 1**: Click thumbnail 2 (best farmland shot)
   - Click **"Approve"** (green checkmark)
   - Green border appears on thumbnail

2. **Scene 2**: Click thumbnail 1
   - Click **"Approve"**

3. **Scene 5**: All variants are poor (AI didn't understand "pilgrims")
   - Edit prompt to be more specific
   - Right-click → **"Regenerate Images"**
   - Wait for 3 new variants
   - Approve best one

4. Continue through all 24 scenes
5. Total time: ~10 minutes to review and approve

**Step 8.2: Final Check**
- Scroll through storyboard
- All scenes have green checkmark ✓
- Visual flow looks good
- Ready for export!

---

#### Phase 9: Export Video

**Step 9.1: Configure Export**
1. Click **"Render Video"** button
2. Export dialog appears

**Settings**:
- **Renderer**: **"Slideshow (FFmpeg)"** (using images, not Veo video clips)
- **Resolution**: **1920x1080 (1080p)**
- **Frame Rate**: **30 fps**
- **Video Codec**: **H.264**
- **Quality**: **High (CRF 18)**

**Effects**:
- **Enable Ken Burns Effect**: ☑️ ON
  - Style: **"Cinematic"**
  - Intensity: **Medium (15%)**
- **Transitions**:
  - Type: **"Smooth Crossfade"**
  - Duration: **1.0 seconds**
  - Enable **"Smooth Transitions"**: ☑️ ON
  - Intelligence: **"Standard"**

**Audio**:
- **Include Audio Track**: ☑️ ON
- Audio file: `C:\Music\my_country_audio.mp3`
- Volume: **80%**
- Fade in: **2.0s**
- Fade out: **3.0s**

**Output**:
- File name: `My_Country_Final_v1.mp4`
- Location: `My Country Video/exports/`

**Step 9.2: Start Rendering**
1. Review settings summary
2. Click **"Start Export"**
3. Rendering begins...

**Step 9.3: Monitor Rendering**
- Progress: "Preparing assets... (5%)"
- "Applying Ken Burns effects... (15%)"
- "Rendering scene 1/24 with transitions... (25%)"
- "Rendering scene 5/24... (45%)"
- "Mixing audio track... (90%)"
- "Finalizing video... (98%)"
- Total time: ~8 minutes

**Step 9.4: Completion**
- **"✓ Export Complete!"**
- Location: `C:\Users\YourName\Videos\ImageAI Projects\My Country Video\exports\My_Country_Final_v1.mp4`
- Size: **145 MB**
- Duration: **2:47**

---

#### Phase 10: Review and Iterate

**Step 10.1: Watch the Video**
1. Click **"Open in Player"** or locate file
2. Watch full video from start to finish
3. Take notes on what to improve

**Observations**:
- ✓ Audio sync is perfect (thanks to timestamped lyrics)
- ✓ Transitions are smooth and professional
- ✓ Ken Burns effects add nice movement
- ✓ Style is consistent throughout
- ⚠️ Scene 8 image is too dark
- ⚠️ Scene 15 transitions too quickly
- ⚠️ Scene 22 doesn't match the emotion

**Step 10.2: Make Adjustments**

**Fix Scene 8** (too dark):
1. Select Scene 8 in storyboard
2. Edit prompt: Add "bright morning light, well-lit"
3. Regenerate just this scene
4. Approve better variant

**Fix Scene 15** (too quick):
1. Select Scene 15
2. Change duration from 3.9s to 5.5s
3. Click **"Update Duration"**

**Fix Scene 22** (wrong emotion):
1. Edit prompt: Change "joyful celebration" to "solemn reverence"
2. Regenerate scene
3. Approve best variant

**Step 10.3: Re-Export**
1. Click **"Render Video"** again
2. Same settings as before
3. File name: `My_Country_Final_v2.mp4` (version 2)
4. Render takes ~8 minutes
5. Review video - much better!

---

#### Phase 11: Final Polish

**Step 11.1: Add End Card** (Optional)
1. Click **"Add Scene"** at end of storyboard
2. Scene 25 created
3. Prompt: "Black screen with white text 'Created with ImageAI' centered"
4. Duration: 5 seconds
5. Generate image
6. Or upload custom end card image

**Step 11.2: Color Grading** (Optional)
If available:
1. Select all scenes
2. Click **"Color Grade"**
3. Choose preset: **"Vintage Americana"**
4. Applies warm tones, slight vignette, film grain
5. Regenerate with color grading applied

**Step 11.3: Final Export**
1. Render one more time: `My_Country_Final_MASTER.mp4`
2. This is the version to share!

---

#### Phase 12: Save and Share

**Step 12.1: Save Project**
- Click **"Save Project"** (Ctrl+S)
- Project file updated with all changes
- All assets remain in project folder

**Step 12.2: Backup**
1. Right-click project in **Project Browser**
2. Select **"Export Project Package"**
3. Creates ZIP file: `My_Country_Video_BACKUP.zip`
4. Contains:
   - Project file
   - All generated images
   - Audio file (linked, so copied here)
   - Exported videos
   - Logs
5. Save ZIP to cloud storage or external drive

**Step 12.3: Share Video**
Upload final video:
- **YouTube**: 1080p, 30fps, H.264 → perfect quality ✓
- **Instagram**: May need to crop to 1:1 or 9:16 (use "Export for Social Media" option)
- **Facebook**: Works as-is
- **Email**: 145MB may be too large - create lower-quality version

---

### Summary of Workflow

**Time Breakdown**:
1. Project setup: 5 minutes
2. Input content: 10 minutes
3. Generate storyboard: 2 minutes
4. Enhance prompts: 1 minute (+ 45s AI processing)
5. Generate video prompts: 2 minutes (+ 60s AI processing)
6. Generate images: 5 minutes user time (+ 15 minutes generation)
7. Review and approve: 10 minutes
8. Export video: 2 minutes setup (+ 8 minutes rendering)
9. Review and iterate: 15 minutes

**Total**: ~1 hour active work, ~25 minutes AI/render time

**Cost Breakdown** (approximate):
- OpenAI GPT-4 prompt enhancement: $0.20
- Google Gemini image generation: $1.44 (72 images)
- **Total**: ~$1.64

**Final Result**:
- Professional-looking 2:47 music video
- 24 AI-generated scenes with cinematic style
- Smooth transitions and Ken Burns effects
- Perfectly synced to audio
- High-quality 1080p MP4

---

### Tips for Your Own Projects

1. **Start Simple**: First project, use plain text, skip MIDI, skip prompt enhancement. Learn the basics.

2. **Iterate**: Don't expect perfection on first export. Generate, review, adjust, re-export.

3. **Save Often**: Project auto-saves, but manually save before major operations.

4. **Test Small**: Generate 3-5 scenes first, export preview. Check quality before generating all 50 scenes.

5. **Use References**: Upload style references for consistent look. Huge quality improvement.

6. **Mind Your Budget**: AI generation costs add up. Start with 1-2 variants per scene, not 4.

7. **Audio First**: If using audio, start with audio file. Helps calculate accurate durations.

8. **Check Duration**: Ensure total duration matches your audio file length (or intended length).

9. **Backup Projects**: Export project packages regularly. Don't lose work!

10. **Experiment**: Try different styles, transitions, effects. Digital art - no cost to experiment!

---

## Conclusion

Video Project in ImageAI is powerful and flexible. This FAQ covered:
- Complete workflow from start to finish
- All major features (storyboard, prompt enhancement, Ken Burns, transitions)
- Advanced techniques (auto-link refs, prompt flow, smooth transitions)
- Practical troubleshooting and best practices
- Real-world example from beginning to end

**Key Takeaways**:
- Workflow Guide keeps you on track
- AI enhancement dramatically improves prompts
- Reference images ensure visual consistency
- Smooth transitions and Ken Burns make videos professional
- Iteration is normal - first export is rarely final

**Next Steps**:
1. Create your first simple project (3-5 scenes, basic settings)
2. Watch the result, learn what works
3. Gradually add advanced features (LLM enhancement, references, smooth transitions)
4. Experiment with different styles and content types
5. Share your creations!

**Need More Help?**
- Check the Help tab in ImageAI for feature documentation
- Review the Plans/ImageAI-VideoProject-PRD.md for technical details
- Join the community forum (if available) for tips and examples
- Post issues on GitHub for bug reports or feature requests

Happy video creating! 🎬✨
