"""
Converts documentation markdown into a styled .docx via python-docx.
python-docx has no markdown/HTML importer, so this walks markdown-it-py's
nested SyntaxTreeNode form (see markdown_render.py) and maps each node type
onto the matching python-docx call. Handles headings, paragraphs with inline
bold/italic/code, nested bullet/numbered lists, and tables — everything the
Documentation Writer's template (CLAUDE.md "Doc Template Sections") can
produce.
"""

import io
from datetime import datetime

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from docx.table import _Cell
from docx.text.paragraph import Paragraph
from docx.text.run import Run
from markdown_it.tree import SyntaxTreeNode

from app.exporters.markdown_render import clean_markdown, parse_tree
from app.exporters.style import ACCENT_HEX, DISCLAIMER_TEXT, DOCX_FONT, format_generated_date

_MAX_LIST_STYLE_DEPTH = 3


def build_docx(workflow_name: str, generated_at: datetime, markdown: str) -> bytes:
    document = Document()
    _apply_base_styles(document)

    document.add_heading(workflow_name or "Documentation", level=0)

    meta = document.add_paragraph()
    _add_italic_note(meta, f"Generated: {format_generated_date(generated_at)}")

    disclaimer = document.add_paragraph()
    run = _add_italic_note(disclaimer, DISCLAIMER_TEXT)
    run.font.color.rgb = RGBColor.from_string("B00020")

    document.add_paragraph()  # spacer before the doc body

    for node in parse_tree(clean_markdown(markdown)).children:
        _add_block(document, node)

    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def _apply_base_styles(document: Document) -> None:
    normal = document.styles["Normal"]
    normal.font.name = DOCX_FONT
    normal.font.size = Pt(11)

    accent = RGBColor.from_string(ACCENT_HEX)
    for style_name in ("Title", "Heading 1", "Heading 2", "Heading 3", "Heading 4"):
        style = document.styles[style_name]
        style.font.name = DOCX_FONT
        style.font.color.rgb = accent


def _add_italic_note(paragraph: Paragraph, text: str) -> Run:
    run = paragraph.add_run(text)
    run.italic = True
    run.font.size = Pt(10)
    return run


def _add_block(document: Document, node: SyntaxTreeNode, list_depth: int = 0) -> None:
    if node.type == "heading":
        heading = document.add_heading(level=int(node.tag[1]))
        if node.children:
            _add_runs(heading, node.children[0])
    elif node.type == "paragraph":
        para = document.add_paragraph()
        if node.children:
            _add_runs(para, node.children[0])
    elif node.type in ("bullet_list", "ordered_list"):
        ordered = node.type == "ordered_list"
        for item in node.children:
            _add_list_item(document, item, list_depth + 1, ordered)
    elif node.type == "table":
        _add_table(document, node)
    elif node.type == "hr":
        document.add_paragraph("—" * 20)
    else:
        # Unhandled container (e.g. blockquote, fence) — best effort, recurse.
        for child in node.children:
            _add_block(document, child, list_depth)


def _add_list_item(document: Document, item_node: SyntaxTreeNode, depth: int, ordered: bool) -> None:
    style = _list_style(depth, ordered)
    for child in item_node.children:
        if child.type == "paragraph":
            para = document.add_paragraph(style=style)
            if child.children:
                _add_runs(para, child.children[0])
        elif child.type in ("bullet_list", "ordered_list"):
            nested_ordered = child.type == "ordered_list"
            for nested_item in child.children:
                _add_list_item(document, nested_item, depth + 1, nested_ordered)
        else:
            _add_block(document, child, depth)


def _list_style(depth: int, ordered: bool) -> str:
    depth = min(depth, _MAX_LIST_STYLE_DEPTH)
    base = "List Number" if ordered else "List Bullet"
    return base if depth == 1 else f"{base} {depth}"


def _add_runs(paragraph: Paragraph, inline_node: SyntaxTreeNode, bold: bool = False, italic: bool = False) -> None:
    for child in inline_node.children:
        if child.type == "text":
            if not child.content:
                continue
            run = paragraph.add_run(child.content)
            run.bold = bold
            run.italic = italic
        elif child.type == "code_inline":
            run = paragraph.add_run(child.content)
            run.bold = bold
            run.italic = italic
            run.font.name = "Consolas"
        elif child.type in ("softbreak", "hardbreak"):
            paragraph.add_run().add_break()
        elif child.type == "strong":
            _add_runs(paragraph, child, bold=True, italic=italic)
        elif child.type == "em":
            _add_runs(paragraph, child, bold=bold, italic=True)
        elif child.children:
            # Unhandled inline node (e.g. link) — best effort, recurse for its text.
            _add_runs(paragraph, child, bold=bold, italic=italic)


def _add_table(document: Document, table_node: SyntaxTreeNode) -> None:
    thead = next((c for c in table_node.children if c.type == "thead"), None)
    tbody = next((c for c in table_node.children if c.type == "tbody"), None)
    header_cells = thead.children[0].children if thead and thead.children else []
    body_rows = tbody.children if tbody else []

    n_cols = len(header_cells) or (len(body_rows[0].children) if body_rows else 0)
    if n_cols == 0:
        return

    table = document.add_table(rows=0, cols=n_cols)
    table.style = "Table Grid"

    if header_cells:
        row = table.add_row()
        for i, th in enumerate(header_cells):
            cell = row.cells[i]
            para = cell.paragraphs[0]
            if th.children:
                _add_runs(para, th.children[0], bold=True)
            for run in para.runs:
                run.font.color.rgb = RGBColor.from_string("FFFFFF")
            _shade_cell(cell, ACCENT_HEX)

    for tr in body_rows:
        row = table.add_row()
        for i, td in enumerate(tr.children[:n_cols]):
            para = row.cells[i].paragraphs[0]
            if td.children:
                _add_runs(para, td.children[0])


def _shade_cell(cell: _Cell, hex_color: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color)
    cell._tc.get_or_add_tcPr().append(shd)
