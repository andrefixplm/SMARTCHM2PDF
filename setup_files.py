"""
setup_files.py — SmartCHM2PDF
Cria todos os arquivos do projeto no diretório atual.
Execute dentro da pasta clonada do repositório:

    git clone https://github.com/andrefixplm/SMARTCHM2PDF.git
    cd SMARTCHM2PDF
    python setup_files.py
    git add .
    git commit -m "Initial release"
    git push origin main
"""

import os
from pathlib import Path

FILES = {}

# ---------------------------------------------------------------------------
FILES["__init__.py"] = '''\
from .converter import ChmToPdfConverter

__all__ = ["ChmToPdfConverter"]
__version__ = "1.0.0"
'''

# ---------------------------------------------------------------------------
FILES["__main__.py"] = '''\
"""CLI entry point.

Usage:
    python __main__.py input.chm [output.pdf]
    python __main__.py --gui
"""

from __future__ import annotations
import sys
from pathlib import Path


def _usage():
    print("Uso: python __main__.py <arquivo.chm> [saida.pdf]")
    print("     python __main__.py --gui")
    sys.exit(1)


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    if not args:
        _usage()
    if args[0] in ("--gui", "-g"):
        from gui.app import main as gui_main
        gui_main()
        return
    chm_path = Path(args[0])
    if not chm_path.exists():
        print(f"Erro: arquivo não encontrado: {chm_path}", file=sys.stderr)
        sys.exit(1)
    output_path = Path(args[1]) if len(args) >= 2 else chm_path.with_suffix(".pdf")
    from converter import ChmToPdfConverter
    converter = ChmToPdfConverter()

    def _progress(step, cur, total):
        bar_len = 30
        filled = int(bar_len * cur / max(total, 1))
        bar = "#" * filled + "-" * (bar_len - filled)
        print(f"\\r[{bar}] {cur:3d}% {step:<40}", end="", flush=True)

    print(f"Convertendo: {chm_path.name} → {output_path.name}")
    try:
        result = converter.convert(chm_path, output_path, progress_cb=_progress)
        print()
        print(f"PDF gerado: {result}")
    except Exception as e:
        print()
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
'''

# ---------------------------------------------------------------------------
FILES["run_gui.py"] = '''\
"""Entry point for PyInstaller — launches the GUI."""
from gui.app import main
main()
'''

# ---------------------------------------------------------------------------
FILES["extractor.py"] = '''\
"""CHM extraction layer.

Primary: pychm (Python bindings for CHMLIB).
Fallback: 7z subprocess (supports CHM natively).
"""

import subprocess
import tempfile
from pathlib import Path


class ChmExtractor:
    def __init__(self, chm_path):
        self.chm_path = Path(chm_path).resolve()
        if not self.chm_path.exists():
            raise FileNotFoundError(f"CHM file not found: {self.chm_path}")
        self._tmpdir = None
        self._extracted_dir = None

    def extract(self):
        """Extract CHM contents to a temp directory and return its Path."""
        self._tmpdir = tempfile.TemporaryDirectory(prefix="chm2pdf_")
        dest = Path(self._tmpdir.name)
        try:
            self._extract_pychm(dest)
        except Exception:
            try:
                self._extract_7z(dest)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to extract {self.chm_path.name}. "
                    "Install pychm (with libchm-dev) or 7-Zip and try again."
                ) from e
        self._extracted_dir = dest
        return dest

    def cleanup(self):
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None
            self._extracted_dir = None

    def __enter__(self):
        self.extract()
        return self._extracted_dir

    def __exit__(self, *_):
        self.cleanup()

    def _extract_pychm(self, dest):
        # chmlib.chm_enumerate preserves the full directory structure.
        from chm import chmlib  # type: ignore[import]
        chm = chmlib.chm_open(str(self.chm_path))
        if chm is None:
            raise RuntimeError("chmlib: chm_open returned None")
        extracted = []

        def _write(chm_file, ui, _context):
            raw = ui.path
            path = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
            path = path.lstrip("/")
            if not path or path.endswith("/") or path.startswith("#") or path.startswith("$"):
                return chmlib.CHM_ENUMERATOR_CONTINUE
            target = dest / path
            target.parent.mkdir(parents=True, exist_ok=True)
            res, data = chmlib.chm_retrieve_object(chm_file, ui, 0, ui.length)
            if res and data:
                target.write_bytes(data)
                extracted.append(path)
            return chmlib.CHM_ENUMERATOR_CONTINUE

        chmlib.chm_enumerate(chm, chmlib.CHM_ENUMERATE_ALL, _write, None)
        chmlib.chm_close(chm)
        if not extracted:
            raise RuntimeError("chmlib: no files were extracted")

    def _extract_7z(self, dest):
        # Use \'x\' (not \'e\') to preserve full directory structure.
        result = subprocess.run(
            ["7z", "x", str(self.chm_path), f"-o{dest}", "-y"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"7z failed: {result.stderr}")
'''

