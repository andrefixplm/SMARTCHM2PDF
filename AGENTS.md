# Repository Guidelines

## Project Structure & Module Organization
SmartCHM2PDF is a Python utility that converts Microsoft CHM help files to PDF while preserving images, CSS, and hierarchical bookmarks. Core pipeline modules live at the repository root: `extractor.py`, `toc_parser.py`, `html_processor.py`, `pdf_renderer.py`, `bookmarks.py`, and the orchestrator `converter.py`. CLI entry is `__main__.py`; GUI launchers are `run_gui.py` and `gui/app.py`. Packaging files include `SmartCHM2PDF.spec`, `smartchm2pdf_cli.spec`, `DEBUG_BUILD.spec`, `hooks/`, and `.github/workflows/build-exe.yml`. Generated artifacts such as `build/`, `dist/`, `__pycache__/`, and local virtual environments should not be treated as source.

## Build, Test, and Development Commands
Create or activate a virtual environment before installing dependencies.

```powershell
python -m pip install -r requirements.txt
playwright install chromium
python __main__.py sample.chm output.pdf
python __main__.py --gui
python run_gui.py
pyinstaller SmartCHM2PDF.spec
```

Use the CLI conversion command for the most direct local smoke test. Use `pyinstaller SmartCHM2PDF.spec` to build the Windows GUI executable expected by the GitHub Actions release workflow.

## Coding Style & Naming Conventions
Use standard Python style with 4-space indentation, `pathlib.Path` for filesystem boundaries, and clear snake_case names for modules, functions, and variables. Keep pipeline stages narrow: add extraction logic in `extractor.py`, TOC parsing in `toc_parser.py`, HTML transformations in `html_processor.py`, rendering in `pdf_renderer.py`, and merge/bookmark behavior in `bookmarks.py`. Preserve the `progress_cb(step, cur, total)` callback contract used by both CLI and GUI.

## Testing Guidelines
There is no formal test suite or linter configured. Validate changes by converting a representative `.chm` file end to end and opening the resulting PDF to confirm content, images, and bookmarks. For GUI changes, verify that conversion still runs in the background and that the UI blocks concurrent runs.

## Commit & Pull Request Guidelines
This checkout has no existing commits, so no historical commit convention is available. Use concise imperative commit messages, for example `Add CLI page format option`. Pull requests should describe the changed pipeline stage, include manual verification commands, note Windows or Chromium assumptions, and attach screenshots for GUI changes when relevant.

## Security & Configuration Tips
Do not commit local CHM samples, generated PDFs, virtual environments, or release binaries. Keep 7-Zip and Playwright Chromium setup documented when changes affect extraction or rendering.

## Agent-Specific Instructions
After a successful new feature implementation, offer to create a short Markdown lessons-learned note. If accepted, write it to the user's Obsidian inbox for later processing.
