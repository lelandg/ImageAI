import argparse
import json
import os
import platform
import sys
from pathlib import Path
from typing import Optional, Tuple
import webbrowser
from datetime import datetime

from google import genai
from google.genai import types

__version__ = "0.4.0"
PROVIDER_NAME = "google"

# UI imports are optional until --gui is requested
try:
    from PySide6.QtCore import Qt, QThread, Signal, QObject
    from PySide6.QtGui import QPixmap, QAction, QGuiApplication
    from PySide6.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QTextEdit,
        QTextBrowser,
        QPushButton,
        QFileDialog,
        QMessageBox,
        QTabWidget,
        QComboBox,
        QDialog,
        QListWidget,
        QListWidgetItem,
        QFormLayout,
        QSizePolicy,
        QCheckBox,
    )
except Exception:
    # If PySide6 isn't installed yet, CLI will still work.
    QApplication = None  # type: ignore

APP_NAME = "LelandGreenGenAI"
DEFAULT_MODEL = "gemini-2.5-flash-image-preview"
API_KEY_URL = "https://aistudio.google.com/apikey"


# ---------------------------
# Cross-platform user config
# ---------------------------

def user_config_dir() -> Path:
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        base = Path(os.getenv("APPDATA", home / "AppData" / "Roaming"))
        return base / APP_NAME
    elif system == "Darwin":  # macOS
        return home / "Library" / "Application Support" / APP_NAME
    else:  # Linux/Unix
        # Prefer XDG_CONFIG_HOME if set
        base = Path(os.getenv("XDG_CONFIG_HOME", home / ".config"))
        return base / APP_NAME


def config_path() -> Path:
    d = user_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "config.json"