# ---------------------------------------------------------------------------
FILES["toc_parser.py"] = '''\
"""Parse CHM Table of Contents from .hhc file."""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from bs4 import BeautifulSoup


@dataclass
class TocEntry:
    title: str
    path: str
    level: int = 0
    children: list["TocEntry"] = field(default_factory=list)


class TocParser:
    def __init__(self, extracted_dir):
        self.extracted_dir = Path(extracted_dir)

    def parse(self):
        hhc = self._find_hhc()
        return self._parse_hhc(hhc) if hhc else self._fallback_from_html_files()

    def _find_hhc(self):
        for p in self.extracted_dir.rglob("*.hhc"):
            return p
        return None

    def _parse_hhc(self, hhc_path):
        text = hhc_path.read_bytes().decode("utf-8", errors="replace")
        soup = BeautifulSoup(text, "lxml")
        root_ul = soup.find("ul")
        if root_ul is None:
            return self._fallback_from_html_files()
        entries = []
        self._parse_ul(root_ul, entries, level=0)
        return entries

    def _parse_ul(self, ul, entries, level):
        for li in ul.find_all("li", recursive=False):
            obj = li.find("object")
            if obj is None:
                continue
            title, local = "", ""
            for param in obj.find_all("param"):
                n = (param.get("name") or "").lower()
                v = param.get("value") or ""
                if n == "name":
                    title = v
                elif n == "local":
                    local = v
            if not local:
                entry = TocEntry(title=title or "(section)", path="", level=level)
            else:
                local = local.replace("\\\\", "/").lstrip("/")
                local_no_anchor = local.split("#")[0]
                entry = TocEntry(title=title or local_no_anchor, path=local_no_anchor, level=level)
            sub_ul = li.find("ul", recursive=False)
            if sub_ul:
                self._parse_ul(sub_ul, entry.children, level=level + 1)
            entries.append(entry)

    def _fallback_from_html_files(self):
        entries = []
        for p in sorted(self.extracted_dir.rglob("*.htm")) + sorted(self.extracted_dir.rglob("*.html")):
            rel = p.relative_to(self.extracted_dir).as_posix()
            entries.append(TocEntry(title=p.stem.replace("_", " ").title(), path=rel, level=0))
        return entries

    def flat(self, entries=None):
        if entries is None:
            entries = self.parse()
        result = []
        for e in entries:
            if e.path:
                result.append(e)
            result.extend(self.flat(e.children))
        return result
'''

