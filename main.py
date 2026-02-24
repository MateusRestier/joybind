"""
main.py — Ponto de entrada do JoyBind.

Inicializa pygame, configura o CustomTkinter e lança a janela principal.
Execute com:
    python main.py
"""
import sys
import ctypes
import tempfile
from pathlib import Path

import pygame
import customtkinter as ctk
from PIL import Image

from gui.app import App

# Caminho base funciona tanto em dev quanto em executável PyInstaller
_BASE = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
_LOGO_PATH = _BASE / "img" / "logo.png"

# Windows: identifica o processo como app própria, não como python.exe.
# Precisa ser chamado ANTES de qualquer janela ser criada.
if sys.platform == "win32":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("mateus.joybind.1")


def _apply_taskbar_icon(root: ctk.CTk, ico_path: str) -> None:
    """Envia WM_SETICON para o HWND real da janela (barra de tarefas)."""
    try:
        # LoadImage com LR_LOADFROMFILE retorna um HICON
        hicon = ctypes.windll.user32.LoadImageW(
            None, ico_path,
            1,                      # IMAGE_ICON
            0, 0,                   # cx, cy = 0 → usa tamanho default do sistema
            0x00000010 | 0x00000040,  # LR_LOADFROMFILE | LR_DEFAULTSIZE
        )
        if not hicon:
            return
        # O HWND da barra de tarefas é o pai do frame interno do Tk
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)  # WM_SETICON, ICON_BIG
        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)  # WM_SETICON, ICON_SMALL
    except Exception as e:
        print(f"[Icon] Erro ao definir ícone na taskbar: {e}")


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

    # Ícone da janela: gera .ico no temp e aplica no titlebar + taskbar
    if _LOGO_PATH.exists():
        try:
            pil_img = Image.open(_LOGO_PATH)
            ico_path = Path(tempfile.gettempdir()) / "joybind_icon.ico"
            pil_img.save(
                str(ico_path),
                format="ICO",
                sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)],
            )
            ico_str = str(ico_path)
            root.iconbitmap(ico_str)                             # titlebar
            root.after(0, lambda: _apply_taskbar_icon(root, ico_str))  # taskbar
        except Exception as e:
            print(f"[Icon] Erro ao definir ícone: {e}")

    app = App(root)

    def on_close() -> None:
        """Encerramento gracioso: garante que a thread do controller seja parada."""
        app.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
