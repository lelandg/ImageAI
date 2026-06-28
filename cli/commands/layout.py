"""CLI handlers for the publication layout engine (design / fill / export)."""
import logging
from pathlib import Path

from cli.runner import resolve_api_key
from core.layout import designer, project_io, styles
from core.layout.models import DocumentSpec, PageSpec, Region
from core.layout.page_sizes import PRESETS, preset_to_page_size
from providers import get_provider

logger = logging.getLogger("imageai.cli.layout")


def _resolve_preset(name: str) -> dict:
    """Match a user page-size name to a PRESETS entry (case-insensitive, substring)."""
    n = (name or "").strip().lower()
    for p in PRESETS:
        if p["name"].lower() == n:
            return p
    for p in PRESETS:
        if n and n in p["name"].lower():
            return p
    choices = ", ".join(p["name"] for p in PRESETS)
    raise ValueError(f"Unknown page size {name!r}. Choices: {choices}")


def _page_px(page_size: str, orientation: str, dpi: int) -> tuple:
    """Resolve (width_px, height_px) for a named page size at an orientation/DPI."""
    ps = preset_to_page_size(_resolve_preset(page_size), orientation, dpi)
    return ps.to_pixels()


def _export_format(out_path: str) -> str:
    """Return 'pdf' or 'png' from the output extension, else raise ValueError."""
    suffix = Path(out_path).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".png":
        return "png"
    raise ValueError(f"--layout-export -o must end in .pdf or .png (got {out_path!r})")


def _region_size_str(region: Region, cap: int = 1024) -> str:
    """'WxH' for a region's bbox, scaled so the long edge is <= cap (aspect kept)."""
    _, _, w, h = region.bbox
    w, h = int(w), int(h)
    longest = max(w, h, 1)
    if longest > cap:
        scale = cap / longest
        w = max(1, round(w * scale))
        h = max(1, round(h * scale))
    return f"{w}x{h}"


def run_design_cmd(args, config) -> int:
    """Generate a layout project from a text description via the layout LLM."""
    text = args.layout_design
    out = getattr(args, "out", None)
    if not out:
        print("Error: --layout-design requires -o/--out (project .json path)")
        return 2
    content_kind = getattr(args, "content_kind", None) or "custom"
    page_size = getattr(args, "page_size", None) or "Letter"
    orientation = getattr(args, "orientation", None) or "portrait"
    dpi = int(getattr(args, "dpi", None) or 300)
    llm_provider = getattr(args, "layout_llm_provider", None) or config.get_layout_llm_provider()
    llm_model = getattr(args, "layout_llm_model", None)
    try:
        page_px = _page_px(page_size, orientation, dpi)
    except ValueError as e:
        print(f"Error: {e}")
        return 2

    messages = designer.build_messages(content_kind, page_px, text)
    try:
        content = designer.run_completion(config, llm_provider, llm_model, messages)
    except Exception as e:  # noqa: BLE001 - surface + log any LLM/runtime failure
        logger.error("Layout design LLM call failed: %s", e)
        print(f"Error: layout design failed: {e}")
        return 3

    result = designer.parse_response(content or "", page_px)
    for q in result.questions:
        print(f"[designer] {q}")
    title = Path(out).stem or "Untitled"
    doc = _assemble_document(result, page_size, orientation, dpi, content_kind, title)
    project_io.save_project(doc, str(Path(out).expanduser()))
    page0 = doc.pages[0]
    print(f"Saved layout project to {out} "
          f"({len(page0.regions)} regions, {len(page0.overlays)} overlays)")
    return 0


def run_fill_cmd(args, config) -> int:
    """Generate images for every prompted image region, in-place (or to -o)."""
    src = Path(getattr(args, "layout_fill")).expanduser()
    if not src.exists():
        print(f"Error: project file not found: {src}")
        return 2
    try:
        doc = project_io.load_project(str(src))
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to load project %s: %s", src, e)
        print(f"Error: failed to load project: {e}")
        return 2

    provider = (getattr(args, "provider", None) or "google").strip().lower()
    key, _ = resolve_api_key(getattr(args, "api_key", None),
                             getattr(args, "api_key_file", None), provider)
    if not key and provider != "local_sd":
        print("No API key. Use --api-key/--api-key-file or --set-key.")
        return 2
    provider_config = {"api_key": key, "auth_mode": getattr(args, "auth_mode", "api-key")}
    try:
        provider_instance = get_provider(provider, provider_config)
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to init provider %s: %s", provider, e)
        print(f"Error: {e}")
        return 2
    model = getattr(args, "model", None) or provider_instance.get_default_model()
    images_dir = Path(config.get_images_dir())
    images_dir.mkdir(parents=True, exist_ok=True)
    stem = src.stem

    filled, skipped, failed = 0, [], []
    for page in doc.pages:
        for r in page.regions:
            if r.kind != "image":
                continue
            if not (r.prompt or "").strip():
                skipped.append(r.id)
                continue
            try:
                _texts, images = provider_instance.generate(
                    prompt=r.prompt, model=model,
                    size=_region_size_str(r), n=1)
                if not images:
                    logger.error("Fill: no image returned for region %s", r.id)
                    failed.append(r.id)
                    continue
                img_path = images_dir / f"{stem}_{r.id}.png"
                img_path.write_bytes(images[0])
                r.image_ref = str(img_path)
                filled += 1
                print(f"Filled region {r.id} -> {img_path}")
            except Exception as e:  # noqa: BLE001 - log, continue, report
                logger.error("Fill failed for region %s: %s", r.id, e)
                print(f"Failed region {r.id}: {e}")
                failed.append(r.id)

    out = Path(getattr(args, "out", None) or src).expanduser()
    project_io.save_project(doc, str(out))
    print(f"Saved project to {out}. "
          f"Filled {filled}, skipped {len(skipped)}, failed {len(failed)}.")
    return 0 if not failed else 4


def _assemble_document(result, page_size: str, orientation: str, dpi: int,
                       content_kind: str, title: str) -> DocumentSpec:
    """Build a one-page DocumentSpec from a DesignerResult (mirrors GUI new-doc)."""
    ps = preset_to_page_size(_resolve_preset(page_size), orientation, dpi)
    pw, ph = ps.to_pixels()
    regions = (result.regions if result.regions is not None
               else designer.fallback_result((pw, ph)).regions)
    page = PageSpec(
        page_size_px=(pw, ph), page_size=ps, background="#FFFFFF",
        regions=list(regions), overlays=list(result.overlays or []),
    )
    return DocumentSpec(
        title=title or "Untitled", pages=[page],
        content_kind=content_kind, style=styles.default_style_for(content_kind),
    )