# ---------------------------------------------------------------------------
FILES["html_processor.py"] = '''\
"""HTML processing: embed images as base64, inline CSS, fix relative URLs."""

from __future__ import annotations
import base64, mimetypes, re, urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup

_BASE_CSS = """
@page { margin: 2cm; size: A4; }
body { font-family: Arial, Helvetica, sans-serif; font-size: 11pt; line-height: 1.5; color: #111; max-width: 100%; word-wrap: break-word; }
img { max-width: 100%; height: auto; display: inline-block; }
pre, code { font-family: Consolas, "Courier New", monospace; font-size: 9.5pt; background: #f5f5f5; border: 1px solid #ddd; padding: 2px 4px; border-radius: 3px; }
pre { padding: 8px; white-space: pre-wrap; word-wrap: break-word; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; }
th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
th { background: #e8e8e8; font-weight: bold; }
h1,h2,h3,h4,h5,h6 { margin-top: 1em; margin-bottom: 0.4em; }
a { color: #1a0dab; }
hr { border: none; border-top: 1px solid #ccc; margin: 1em 0; }
"""


class HtmlProcessor:
    def __init__(self, extracted_dir):
        self.extracted_dir = Path(extracted_dir)

    def process_topic(self, rel_path):
        topic_path = self._resolve(rel_path)
        if topic_path is None or not topic_path.exists():
            return (f\'\'\'<!DOCTYPE html><html><head><style>{_BASE_CSS}</style></head>\'\'\'
                    f\'\'\'<body><p style="color:#999">Tópico não encontrado: {rel_path}</p></body></html>\'\'\')
        soup = BeautifulSoup(topic_path.read_bytes().decode("utf-8", errors="replace"), "lxml")
        topic_dir = topic_path.parent
        self._inline_stylesheets(soup, topic_dir)
        self._embed_images(soup, topic_dir)
        self._fix_links(soup)
        self._inject_base_css(soup)
        return str(soup)

    def _resolve(self, rel_path):
        if not rel_path:
            return None
        c = self.extracted_dir / rel_path
        if c.exists():
            return c
        cur = self.extracted_dir
        for part in Path(rel_path).parts:
            found = None
            try:
                for child in cur.iterdir():
                    if child.name.lower() == part.lower():
                        found = child
                        break
            except (NotADirectoryError, PermissionError):
                return None
            if found is None:
                return None
            cur = found
        return cur if cur != self.extracted_dir else None

    def _inline_stylesheets(self, soup, topic_dir):
        for link in soup.find_all("link", rel=lambda r: r and "stylesheet" in r):
            href = link.get("href", "")
            if not href or href.startswith(("http", "data:")):
                continue
            css_path = self._find_file(href, topic_dir)
            if css_path and css_path.exists():
                try:
                    css_text = self._embed_css_images(
                        css_path.read_text(encoding="utf-8", errors="replace"), css_path.parent
                    )
                    st = soup.new_tag("style")
                    st.string = css_text
                    link.replace_with(st)
                except Exception:
                    link.decompose()
            else:
                link.decompose()

    def _embed_images(self, soup, topic_dir):
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if not src or src.startswith("data:"):
                continue
            uri = self._to_data_uri(src, topic_dir)
            if uri:
                img["src"] = uri
            else:
                img["alt"] = img.get("alt", "") + f" [{src}]"

    def _fix_links(self, soup):
        for a in soup.find_all("a", href=True):
            if not a["href"].startswith(("http", "mailto:", "#", "javascript:")):
                a.unwrap()

    def _inject_base_css(self, soup):
        head = soup.find("head")
        if head is None:
            head = soup.new_tag("head")
            if soup.html:
                soup.html.insert(0, head)
        st = soup.new_tag("style")
        st.string = _BASE_CSS
        head.insert(0, st)

    def _to_data_uri(self, src, topic_dir):
        decoded = urllib.parse.unquote(src.split("?")[0].split("#")[0])
        p = self._find_file(decoded, topic_dir)
        if not p or not p.exists():
            return None
        try:
            data = p.read_bytes()
            mime = mimetypes.guess_type(p.name)[0] or "image/png"
            return f"data:{mime};base64,{base64.b64encode(data).decode()}"
        except Exception:
            return None

    def _embed_css_images(self, css_text, css_dir):
        def replace_url(m):
            url = m.group(1).strip("\'\"")
            if url.startswith(("data:", "http")):
                return m.group(0)
            p = self._find_file(url, css_dir)
            if p and p.exists():
                try:
                    data = p.read_bytes()
                    mime = mimetypes.guess_type(p.name)[0] or "image/png"
                    return f"url(\'data:{mime};base64,{base64.b64encode(data).decode()}\')"
                except Exception:
                    pass
            return m.group(0)
        return re.sub(r"url\\(([^)]+)\\)", replace_url, css_text)

    def _find_file(self, rel, base_dir):
        decoded = urllib.parse.unquote(rel)
        direct = base_dir / decoded
        if direct.exists():
            return direct
        cur = base_dir
        for part in Path(decoded).parts:
            found = None
            try:
                for child in cur.iterdir():
                    if child.name.lower() == part.lower():
                        found = child
                        break
            except (NotADirectoryError, PermissionError):
                return None
            if found is None:
                return None
            cur = found
        return cur if cur != base_dir else None
'''

