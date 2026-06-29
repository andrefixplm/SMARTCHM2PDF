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
