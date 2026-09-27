"""
Tests for the two defensive LLM-output fixups both exporters (and the
frontend's in-browser preview) rely on. strip_wrapping_code_fence was added
after a real live run against samples/Format Multiple Excel Sheets.knwf came
back with its entire document wrapped in a single ```markdown fence — this
locks that fix in with the actual shape of markdown the LLM produced.
"""

from app.exporters.markdown_render import clean_markdown, strip_leading_h1, strip_wrapping_code_fence

_REAL_WRAPPED_EXAMPLE = (
    "```markdown\n"
    "## Purpose\n\n"
    "To be confirmed by workflow owner.\n\n"
    "## Inputs\n\n"
    "- **Read Excel Sheet Names** (node 11): reads sheet names.\n"
    "```"
)


def test_strip_wrapping_code_fence_unwraps_whole_document():
    result = strip_wrapping_code_fence(_REAL_WRAPPED_EXAMPLE)
    assert not result.startswith("```")
    assert not result.endswith("```")
    assert result.startswith("## Purpose")


def test_strip_wrapping_code_fence_ignores_fence_without_language_tag():
    wrapped = "```\n## Purpose\n\nText.\n```"
    result = strip_wrapping_code_fence(wrapped)
    assert result == "## Purpose\n\nText."


def test_strip_wrapping_code_fence_leaves_normal_markdown_alone():
    markdown = "## Purpose\n\nText with an inline `code` span.\n"
    assert strip_wrapping_code_fence(markdown) == markdown


def test_strip_wrapping_code_fence_leaves_embedded_fence_alone():
    """A fence used deliberately partway through the doc (e.g. a config
    snippet in Notes) must not be touched — only a fence spanning the entire
    document is the bug this guards against."""
    markdown = "## Purpose\n\nText.\n\n## Notes\n\nExample:\n\n```json\n{\"a\": 1}\n```\n"
    assert strip_wrapping_code_fence(markdown) == markdown


def test_clean_markdown_unwraps_fence_then_strips_leading_h1():
    wrapped_with_title = "```markdown\n# Retry Database Connection\n\n## Purpose\n\nText.\n```"
    result = clean_markdown(wrapped_with_title)
    assert result == "## Purpose\n\nText."
    # Confirms the ordering matters: stripping the H1 first (before
    # unwrapping) would never find it, since it's inside the fence.
    assert strip_leading_h1(wrapped_with_title) == wrapped_with_title