# ---------------------------------------------------------------------------
FILES["pdf_renderer.py"] = '''\
"""PDF rendering via Playwright headless Chromium."""

from __future__ import annotations
import os
from pathlib import Path

_CHROMIUM_CANDIDATES = [
    os.environ.get("PLAYWRIGHT_CHROMIUM_PATH", ""),
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/usr/bin/google-chrome",
]


def _find_chromium():
    for p in _CHROMIUM_CANDIDATES:
        if p and Path(p).exists():
            return p
    return None


class PdfRenderer:
    def __init__(self, page_format="A4", print_background=True, margin=None):
        self.page_format = page_format
        self.print_background = print_background
        self.margin = margin or {"top": "1.5cm", "bottom": "1.5cm", "left": "1.5cm", "right": "1.5cm"}
        self._executable = _find_chromium()

    def render_topics(self, topics_html, progress_cb=None):
        from playwright.sync_api import sync_playwright
        launch_kwargs = {
            "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        }
        if self._executable:
            launch_kwargs["executable_path"] = self._executable
        results = []
        total = len(topics_html)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**launch_kwargs)
            try:
                for i, html in enumerate(topics_html):
                    page = browser.new_page()
                    try:
                        page.set_content(html, wait_until="networkidle", timeout=30_000)
                        results.append(page.pdf(
                            format=self.page_format,
                            print_background=self.print_background,
                            margin=self.margin,
                        ))
                    except Exception:
                        results.append(b"")
                    finally:
                        page.close()
                    if progress_cb:
                        progress_cb(i + 1, total)
            finally:
                browser.close()
        return results
'''

# ---------------------------------------------------------------------------
FILES["bookmarks.py"] = '''\
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
'''

# ---------------------------------------------------------------------------
FILES["converter.py"] = '''\
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
'''

# ---------------------------------------------------------------------------
FILES["requirements.txt"] = """\
# SmartCHM2PDF dependencies
beautifulsoup4>=4.12.0
lxml>=5.0.0
playwright>=1.40.0
pypdf>=4.0.0
customtkinter>=5.2.0

# CHM extraction (primary) -- requires libchm-dev on Linux:
#   apt install libchm-dev python3-dev && pip install pychm
# Fallback: 7-Zip must be on PATH
#   apt install 7zip  (Linux) / choco install 7zip  (Windows)
"""

# ---------------------------------------------------------------------------
FILES["README.md"] = """\
# SmartCHM2PDF

> Converte arquivos de ajuda Microsoft CHM para PDF com alta fidelidade:
> imagens embutidas, CSS preservado e bookmarks hierárquicos clicáveis.

## Download

Baixe o último executável Windows na aba **[Releases](../../releases/latest)**.

## Instalação de Dependências (uso via Python)

```bash
# Linux
apt install libchm-dev python3-dev 7zip
pip install beautifulsoup4 lxml playwright pypdf customtkinter
playwright install chromium
```

> **Windows:** instale o [7-Zip](https://www.7-zip.org/) e adicione ao PATH.

## Uso — GUI

```bash
python run_gui.py
```

## Uso — CLI

```bash
python __main__.py arquivo.chm saida.pdf
python __main__.py --gui
```

## Uso — API Python

```python
from converter import ChmToPdfConverter

conv = ChmToPdfConverter(page_format="A4", print_background=True)
conv.convert("arquivo.chm", "saida.pdf")
```

## Pipeline

```
CHM file
  ↓ extractor.py      -- pychm (primário) ou 7z (fallback)
  ↓ toc_parser.py     -- parseia .hhc → lista de tópicos
  ↓ html_processor.py -- embute imagens base64, inlina CSS
  ↓ pdf_renderer.py   -- Playwright + Chromium headless
  ↓ bookmarks.py      -- pypdf: mescla + outline hierárquico
  ↓ output.pdf
```

## Estrutura

```
SmartCHM2PDF/
├── run_gui.py          -- entry point GUI / PyInstaller
├── __main__.py         -- entry point CLI
├── converter.py        -- orquestrador do pipeline
├── extractor.py        -- extração CHM
├── toc_parser.py       -- parse do índice .hhc
├── html_processor.py   -- processamento HTML
├── pdf_renderer.py     -- renderização Playwright
├── bookmarks.py        -- bookmarks pypdf
├── SmartCHM2PDF.spec   -- PyInstaller spec
├── requirements.txt
└── gui/
    └── app.py          -- CustomTkinter GUI
```
"""

