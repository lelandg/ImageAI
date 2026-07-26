"""CLI handler for custom-style management verbs."""
import json
import logging
import sys
from pathlib import Path

from core.styles.models import Style
from core.styles.store import StyleStore

logger = logging.getLogger("imageai.cli.style")


class StyleCliError(Exception):
    """User-facing CLI validation error (maps to exit code 2)."""


def _emit(msg: str) -> None:
    """Human-facing progress line -> stderr (keeps stdout pure for data)."""
    print(msg, file=sys.stderr)


def _require(store: StyleStore, name: str) -> Style:
    style = store.get_by_name(name)
    if style is None:
        names = ", ".join(s.name for s in store.list_styles()) or "(none)"
        raise StyleCliError(f"Style not found: {name}. Available: {names}")
    return style


def run_style_cmd(args, config) -> int:
    """Route style management verbs. Returns 0 ok / 2 user error / 3 failure."""
    store = StyleStore()
    try:
        if getattr(args, "style_list", False):
            styles = store.list_styles()
            if not styles:
                print("No styles saved. Create one with --style-create NAME "
                      "--style-images PATH...")
                return 0
            for s in styles:
                refs = len(s.reference_images)
                text = (s.prompt_text or "")[:60].replace("\n", " ")
                print(f"{s.id:24}  {s.name:24}  {refs:3} ref(s)  {text}")
            return 0

        if getattr(args, "style_show", None):
            style = _require(store, args.style_show)
            print(json.dumps(style.to_dict(), indent=2, ensure_ascii=False))
            return 0

        if getattr(args, "style_delete", None):
            style = _require(store, args.style_delete)
            store.delete(style.id)
            _emit(f"Deleted style '{style.name}' ({style.id})")
            return 0

        # Tasks 8-9 extend this router: --style-create, --style-export/import.
        raise StyleCliError("No style verb matched")
    except StyleCliError as e:
        logger.warning(str(e))
        print(f"Error: {e}")
        return 2
    except Exception as e:  # noqa: BLE001 - CLI boundary
        logger.error(f"Style command failed: {e}", exc_info=True)
        print(f"Error: {e}")
        return 3
