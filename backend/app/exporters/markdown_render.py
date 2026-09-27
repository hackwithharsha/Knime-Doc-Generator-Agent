"""
Thin shared wrapper around markdown-it-py, used by both exporters: the DOCX
builder walks the nested SyntaxTreeNode form (python-docx has no HTML/markdown
importer, so the token tree has to be walked by hand); the PDF builder just
needs the rendered HTML string for WeasyPrint. Table support requires the
"table" plugin — off by default in markdown-it-py's "commonmark" preset.
"""

import re

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

_MD = MarkdownIt("commonmark").enable("table")

# Anchored end-to-end (via fullmatch) so this only matches when the *entire*
# document is one big fence — never a legitimate code block the doc itself
# includes partway through (e.g. a config snippet in Notes), since that
# wouldn't span from the very first to the very last character.
_WRAPPING_FENCE_RE = re.compile(r"```(?:markdown|md)?\s*\n(.*)\n```", re.DOTALL)


def render_html(markdown_text: str) -> str:
    return _MD.render(markdown_text)


def parse_tree(markdown_text: str) -> SyntaxTreeNode:
    return SyntaxTreeNode(_MD.parse(markdown_text))


def strip_wrapping_code_fence(markdown_text: str) -> str:
    """Removes a single ```markdown fence wrapped around the *entire* document,
    if present. Found live: the Documentation Writer occasionally responds as
    if demonstrating markdown syntax (fencing its whole answer) rather than
    emitting raw markdown — on a large real workflow, not a small one, so it
    went unnoticed until testing with samples/Format Multiple Excel
    Sheets.knwf. Left in, every heading/list/table renders as one inert
    preformatted code block instead of being parsed."""
    match = _WRAPPING_FENCE_RE.fullmatch(markdown_text.strip())
    return match.group(1) if match else markdown_text


def strip_leading_h1(markdown_text: str) -> str:
    """Removes a single leading '# Title' line, if present. Both exporters
    always render their own title/date/disclaimer header block; the
    Documentation Writer's task only asks for the five '##' sections, but the LLM
    sometimes free-styles a top-level title line anyway — found by comparing
    two real generated documents, one with it and one without. Left in, it
    would show up as a duplicate heading above "Purpose"."""
    stripped = markdown_text.lstrip()
    if stripped.startswith("# "):
        _, _, rest = stripped.partition("\n")
        return rest.lstrip("\n")
    return markdown_text


def clean_markdown(markdown_text: str) -> str:
    """Applies both defensive LLM-output fixups the exporters need, in the
    order that matters: unwrap a whole-document code fence first (a stray
    leading '#' line would be *inside* the fence), then strip that H1."""
    return strip_leading_h1(strip_wrapping_code_fence(markdown_text))