# ---------------------------------------------------------------------------
FILES["SmartCHM2PDF.spec"] = """\
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

ctk_datas = collect_data_files("customtkinter")

a = Analysis(
    ["run_gui.py"],
    pathex=[],
    binaries=[],
    datas=ctk_datas,
    hiddenimports=[
        "customtkinter",
        "PIL", "PIL.Image",
        "bs4",
        "lxml", "lxml.etree", "lxml._elementpath",
        "pypdf", "pypdf._crypt_filters",
        "playwright", "playwright.sync_api",
        "extractor", "toc_parser", "html_processor",
        "pdf_renderer", "bookmarks", "converter",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SmartCHM2PDF",
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=None,
)
"""

# ---------------------------------------------------------------------------
FILES["gui/__init__.py"] = ""

# ---------------------------------------------------------------------------
FILES["gui/app.py"] = '''\
"""SmartCHM2PDF — CustomTkinter GUI."""

from __future__ import annotations
import os, subprocess, sys, threading
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

BG = "#ECEFF4"; CARD_BG = "#FFFFFF"; PRIMARY = "#1565C0"; ACCENT = "#1B2A44"
SUCCESS = "#1E9E5A"; TEXT = "#16202E"; MUTED = "#566479"; BORDER = "#C7D0DD"; ON_PRIMARY = "#FFFFFF"
FONT_TITLE   = ("Segoe UI", 22, "bold")
FONT_SECTION = ("Segoe UI", 14, "bold")
FONT_LABEL   = ("Segoe UI", 12)
FONT_MONO    = ("Consolas", 11)
FONT_BTN     = ("Segoe UI", 13, "bold")
FONT_STATUS  = ("Segoe UI", 11)

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class ChmPdfApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SmartCHM2PDF")
        self.geometry("780x620"); self.minsize(680, 540)
        self.resizable(True, True); self.configure(fg_color=BG)
        self._chm_path = None; self._output_dir = None
        self._running = False; self._thread = None; self._last_pdf = None
        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(0, weight=1); self.rowconfigure(1, weight=1)
        self._build_header(); self._build_body(); self._build_footer()

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=ACCENT, corner_radius=0, height=80)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(0, weight=1); hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="SmartCHM2PDF", font=FONT_TITLE, text_color=ON_PRIMARY).grid(
            row=0, column=0, sticky="w", padx=24, pady=(14, 2))
        ctk.CTkLabel(hdr, text="Converte arquivos de ajuda (.chm) para PDF com imagens e bookmarks",
                     font=FONT_STATUS, text_color="#AAC0E0").grid(
            row=1, column=0, sticky="w", padx=24, pady=(0, 14))

    def _build_body(self):
        body = ctk.CTkScrollableFrame(self, fg_color=BG, scrollbar_button_color=BORDER)
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=12)
        body.columnconfigure(1, weight=1)

        self._section(body, "Arquivo CHM", 0)
        ctk.CTkLabel(body, text="Arquivo .chm:", font=FONT_LABEL, text_color=TEXT, anchor="w").grid(
            row=1, column=0, sticky="w", padx=(8, 4), pady=4)
        self._chm_var = ctk.StringVar(value="Nenhum arquivo selecionado")
        ctk.CTkEntry(body, textvariable=self._chm_var, font=FONT_MONO, text_color=MUTED,
                     fg_color=CARD_BG, border_color=BORDER, state="readonly").grid(
            row=1, column=1, sticky="ew", padx=4, pady=4)
        ctk.CTkButton(body, text="Procurar...", font=FONT_BTN, width=110,
                      fg_color=PRIMARY, hover_color=ACCENT, text_color=ON_PRIMARY,
                      command=self._browse_chm).grid(row=1, column=2, padx=(4, 8), pady=4)

        self._section(body, "Destino do PDF", 2)
        ctk.CTkLabel(body, text="Salvar em:", font=FONT_LABEL, text_color=TEXT, anchor="w").grid(
            row=3, column=0, sticky="w", padx=(8, 4), pady=4)
        self._out_var = ctk.StringVar(value="Mesma pasta do arquivo CHM")
        ctk.CTkEntry(body, textvariable=self._out_var, font=FONT_MONO, text_color=MUTED,
                     fg_color=CARD_BG, border_color=BORDER, state="readonly").grid(
            row=3, column=1, sticky="ew", padx=4, pady=4)
        ctk.CTkButton(body, text="Procurar...", font=FONT_BTN, width=110,
                      fg_color=PRIMARY, hover_color=ACCENT, text_color=ON_PRIMARY,
                      command=self._browse_output).grid(row=3, column=2, padx=(4, 8), pady=4)

        self._section(body, "Opções", 4)
        opts = ctk.CTkFrame(body, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER)
        opts.grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=(4, 8))
        opts.columnconfigure(0, weight=1)
        self._bg_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opts, text="Preservar cores de fundo (print_background)",
                        variable=self._bg_var, font=FONT_LABEL, text_color=TEXT).grid(
            row=0, column=0, sticky="w", padx=12, pady=8)
        ctk.CTkLabel(opts, text="Formato de página:", font=FONT_LABEL, text_color=TEXT, anchor="e").grid(
            row=0, column=1, sticky="e", padx=(0, 8))
        self._fmt_var = ctk.StringVar(value="A4")
        ctk.CTkOptionMenu(opts, values=["A4", "Letter", "Legal", "A3"], variable=self._fmt_var,
                          font=FONT_LABEL, fg_color=PRIMARY, button_color=ACCENT, text_color=ON_PRIMARY,
                          width=100).grid(row=0, column=2, padx=12, pady=8)

        self._section(body, "Log", 6)
        self._log_box = ctk.CTkTextbox(body, font=FONT_MONO, text_color=TEXT,
                                        fg_color=CARD_BG, border_color=BORDER, border_width=1,
                                        height=180, wrap="word")
        self._log_box.grid(row=7, column=0, columnspan=3, sticky="nsew", padx=8, pady=(4, 8))
        self._log_box.configure(state="disabled")

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=0,
                              border_width=1, border_color=BORDER, height=72)
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(1, weight=1); footer.grid_propagate(False)
        self._progress = ctk.CTkProgressBar(footer, fg_color=BORDER, progress_color=PRIMARY, height=8, width=400)
        self._progress.grid(row=0, column=0, columnspan=3, sticky="ew", padx=20, pady=(12, 4))
        self._progress.set(0)
        self._status_var = ctk.StringVar(value="Pronto. Selecione um arquivo .chm para começar.")
        ctk.CTkLabel(footer, textvariable=self._status_var, font=FONT_STATUS, text_color=MUTED, anchor="w").grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 8))
        self._btn_open = ctk.CTkButton(footer, text="Abrir PDF", font=FONT_BTN, width=110,
                                        fg_color=SUCCESS, hover_color="#145A32", text_color=ON_PRIMARY,
                                        command=self._open_pdf, state="disabled")
        self._btn_open.grid(row=1, column=1, sticky="e", padx=4, pady=(0, 8))
        self._btn_convert = ctk.CTkButton(footer, text="Converter", font=FONT_BTN, width=130,
                                           fg_color=PRIMARY, hover_color=ACCENT, text_color=ON_PRIMARY,
                                           command=self._start_conversion)
        self._btn_convert.grid(row=1, column=2, sticky="e", padx=20, pady=(0, 8))

    def _section(self, parent, title, row):
        ctk.CTkLabel(parent, text=title, font=FONT_SECTION, text_color=ACCENT, anchor="w").grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8, pady=(12, 2))

    def _log(self, msg):
        def _do():
            self._log_box.configure(state="normal")
            self._log_box.insert("end", msg + "\\n")
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        self.after(0, _do)

    def _set_progress(self, pct, status=""):
        def _do():
            self._progress.set(pct / 100)
            if status:
                self._status_var.set(status)
        self.after(0, _do)

    def _browse_chm(self):
        path = filedialog.askopenfilename(
            title="Selecionar arquivo CHM",
            filetypes=[("Arquivos CHM", "*.chm"), ("Todos os arquivos", "*.*")])
        if path:
            self._chm_path = Path(path)
            self._chm_var.set(str(self._chm_path))
            self._log(f"Arquivo selecionado: {self._chm_path.name}")
            self._status_var.set(f"Arquivo carregado: {self._chm_path.name}")
            self._btn_open.configure(state="disabled")
            self._last_pdf = None

    def _browse_output(self):
        path = filedialog.askdirectory(title="Selecionar pasta de saída")
        if path:
            self._output_dir = Path(path)
            self._out_var.set(str(self._output_dir))
            self._log(f"Pasta de saída: {self._output_dir}")

    def _open_pdf(self):
        if self._last_pdf and self._last_pdf.exists():
            if sys.platform == "win32":
                os.startfile(self._last_pdf)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(self._last_pdf)])
            else:
                subprocess.run(["xdg-open", str(self._last_pdf)])

    def _start_conversion(self):
        if self._running:
            return
        if self._chm_path is None:
            messagebox.showwarning("Arquivo não selecionado", "Selecione um arquivo .chm antes de converter.")
            return
        output_path = (
            (self._output_dir / (self._chm_path.stem + ".pdf"))
            if self._output_dir else self._chm_path.with_suffix(".pdf")
        )
        self._running = True
        self._btn_convert.configure(state="disabled", text="Convertendo...")
        self._btn_open.configure(state="disabled")
        self._progress.set(0)
        self._status_var.set("Iniciando conversão...")
        self._log("=" * 50)
        self._log(f"CHM : {self._chm_path}")
        self._log(f"PDF : {output_path}")
        self._log("=" * 50)

        def _run():
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from converter import ChmToPdfConverter
            conv = ChmToPdfConverter(page_format=self._fmt_var.get(), print_background=self._bg_var.get())

            def _progress(step, cur, total):
                self._log(f"  [{cur:3d}%] {step}")
                self._set_progress(cur, step)

            try:
                result = conv.convert(self._chm_path, output_path, progress_cb=_progress)
                self.after(0, self._on_success, result)
            except Exception as e:
                self.after(0, self._on_error, str(e))

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def _on_success(self, result):
        self._running = False
        self._last_pdf = result
        self._log(f"\\nPDF salvo em: {result}")
        self._log(f"Tamanho: {result.stat().st_size / 1024:.1f} KB")
        self._status_var.set(f"Concluído: {result.name}")
        self._progress.set(1.0)
        self._btn_convert.configure(state="normal", text="Converter")
        self._btn_open.configure(state="normal")

    def _on_error(self, msg):
        self._running = False
        self._log(f"\\nERRO: {msg}")
        self._status_var.set("Erro durante a conversão. Veja o log.")
        self._progress.set(0)
        self._btn_convert.configure(state="normal", text="Converter")
        messagebox.showerror("Erro na Conversão", msg)


def main():
    app = ChmPdfApp()
    app.mainloop()


if __name__ == "__main__":
    main()
'''