def load_config() -> dict:
    cfg_file = config_path()
    if cfg_file.exists():
        try:
            return json.loads(cfg_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_config(cfg: dict) -> None:
    cfg_file = config_path()
    cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


# ---------------------------
# Details (templates) persistence
# ---------------------------

def details_path() -> Path:
    d = user_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "details.jsonl"


def save_details_record(details: dict) -> None:
    try:
        p = details_path()
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(details, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_key_file(path: Path) -> Optional[str]:
    try:
        # Read first non-empty line as key
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s:
                return s
    except Exception:
        return None
    return None


# ---------------------------
# README helpers
# ---------------------------

README_PATH = Path(__file__).parent / "README.md"


def read_readme_text() -> str:
    try:
        if README_PATH.exists():
            return README_PATH.read_text(encoding="utf-8")
    except Exception:
        pass
    # Fallback minimal help
    return (
        "Google Gemini API setup:\n"
        "1) Visit AI Studio and create an API key: " + API_KEY_URL + "\n"
        "2) Enable billing if required: https://ai.google.dev/pricing\n"
        "3) Save your key in the app Settings or via CLI -s with -k/-K.\n"
    )


def extract_api_key_help(md: str) -> str:
    # Extract the section starting at the API key/billing header until the next top-level header (## )
    start_header = "## 2) Get your Gemini API key and enable billing"
    if start_header in md:
        start = md.index(start_header)
        # Find next section header after start
        remainder = md[start + len(start_header):]
        next_idx = remainder.find("\n## ")
        if next_idx != -1:
            return start_header + remainder[:next_idx]
        else:
            return md[start:]
    # If not found, return entire README
    return md


# ---------------------------
# API key resolution
# ---------------------------

def resolve_api_key(cli_key: Optional[str], cli_key_file: Optional[str]) -> Tuple[Optional[str], str]:
    """Return (api_key, source). Precedence: CLI key > CLI key file > stored config > env GOOGLE_API_KEY.
    """
    if cli_key:
        return cli_key.strip(), "cli"
    if cli_key_file:
        p = Path(cli_key_file).expanduser()
        if p.exists():
            k = read_key_file(p)
            if k:
                return k, f"file:{p}"
    cfg = load_config()
    if isinstance(cfg, dict) and cfg.get("api_key"):
        return str(cfg["api_key"]).strip(), "stored"
    env_k = os.getenv("GOOGLE_API_KEY")
    if env_k:
        return env_k.strip(), "env:GOOGLE_API_KEY"
    return None, "none"


def store_api_key(key: str) -> None:
    cfg = load_config()
    cfg["api_key"] = key.strip()
    save_config(cfg)


# ---------------------------
# Google GenAI helpers
# ---------------------------

def make_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def generate_any(client: genai.Client, model: str, prompt: str):
    """Call generate_content. Returns (texts, image_bytes_list)."""
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    texts = []
    images = []
    if response and response.candidates:
        cand = response.candidates[0]
        if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
            for part in cand.content.parts:
                # part.text or part.inline_data
                if getattr(part, "text", None):
                    texts.append(part.text)
                elif getattr(part, "inline_data", None) is not None:
                    data = getattr(part.inline_data, "data", None)
                    if isinstance(data, (bytes, bytearray)):
                        images.append(bytes(data))
    return texts, images


def images_output_dir() -> Path:
    """Directory where generated images are auto-saved."""
    d = user_config_dir() / "generated"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sidecar_path(image_path: Path) -> Path:
    """Return the path of the JSON sidecar for a given image path."""
    return image_path.with_suffix(image_path.suffix + ".json")


def write_image_sidecar(image_path: Path, meta: dict) -> None:
    """Write human-readable JSON beside the image. Avoid secrets, use indent=2."""
    try:
        p = sidecar_path(image_path)
        # Ensure only simple types are stored
        p.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except Exception:
        pass


def detect_image_extension(data: bytes) -> str:
    """Guess file extension from image bytes. Defaults to .png."""
    try:
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if data.startswith(b"\xff\xd8"):
            return ".jpg"
        if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
            return ".gif"
        if data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
            return ".webp"
    except Exception:
        pass
    return ".png"


def sanitize_stub_from_prompt(prompt: str, max_len: int = 60) -> str:
    """Create a safe filename stub from the prompt. Collapses whitespace, removes unsafe chars,
    limits length, and falls back to 'gen' if empty."""
    try:
        s = (prompt or "").strip()
        # use only first line to avoid huge names
        s = s.splitlines()[0] if s else ""
        # Replace separators with spaces, keep alnum, space, dash, underscore
        allowed = []
        for ch in s:
            if ch.isalnum() or ch in (" ", "-", "_"):
                allowed.append(ch)
            else:
                # convert other separators to space
                allowed.append(" ")
        s = "".join(allowed)
        # collapse whitespace to single underscore
        s = "_".join([t for t in s.strip().split() if t])
        if not s:
            s = "gen"
        # trim length
        if len(s) > max_len:
            s = s[:max_len].rstrip("_-")
        # Ensure doesn't start with dot to avoid hidden files on some OS
        if s.startswith("."):
            s = s.lstrip(".") or "gen"
        return s
    except Exception:
        return "gen"


def auto_save_images(images: list, base_stub: str = "gen") -> list:
    """Auto-save all images to the images_output_dir(). Returns list of absolute Paths."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = images_output_dir()
    saved = []
    for idx, data in enumerate(images, start=1):
        ext = detect_image_extension(data if isinstance(data, (bytes, bytearray)) else bytes(data))
        name = f"{base_stub}_{ts}_{idx}{ext}"
        p = out_dir / name
        p.write_bytes(data)
        saved.append(p.resolve())
    return saved


def read_image_sidecar(image_path: Path) -> Optional[dict]:
    try:
        sp = sidecar_path(image_path)
        if sp.exists():
            return json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def scan_disk_history(max_items: int = 500) -> list[Path]:
    """Scan generated dir for images and return sorted list by mtime desc."""
    try:
        out_dir = images_output_dir()
        exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        items = [p for p in out_dir.iterdir() if p.is_file() and p.suffix.lower() in exts]
        items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return items[:max_items]
    except Exception:
        return []


def find_cached_demo(prompt: str) -> Optional[Path]:
    """If prompt is one of the examples and a sidecar matches prompt+provider, return newest image path."""
    try:
        if prompt not in getattr(ExamplesDialog, "EXAMPLES", []):
            return None
        matches: list[tuple[float, Path]] = []
        for img in scan_disk_history(1000):
            meta = read_image_sidecar(img)
            if not meta:
                continue
            if meta.get("prompt") == prompt and meta.get("provider") == PROVIDER_NAME:
                try:
                    mtime = img.stat().st_mtime
                except Exception:
                    mtime = 0.0
                matches.append((mtime, img))
        if matches:
            matches.sort(key=lambda t: t[0], reverse=True)
            return matches[0][1]
    except Exception:
        return None
    return None


# ---------------------------
# CLI
# ---------------------------

def run_cli(args) -> int:
    # Print API key setup help and exit, if requested
    if getattr(args, "help_api_key", False):
        md = read_readme_text()
        section = extract_api_key_help(md)
        print(section)
        return 0
    key, source = resolve_api_key(args.api_key, args.api_key_file)
    if args.set_key:
        # Persist either provided key or from file
        set_key = args.api_key
        if not set_key and args.api_key_file:
            fp = Path(args.api_key_file).expanduser()
            set_key = read_key_file(fp)
        if not set_key:
            print("No API key provided to --set-key. Use --api-key or --api-key-file.")
            return 2
        store_api_key(set_key)
        print(f"API key saved to {config_path()}")
        # Also use it for this invocation
        key = set_key
        source = "stored"

    if args.test:
        if not key:
            print("No API key found. Provide with --api-key/--api-key-file or set via --set-key.")
            return 2
        try:
            client = make_client(key)
            # Light call: list models OR tiny generation attempt
            # The SDK may not have list; do a minimal generation with a tiny prompt
            generate_any(client, args.model or DEFAULT_MODEL, "Hello from test")
            print(f"API key appears valid (source={source}).")
            return 0
        except Exception as e:
            print(f"API key test failed: {e}")
            return 3

    if args.prompt:
        if not key:
            print("No API key. Use --api-key/--api-key-file or --set-key.")
            return 2
        try:
            client = make_client(key)
            model = args.model or DEFAULT_MODEL
            texts, images = generate_any(client, model, args.prompt)
            # Print texts
            for t in texts:
                print(t)
            # Auto-save images
            if images:
                if args.out:
                    first_out = Path(args.out).expanduser().resolve()
                    first_out.parent.mkdir(parents=True, exist_ok=True)
                    first_out.write_bytes(images[0])
                    print(f"Saved image to {first_out}")
                    # Save remaining images alongside the first with numbered suffixes
                    stem = first_out.stem
                    for i, data in enumerate(images[1:], start=2):
                        ext2 = first_out.suffix if first_out.suffix else detect_image_extension(data)
                        p = first_out.with_name(f"{stem}_{i}{ext2}")
                        p.write_bytes(data)
                        print(f"Saved image to {p}")
                else:
                    stub = sanitize_stub_from_prompt(args.prompt)
                    saved_paths = auto_save_images(images, base_stub=stub)
                    for p in saved_paths:
                        print(f"Saved image to {p}")
            return 0
        except Exception as e:
            print(f"Generation failed: {e}")
            return 4

    # If nothing else, suggest usage
    print("Nothing to do. Run without arguments to open the GUI, or use -p/--prompt to generate, or -t/--test to validate the key.")
    return 0


# ---------------------------
# UI (PySide6)
# ---------------------------

class GenWorker(QObject):
    finished = Signal(list, list, str)  # texts, images(bytes), error

    def __init__(self, api_key: str, model: str, prompt: str):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.prompt = prompt

    def run(self):
        try:
            client = make_client(self.api_key)
            texts, images = generate_any(client, self.model, self.prompt)
            self.finished.emit(texts, images, "")
        except Exception as e:
            self.finished.emit([], [], str(e))


class ExamplesDialog(QDialog):
    EXAMPLES = [
        "A whimsical city made of candy canes and gumdrops at sunset, ultra-detailed, 8k",
        "A photorealistic glass terrarium containing a micro jungle with tiny glowing fauna",
        "Retro-futuristic poster of a rocket-powered bicycle racing across neon clouds",
        "An isometric diorama of a tiny island with waterfalls flowing into space",
        "Blueprint style render of a mechanical hummingbird with clockwork internals",
        "Studio portrait of a robot chef carefully plating molecular gastronomy",
        "A children’s book illustration of a dragon learning to paint with oversized brushes",
        "Macro shot of dew drops forming constellations on a leaf under moonlight",
    ]

    # Simple set of templates inspired by Gemini image generation docs
    TEMPLATES = [
        {
            "name": "Photorealistic product shot",
            "template": "A high-resolution studio photograph of [product] on a [background] background, [lighting] lighting, [camera] lens, [style] style, [mood] mood"
        },
        {
            "name": "Character concept art",
            "template": "Concept art of [character], [age], wearing [clothing], in a [pose] pose, in [environment], [style] style, [mood] mood, highly detailed"
        },
        {
            "name": "Landscape matte painting",
            "template": "A wide-angle [environment] landscape with [weather], [time of day], [style] style, [details]"
        },
        {
            "name": "Isometric game asset",
            "template": "Isometric pixel art of [object], using a [palette] palette, at [scale] scale, with [details] on a transparent background"
        },
        {
            "name": "Flat icon / logo",
            "template": "A flat vector icon of [subject], [color palette], [style] style, [background] background, minimal, scalable"
        },
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Examples & Templates")
        self.resize(620, 440)

        self.append_to_prompt: bool = False
        self._last_values: dict[str, dict[str, str]] = {}

        v = QVBoxLayout(self)
        # Tabs: Examples and Templates
        self.tabs = QTabWidget()

        # --- Examples tab ---
        tab_examples = QWidget()
        v_ex = QVBoxLayout(tab_examples)
        self.listw = QListWidget()
        for ex in self.EXAMPLES:
            QListWidgetItem(ex, self.listw)
        v_ex.addWidget(QLabel("Choose an example to insert into the prompt:"))
        v_ex.addWidget(self.listw)
        self.tabs.addTab(tab_examples, "Examples")

        # --- Templates tab (dynamic, like main Templates) ---
        tab_templates = QWidget()
        v_t = QVBoxLayout(tab_templates)
        v_t.addWidget(QLabel("Select a template and fill in any attributes (all optional):"))
        self.template_combo = QComboBox()
        self.template_combo.addItems([t["name"] for t in self.TEMPLATES])
        v_t.addWidget(self.template_combo)
        # Dynamic form container
        self.template_form = QFormLayout()
        self.template_form_holder = QWidget()
        self.template_form_holder.setLayout(self.template_form)
        v_t.addWidget(self.template_form_holder)
        # Signals and initial form build
        self.template_combo.currentIndexChanged.connect(self._rebuild_template_form)
        self._rebuild_template_form()
        self.tabs.addTab(tab_templates, "Templates")

        v.addWidget(self.tabs)

        # Options
        self.chkAppend = QCheckBox("Append to current prompt instead of replacing")
        v.addWidget(self.chkAppend)

        # Buttons
        btns = QHBoxLayout()
        self.btnInsert = QPushButton("Insert")
        self.btnClose = QPushButton("Close")
        btns.addStretch(1)
        btns.addWidget(self.btnInsert)
        btns.addWidget(self.btnClose)
        v.addLayout(btns)

        # Signals
        self.btnInsert.clicked.connect(self._on_insert)
        self.btnClose.clicked.connect(self.reject)
        # No dynamic template form in dialog anymore

    def _current_template(self) -> Tuple[str, str]:
        idx = self.template_combo.currentIndex() if hasattr(self, "template_combo") else -1
        if 0 <= idx < len(self.TEMPLATES):
            t = self.TEMPLATES[idx]
            return t["name"], t["template"]
        return "", ""

    def _rebuild_template_form(self):
        # Clear existing rows
        while self.template_form.rowCount():
            self.template_form.removeRow(0)
        # Build from placeholders in template
        name, tmpl = self._current_template()
        if not tmpl:
            return
        import re
        placeholders = []
        try:
            placeholders = [p for p in re.findall(r"\[([^\[\]]+)\]", tmpl)]
        except Exception:
            placeholders = []
        # Deduplicate preserving order
        seen = set()
        ordered = []
        for p in placeholders:
            if p not in seen:
                seen.add(p)
                ordered.append(p)
        # Create line edits
        self._template_fields = {}
        prev_vals = self._last_values.get(name, {}) if hasattr(self, "_last_values") else {}
        for key in ordered:
            le = QLineEdit()
            le.setPlaceholderText(f"[{key}]")
            if isinstance(prev_vals, dict) and prev_vals.get(key):
                le.setText(str(prev_vals.get(key)))
            else:
                le.setText(f"[{key}]")
            try:
                le.textChanged.connect(self._on_field_changed)
            except Exception:
                pass
            self._template_fields[key] = le
            self.template_form.addRow(QLabel(key + ":"), le)
        # After rebuilding, autosave current state
        try:
            self._autosave_template_state()
        except Exception:
            pass

    def _collect_template_fields(self) -> dict:
        vals: dict[str, str] = {}
        if hasattr(self, "_template_fields"):
            for key, le in self._template_fields.items():
                vals[key] = (le.text() or "").strip()
        return vals

    def _assemble_preview(self) -> str:
        # Non-persisting assembler used for autosave preview
        name, tmpl = self._current_template()
        if not tmpl:
            return ""
        filled_raw = self._collect_template_fields()
        # Treat bracketed values as empty
        filled: dict[str, str] = {}
        for k, v in filled_raw.items():
            if v.startswith("[") and v.endswith("]"):
                filled[k] = ""
            else:
                filled[k] = v
        import re as _re
        segments = [s.strip() for s in tmpl.split(',')]
        out_segments = []
        for seg in segments:
            phs = _re.findall(r"\[([^\[\]]+)\]", seg)
            seg_out = seg
            # Replace or remove placeholders
            for p in phs:
                val = filled.get(p, "")
                if val:
                    seg_out = seg_out.replace(f"[{p}]", val)
                else:
                    # remove common preposition/article + placeholder or bare placeholder
                    patterns = [
                        rf"\b(?:a|an|the)\s*\[{_re.escape(p)}\]",
                        rf"\b(?:in|on|with|using|at|of|for|to)\s*\[{_re.escape(p)}\]",
                        rf"\[{_re.escape(p)}\]",
                    ]
                    for pat in patterns:
                        seg_out = _re.sub(pat, "", seg_out)
            # Cleanup repeated spaces and dangling connectors
            seg_out = _re.sub(r"\s{2,}", " ", seg_out).strip()
            seg_out = _re.sub(r"^(?:and|with|in|on|using|at|of|for|to)\b[,\s]*", "", seg_out, flags=_re.IGNORECASE)
            seg_out = _re.sub(r"[,\s]*(?:and|with|in|on|using|at|of|for|to)$", "", seg_out, flags=_re.IGNORECASE)
            if seg_out:
                out_segments.append(seg_out)
        out = ", ".join([s for s in out_segments if s]).strip()
        out = _re.sub(r"\s+,\s+", ", ", out)
        out = out.strip().strip(',').strip()
        out = _re.sub(r"\s{2,}", " ", out).strip()
        return out

    def _autosave_template_state(self):
        try:
            name, tmpl = self._current_template()
            fields_now = self._collect_template_fields()
            # Update in-session cache of last values
            if hasattr(self, "_last_values"):
                self._last_values[name] = dict(fields_now)
            details = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "template_name": name,
                "template_string": tmpl,
                "fields": fields_now,
                "assembled_preview": self._assemble_preview(),
                "event": "template_autosave",
            }
            save_details_record(details)
        except Exception:
            pass

    def _on_field_changed(self, *_):
        try:
            self._autosave_template_state()
        except Exception:
            pass

    def _assemble_from_template(self) -> Optional[str]:
        name, tmpl = self._current_template()
        if not tmpl:
            return None
        out = self._assemble_preview()
        # Persist assembled on explicit insert
        try:
            details = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "template_name": name,
                "template_string": tmpl,
                "fields": self._collect_template_fields(),
                "assembled_prompt": out,
                "event": "template_insert",
            }
            save_details_record(details)
        except Exception:
            pass
        return out if out else None

    def _on_insert(self):
        # Determine which tab is active and collect text
        self.append_to_prompt = bool(self.chkAppend.isChecked())
        if self.tabs.currentIndex() == 1:  # Templates tab (dynamic)
            out = None
            try:
                # Assemble using the same logic as _assemble_preview, and persist details
                name, tmpl = self._current_template()
                out = self._assemble_preview()
                details = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "template_name": name,
                    "template_string": tmpl,
                    "fields": self._collect_template_fields(),
                    "assembled_prompt": out,
                    "event": "template_insert_examples",
                }
                save_details_record(details)
            except Exception:
                pass
            if out:
                self._selected = out
                # Provide full template context back to MainWindow
                try:
                    self.selected_template_context = {
                        "name": name,
                        "template": tmpl,
                        "fields": dict(self._collect_template_fields()),
                        "assembled_prompt": out,
                        "append": self.append_to_prompt,
                        "source": "examples_dialog_templates_tab",
                    }
                except Exception:
                    self.selected_template_context = None
                self.accept()
            else:
                QMessageBox.information(self, APP_NAME, "Please fill in template fields or select a template.")
        else:  # Examples tab
            item = self.listw.currentItem()
            if item:
                self._selected = item.text()
                # Clear any template context for plain examples
                self.selected_template_context = None
                self.accept()
            else:
                QMessageBox.information(self, APP_NAME, "Please select an example.")

    def selected_text(self) -> Optional[str]:
        return getattr(self, "_selected", None)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(900, 650)

        self.current_api_key, _ = resolve_api_key(None, None)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_generate = QWidget()
        self.tab_templates = QWidget()
        self.tab_settings = QWidget()
        self.tab_help = QWidget()
        self.tab_history = QWidget()
        self.tabs.addTab(self.tab_generate, "Generate")
        self.tabs.addTab(self.tab_templates, "Templates")
        self.tabs.addTab(self.tab_settings, "Settings")
        # Insert History before Help
        self.tabs.addTab(self.tab_help, "Help")

        # Session state
        self.history_paths: list[Path] = scan_disk_history()
        self.current_prompt: str = ""
        self.current_model: str = DEFAULT_MODEL
        try:
            cfg = load_config()
            self.auto_copy_filename: bool = bool(cfg.get("auto_copy_filename", False))
            # Restore window geometry if present
            try:
                geo = cfg.get("window_geometry") if isinstance(cfg, dict) else None
                if isinstance(geo, dict):
                    x = int(geo.get("x", self.x()))
                    y = int(geo.get("y", self.y()))
                    w = int(geo.get("w", self.width()))
                    h = int(geo.get("h", self.height()))
                    self.move(x, y)
                    self.resize(w, h)
            except Exception:
                pass
        except Exception:
            self.auto_copy_filename = False

        self._init_generate()
        self._init_templates()
        self._init_settings()
        self._init_history()
        # Place History before Help
        idx_help = self.tabs.indexOf(self.tab_help)
        if idx_help != -1:
            self.tabs.insertTab(idx_help, self.tab_history, "History")
        else:
            self.tabs.addTab(self.tab_history, "History")
        self._init_help()
        self._init_menu()
        # Template context tracking for history sidecar embedding
        self._last_template_context: Optional[dict] = None
        self._suppress_dirty_clear_template: bool = False

    def _init_menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu("File")
        act_save = QAction("Save Image As...", self)
        act_save.triggered.connect(self._save_image_as)
        file_menu.addAction(act_save)

    def _init_generate(self):
        v = QVBoxLayout(self.tab_generate)
        form = QFormLayout()
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            DEFAULT_MODEL,
            "gemini-2.0-flash-lite-preview-02-05",
            "gemini-2.0-flash-thinking-exp-01-21",
        ])
        form.addRow("Model:", self.model_combo)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText(
            "Describe what to generate... (image or text)."
        )
        self.prompt_edit.setAcceptRichText(False)
        # Make the prompt area visually about 3 lines tall and fixed vertically
        try:
            fm = self.prompt_edit.fontMetrics()
            line_h = fm.lineSpacing() if fm else 18
            self.prompt_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.prompt_edit.setFixedHeight(int(line_h * 3 + 12))
            # Allow scrolling if user types more than 3 lines
            self.prompt_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        except Exception:
            pass
        form.addRow("Prompt:", self.prompt_edit)

        v.addLayout(form)
        hb = QHBoxLayout()
        self.btn_examples = QPushButton("Examples")
        self.btn_generate = QPushButton("Generate")
        hb.addWidget(self.btn_examples)
        hb.addStretch(1)
        hb.addWidget(self.btn_generate)
        v.addLayout(hb)

        self.status_label = QLabel("Ready.")
        v.addWidget(self.status_label)

        self.output_image_label = QLabel()
        self.output_image_label.setAlignment(Qt.AlignCenter)
        self.output_image_label.setMinimumHeight(300)
        # Allow the image label to expand and fill available space
        self.output_image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        # Make the output text area visually about 3 lines tall and fixed vertically
        try:
            fm2 = self.output_text.fontMetrics()
            line_h2 = fm2.lineSpacing() if fm2 else 18
            self.output_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.output_text.setFixedHeight(int(line_h2 * 3 + 12))
            self.output_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        except Exception:
            pass

        # Give the image area dominant space in the layout
        v.addWidget(self.output_image_label, 10)
        v.addWidget(QLabel("Output Text:"))
        v.addWidget(self.output_text)

        self.btn_examples.clicked.connect(self._open_examples)
        self.btn_generate.clicked.connect(self._on_generate)
        try:
            self.prompt_edit.textChanged.connect(self._mark_dirty)
            self.model_combo.currentTextChanged.connect(self._mark_dirty)
        except Exception:
            pass

        self.last_image_bytes: Optional[bytes] = None

    def _init_templates(self):
        v = QVBoxLayout(self.tab_templates)
        # Templates data moved from Examples dialog
        self.tmpl_templates = [
            {
                "name": "Photorealistic product shot",
                "template": "A high-resolution studio photograph of [product] on a [background] background, [lighting] lighting, [camera] lens, [style] style, [mood] mood",
            },
            {
                "name": "Character concept art",
                "template": "Concept art of [character], [age], wearing [clothing], in a [pose] pose, in [environment], [style] style, [mood] mood, highly detailed",
            },
            {
                "name": "Landscape matte painting",
                "template": "A wide-angle [environment] landscape with [weather], [time of day], [style] style, [details]",
            },
            {
                "name": "Isometric game asset",
                "template": "Isometric pixel art of [object], using a [palette] palette, at [scale] scale, with [details] on a transparent background",
            },
            {
                "name": "Flat icon / logo",
                "template": "A flat vector icon of [subject], [color palette], [style] style, [background] background, minimal, scalable",
            },
        ]
        v.addWidget(QLabel("Select a template and fill in any attributes (all optional):"))
        self.tmpl_combo = QComboBox()
        self.tmpl_combo.addItems([t["name"] for t in self.tmpl_templates])
        v.addWidget(self.tmpl_combo)
        # Dynamic form container
        self.tmpl_form = QFormLayout()
        self.tmpl_form_holder = QWidget()
        self.tmpl_form_holder.setLayout(self.tmpl_form)
        v.addWidget(self.tmpl_form_holder)
        # Options
        self.chkAppendTemplate = QCheckBox("Append to current prompt instead of replacing")
        v.addWidget(self.chkAppendTemplate)
        # Buttons
        hb = QHBoxLayout()
        self.btn_insert_template = QPushButton("Insert into Prompt")
        hb.addStretch(1)
        hb.addWidget(self.btn_insert_template)
        v.addLayout(hb)
        # Signals
        self.tmpl_combo.currentIndexChanged.connect(self._tmpl_rebuild_template_form)
        try:
            self.chkAppendTemplate.toggled.connect(self._tmpl_autosave_template_state)
        except Exception:
            pass
        self.btn_insert_template.clicked.connect(self._on_insert_template_to_prompt)
        # State holders
        self._tmpl_last_values: dict[str, dict[str, str]] = {}
        # Build initial form
        self._tmpl_rebuild_template_form()
        try:
            self._tmpl_autosave_template_state()
        except Exception:
            pass

    def _tmpl_current_template(self) -> Tuple[str, str]:
        idx = self.tmpl_combo.currentIndex() if hasattr(self, "tmpl_combo") else -1
        if 0 <= idx < len(self.tmpl_templates):
            t = self.tmpl_templates[idx]
            return t["name"], t["template"]
        return "", ""

    def _tmpl_rebuild_template_form(self):
        # Clear existing rows
        while self.tmpl_form.rowCount():
            self.tmpl_form.removeRow(0)
        # Build from placeholders in template
        name, tmpl = self._tmpl_current_template()
        if not tmpl:
            return
        import re
        try:
            placeholders = [p for p in re.findall(r"\[([^\[\]]+)\]", tmpl)]
        except Exception:
            placeholders = []
        # Deduplicate preserving order
        seen = set()
        ordered = []
        for p in placeholders:
            if p not in seen:
                seen.add(p)
                ordered.append(p)
        # Create line edits
        self._tmpl_fields = {}
        prev_vals = self._tmpl_last_values.get(name, {}) if hasattr(self, "_tmpl_last_values") else {}
        for key in ordered:
            le = QLineEdit()
            le.setPlaceholderText(f"[{key}]")
            if isinstance(prev_vals, dict) and prev_vals.get(key):
                le.setText(str(prev_vals.get(key)))
            else:
                le.setText(f"[{key}]")
            try:
                le.textChanged.connect(self._tmpl_on_field_changed)
            except Exception:
                pass
            self._tmpl_fields[key] = le
            self.tmpl_form.addRow(QLabel(key + ":"), le)
        # After rebuilding, autosave current state
        try:
            self._tmpl_autosave_template_state()
        except Exception:
            pass

    def _tmpl_collect_fields(self) -> dict:
        vals: dict[str, str] = {}
        if hasattr(self, "_tmpl_fields"):
            for key, le in self._tmpl_fields.items():
                vals[key] = (le.text() or "").strip()
        return vals

    def _tmpl_assemble_preview(self) -> str:
        name, tmpl = self._tmpl_current_template()
        if not tmpl:
            return ""
        filled_raw = self._tmpl_collect_fields()
        filled: dict[str, str] = {}
        for k, v in filled_raw.items():
            if v.startswith("[") and v.endswith("]"):
                filled[k] = ""
            else:
                filled[k] = v
        import re as _re
        segments = [s.strip() for s in tmpl.split(',')]
        out_segments = []
        for seg in segments:
            phs = _re.findall(r"\[([^\[\]]+)\]", seg)
            seg_out = seg
            for p in phs:
                val = filled.get(p, "")
                if val:
                    seg_out = seg_out.replace(f"[{p}]", val)
                else:
                    patterns = [
                        rf"\b(?:a|an|the)\s*\[{_re.escape(p)}\]",
                        rf"\b(?:in|on|with|using|at|of|for|to)\s*\[{_re.escape(p)}\]",
                        rf"\[{_re.escape(p)}\]",
                    ]
                    for pat in patterns:
                        seg_out = _re.sub(pat, "", seg_out)
            seg_out = _re.sub(r"\s{2,}", " ", seg_out).strip()
            seg_out = _re.sub(r"^(?:and|with|in|on|using|at|of|for|to)\b[,\s]*", "", seg_out, flags=_re.IGNORECASE)
            seg_out = _re.sub(r"[,\s]*(?:and|with|in|on|using|at|of|for|to)$", "", seg_out, flags=_re.IGNORECASE)
            if seg_out:
                out_segments.append(seg_out)
        out = ", ".join([s for s in out_segments if s]).strip()
        out = _re.sub(r"\s+,\s+", ", ", out)
        out = out.strip().strip(',').strip()
        out = _re.sub(r"\s{2,}", " ", out).strip()
        return out

    def _tmpl_autosave_template_state(self):
        try:
            name, tmpl = self._tmpl_current_template()
            fields_now = self._tmpl_collect_fields()
            if hasattr(self, "_tmpl_last_values"):
                self._tmpl_last_values[name] = dict(fields_now)
            details = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "template_name": name,
                "template_string": tmpl,
                "fields": fields_now,
                "assembled_preview": self._tmpl_assemble_preview(),
                "event": "template_autosave_main",
            }
            save_details_record(details)
        except Exception:
            pass

    def _tmpl_on_field_changed(self, *_):
        try:
            self._tmpl_autosave_template_state()
        except Exception:
            pass

    def _on_insert_template_to_prompt(self):
        txt = self._tmpl_assemble_preview()
        if not txt:
            QMessageBox.information(self, APP_NAME, "Please select a template or fill in fields (optional).")
            return
        name, tmpl = self._tmpl_current_template()
        fields = self._tmpl_collect_fields()
        append = bool(self.chkAppendTemplate.isChecked())
        # Track context for sidecar embedding
        self._last_template_context = {
            "name": name,
            "template": tmpl,
            "fields": dict(fields),
            "assembled_prompt": txt,
            "append": append,
            "source": "main_templates_tab",
        }
        try:
            details = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "template_name": name,
                "template_string": tmpl,
                "fields": fields,
                "assembled_prompt": txt,
                "event": "template_insert_main",
            }
            save_details_record(details)
        except Exception:
            pass
        existing = (self.prompt_edit.toPlainText() or "").strip()
        try:
            self._suppress_dirty_clear_template = True
            if append and existing:
                self.prompt_edit.setPlainText(existing + " " + txt)
            else:
                self.prompt_edit.setPlainText(txt)
        finally:
            self._suppress_dirty_clear_template = False
        try:
            self._mark_dirty()
        except Exception:
            pass

    def _init_settings(self):
        v = QVBoxLayout(self.tab_settings)
        form = QFormLayout()
        self.api_key_edit = QLineEdit()
        if self.current_api_key:
            self.api_key_edit.setText(self.current_api_key)
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("API Key:", self.api_key_edit)

        self.storage_path_label = QLabel(str(config_path()))
        form.addRow("Stored at:", self.storage_path_label)

        # Options
        self.chk_auto_copy = QCheckBox("Auto copy saved filename to clipboard")
        try:
            self.chk_auto_copy.setChecked(bool(self.auto_copy_filename))
        except Exception:
            pass
        form.addRow(self.chk_auto_copy)

        v.addLayout(form)
        hb = QHBoxLayout()
        self.btn_browse = QPushButton("Load from file…")
        self.btn_get_key = QPushButton("Get API key")
        self.btn_save_test = QPushButton("Save & Test")
        hb.addWidget(self.btn_browse)
        hb.addWidget(self.btn_get_key)
        hb.addStretch(1)
        hb.addWidget(self.btn_save_test)
        v.addLayout(hb)

        self.chk_auto_copy.toggled.connect(self._toggle_auto_copy)
        self.btn_browse.clicked.connect(self._browse_key)
        self.btn_get_key.clicked.connect(self._open_api_key_page)
        self.btn_save_test.clicked.connect(self._save_and_test)

        v.addStretch(1)

    # -------- settings handlers --------

    def _toggle_auto_copy(self, checked: bool):
        try:
            self.auto_copy_filename = bool(checked)
            cfg = load_config()
            if not isinstance(cfg, dict):
                cfg = {}
            cfg["auto_copy_filename"] = self.auto_copy_filename
            save_config(cfg)
        except Exception:
            # Silently ignore config save errors
            pass

    def _browse_key(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Select API Key File", str(Path.home()))
        if fn:
            k = read_key_file(Path(fn))
            if k:
                self.api_key_edit.setText(k)
            else:
                QMessageBox.warning(self, APP_NAME, "Could not read an API key from the selected file.")

    def _save_and_test(self):
        key = self.api_key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, APP_NAME, "Please enter an API key.")
            return
        try:
            store_api_key(key)
            self.current_api_key = key
            # quick test
            client = make_client(key)
            generate_any(client, DEFAULT_MODEL, "Hello from UI test")
            QMessageBox.information(self, APP_NAME, f"API key saved and tested.\nLocation: {config_path()}")
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"API key test failed: {e}")

    def _open_api_key_page(self):
        try:
            webbrowser.open(API_KEY_URL)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Could not open browser: {e}")

    def _init_help(self):
        v = QVBoxLayout(self.tab_help)
        self.help_browser = QTextBrowser()
        # Make help text larger and improve image layout
        try:
            # Increase base font size for the help viewer
            self.help_browser.setStyleSheet("QTextBrowser { font-size: 13pt; }")
            # Center images and add spacing; also bump heading sizes
            doc = self.help_browser.document()
            doc.setDefaultStyleSheet(
                "body { font-size: 13pt; line-height: 1.4; }\n"
                "h1 { font-size: 20pt; }\n"
                "h2 { font-size: 16pt; }\n"
                "img { display: block; margin: 12px auto; max-width: 100%; height: auto; }\n"
            )
        except Exception:
            pass
        md = read_readme_text()
        try:
            self.help_browser.setMarkdown(md)
        except Exception:
            self.help_browser.setPlainText(md)
        try:
            self.help_browser.setOpenExternalLinks(True)
        except Exception:
            pass
        v.addWidget(self.help_browser)

    def _init_history(self):
        v = QVBoxLayout(self.tab_history)
        # List of files
        self.list_history = QListWidget()
        self.list_history.itemSelectionChanged.connect(self._on_history_selection_changed)
        try:
            self.list_history.itemDoubleClicked.connect(self._on_history_item_double_clicked)
        except Exception:
            pass
        v.addWidget(QLabel("Generated Images:"))
        v.addWidget(self.list_history)
        # Preview area
        self.history_preview_label = QLabel()
        self.history_preview_label.setAlignment(Qt.AlignCenter)
        self.history_preview_label.setMinimumHeight(240)
        self.history_preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        v.addWidget(QLabel("Preview:"))
        v.addWidget(self.history_preview_label, 10)
        # Buttons
        hb = QHBoxLayout()
        self.btn_history_save = QPushButton("Save As…")
        self.btn_history_save.clicked.connect(self._history_save_as)
        hb.addStretch(1)
        hb.addWidget(self.btn_history_save)
        v.addLayout(hb)
        # Populate if any
        self._refresh_history_list()

    def _refresh_history_list(self):
        try:
            self.list_history.clear()
            for p in self.history_paths:
                item = QListWidgetItem(os.path.basename(str(p)))
                # Store full path in item data
                item.setData(Qt.UserRole, str(p))
                # Tooltip with full path
                item.setToolTip(str(p))
                self.list_history.addItem(item)
        except Exception:
            pass

    def _on_history_selection_changed(self):
        try:
            items = self.list_history.selectedItems()
            if not items:
                self.history_preview_label.clear()
                return
            item = items[0]
            full_path = item.data(Qt.UserRole)
            if not full_path:
                self.history_preview_label.clear()
                return
            p = Path(full_path)
            if not p.exists():
                self.history_preview_label.setText("File not found.")
                return
            data = p.read_bytes()
            # Update History preview
            pix_hist = QPixmap()
            if pix_hist.loadFromData(data):
                self.history_preview_label.setPixmap(pix_hist.scaled(
                    self.history_preview_label.width(),
                    self.history_preview_label.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                ))
            else:
                self.history_preview_label.setText("Preview unavailable.")
            # Reload into Generate tab: prompt/model and main preview
            meta = read_image_sidecar(p)
            if isinstance(meta, dict):
                pr = meta.get("prompt")
                if isinstance(pr, str) and pr:
                    self.prompt_edit.setPlainText(pr)
                    self.current_prompt = pr
                mdl = meta.get("model")
                if isinstance(mdl, str) and mdl:
                    idx = self.model_combo.findText(mdl)
                    if idx >= 0:
                        self.model_combo.setCurrentIndex(idx)
                    else:
                        # Ensure model is selectable
                        self.model_combo.addItem(mdl)
                        self.model_combo.setCurrentText(mdl)
                    self.current_model = mdl
            # Update main preview
            self.last_image_bytes = data
            pix_main = QPixmap()
            if pix_main.loadFromData(data):
                self.output_image_label.setPixmap(pix_main.scaled(
                    self.output_image_label.width(),
                    self.output_image_label.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                ))
            try:
                self.status_label.setText("Loaded from history")
            except Exception:
                pass
            # Mark dirty since prompt/model changed via history
            try:
                self._mark_dirty()
            except Exception:
                pass
            # Switch to Generate tab for editing/regeneration
            try:
                self.tabs.setCurrentWidget(self.tab_generate)
            except Exception:
                pass
        except Exception:
            self.history_preview_label.setText("Error loading preview.")

    def _on_history_item_double_clicked(self, item):
        try:
            if not item:
                return
            full_path = item.data(Qt.UserRole)
            if not full_path:
                return
            p = Path(full_path)
            meta = read_image_sidecar(p)
            if isinstance(meta, dict):
                tctx = meta.get("template")
                if isinstance(tctx, dict):
                    # Keep context for next generation
                    self._last_template_context = dict(tctx)
                    try:
                        self._restore_template_from_context(tctx)
                    except Exception:
                        pass
        except Exception:
            pass

    def _restore_template_from_context(self, ctx: dict):
        try:
            if not isinstance(ctx, dict):
                return
            name = ctx.get("name")
            tmpl = ctx.get("template")
            fields = ctx.get("fields") if isinstance(ctx.get("fields"), dict) else {}
            # Find or add template by name or by template string
            idx = -1
            if name:
                for i, t in enumerate(self.tmpl_templates):
                    if t.get("name") == name:
                        idx = i
                        break
            if idx == -1 and tmpl:
                for i, t in enumerate(self.tmpl_templates):
                    if t.get("template") == tmpl:
                        idx = i
                        break
            if idx == -1 and name and tmpl:
                # Add unknown template so we can restore
                self.tmpl_templates.append({"name": name, "template": tmpl})
                try:
                    self.tmpl_combo.addItem(name)
                except Exception:
                    pass
                idx = len(self.tmpl_templates) - 1
            if idx >= 0:
                try:
                    self.tmpl_combo.setCurrentIndex(idx)
                except Exception:
                    pass
                # Rebuild form to ensure fields exist
                try:
                    self._tmpl_rebuild_template_form()
                except Exception:
                    pass
                # Populate fields
                try:
                    for k, v in fields.items():
                        le = self._tmpl_fields.get(k) if hasattr(self, "_tmpl_fields") else None
                        if le is not None:
                            le.setText(str(v))
                except Exception:
                    pass
                try:
                    self._tmpl_autosave_template_state()
                except Exception:
                    pass
            # Switch to Templates tab
            try:
                self.tabs.setCurrentWidget(self.tab_templates)
            except Exception:
                pass
        except Exception:
            pass

    def _history_save_as(self):
        try:
            items = self.list_history.selectedItems()
            if not items:
                QMessageBox.information(self, APP_NAME, "No history item selected.")
                return
            item = items[0]
            full_path = item.data(Qt.UserRole)
            if not full_path:
                QMessageBox.warning(self, APP_NAME, "Missing file path.")
                return
            src = Path(full_path)
            if not src.exists():
                QMessageBox.warning(self, APP_NAME, "File does not exist on disk.")
                return
            # Suggest same name in Save As dialog
            fn, _ = QFileDialog.getSaveFileName(self, "Save Image As", str(Path.home() / src.name), "Images (*.png *.jpg *.jpeg *.gif *.webp);;All Files (*.*)")
            if fn:
                try:
                    Path(fn).write_bytes(src.read_bytes())
                    QMessageBox.information(self, APP_NAME, f"Saved: {fn}")
                except Exception as e:
                    QMessageBox.critical(self, APP_NAME, f"Save failed: {e}")
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Error: {e}")

    # -------- generate handlers --------

    def _open_examples(self):
        dlg = ExamplesDialog(self)
        if dlg.exec() == QDialog.Accepted:
            txt = dlg.selected_text()
            ctx = getattr(dlg, "selected_template_context", None)
            if ctx and txt:
                # Capture context for sidecar embedding
                self._last_template_context = dict(ctx)
                # Also pre-populate Templates tab with chosen template and fields
                try:
                    self._restore_template_from_context(ctx)
                except Exception:
                    pass
            if txt:
                append = bool(getattr(dlg, "append_to_prompt", False))
                existing = (self.prompt_edit.toPlainText() or "").strip()
                try:
                    self._suppress_dirty_clear_template = True
                    if append and existing:
                        self.prompt_edit.setPlainText(existing + " " + txt)
                    else:
                        self.prompt_edit.setPlainText(txt)
                finally:
                    self._suppress_dirty_clear_template = False
            try:
                self._mark_dirty()
            except Exception:
                pass

    def _mark_dirty(self, *args):
        try:
            self.btn_generate.setText("Generate")
        except Exception:
            pass
        # Clear last template context on user edits unless suppressed
        try:
            if not getattr(self, "_suppress_dirty_clear_template", False):
                self._last_template_context = None
        except Exception:
            pass

    def _on_generate(self):
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, APP_NAME, "Please enter a prompt.")
            return
        # Remember current prompt for naming and clipboard
        self.current_prompt = prompt
        model = self.model_combo.currentText().strip() or DEFAULT_MODEL
        self.current_model = model

        # Demo cache: if prompt is one of the examples and a cached image exists for this provider, load it
        cached = find_cached_demo(prompt)
        if cached and cached.exists():
            try:
                data = cached.read_bytes()
                self.last_image_bytes = data
                pix = QPixmap()
                pix.loadFromData(data)
                self.output_image_label.setPixmap(pix.scaled(
                    self.output_image_label.width(),
                    self.output_image_label.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                ))
                # Output text: show first line with status and absolute path on second line
                self.output_text.setPlainText("Loaded cached demo\n" + str(cached.resolve()))
                self.status_label.setText("Loaded cached demo")
                try:
                    self.btn_generate.setText("Regenerate")
                except Exception:
                    pass
                # Ensure item is in history list
                try:
                    if cached not in self.history_paths:
                        self.history_paths.insert(0, cached)
                        self._refresh_history_list()
                except Exception:
                    pass
                return
            except Exception:
                # fallback to normal generation if cache load fails
                pass

        api_key = self.current_api_key or self.api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, APP_NAME, "No API key configured. Go to Settings to save one.")
            self.tabs.setCurrentWidget(self.tab_settings)
            return

        self.btn_generate.setEnabled(False)
        try:
            self.btn_generate.setText("Generating…")
        except Exception:
            pass
        self.status_label.setText("Generating…")
        self.output_text.clear()
        self.output_image_label.clear()

        self.thread = QThread(self)
        self.worker = GenWorker(api_key, model, prompt)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_generated)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _on_generated(self, texts, images, error: str):
        self.btn_generate.setEnabled(True)
        try:
            self.btn_generate.setText("Regenerate")
        except Exception:
            pass
        if error:
            self.status_label.setText("Error")
            QMessageBox.critical(self, APP_NAME, error)
            return
        # Auto-save any images
        saved_paths = []
        if images:
            try:
                stub = sanitize_stub_from_prompt(self.current_prompt)
                saved_paths = auto_save_images(images, base_stub=stub)
                # Update in-session history
                try:
                    self.history_paths.extend(saved_paths)
                    self._refresh_history_list()
                except Exception:
                    pass
                # Write sidecar JSON for each saved image
                try:
                    first_line = (texts[0].strip() if texts else "")
                    meta_base = {
                        "prompt": self.current_prompt,
                        "model": getattr(self, "current_model", self.model_combo.currentText().strip() or DEFAULT_MODEL),
                        "provider": PROVIDER_NAME,
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                        "app_version": __version__,
                        "output_text": first_line,
                        "settings": {
                            "auto_copy_filename": bool(getattr(self, "auto_copy_filename", False)),
                        },
                    }
                    for pth in saved_paths:
                        meta = dict(meta_base)
                        try:
                            if getattr(self, "_last_template_context", None):
                                meta["template"] = dict(self._last_template_context)
                        except Exception:
                            pass
                        write_image_sidecar(Path(pth), meta)
                except Exception:
                    pass
                # Optionally copy filename (without path) to clipboard
                try:
                    if getattr(self, "auto_copy_filename", False) and saved_paths:
                        fname = os.path.basename(str(saved_paths[0]))
                        cb = QGuiApplication.clipboard()
                        if cb:
                            cb.setText(fname)
                except Exception:
                    pass
            except Exception as e:
                # Saving failed; we still show the image and indicate error
                saved_paths = []
                QMessageBox.warning(self, APP_NAME, f"Auto-save failed: {e}")
        # Prepare output text with absolute filename on second line when image exists
        if images:
            lines = []
            first_line = (texts[0].strip() if texts else "Done (image generated)").strip()
            lines.append(first_line)
            if saved_paths:
                lines.append(str(saved_paths[0]))  # absolute path on second line
            # Optional third line info
            if len(saved_paths) > 1:
                lines.append(f"Saved {len(saved_paths)} images to {images_output_dir()}")
            elif not saved_paths:
                lines.append("(Auto-save failed)")
            # Set output text (limit to up to 3 lines to keep UI compact)
            self.output_text.setPlainText("\n".join(lines[:3]))
        else:
            # No images: retain original behavior of showing all texts
            if texts:
                self.output_text.setPlainText("\n\n".join(texts))
            else:
                self.output_text.setPlainText("Done")
        # Display first image
        self.last_image_bytes = None
        if images:
            self.last_image_bytes = images[0]
            pix = QPixmap()
            pix.loadFromData(self.last_image_bytes)
            self.output_image_label.setPixmap(pix.scaled(
                self.output_image_label.width(),
                self.output_image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            ))
            self.status_label.setText("Done (image generated)")
        else:
            self.status_label.setText("Done")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Rescale image on resize
        if self.last_image_bytes:
            pix = QPixmap()
            pix.loadFromData(self.last_image_bytes)
            self.output_image_label.setPixmap(pix.scaled(
                self.output_image_label.width(),
                self.output_image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            ))

    def closeEvent(self, event):
        try:
            cfg = load_config()
            if not isinstance(cfg, dict):
                cfg = {}
            cfg["window_geometry"] = {
                "x": int(self.x()),
                "y": int(self.y()),
                "w": int(self.width()),
                "h": int(self.height()),
            }
            save_config(cfg)
        except Exception:
            pass
        try:
            super().closeEvent(event)
        except Exception:
            event.accept()

    def _save_image_as(self):
        if not self.last_image_bytes:
            QMessageBox.information(self, APP_NAME, "No image to save.")
            return
        fn, _ = QFileDialog.getSaveFileName(self, "Save Image", str(Path.home() / "generated_image.png"), "PNG (*.png);;JPEG (*.jpg *.jpeg);;All Files (*.*)")
        if fn:
            try:
                Path(fn).write_bytes(self.last_image_bytes)
                QMessageBox.information(self, APP_NAME, f"Saved: {fn}")
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Save failed: {e}")


# ---------------------------
# Entrypoint
# ---------------------------

def build_arg_parser():
    p = argparse.ArgumentParser(
        description="LelandGreenGenAI: CLI for Gemini image/text generation. Run without arguments to open the GUI.")
    p.add_argument("-k", "--api-key", dest="api_key", help="API key string (takes precedence)")
    p.add_argument("-K", "--api-key-file", dest="api_key_file", help="Path to a file containing the API key.")
    p.add_argument("-s", "--set-key", action="store_true", help="Persist the provided key to user config.")
    p.add_argument("-t", "--test", action="store_true", help="Test that the resolved API key works.")
    p.add_argument("-p", "--prompt", help="Prompt to generate from (CLI mode).")
    p.add_argument("-m", "--model", help=f"Model to use (default: {DEFAULT_MODEL}).")
    p.add_argument("-o", "--out", help="Output path for the first generated image (CLI mode).")
    p.add_argument("-H", "--help-api-key", action="store_true", help="Print API key setup and billing instructions and exit.")
    return p


def main():
    # If no command-line arguments are provided, launch the GUI by default
    if len(sys.argv) == 1:
        if QApplication is None:
            print("PySide6 is not installed. Install dependencies and try again.")
            return 1
        app = QApplication([])
        win = MainWindow()
        win.show()
        return app.exec()

    # If any arguments are provided (including -h), run console mode
    parser = build_arg_parser()
    args = parser.parse_args()
    return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())