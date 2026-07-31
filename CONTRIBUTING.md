# Contributing to ImageAI

Glad you're here. ImageAI gets better every time someone reports a bug, suggests a feature, or sends a pull request — and all three are welcome, whether it's your first contribution or your fiftieth.

## Have an idea? Come chat.

The fastest way to kick an idea around is the [Chameleon Labs Discord](https://discord.gg/chameleonlabs). That's where we talk features, share AI art and help each other with setup. No formality needed — "wouldn't it be cool if..." is a perfectly good opener. If the idea has legs, we'll help you shape it into an issue (or you can just build it and open a PR).

## Detailed issues and PRs get automatic analysis

Here's a perk worth knowing about: when you file a detailed issue or open a pull request, our automated tooling analyzes it against the actual codebase. It checks whether the bug was already fixed, traces the likely cause and often posts a diagnosis or review without you having to wait for a human.

The more you give it, the more you get back. Steps to reproduce, log output and version info produce a real analysis. "It doesn't work" produces a shrug.

## Reporting a bug

Before filing:

- **Search existing issues** — someone may have beaten you to it.
- **Update to the latest version** and confirm the bug is still there.
- **Grab your environment details** — OS, ImageAI version, Python version and which provider you were using (Google, OpenAI, Stability or Local SD).

Handy tip: ImageAI copies the most recent session log to `./imageai_current.log` in your working directory when it exits. Attach it. It usually tells us exactly what went wrong.

### Title

Short and specific. `[Bug] File upload fails with special characters` beats `Help, not working!` every time.

### What to include

**Summary:** one line describing the issue.

**Environment:** OS, ImageAI version, Python version, provider.

**Steps to reproduce:** numbered steps, starting from launch if needed.

**Expected vs. actual:** what you thought would happen, and what happened instead (include crashes, error text or log excerpts).

**Reproducibility:** always, intermittent or rare.

**Attachments:** screenshots, `imageai_current.log`, or a minimal example that triggers the bug. Small reproductions get fixed fastest.

## Suggesting a feature

Feature ideas are welcome as issues too — but for anything fuzzy or early-stage, Discord is the better first stop. A quick conversation there often saves a lot of back-and-forth in the issue thread. When you do file a feature issue, describe the problem you're trying to solve, not just the solution you have in mind. (Sometimes there's already a way to do it, and sometimes the real fix is even better than the first idea.)

## Pull requests

Want to fix it yourself? Even better.

1. Fork the repo and create a branch.
2. Set up your environment: `python -m venv .venv`, activate it, then `pip install -r requirements.txt` (details in the [README](README.md)).
3. Keep the PR focused — one fix or one feature per PR.
4. Describe what changed and why. Remember, detailed PRs get that same automatic analysis, so a clear description means a faster, better review.

Not sure whether a change would be accepted? Ask first — on Discord or in an issue. Nobody wants you to spend a weekend on something that needed a five-minute conversation.

## After you submit

Keep an eye on the thread and answer follow-up questions when they come. If your issue gets resolved, a quick note about what fixed it helps the next person who hits the same thing.

Thanks for helping make ImageAI better. See you on Discord!
