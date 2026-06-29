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
        # Use 'x' (not 'e') to preserve full directory structure.
        result = subprocess.run(
            ["7z", "x", str(self.chm_path), f"-o{dest}", "-y"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"7z failed: {result.stderr}")
