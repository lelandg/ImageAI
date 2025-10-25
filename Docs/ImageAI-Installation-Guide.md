# 🧭 ImageAI Installation Guide (Cross‑Platform, Non‑Technical)

This guide walks you through installing and running **ImageAI** on **Windows**, **macOS**, or **Linux** — even if you’ve never used developer tools before. It includes simple options for downloading, installing Python 3.12, setting up a secure environment, and adding your AI provider keys.

---

## 1️⃣  Downloading ImageAI

You have three main options to get the ImageAI files. Choose whichever feels easiest.

### Option A — Download ZIP (Simplest)
1. Visit **[https://github.com/lelandg/ImageAI](https://github.com/lelandg/ImageAI)**.  
2. Click **“Code” → “Download ZIP.”**  
3. Once downloaded, **right‑click → Extract All** (Windows) or **double‑click the ZIP** (macOS/Linux).  
4. You’ll get a folder named `ImageAI-main` — move it somewhere easy to find (e.g. Desktop or Documents).

### Option B — Use Git CLI (Command Line)
If you’re comfortable with a terminal:

```bash
git clone https://github.com/lelandg/ImageAI.git
cd ImageAI
```

**Why use this method?** You can later run `git pull` to update your copy easily.

### Option C — Use GitHub Desktop (Graphical App)
1. Install [GitHub Desktop](https://desktop.github.com/).  
2. In the app: **File → Clone Repository → URL** and enter  
   `https://github.com/lelandg/ImageAI.git`.  
3. Choose a local folder and click **Clone**.  
4. Click **Open in Explorer/Finder** to view your files.

Other GUI options: **Sourcetree**, **GitKraken**, or **VS Code’s Source Control** panel — they all work the same way.

---

## 2️⃣  Installing Python 3.12

ImageAI requires **Python 3.12** (or newer even‑numbered minor releases).

### Why 3.12?
- Stable long‑term support.  
- Compatible with most scientific and AI libraries.  
- Odd minor versions (3.11, 3.13, etc.) are **interim** releases that may break dependencies or lack binary wheels for key packages.

### How to Install
| System | Instructions |
|---------|---------------|
| **Windows** | Go to [python.org/downloads](https://www.python.org/downloads/). Choose *Python 3.12.x*. During setup, **check “Add Python to PATH.”** |
| **macOS** | Use the same website or install via Homebrew: `brew install python@3.12` |
| **Linux (Ubuntu/Debian)** | Run `sudo apt update && sudo apt install python3.12 python3.12-venv -y` |

To confirm installation, open a terminal or PowerShell window and type:

```bash
python --version
```

It should show **Python 3.12.x**.

---

## 3️⃣  Create a Virtual Environment

This keeps ImageAI’s libraries isolated so nothing else on your computer is affected.

1. Open a terminal (PowerShell on Windows or Terminal on macOS/Linux).  
2. Navigate to the ImageAI folder you downloaded:

```bash
cd path/to/ImageAI-main
```

3. Create a virtual environment:

```bash
python -m venv .venv
```

4. Activate it:

| OS | Command |
|----|----------|
| **Windows (PowerShell)** | `.\.venv\Scripts\Activate.ps1` |
| **macOS/Linux** | `source .venv/bin/activate` |

When active, your prompt will show **`(.venv)`** at the start.

---

## 4️⃣  Install Dependencies

While inside the activated environment, install required packages:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

If you see errors about permissions, ensure the virtual environment is active (look for `(.venv)` at the start of the line).

---

## 5️⃣  Run ImageAI

Once installed, start the program:

```bash
python app.py
```

The main interface will open. From here you can generate images, lyrics‑based prompts, and videos.

If it fails with “module not found,” double‑check that the virtual environment is active and `requirements.txt` was installed successfully.

---

## 6️⃣  Configure Authentication (API Keys)

ImageAI connects to various AI providers. You’ll need API keys or credentials depending on what you want to generate.

| Provider | Key Type | Recommended Use | Advantages |
|-----------|-----------|----------------|-------------|
| **OpenAI** | API Key (`sk-...`) | Text‑to‑image via DALL·E 3, or prompt enhancement | Simple, reliable, wide‑language support |
| **Anthropic** | API Key (`sk-ant-...`) | Prompt enhancement, storytelling, or caption generation | Creative and safe narrative generation |
| **Google Cloud (Veo / Gemini)** | `gcloud` authentication | Video, photo realism, and multimodal analysis | Fast generation, advanced context handling |

You can safely mix providers — ImageAI will route each request to the best available engine based on your settings.

> 🔐 **Tip:** Store keys only in your local `.env` or credentials file. Never post them publicly.

---

## 7️⃣  Next Steps

- See the **Help → Authentication** section in ImageAI’s built‑in Help tab or in the project’s README for detailed setup instructions for each provider.  
- Once authentication is complete, restart ImageAI to load the keys.  
- Your first prompts are now ready to run!

---

### Troubleshooting
| Issue | Likely Cause | Fix |
|-------|---------------|-----|
| “pip not found” | Python not added to PATH | Reinstall Python 3.12 and check “Add to PATH.” |
| “Permission denied” on activate | Script execution restricted on Windows | Run PowerShell as Administrator, then: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| “No module named ...” | Virtual environment inactive | Reactivate `.venv` and reinstall dependencies. |

---

✅ **You’re ready to create and explore with ImageAI!**  
For more help, open the **Help tab → Authentication** section inside the app or check the README in the repository.
