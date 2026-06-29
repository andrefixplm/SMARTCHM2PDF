"""Main orchestrator: CHM → PDF pipeline."""

from __future__ import annotations
from pathlib import Path
from typing import Callable
from bookmarks import merge_pdfs_with_bookmarks
from extractor import ChmExtractor
from html_processor import HtmlProcessor
from pdf_renderer import PdfRenderer
from toc_parser import TocEntry, TocParser

ProgressCallback = Callable[[str, int, int], None]


class ChmToPdfConverter:
    def __init__(self, page_format="A4", print_background=True):
        self.page_format = page_format
        self.print_background = print_background

    def convert(self, chm_path, output_path, progress_cb=None):
        chm_path = Path(chm_path).resolve()
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        def _cb(step, cur, total):
            if progress_cb:
                progress_cb(step, cur, total)

        _cb("Extraindo CHM...", 0, 100)
        extractor = ChmExtractor(chm_path)
        extracted_dir = extractor.extract()
        try:
            _cb("Lendo índice (TOC)...", 5, 100)
            parser = TocParser(extracted_dir)
            flat_entries = parser.flat(parser.parse())
            if not flat_entries:
                raise ValueError("Nenhum tópico encontrado no CHM.")
            _cb(f"Processando {len(flat_entries)} tópico(s)...", 10, 100)
            processor = HtmlProcessor(extracted_dir)
            renderer = PdfRenderer(page_format=self.page_format, print_background=self.print_background)

            def _render_progress(done, total):
                _cb(f"Renderizando tópico {done}/{total}...", 10 + int(80 * done / max(total, 1)), 100)

            htmls = [processor.process_topic(e.path) for e in flat_entries]
            pdf_bytes_list = renderer.render_topics(htmls, progress_cb=_render_progress)
            topic_pdfs = list(zip(flat_entries, pdf_bytes_list))
            _cb("Mesclando PDF e inserindo bookmarks...", 92, 100)
            final_pdf = merge_pdfs_with_bookmarks(topic_pdfs)
            _cb("Salvando arquivo...", 97, 100)
            output_path.write_bytes(final_pdf)
            _cb("Concluído!", 100, 100)
            return output_path
        finally:
            extractor.cleanup()
