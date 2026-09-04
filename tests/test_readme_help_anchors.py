"""Guard tests for the Help tab's README source: every TOC link must resolve.

The Help tab renders README.md through ``MainWindow._markdown_to_html_with_anchors``,
which builds heading ids with ``MainWindow._github_slugify``. GitHub renders the same
file with its own slugger. A heading that the two slug rules disagree on gives a TOC
link that works in one renderer and dead-ends in the other, so both rules are checked
here. An emoji in a heading is exactly such a disagreement: the app strips the leading
hyphen it leaves behind and GitHub keeps it.
"""
import pathlib
import re

# Anchored on this file, not on the working directory: the Help tab reads the
# README that ships with the package, wherever pytest was started.
README = pathlib.Path(__file__).resolve().parents[1] / "README.md"

TOC_LINK_RE = re.compile(r"^\s*-\s*\[([^\]]+)\]\(#([^)]+)\)\s*$")
HEADING_RE = re.compile(r"^(#{2,6})\s+(.*?)\s*$")


def _readme_lines():
    return README.read_text(encoding="utf-8").splitlines()


def app_slug(text: str) -> str:
    """``gui/main_window.py``'s ``_github_slugify``, copied so the test needs no Qt."""
    value = text.lower()
    value = re.sub(r"[\s\.]+", "-", value)
    value = re.sub(r"[^\w\-]", "", value)
    return value.strip("-")


def github_slug(text: str) -> str:
    """github-slugger: lowercase, trim, drop punctuation, then spaces to hyphens.

    The trim happens before the drop, so a stripped leading emoji leaves a
    leading hyphen that GitHub keeps.
    """
    value = text.lower().strip()
    value = re.sub(r"[^\w\- ]", "", value)
    return value.replace(" ", "-")


def _headings():
    return [HEADING_RE.match(line).group(2)
            for line in _readme_lines() if HEADING_RE.match(line)]


def _toc_anchors():
    anchors = []
    for line in _readme_lines():
        match = TOC_LINK_RE.match(line)
        if match and not match.group(2).startswith("http"):
            anchors.append((match.group(1), match.group(2)))
    return anchors


def test_sprite_tab_section_exists():
    assert "#### Sprite Tab" in _readme_lines()


def test_sprite_tab_is_in_the_table_of_contents():
    assert ("Sprite Tab", "sprite-tab") in _toc_anchors()


def test_every_toc_anchor_matches_a_heading_in_both_slug_rules():
    headings = _headings()
    app_slugs = {app_slug(h) for h in headings}
    github_slugs = {github_slug(h) for h in headings}
    missing = [(label, anchor) for label, anchor in _toc_anchors()
               if anchor not in app_slugs or anchor not in github_slugs]
    assert not missing, (
        "TOC links that do not resolve in the Help tab and on GitHub alike: " + repr(missing))