# ---------------------------------------------------------------------------
FILES[".github/workflows/build-exe.yml"] = """\
name: Build Windows EXE

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build-windows:
    runs-on: windows-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install beautifulsoup4 lxml playwright pypdf customtkinter pyinstaller
          playwright install chromium

      - name: Build EXE with PyInstaller
        run: pyinstaller SmartCHM2PDF.spec

      - name: Get version tag
        id: version
        run: echo "tag=v1.0.${{ github.run_number }}" >> $env:GITHUB_OUTPUT

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ steps.version.outputs.tag }}
          name: "SmartCHM2PDF ${{ steps.version.outputs.tag }}"
          body: |
            ## SmartCHM2PDF — Conversor CHM para PDF

            Converte arquivos `.chm` (Microsoft Help) para PDF com imagens, CSS e bookmarks.

            ### Como usar
            1. Baixe `SmartCHM2PDF.exe`
            2. Execute — nenhuma instalação necessária
            3. Selecione o arquivo `.chm` e clique em **Converter**

            > **Nota:** na primeira execução o app precisa encontrar o Chromium.
            > Caso necessário: `pip install playwright && playwright install chromium`
          files: dist/SmartCHM2PDF.exe
          draft: false
          prerelease: false
"""

# ---------------------------------------------------------------------------
# WRITE ALL FILES
# ---------------------------------------------------------------------------
root = Path(__file__).parent

created = []
for rel_path, content in FILES.items():
    target = root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    created.append(rel_path)

print(f"✓ {len(created)} arquivos criados:")
for f in created:
    print(f"  {f}")

print()
print("Próximos passos:")
print("  git add .")
print('  git commit -m "Initial release"')
print("  git push origin main")
print()
print("O GitHub Actions vai compilar SmartCHM2PDF.exe automaticamente.")
print("Link do release: https://github.com/andrefixplm/SMARTCHM2PDF/releases/latest")
