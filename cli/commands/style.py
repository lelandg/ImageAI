"""CLI handler for custom-style management verbs."""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from core.styles.analyzer import StyleAnalysisError, StyleAnalysisService
from core.styles.models import Style, StyleDescriptor
from core.styles.store import StyleStore, EXEMPLAR_DEFAULT_CAP

logger = logging.getLogger("imageai.cli.style")


class StyleCliError(Exception):
    """User-facing CLI validation error (maps to exit code 2)."""


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _emit(msg: str) -> None:
    """Human-facing progress line -> stderr (keeps stdout pure for data)."""
    print(msg, file=sys.stderr)


def _require(store: StyleStore, name: str) -> Style:
    style = store.get_by_name(name)
    if style is None:
        names = ", ".join(s.name for s in store.list_styles()) or "(none)"
        raise StyleCliError(f"Style not found: {name}. Available: {names}")
    return style


def _collect_images(specs) -> list:
    """Resolve --style-images specs (files, dirs, globs) to sorted unique paths."""
    import glob as globmod
    found = []
    for spec in specs or []:
        p = Path(spec).expanduser()
        if p.is_dir():
            found.extend(c for c in p.iterdir()
                         if c.suffix.lower() in IMAGE_EXTS)
        elif p.is_file():
            if p.suffix.lower() in IMAGE_EXTS:
                found.append(p)
            else:
                logger.warning(f"Skipping non-image file: {p}")
        else:
            found.extend(Path(m) for m in globmod.glob(str(p))
                         if Path(m).suffix.lower() in IMAGE_EXTS)
    unique = sorted(set(p.resolve() for p in found))
    if not unique:
        raise StyleCliError(
            f"No images found in: {', '.join(specs or ['(nothing)'])}")
    return unique


def _handle_create(args, config, store: StyleStore) -> int:
    if not getattr(args, "style_images", None):
        raise StyleCliError("--style-create requires --style-images PATH ...")
    paths = _collect_images(args.style_images)
    _emit(f"Deriving style '{args.style_create}' from {len(paths)} image(s)...")

    service = StyleAnalysisService(config,
                                   provider=getattr(args, "style_llm_provider", None),
                                   model=getattr(args, "style_llm_model", None))
    data = service.derive(paths, progress_cb=_emit)

    style = Style(id=store.new_id(args.style_create), name=args.style_create,
                  descriptor=StyleDescriptor.from_dict(data["descriptor"]),
                  prompt_text=data["prompt_text"],
                  source={"provider": service.provider, "model": service.model,
                          "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                          "image_count": len(paths)})
    store.add_reference_images(style, paths)
    style.exemplars = style.reference_images[:EXEMPLAR_DEFAULT_CAP]
    store.save(style)
    _emit(f"Created style '{style.name}' ({style.id}) with "
          f"{len(style.reference_images)} reference image(s)")
    print(style.id)  # stdout: the id, scripting-friendly
    return 0


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

        if getattr(args, "style_create", None):
            return _handle_create(args, config, store)

        # Task 9 extends this router: --style-export/import.
        if getattr(args, "style_export", None):
            style = _require(store, args.style_export)
            out = getattr(args, "out", None)
            if not out:
                raise StyleCliError(
                    "--style-export needs -o FILE.zip for the output path")
            out_path = Path(out).expanduser()
            if out_path.suffix.lower() != ".zip":
                out_path = out_path.with_suffix(".zip")
            if not store.export_zip(style.id, out_path):
                raise StyleCliError(f"Export failed for {style.id}")
            _emit(f"Exported '{style.name}' to {out_path}")
            return 0

        if getattr(args, "style_import", None):
            zip_path = Path(args.style_import).expanduser()
            if not zip_path.exists():
                raise StyleCliError(f"File not found: {zip_path}")
            imported = store.import_zip(zip_path)
            if imported is None:
                raise StyleCliError(f"Not a valid style zip: {zip_path}")
            _emit(f"Imported '{imported.name}' as {imported.id}")
            print(imported.id)
            return 0

        raise StyleCliError("No style verb matched")
    except (StyleCliError, StyleAnalysisError) as e:
        logger.warning(str(e))
        print(f"Error: {e}")
        return 2
    except Exception as e:  # noqa: BLE001 - CLI boundary
        logger.error(f"Style command failed: {e}", exc_info=True)
        print(f"Error: {e}")
        return 3
