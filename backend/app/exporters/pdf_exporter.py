"""
Converts documentation markdown into a styled PDF: markdown -> HTML
(markdown-it-py) -> PDF (WeasyPrint). The CSS mirrors style.py's DOCX values
(same accent color, same disclaimer/date header block) so the two formats
read as one document family rather than two unrelated outputs.
"""

from datetime import datetime
from html import escape

from weasyprint import HTML

from app.exporters.markdown_render import clean_markdown, render_html
from app.exporters.style import ACCENT_HEX, DISCLAIMER_TEXT, PDF_FONT_STACK, format_generated_date

_CSS = f"""
@page {{ size: A4; margin: 2.2cm 2cm; }}
body {{ font-family: {PDF_FONT_STACK}; font-size: 11pt; color: #1a1a1a; line-height: 1.45; }}
h1, h2, h3, h4 {{ color: #{ACCENT_HEX}; font-weight: 700; }}
h1.doc-title {{ font-size: 22pt; margin-bottom: 0.1em; }}
.meta {{ font-style: italic; font-size: 9.5pt; color: #444; margin: 0 0 0.2em 0; }}
.disclaimer {{ font-style: italic; font-size: 9.5pt; color: #B00020; margin: 0 0 1.2em 0; }}
h2 {{ font-size: 15pt; border-bottom: 1px solid #{ACCENT_HEX}; padding-bottom: 0.15em; margin-top: 1.4em; }}
ul, ol {{ margin: 0.3em 0 0.8em 0; padding-left: 1.4em; }}
li {{ margin: 0.15em 0; }}
code {{ font-family: "Courier New", monospace; background: #f2f2f2; padding: 0.05em 0.3em; border-radius: 3px; font-size: 0.92em; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.6em 0 1em 0; }}
th, td {{ border: 1px solid #ccc; padding: 0.35em 0.6em; text-align: left; font-size: 10pt; }}
th {{ background: #{ACCENT_HEX}; color: #fff; }}
"""


def build_pdf(workflow_name: str, generated_at: datetime, markdown: str) -> bytes:
    title = escape(workflow_name or "Documentation")
    body_html = render_html(clean_markdown(markdown))
    html = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><style>{_CSS}</style></head>
<body>
<h1 class="doc-title">{title}</h1>
<p class="meta">Generated: {escape(format_generated_date(generated_at))}</p>
<p class="disclaimer">{escape(DISCLAIMER_TEXT)}</p>
{body_html}
</body>
</html>"""
    return HTML(string=html).write_pdf()
