# 🎮 **New in ImageAI: Sprite tab**

Drop in a character image (or right-click any Image tab result and pick **Send to Sprite**) and ImageAI takes it to an engine-ready animation set. Biggest single feature we've ever shipped.

**How it works**
- 🧍 Gemini puts your character on a chroma plate, plus an optional four-view turnaround.
- 🃏 An LLM writes the action cards for your genre (sidescroller has: idle, walk, run, jump, fall, attack, hurt, death). Edit them or write your own.
- 🎬 A render queue sends each card to Gemini Omni or Veo with a cost row per action. 
- ✂️ Frames get pulled, keyed, cleaned and stabilized. The keyer samples the clip's *real* background, because current models drift from the color you asked for. 
- 🕹️ Two output profiles: `hd` at >= 256×256 in true color, and `pixel` at 64×64 with a 32-color shared palette and integer scaling, so nothing swims.

### **The workspace**

Frame strip with undo, a preview player with a loop-seam meter (0 = perfect loop), and a pixel view with a grid. Draw a box on a frame and ask Gemini or gpt-image to fix it ("five fingers, same glove"). Neighbor frames go along as references. The original is never touched.

When a clip is too soft or too pricey for a short action, **Render (image)** builds the frames from an image model instead, plus an optional white/black plate pair for a clean alpha.

### **Export**
- Sheet PNG + Aseprite JSON, TexturePacker JSON, PNG sequence, transparent GIF, Godot 4 `.tres`, native `.aseprite`. 
- An engine preset (Unity, Godot 4, Phaser 3, PixiJS, UE5 Paper2D, libGDX, RPG Maker MZ, web) sets padding, pivot and file names, then prints that engine's import steps. 
- Frames scale proportionally, never cropped or squashed.

Shipped in v0.47.0 (PR #45), plus a 0.47.1 fix round the same day. Needs a Google API key. Go make a knight walk. 🚀

🔗 Repo: <https://github.com/lelandg/ImageAI>