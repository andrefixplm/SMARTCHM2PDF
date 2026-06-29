# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SmartCHM2PDF — converts Microsoft Compiled Help (`.chm`) to PDF with embedded images, inlined CSS, and hierarchical bookmarks. Python + Playwright + pypdf + CustomTkinter. Targets Windows release; runs cross-platform.

## Run

```bash
# CLI
python __main__.py arquivo.chm saida.pdf      # convert one file
python __main__.py --gui                       # launch GUI
python __main__.py arquivo.chm                 # output = input with .pdf

# GUI directly
python run_gui.py

# Programmatic
from converter import ChmToPdfConverter
ChmToPdfConverter(page_format="A4", print_background=True).convert(in.chm, out.pdf)
```

No formal test suite. No linter configured. Validate by converting a CHM end-to-end.

## System dependencies

- Windows: install [7-Zip](https://www.7-zip.org/) and add to PATH.
- Linux: `apt install libchm-dev python3-dev 7zip` then `pip install pychm` (optional primary backend).
- Playwright Chromium: `playwright install chromium`. `pdf_renderer.py` probes several Linux paths via `_CHROMIUM_CANDIDATES`; override with env `PLAYWRIGHT_CHROMIUM_PATH`.

## Build executable

```bash
pyinstaller SmartCHM2PDF.spec     # entry: run_gui.py → dist/SMARTCHM2PDF.exe
```

## Pipeline

Sequential, single direction. Each stage returns bytes/paths to next:

```
converter.py (ChmToPdfConverter.convert)
  ├─ extractor.py    -- pychm chmlib (primary) → 7z subprocess (fallback) to temp dir
  ├─ toc_parser.py   -- parse .hhc → TocEntry tree, flat() → ordered list
  │                    fallback: glob *.htm/*.html if no .hhc
  ├─ html_processor.py -- per-topic: inline <link stylesheet>, embed <img> + CSS url() as base64,
  │                      strip internal <a> (unwrap), inject _BASE_CSS into <head>
  ├─ pdf_renderer.py -- Playwright Chromium, page per topic → page.pdf() bytes
  │                    one new_page per topic (sequential, not pooled)
  └─ bookmarks.py    -- pypdf PdfWriter: append pages, add_outline_item() with parent stack
                       mirrors TocEntry tree → PDF outline
```

`ChmToPdfConverter.convert` reports progress via `progress_cb(step, cur, total)` — 0→5 extract, 5→10 TOC, 10→90 render, 92 merge, 97 write, 100 done. GUI and CLI both consume this callback.

## Structure

- `__main__.py` — CLI arg parser + progress bar.
- `run_gui.py` — thin launcher for GUI (PyInstaller entry).
- `converter.py` — orchestrator; the only file that wires all stages.
- `extractor.py` — temp-dir lifecycle (`__enter__`/`__exit__`); always call `cleanup()` in a `finally`.
- `toc_parser.py` — dataclass `TocEntry(title, path, level, children)`. `parse()` → tree, `flat()` → DFS-ordered list with non-empty `path`.
- `html_processor.py` — case-insensitive `_find_file` walks parents; needed because CHM casing is unreliable.
- `pdf_renderer.py` — `--no-sandbox` etc. required for containers. Failed topic → empty bytes; pipeline still inserts a placeholder offset.
- `bookmarks.py` — `merge_pdfs_with_bookmarks(zip(flat_entries, pdf_bytes))`. `parent_stack` maintains outline hierarchy by `entry.level`.
- `gui/app.py` — CustomTkinter. Runs conversion in background thread; `_running` flag guards concurrent runs.

## Conventions

- Paths: `pathlib.Path`, resolved at boundaries. Relative topic paths kept as POSIX strings for `TocEntry.path`.
- Encoding: read bytes, decode `utf-8` with `errors="replace"`.
- Progress: `progress_cb(step: str, cur: int, total: int)` — GUI/CLI both honor this exact signature.
- Headless: all Chromium interactions via Playwright sync API inside `with sync_playwright()`.
- Errors: stages raise; `converter.convert` re-raises after `extractor.cleanup()` in `finally`.

## Adding a feature

- New pipeline stage: implement module returning data, wire into `converter.py:ChmToPdfConverter.convert` between existing stages, extend progress percentages.
- New bookmark level: rely on `TocEntry.level`; `bookmarks._add_outline` handles arbitrary depth via `parent_stack`.
- New CLI flag: parse in `__main__.py:main`, forward via converter kwarg.
