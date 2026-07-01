🤖 **ImageAI has a full-power CLI — and a skill that teaches your agent to drive it**

Everything ImageAI does in the GUI now runs headless from one entry point: `python main.py`. Images, video, page layouts, batch jobs — scriptable end to end.

**One command line, the whole toolbox**
- 🎨 **Four image providers** — Google Nano Banana (up to 4K), OpenAI gpt-image-2 / DALL·E, Stability AI, and fully offline local Stable Diffusion.
- 🎬 **Two video providers** — Veo (extend clips, frame-to-frame interpolation) and Gemini Omni (conversational refine, edit your own footage, audio baked in).
- 📄 **Publication layout engine** — describe a page ("3-panel comic: a raccoon pulls off a birthday-cake heist"), and design → fill → export to PDF, no window ever opens.
- 🎵 **Lyrics → prompts** pipeline, reference images, masks, streaming partials, and OpenAI Batch API at a 50% discount.

**Why agents love it**
This CLI was built to be driven by another program, not just a human:
- `--json` puts *exactly one* JSON object on stdout — all logs go to stderr, so parsers never trip.
- Meaningful exit codes (`0/1/2/3`) — branch on failure vs. bad flags without grepping text.
- Every image and video gets a `.json` sidecar — durable metadata (prompt, model, ids) your agent can read later.
- Any action flag keeps it headless — an automated run can never accidentally block on the GUI.

**The imageai-cli skill**
The repo ships a skill (`.claude/skills/imageai-cli`) that hands Claude Code — or any skill-aware CLI agent — the complete cheat-sheet: every flag, provider quirks, cost tiers, and the anti-footgun list (like why you never put pixel dimensions in a Gemini prompt). Point your agent at the repo and just say what you want made.

Full guide with agent recipes lives in `Docs/ImageAI-CLI-Guide.md`. Go make something weird! 🚀

🔗 Repo: <https://github.com/lelandg/ImageAI>
