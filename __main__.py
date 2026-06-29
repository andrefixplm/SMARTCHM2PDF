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
        print(f"\r[{bar}] {cur:3d}% {step:<40}", end="", flush=True)

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
