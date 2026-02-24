"""
main.py — Ponto de entrada do JoyBind.

Inicializa pygame, configura o CustomTkinter e lança a janela principal.
Execute com:
    python main.py
"""
import sys
from pathlib import Path

import pygame
import customtkinter as ctk
from PIL import Image, ImageTk

from gui.app import App

# Caminho base funciona tanto em dev quanto em executável PyInstaller
_BASE = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
_LOGO_PATH = _BASE / "img" / "logo.png"


def main() -> None:
    # ── Aparência do CustomTkinter ─────────────────────────────────
    ctk.set_appearance_mode("dark")          # "dark" | "light" | "system"
    ctk.set_default_color_theme("blue")      # "blue" | "green" | "dark-blue"

    # ── Inicialização do pygame ────────────────────────────────────
    # Precisamos inicializar antes de criar a App pois o ControllerListener
    # usa pygame.event.pump() no loop de polling.
    pygame.init()

    # ── Janela principal ───────────────────────────────────────────
    root = ctk.CTk()

    # Ícone da janela (barra de tarefas + titlebar)
    if _LOGO_PATH.exists():
        pil_icon = Image.open(_LOGO_PATH).resize((256, 256))
        _icon_photo = ImageTk.PhotoImage(pil_icon)
        root.iconphoto(True, _icon_photo)
        root._icon_photo = _icon_photo  # evita garbage collection

    app = App(root)

    def on_close() -> None:
        """Encerramento gracioso: garante que a thread do controller seja parada."""
        app.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
