🎬 **New in ImageAI: Gemini Omni video generation**

We just wired up Google's newest video model — **Gemini Omni** — into the Video tab. It's fast, conversational, and generates video *with audio* right out of the box.

**What it does**
- 🟢 **Text → video** — describe a scene, get a clip.
- 🖼️ **Image → video** — feed it a starting frame and let it animate.
- 💬 **Conversational editing** — keep refining the *same* clip across turns ("make it slower", "now at sunset") instead of starting over each time.
- 🔊 **Audio in the output** — sound comes baked into the generated video.

**The details that matter**
- Pick your aspect ratio (16:9 or 9:16) — it's set on the request, never jammed into the prompt text, so no stray ratios showing up on screen.
- Model ID is resolved at runtime from the registry, so it stays current without code changes.
- Runs on Google's Interactions API (`google-genai` 2.9.0+).

While in there we also squashed a Veo bug where video settings weren't sticking between sessions — those now save and restore properly.

Full test suite is green (415 passing), and it's up as **PR #29**. Give Omni a spin in the Video tab and let us know what you make! 🚀

🔗 Repo: <https://github.com/lelandg/ImageAI>
