import argparse
import json
import os
import platform
import sys
from pathlib import Path
from typing import Optional, Tuple
import webbrowser

from google import genai
from google.genai import types

# UI imports are optional until --gui is requested
try:
    from PySide6.QtCore import Qt, QThread, Signal, QObject
    from PySide6.QtGui import QPixmap, QAction
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
            # Save first image if requested
            if images:
                out = args.out or str(Path.cwd() / "generated_image.png")
                Path(out).write_bytes(images[0])
                print(f"Saved image to {out}")
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Example Prompts")
        self.resize(520, 360)
        v = QVBoxLayout(self)
        self.listw = QListWidget()
        for ex in self.EXAMPLES:
            QListWidgetItem(ex, self.listw)
        v.addWidget(QLabel("Choose an example to insert into the prompt:"))
        v.addWidget(self.listw)
        btns = QHBoxLayout()
        self.btnInsert = QPushButton("Insert")
        self.btnClose = QPushButton("Close")
        btns.addStretch(1)
        btns.addWidget(self.btnInsert)
        btns.addWidget(self.btnClose)
        v.addLayout(btns)
        self.btnInsert.clicked.connect(self.accept)
        self.btnClose.clicked.connect(self.reject)

    def selected_text(self) -> Optional[str]:
        item = self.listw.currentItem()
        return item.text() if item else None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(900, 650)

        self.current_api_key, _ = resolve_api_key(None, None)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_generate = QWidget()
        self.tab_settings = QWidget()
        self.tab_help = QWidget()
        self.tabs.addTab(self.tab_generate, "Generate")
        self.tabs.addTab(self.tab_settings, "Settings")
        self.tabs.addTab(self.tab_help, "Help")

        self._init_generate()
        self._init_settings()
        self._init_help()
        self._init_menu()

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
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)

        v.addWidget(self.output_image_label)
        v.addWidget(QLabel("Output Text:"))
        v.addWidget(self.output_text)

        self.btn_examples.clicked.connect(self._open_examples)
        self.btn_generate.clicked.connect(self._on_generate)

        self.last_image_bytes: Optional[bytes] = None

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

        self.btn_browse.clicked.connect(self._browse_key)
        self.btn_get_key.clicked.connect(self._open_api_key_page)
        self.btn_save_test.clicked.connect(self._save_and_test)

        v.addStretch(1)

    # -------- settings handlers --------

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

    # -------- generate handlers --------

    def _open_examples(self):
        dlg = ExamplesDialog(self)
        if dlg.exec() == QDialog.Accepted:
            txt = dlg.selected_text()
            if txt:
                self.prompt_edit.setPlainText(txt)

    def _on_generate(self):
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, APP_NAME, "Please enter a prompt.")
            return
        api_key = self.current_api_key or self.api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, APP_NAME, "No API key configured. Go to Settings to save one.")
            self.tabs.setCurrentWidget(self.tab_settings)
            return
        model = self.model_combo.currentText().strip() or DEFAULT_MODEL

        self.btn_generate.setEnabled(False)
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
        if error:
            self.status_label.setText("Error")
            QMessageBox.critical(self, APP_NAME, error)
            return
        # Display text
        if texts:
            self.output_text.setPlainText("\n\n".join(texts))
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
        if self.last_image_bytes and not self.output_image_label.pixmap().isNull():
            pix = QPixmap()
            pix.loadFromData(self.last_image_bytes)
            self.output_image_label.setPixmap(pix.scaled(
                self.output_image_label.width(),
                self.output_image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            ))

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