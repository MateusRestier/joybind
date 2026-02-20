"""
main.py — Ponto de entrada do JoyBind.

Inicializa pygame, configura o CustomTkinter e lança a janela principal.
Execute com:
    python main.py
"""
import pygame
import customtkinter as ctk

from gui.app import App


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
    app = App(root)

    def on_close() -> None:
        """Encerramento gracioso: garante que a thread do controller seja parada."""
        app.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
