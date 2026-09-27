/**
 * Mirrors the backend's app/exporters/markdown_render.py — the in-browser
 * preview renders the same job.markdown the exporters do, so it needs the
 * same two defensive fixups or it shows the same bugs they had.
 */

const WRAPPING_FENCE_RE = /^```(?:markdown|md)?\s*\n([\s\S]*)\n```$/;

/**
 * Removes a single ```markdown fence wrapped around the *entire* document,
 * if present. Found live testing samples/Format Multiple Excel Sheets.knwf:
 * the Documentation Writer occasionally responds as if demonstrating
 * markdown syntax (fencing its whole answer) rather than emitting raw
 * markdown. Left in, react-markdown renders the whole doc as one inert
 * preformatted code block instead of parsing it.
 */
export function stripWrappingCodeFence(markdown: string): string {
  const match = markdown.trim().match(WRAPPING_FENCE_RE);
  return match ? match[1] : markdown;
}

/**
 * Removes a single leading "# Title" line, if present — the SOP/Doc Writer's
 * task only asks for the five "##" sections, but the LLM sometimes
 * free-styles a top-level title line anyway. Both exporters strip it before
 * rendering their own title; this component renders its own heading too
 * (from job.workflow_name), so it needs the same fix or it shows the same
 * duplicate-title bug the exporters had.
 */
export function stripLeadingH1(markdown: string): string {
  const stripped = markdown.replace(/^\s+/, "");
  if (stripped.startsWith("# ")) {
    const newlineIndex = stripped.indexOf("\n");
    return newlineIndex === -1 ? "" : stripped.slice(newlineIndex + 1).replace(/^\n+/, "");
  }
  return markdown;
}

/** Applies both fixups in the order that matters: unwrap the whole-document
 * code fence first (a stray leading "#" line would be *inside* the fence),
 * then strip that H1. */
export function cleanMarkdown(markdown: string): string {
  return stripLeadingH1(stripWrappingCodeFence(markdown));
}
