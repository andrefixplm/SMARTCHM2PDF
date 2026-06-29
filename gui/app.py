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
            self._log_box.insert("end", msg + "\n")
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
        self._log(f"\nPDF salvo em: {result}")
        self._log(f"Tamanho: {result.stat().st_size / 1024:.1f} KB")
        self._status_var.set(f"Concluído: {result.name}")
        self._progress.set(1.0)
        self._btn_convert.configure(state="normal", text="Converter")
        self._btn_open.configure(state="normal")

    def _on_error(self, msg):
        self._running = False
        self._log(f"\nERRO: {msg}")
        self._status_var.set("Erro durante a conversão. Veja o log.")
        self._progress.set(0)
        self._btn_convert.configure(state="normal", text="Converter")
        messagebox.showerror("Erro na Conversão", msg)


def main():
    app = ChmPdfApp()
    app.mainloop()


if __name__ == "__main__":
    main()
