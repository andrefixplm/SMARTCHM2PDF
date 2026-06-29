"""PyInstaller hook to force inclusion of local module `html_processor`.

PyInstaller's static analyser sometimes drops top-level local modules when
their name overlaps with stdlib namespace fragments or when sibling
modules are referenced only by entry-graph transit. This hook ensures
html_processor is compiled to bytecode and bundled into the PYZ archive.
"""

hiddenimports = ["html_processor"]
