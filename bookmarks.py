"""Insert hierarchical PDF bookmarks from CHM TOC entries."""

from __future__ import annotations
import io
from pypdf import PdfWriter, PdfReader
from toc_parser import TocEntry


def merge_pdfs_with_bookmarks(topic_pdfs):
    writer = PdfWriter()
    page_offsets = {}
    current_page = 0
    for idx, (entry, pdf_bytes) in enumerate(topic_pdfs):
        if not pdf_bytes:
            page_offsets[idx] = max(current_page - 1, 0)
            continue
        reader = PdfReader(io.BytesIO(pdf_bytes))
        page_offsets[idx] = current_page
        for page in reader.pages:
            writer.add_page(page)
        current_page += len(reader.pages)
    if current_page == 0:
        writer.add_blank_page(width=595, height=842)
    _add_outline(writer, topic_pdfs, page_offsets)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _add_outline(writer, topic_pdfs, page_offsets):
    parent_stack = [None]
    for idx, (entry, _) in enumerate(topic_pdfs):
        page_num = page_offsets.get(idx, 0)
        title = entry.title or "(sem título)"
        level = entry.level
        while len(parent_stack) <= level:
            parent_stack.append(None)
        parent = parent_stack[level]
        bm = writer.add_outline_item(title, page_num, parent=parent)
        slot = level + 1
        if slot < len(parent_stack):
            parent_stack[slot] = bm
            del parent_stack[slot + 1:]
        else:
            parent_stack.append(bm)
