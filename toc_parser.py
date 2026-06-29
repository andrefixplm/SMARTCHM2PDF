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
                local = local.replace("\\", "/").lstrip("/")
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
