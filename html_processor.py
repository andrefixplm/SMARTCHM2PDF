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
            return (f'''<!DOCTYPE html><html><head><style>{_BASE_CSS}</style></head>'''
                    f'''<body><p style="color:#999">Tópico não encontrado: {rel_path}</p></body></html>''')
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
            url = m.group(1).strip("'\"")
            if url.startswith(("data:", "http")):
                return m.group(0)
            p = self._find_file(url, css_dir)
            if p and p.exists():
                try:
                    data = p.read_bytes()
                    mime = mimetypes.guess_type(p.name)[0] or "image/png"
                    return f"url('data:{mime};base64,{base64.b64encode(data).decode()}')"
                except Exception:
                    pass
            return m.group(0)
        return re.sub(r"url\(([^)]+)\)", replace_url, css_text)

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
