"""
gui/app.py — Janela principal do JoyBind.

Layout:
  Header → Preset bar → Controle → Status
  TabView:
    [Botões]     — lista de mapeamentos + CRUD
    [Analógicos] — dois painéis de analógico (esq/dir) com 4 botões de direção

Thread safety:
  • _on_button_press e _on_axes_update rodam na thread daemon do controller.
  • Apenas pyautogui é chamado nessas threads (thread-safe).
  • Qualquer atualização de widget usa root.after(0, ...).
"""
import threading
import time
import webbrowser
from pathlib import Path
from tkinter import messagebox, filedialog

import pygame
import customtkinter as ctk
from PIL import Image
from pynput.keyboard import Listener as KeyListener

from core import presets
from core import actions
from core.controller import ControllerListener
from .bind_dialog import BindDialog, SequenceDialog
import i18n
from i18n import t, step_plural, analog_type_opts

# ── Recursos ───────────────────────────────────────────────────────────────
# Funciona tanto em desenvolvimento quanto em executável PyInstaller (onefile).
import sys as _sys
_BASE = Path(_sys._MEIPASS) if getattr(_sys, "frozen", False) else Path(__file__).resolve().parent.parent
_LOGO_PATH = _BASE / "img" / "logo.png"

# ── Cores ──────────────────────────────────────────────────────────────────
_COLOR_ACTIVE          = "#2ecc71"
_COLOR_STOPPED         = "#e74c3c"
_COLOR_BTN_START       = "#2ecc71"
_COLOR_BTN_START_HOVER = "#27ae60"
_COLOR_BTN_STOP        = "#e67e22"
_COLOR_BTN_STOP_HOVER  = "#d35400"

def _type_labels() -> dict[str, str]:
    return {
        "keyboard":    t("type_keyboard"),
        "sequence":    t("type_sequence"),
        "mouse_combo": t("type_mouse"),
    }
_TYPE_COLORS: dict[str, str] = {
    "keyboard":    "#3498db",
    "sequence":    "#e67e22",
    "mouse_combo": "#9b59b6",
}


# ── Helpers de analógico ───────────────────────────────────────────────────

def _apply_deadzone(value: float, dz: float) -> float:
    """Aplica zona morta com re-escala linear [dz, 1] → [0, 1]."""
    if abs(value) < dz:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    return sign * (abs(value) - dz) / max(1.0 - dz, 1e-6)


def _default_sticks() -> list[dict]:
    """Configuração padrão para os dois analógicos (pré-mapeados para mouse)."""
    return [
        {
            "label": t("sec_analog_left"), "axis_x": 0, "axis_y": 1, "deadzone": 0.15,
            "sensitivity": 600.0,
            "up":    {"type": "mouse_y", "sensitivity": 600},
            "down":  {"type": "mouse_y", "sensitivity": 600},
            "left":  {"type": "mouse_x", "sensitivity": 600},
            "right": {"type": "mouse_x", "sensitivity": 600},
        },
        {
            "label": t("sec_analog_right"), "axis_x": 2, "axis_y": 3, "deadzone": 0.15,
            "sensitivity": 10000.0,
            "up":    {"type": "none"},
            "down":  {"type": "none"},
            "left":  {"type": "none"},
            "right": {"type": "none"},
        },
    ]


def _dir_btn_text(direction: str, binding: dict) -> str:
    """Texto exibido no botão de direção: seta + rótulo curto da binding."""
    arrow = {"up": "↑", "down": "↓", "left": "←", "right": "→"}.get(direction, "?")
    btype = binding.get("type", "none")
    n = len(binding.get("steps", []))
    short = {
        "none":     "—",
        "mouse_x":  "Mouse X",
        "mouse_y":  "Mouse Y",
        "scroll_v": "Scroll ↕",
        "scroll_h": "Scroll ↔",
        "key":      binding.get("key", "?"),
        "sequence": f"Seq ({n})",
    }.get(btype, "?")
    return f"{arrow}\n{short}"


def _sanitize_filename(name: str) -> str:
    return "".join(c for c in name if c not in r'\/:*?"<>|').strip()


# Sensibilidade de scroll (cliques/s) usada pelo analógico direito no modo mouse
_SCROLL_SENS_MOUSE_MODE: float = 8.0

# Intervalo de frames entre pressões repetidas de tecla no modo analógico
# Layout padrão: vazio — o usuário configura manualmente ou via Auto-mapear.
_DEFAULT_LAYOUT: dict[str, str] = {}

# Ordem em que o wizard de Auto-mapear percorre os tiles
_TILE_ORDER: list[str] = [
    "A", "B", "X", "Y",
    "LB", "RB", "LT", "RT",
    "SELECT", "START", "LS", "RS",
    "↑", "↓", "←", "→",
]


def _find_sens(stick: dict, target_types: tuple, fallback: float = 600.0) -> float:
    """Retorna a primeira sensibilidade configurada para um dos tipos alvo."""
    for d in ("right", "left", "down", "up"):
        b = stick.get(d, {})
        if b.get("type") in target_types:
            try:
                return max(0.1, float(b["sensitivity"]))
            except (ValueError, TypeError):
                pass
    return fallback


# ── Diálogo de configuração de direção analógica ───────────────────────────

class AnalogDirectionDialog:
    """Dialog para configurar a ação de uma direção do analógico."""

    def __init__(self, parent, direction_label: str, current: dict) -> None:
        self.result: dict | None = None
        self._capturing = False
        self._parent = parent

        # Language-aware type options (computed fresh each time)
        self._TYPE_OPTS = analog_type_opts()
        self._BY_LABEL = {v: k for k, v in self._TYPE_OPTS.items()}

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(t("title_configure", label=direction_label))
        self.dialog.geometry("400x220")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.lift()
        self.dialog.focus_force()

        cur_type = current.get("type", "none")
        self._cur_sens  = str(int(float(current.get("sensitivity", 600))))
        self._cur_key   = current.get("key", "")
        self._cur_steps = list(current.get("steps", []))

        # ── Tipo ──────────────────────────────────────────────────
        row_type = ctk.CTkFrame(self.dialog, fg_color="transparent")
        row_type.pack(fill="x", padx=20, pady=(16, 6))
        ctk.CTkLabel(row_type, text=t("lbl_type"), width=90, anchor="w").pack(side="left")
        self._type_var = ctk.StringVar(value=self._TYPE_OPTS.get(cur_type, t("analog_none")))
        ctk.CTkOptionMenu(
            row_type, variable=self._type_var,
            values=list(self._TYPE_OPTS.values()),
            command=self._on_type_changed, width=270,
        ).pack(side="left")

        # ── Área dinâmica (sens ou tecla) ─────────────────────────
        self._dyn = ctk.CTkFrame(self.dialog, fg_color="transparent")
        self._dyn.pack(fill="x", padx=20)
        self._sens_entry: ctk.CTkEntry | None = None
        self._key_entry:  ctk.CTkEntry | None = None
        self._on_type_changed(self._type_var.get())

        # ── Botões ────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self.dialog, fg_color="transparent")
        btn_row.pack(pady=14)
        ctk.CTkButton(
            btn_row, text=t("btn_cancel"), width=100,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            command=self.dialog.destroy,
        ).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text=t("btn_ok"), width=100, command=self._on_ok).pack(side="left", padx=8)

        self.dialog.protocol("WM_DELETE_WINDOW", self.dialog.destroy)

    def _on_type_changed(self, label: str) -> None:
        for w in self._dyn.winfo_children():
            w.destroy()
        self._sens_entry = self._key_entry = None
        type_key = self._BY_LABEL.get(label, "none")

        if type_key in ("mouse_x", "mouse_y", "scroll_v", "scroll_h"):
            row = ctk.CTkFrame(self._dyn, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkLabel(row, text=t("lbl_speed"), width=90, anchor="w").pack(side="left")
            self._sens_entry = ctk.CTkEntry(row, width=80, justify="center")
            self._sens_entry.insert(0, self._cur_sens)
            self._sens_entry.pack(side="left")
            unit = "px/s" if type_key in ("mouse_x", "mouse_y") else "cliques/s"
            ctk.CTkLabel(
                row, text=unit, font=ctk.CTkFont(size=11),
                text_color=("gray50", "gray55"),
            ).pack(side="left", padx=8)

        elif type_key == "key":
            row = ctk.CTkFrame(self._dyn, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkLabel(row, text=t("lbl_key"), width=90, anchor="w").pack(side="left")
            self._key_entry = ctk.CTkEntry(row, width=100, justify="center")
            self._key_entry.insert(0, self._cur_key)
            self._key_entry.pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                row, text=t("btn_capture"), width=80,
                fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
                command=self._capture_key,
            ).pack(side="left")

        elif type_key == "sequence":
            n = len(self._cur_steps)
            s = "s" if n != 1 else ""
            lbl_text = (
                t("msg_analog_steps_n", n=n, s=s)
                if n else t("msg_analog_no_steps")
            )
            ctk.CTkLabel(
                self._dyn, text=lbl_text,
                font=ctk.CTkFont(size=11), text_color=("gray55", "gray55"),
            ).pack(pady=(6, 4))
            ctk.CTkButton(
                self._dyn, text=t("btn_edit_seq"), width=180,
                fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
                command=self._open_sequence_editor,
            ).pack()

        else:
            pass  # "none" — nenhum widget extra

    def _open_sequence_editor(self) -> None:
        """Abre o SequenceDialog para editar os passos desta direção."""
        dlg = SequenceDialog(self.dialog, current_steps=self._cur_steps)
        self.dialog.wait_window(dlg.dialog)
        if dlg.result is not None:
            self._cur_steps = dlg.result
            # Atualiza o rótulo de resumo na _dyn
            for w in self._dyn.winfo_children():
                if isinstance(w, ctk.CTkLabel):
                    n = len(self._cur_steps)
                    s = "s" if n != 1 else ""
                    w.configure(text=(
                        t("msg_analog_steps_n", n=n, s=s)
                        if n else t("msg_analog_no_steps")
                    ))
                    break

    def _capture_key(self) -> None:
        if self._capturing:
            return
        self._capturing = True
        self._key_entry.delete(0, "end")
        self._key_entry.insert(0, t("status_waiting"))

        def _listen() -> None:
            # Mapeamento de nomes pynput → nome canônico do modificador
            _MOD_MAP = {
                "ctrl":    "ctrl", "ctrl_l":  "ctrl", "ctrl_r":  "ctrl",
                "shift":   "shift","shift_l": "shift","shift_r": "shift",
                "alt":     "alt",  "alt_l":   "alt",  "alt_r":   "alt",  "alt_gr": "alt",
                "cmd":     "win",  "cmd_l":   "win",  "cmd_r":   "win",
            }
            _MOD_ORDER = ["ctrl", "shift", "alt", "win"]
            active_mods: set[str] = set()

            def _key_name(key) -> str:
                try:
                    return key.char if key.char is not None else key.name
                except AttributeError:
                    return key.name

            def on_press(key):
                if not self._capturing:
                    return False
                name = _key_name(key)
                canonical = _MOD_MAP.get(name)
                if canonical:
                    active_mods.add(canonical)
                    return  # aguarda a tecla principal
                # Tecla principal pressionada — monta o combo
                parts = [m for m in _MOD_ORDER if m in active_mods] + [name]
                combo = "+".join(parts)
                self.dialog.after(0, lambda c=combo: (
                    self._key_entry.delete(0, "end"),
                    self._key_entry.insert(0, c),
                ))
                self._capturing = False
                return False

            def on_release(key):
                name = _key_name(key)
                canonical = _MOD_MAP.get(name)
                if canonical:
                    active_mods.discard(canonical)

            with KeyListener(on_press=on_press, on_release=on_release) as lst:
                lst.join()

        threading.Thread(target=_listen, daemon=True).start()

    def _on_ok(self) -> None:
        type_key = self._BY_LABEL.get(self._type_var.get(), "none")
        if type_key in ("mouse_x", "mouse_y", "scroll_v", "scroll_h"):
            try:
                sens = max(0.1, float(self._sens_entry.get()))
            except (ValueError, AttributeError):
                sens = 600.0
            self.result = {"type": type_key, "sensitivity": sens}
        elif type_key == "key":
            key = (self._key_entry.get().strip() if self._key_entry else "")
            if not key or key == t("status_waiting"):
                self.result = {"type": "none"}
            else:
                self.result = {"type": "key", "key": key}
        elif type_key == "sequence":
            self.result = {"type": "sequence", "steps": self._cur_steps}
        else:
            self.result = {"type": "none"}
        self.dialog.destroy()


# ── Wizard de mapeamento automático de botões ──────────────────────────────

class AutoMapWizard:
    """
    Percorre cada tile do layout visual e detecta qual botão físico lhe corresponde.
    O usuário pressiona o botão do controle quando indicado; o número detectado
    (incluindo HAT e eixos de gatilho) é armazenado no layout.

    Attributes:
        result (dict[str, str] | None): visual_id → btn_key detectado, ou None se cancelado.
        dialog (CTkToplevel): Janela do wizard.
    """

    # Mesmos mapeamentos de controller.py — duplicados aqui para evitar import circular
    _AXIS_TO_VBTN: dict[int, int] = {4: 100, 5: 101}
    _HAT_TO_VBTN: dict[tuple[int, int], int] = {
        (0,  1): 102, (0, -1): 103, (-1, 0): 104, (1, 0): 105,
    }

    def __init__(
        self, parent: ctk.CTk, tiles: list[str], current_layout: dict[str, str],
    ) -> None:
        self.result: dict[str, str] | None = None
        self._tiles = tiles
        self._layout = dict(current_layout)
        self._idx = 0
        self._capturing = False

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(t("title_auto_map"))
        self.dialog.geometry("380x300")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.lift()
        self.dialog.focus_force()
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.dialog,
            text=t("msg_automap_hint"),
            font=ctk.CTkFont(size=12),
            wraplength=340,
        ).grid(row=0, column=0, pady=(18, 4), padx=20)

        self._progress_lbl = ctk.CTkLabel(
            self.dialog, text="",
            font=ctk.CTkFont(size=11), text_color=("gray50", "gray60"),
        )
        self._progress_lbl.grid(row=1, column=0)

        self._tile_lbl = ctk.CTkLabel(
            self.dialog, text="",
            font=ctk.CTkFont(size=40, weight="bold"),
        )
        self._tile_lbl.grid(row=2, column=0, pady=12)

        self._status_lbl = ctk.CTkLabel(
            self.dialog, text="",
            font=ctk.CTkFont(size=11), text_color=("gray50", "gray60"),
        )
        self._status_lbl.grid(row=3, column=0)

        btn_row = ctk.CTkFrame(self.dialog, fg_color="transparent")
        btn_row.grid(row=4, column=0, pady=20)
        ctk.CTkButton(
            btn_row, text=t("btn_cancel"), width=100,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            command=self._on_cancel,
        ).pack(side="left", padx=6)
        self._skip_btn = ctk.CTkButton(
            btn_row, text=t("btn_skip"), width=80,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            command=self._on_skip,
        )
        self._skip_btn.pack(side="left", padx=6)

        self._advance()

    # ── Fluxo ──────────────────────────────────────────────────────

    def _advance(self) -> None:
        if self._idx >= len(self._tiles):
            self.result = self._layout
            self.dialog.destroy()
            return

        vid = self._tiles[self._idx]
        current_key = self._layout.get(vid, vid)
        self._progress_lbl.configure(
            text=t("msg_automap_tile", idx=self._idx + 1, total=len(self._tiles))
        )
        self._tile_lbl.configure(text=vid)
        self._status_lbl.configure(
            text=t("msg_automap_waiting", btn=current_key),
            text_color=("gray50", "gray60"),
        )
        self._skip_btn.configure(state="normal")
        self._capturing = True
        threading.Thread(
            target=self._detect_loop, args=(vid,), daemon=True, name="AutoMap"
        ).start()

    def _detect_loop(self, vid: str) -> None:
        try:
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            if pygame.joystick.get_count() == 0:
                self.dialog.after(0, lambda: self._on_fail(t("msg_no_ctrl_connected")))
                return

            joy = pygame.joystick.Joystick(0)
            joy.init()
            nb = joy.get_numbuttons()
            na = joy.get_numaxes()
            nh = joy.get_numhats()
            prev_b = {b: joy.get_button(b) for b in range(nb)}
            prev_a = {a: joy.get_axis(a) for a in range(na)}
            prev_h = {h: joy.get_hat(h) for h in range(nh)}
            deadline = time.monotonic() + 15.0

            while time.monotonic() < deadline and self._capturing:
                try:
                    pygame.event.pump()
                except Exception:
                    pass
                for b in range(nb):
                    curr = joy.get_button(b)
                    if curr == 1 and prev_b.get(b, 0) == 0:
                        try: joy.quit()
                        except Exception: pass
                        self.dialog.after(0, lambda k=str(b): self._on_detected(vid, k))
                        return
                    prev_b[b] = curr
                for axis_idx, vbtn in self._AXIS_TO_VBTN.items():
                    if axis_idx >= na:
                        continue
                    val = joy.get_axis(axis_idx)
                    if val > 0.5 and prev_a.get(axis_idx, -1.0) <= 0.5:
                        try: joy.quit()
                        except Exception: pass
                        self.dialog.after(0, lambda k=str(vbtn): self._on_detected(vid, k))
                        return
                    prev_a[axis_idx] = val
                for h in range(nh):
                    curr_h = joy.get_hat(h)
                    if curr_h in self._HAT_TO_VBTN and curr_h != prev_h.get(h, (0, 0)):
                        try: joy.quit()
                        except Exception: pass
                        k = str(self._HAT_TO_VBTN[curr_h])
                        self.dialog.after(0, lambda kk=k: self._on_detected(vid, kk))
                        return
                    prev_h[h] = curr_h
                time.sleep(1 / 60)

            try: joy.quit()
            except Exception: pass
            if self._capturing:
                self.dialog.after(0, lambda: self._on_fail(t("msg_timeout_automap")))
        except Exception as exc:
            self.dialog.after(0, lambda e=str(exc): self._on_fail(e))

    def _on_detected(self, vid: str, btn_key: str) -> None:
        self._capturing = False
        self._layout[vid] = btn_key
        self._status_lbl.configure(
            text=t("msg_automap_detected", btn=btn_key),
            text_color=("#2ecc71", "#2ecc71"),
        )
        self._skip_btn.configure(state="disabled")
        self.dialog.after(700, self._next)

    def _on_fail(self, msg: str) -> None:
        self._capturing = False
        self._status_lbl.configure(
            text=t("msg_automap_failed", msg=msg), text_color=("#e74c3c", "#e74c3c"),
        )

    def _next(self) -> None:
        self._idx += 1
        self._advance()

    def _on_skip(self) -> None:
        self._capturing = False
        self._idx += 1
        self._advance()

    def _on_cancel(self) -> None:
        self._capturing = False
        self.result = None
        self.dialog.destroy()


# ── Classe principal ───────────────────────────────────────────────────────

class App:
    """Classe principal que monta e gerencia a interface gráfica."""

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.geometry("800x860")
        self.root.minsize(700, 780)

        # ── Presets ──────────────────────────────────────────────────
        self._settings = presets.load_settings()
        self._presets_dir = Path(self._settings["presets_dir"])
        self._current_preset_path: Path | None = None
        self.cfg = self._load_initial_preset()

        title = (
            f"JoyBind — {self._current_preset_path.stem}"
            if self._current_preset_path else "JoyBind"
        )
        self.root.title(title)

        # ── Layout de botões (visual_id → btn_key) ───────────────────
        # Carregado das configurações globais; _DEFAULT_LAYOUT é usado como fallback.
        saved_layout = self._settings.get("btn_layout", {})
        self._layout: dict[str, str] = {**_DEFAULT_LAYOUT, **saved_layout}

        # ── Estado geral ──────────────────────────────────────────────
        self._is_listening = False
        # Tiles clicáveis do layout visual: visual_id → CTkButton
        self._btn_tiles: dict[str, ctk.CTkButton] = {}

        # ── Estado analógico ──────────────────────────────────────────
        self._acc_x:  float = 0.0
        self._acc_y:  float = 0.0
        self._acc_sv: float = 0.0
        self._acc_sh: float = 0.0
        self._held_keys: set[str] = set()
        # Botões com 'Segurar enquanto pressionado' ativos: button_int → key_str
        self._held_btn_keys: dict[int, str] = {}
        # Threads de macro em execução: button_int → threading.Event (stop)
        self._macro_stop_events: dict[int, threading.Event] = {}
        # Estado anterior de ativação por direção — para edge-trigger
        # Chave: (stick_index, direction_str)
        self._prev_dir_active: dict[tuple, bool] = {}

        # Placeholders — populados em _build_controller_layout
        self._left_stick_frame:  ctk.CTkFrame | None = None
        self._right_stick_frame: ctk.CTkFrame | None = None
        self._stick_panels:      list[dict | None]   = [None, None]

        self.listener = ControllerListener(
            on_button_press=self._on_button_press,
            on_axes_update=self._on_axes_update,
            on_button_release=self._on_button_release,
        )

        self._build_ui()
        self._refresh_joystick_dropdown()
        self._refresh_preset_dropdown()
        self._update_btn_tiles()
        self._render_analog_config()

    # ──────────────────────────────────────────────────────────────
    # Preset inicial e utilitários
    # ──────────────────────────────────────────────────────────────

    def _load_initial_preset(self) -> dict:
        last = self._settings.get("last_preset")
        if last:
            path = Path(last)
            if path.exists():
                self._current_preset_path = path
                self._presets_dir = path.parent
                return self._ensure_defaults(presets.load_preset(path))

        lst = presets.list_presets(self._presets_dir)
        if lst:
            self._current_preset_path = lst[0]
            return self._ensure_defaults(presets.load_preset(lst[0]))

        default_path = self._presets_dir / "default.json"
        cfg: dict = {"binds": {}, "analog": {"enabled": False, "sticks": _default_sticks()}}
        presets.save_preset(default_path, cfg)
        self._current_preset_path = default_path
        self._settings["last_preset"] = str(default_path)
        presets.save_settings(self._settings)
        return cfg

    @staticmethod
    def _ensure_defaults(cfg: dict) -> dict:
        cfg.setdefault("binds", {})
        analog = cfg.setdefault("analog", {"enabled": False})
        analog.setdefault("enabled", False)
        # Migra formato antigo (axes[]) para novo (sticks[])
        if "axes" in analog:
            del analog["axes"]
        analog.setdefault("sticks", _default_sticks())
        for i, stick in enumerate(analog["sticks"]):
            stick.setdefault("deadzone", 0.15)
            stick.setdefault("sensitivity", 600.0 if i == 0 else 10000.0)
            for d in ("up", "down", "left", "right"):
                stick.setdefault(d, {"type": "none"})
        return cfg

    # ──────────────────────────────────────────────────────────────
    # Construção da Interface
    # ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(4, weight=1)

        self._build_header()
        self._build_preset_bar()
        self._build_controller_row()
        self._build_status_row()
        self._build_controller_layout()

    def _build_header(self) -> None:
        frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color=("gray85", "gray17"))
        frame.grid(row=0, column=0, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        # Logo (coluna 0, ocupa as duas linhas de texto)
        if _LOGO_PATH.exists():
            pil_img = Image.open(_LOGO_PATH)
            logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(48, 48))
            ctk.CTkLabel(frame, image=logo_img, text="").grid(
                row=0, column=0, rowspan=2, padx=(16, 4), pady=10,
            )
            col_text = 1
        else:
            col_text = 0

        ctk.CTkLabel(
            frame, text="JoyBind",
            font=ctk.CTkFont(size=24, weight="bold"), anchor="w",
        ).grid(row=0, column=col_text, padx=(8, 20) if col_text else 20, pady=(14, 2), sticky="w")
        ctk.CTkLabel(
            frame, text=t("header_subtitle"),
            font=ctk.CTkFont(size=11), text_color=("gray55", "gray60"), anchor="w",
        ).grid(row=1, column=col_text, padx=(8, 20) if col_text else 20, pady=(0, 12), sticky="w")

        # Language selector
        _active_col   = ("#1f538d", "#1f6aa5")
        _inactive_col = ("gray65", "gray30")
        _active_hov   = ("#1a4a7a", "#1a5a8a")
        _inactive_hov = ("gray55", "gray40")
        lang_frame = ctk.CTkFrame(frame, fg_color="transparent")
        lang_frame.grid(row=0, column=col_text + 1, rowspan=2, padx=(0, 14), pady=10, sticky="e")
        _cur = i18n._lang
        ctk.CTkButton(
            lang_frame, text="EN", width=36, height=26,
            font=ctk.CTkFont(size=11, weight="bold" if _cur == "en" else "normal"),
            fg_color=_active_col if _cur == "en" else _inactive_col,
            hover_color=_active_hov if _cur == "en" else _inactive_hov,
            command=lambda: self._on_lang_change("en"),
        ).pack(pady=(0, 2))
        ctk.CTkButton(
            lang_frame, text="PT", width=36, height=26,
            font=ctk.CTkFont(size=11, weight="bold" if _cur == "pt" else "normal"),
            fg_color=_active_col if _cur == "pt" else _inactive_col,
            hover_color=_active_hov if _cur == "pt" else _inactive_hov,
            command=lambda: self._on_lang_change("pt"),
        ).pack(pady=(2, 0))

    def _build_preset_bar(self) -> None:
        frame = ctk.CTkFrame(self.root)
        frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(8, 0))
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text=t("lbl_preset"), font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(14, 8), pady=7,
        )
        self._preset_var = ctk.StringVar()
        self._preset_combo = ctk.CTkComboBox(
            frame, variable=self._preset_var, state="readonly",
            command=self._on_preset_selected,
        )
        self._preset_combo.grid(row=0, column=1, padx=4, pady=7, sticky="ew")
        ctk.CTkButton(
            frame, text=t("btn_new"), width=70, command=self._new_preset,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
        ).grid(row=0, column=2, padx=(4, 0), pady=7)
        ctk.CTkButton(
            frame, text=t("btn_delete"), width=76, command=self._delete_current_preset,
            fg_color=("#b33030", "#7a1f1f"), hover_color=("#8c2020", "#5c1010"),
        ).grid(row=0, column=3, padx=(4, 0), pady=7)
        ctk.CTkButton(
            frame, text=t("btn_folder"), width=80, command=self._change_presets_folder,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
        ).grid(row=0, column=4, padx=(4, 14), pady=7)

    def _build_controller_row(self) -> None:
        frame = ctk.CTkFrame(self.root)
        frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 4))
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text=t("lbl_controller"), font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(14, 8), pady=8,
        )
        self._joystick_var = ctk.StringVar()
        self._joystick_combo = ctk.CTkComboBox(
            frame, variable=self._joystick_var, state="readonly",
        )
        self._joystick_combo.grid(row=0, column=1, padx=4, pady=8, sticky="ew")
        self._refresh_btn = ctk.CTkButton(
            frame, text="↻", width=38, command=self._refresh_joystick_dropdown,
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
        )
        self._refresh_btn.grid(row=0, column=2, padx=(4, 14), pady=8)

    def _build_status_row(self) -> None:
        frame = ctk.CTkFrame(self.root)
        frame.grid(row=3, column=0, sticky="ew", padx=12, pady=2)
        frame.grid_columnconfigure(1, weight=1)
        self._toggle_btn = ctk.CTkButton(
            frame, text=t("btn_start_listen"), width=170,
            fg_color=_COLOR_BTN_START, hover_color=_COLOR_BTN_START_HOVER,
            command=self._toggle_listener,
        )
        self._toggle_btn.grid(row=0, column=0, padx=14, pady=12)
        self._status_label = ctk.CTkLabel(
            frame, text=t("status_stopped"), text_color=_COLOR_STOPPED,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._status_label.grid(row=0, column=1, padx=8, pady=12, sticky="w")
        self._last_action_label = ctk.CTkLabel(
            frame, text="", font=ctk.CTkFont(size=11),
            text_color=("gray55", "gray55"), anchor="e",
        )
        self._last_action_label.grid(row=0, column=2, padx=14, pady=12, sticky="e")
        frame.grid_columnconfigure(2, weight=1)

    # ──────────────────────────────────────────────────────────────
    # Layout visual do controle (silhueta de gamepad)
    # ──────────────────────────────────────────────────────────────

    def _build_controller_layout(self) -> None:
        """Monta o layout visual de gamepad com todos os botões clicáveis."""
        outer = ctk.CTkFrame(self.root)
        outer.grid(row=4, column=0, sticky="nsew", padx=12, pady=4)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        # Oculta a scrollbar quando todo o conteúdo cabe na área visível
        if hasattr(scroll, "_parent_canvas") and hasattr(scroll, "_scrollbar"):
            def _scrollbar_update(first, last):
                scroll._scrollbar.set(first, last)
                if float(first) <= 0.0 and float(last) >= 1.0:
                    scroll._scrollbar.grid_remove()
                else:
                    scroll._scrollbar.grid()
            scroll._parent_canvas.configure(yscrollcommand=_scrollbar_update)

        # 0. Toolbar de ações rápidas
        toolbar = ctk.CTkFrame(scroll, fg_color="transparent")
        toolbar.pack(fill="x", padx=8, pady=(8, 0))
        ctk.CTkButton(
            toolbar, text=t("btn_clear_binds"), width=160,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            command=self._on_clear_binds,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            toolbar, text=t("btn_auto_map"), width=160,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            command=self._on_auto_map,
        ).pack(side="left")
        ctk.CTkButton(
            toolbar, text=t("btn_feedback"), width=90,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            command=lambda: webbrowser.open(
                "https://docs.google.com/forms/d/e/"
                "1FAIpQLSfji-06RCfh_Dq7pIa2agyr3ycS8mBK-wK6BVZX-RzGT1N8_g/viewform"
            ),
        ).pack(side="right")

        # 1. Gatilhos / ombros (topo)
        self._build_trigger_row(scroll)

        # 2. Corpo: D-pad | Centro | Botões de face
        body = ctk.CTkFrame(scroll, fg_color="transparent")
        body.pack(fill="x", padx=8, pady=(0, 4))
        body.grid_columnconfigure((0, 1, 2), weight=1)
        self._build_dpad_cluster(body)
        self._build_center_cluster(body)
        self._build_face_cluster(body)

        # 3. Analógicos (reutiliza _build_stick_panel via _render_analog_config)
        sticks_outer = ctk.CTkFrame(scroll, fg_color="transparent")
        sticks_outer.pack(fill="x", padx=8, pady=(4, 8))
        sticks_outer.grid_columnconfigure((0, 1), weight=1)
        self._left_stick_frame  = ctk.CTkFrame(sticks_outer)
        self._right_stick_frame = ctk.CTkFrame(sticks_outer)
        self._left_stick_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self._right_stick_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

    def _build_trigger_row(self, parent: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(8, 0))
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left")
        self._build_btn_tile(left, "LT", r=0, c=0, w=96, h=42)
        self._build_btn_tile(left, "LB", r=0, c=1, w=96, h=42)
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side="right")
        self._build_btn_tile(right, "RB", r=0, c=0, w=96, h=42)
        self._build_btn_tile(right, "RT", r=0, c=1, w=96, h=42)

    def _build_dpad_cluster(self, parent: ctk.CTkFrame) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=0, padx=4, pady=4, sticky="n")
        ctk.CTkLabel(
            frame, text=t("sec_dpad"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray55", "gray55"),
        ).pack(pady=(4, 2))
        cross = ctk.CTkFrame(frame, fg_color="transparent")
        cross.pack()
        W, H = 82, 44
        self._build_btn_tile(cross, "↑", r=0, c=1, w=W, h=H)
        self._build_btn_tile(cross, "←", r=1, c=0, w=W, h=H)
        ctk.CTkLabel(
            cross, text="D", width=W, height=H,
            font=ctk.CTkFont(size=18), text_color=("gray45", "gray55"),
        ).grid(row=1, column=1, padx=3, pady=3)
        self._build_btn_tile(cross, "→", r=1, c=2, w=W, h=H)
        self._build_btn_tile(cross, "↓", r=2, c=1, w=W, h=H)

    def _build_face_cluster(self, parent: ctk.CTkFrame) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=2, padx=4, pady=4, sticky="n")
        ctk.CTkLabel(
            frame, text=t("sec_buttons"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray55", "gray55"),
        ).pack(pady=(4, 2))
        cross = ctk.CTkFrame(frame, fg_color="transparent")
        cross.pack()
        W, H = 82, 44
        self._build_btn_tile(cross, "Y", r=0, c=1, w=W, h=H)
        self._build_btn_tile(cross, "X", r=1, c=0, w=W, h=H)
        ctk.CTkLabel(
            cross, text="◎", width=W, height=H,
            font=ctk.CTkFont(size=18), text_color=("gray45", "gray55"),
        ).grid(row=1, column=1, padx=3, pady=3)
        self._build_btn_tile(cross, "B", r=1, c=2, w=W, h=H)
        self._build_btn_tile(cross, "A", r=2, c=1, w=W, h=H)

    def _build_center_cluster(self, parent: ctk.CTkFrame) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=1, padx=4, pady=4, sticky="n")
        ctk.CTkLabel(
            frame, text=t("sec_central"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray55", "gray55"),
        ).pack(pady=(4, 2))
        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack()
        W, H = 88, 44
        self._build_btn_tile(grid, "SELECT", r=0, c=0, w=W, h=H)
        self._build_btn_tile(grid, "START",  r=0, c=1, w=W, h=H)
        self._build_btn_tile(grid, "LS", r=1, c=0, w=W, h=H)
        self._build_btn_tile(grid, "RS", r=1, c=1, w=W, h=H)

    def _build_btn_tile(
        self, parent: ctk.CTkFrame, visual_id: str,
        r: int, c: int, w: int = 88, h: int = 54,
    ) -> ctk.CTkButton:
        """Cria um tile clicável para um botão físico do controle."""
        btn_key = self._layout.get(visual_id)
        key_label = btn_key if btn_key is not None else "—"
        btn = ctk.CTkButton(
            parent,
            text=f"{visual_id} ({key_label})\n{self._btn_tile_text(btn_key)}",
            width=w, height=h,
            fg_color=("gray68", "gray28"),
            hover_color=("gray58", "gray38"),
            font=ctk.CTkFont(size=11),
            command=lambda vid=visual_id: self._on_btn_tile_click(vid),
        )
        btn.grid(row=r, column=c, padx=3, pady=3)
        self._btn_tiles[visual_id] = btn
        return btn

    def _mouse_key_display(self) -> dict[str, str]:
        return {
            "mouse_left":   t("mouse_display_left"),
            "mouse_right":  t("mouse_display_right"),
            "mouse_middle": t("mouse_display_middle"),
        }

    def _btn_tile_text(self, btn_key: str | None) -> str:
        """Retorna texto resumido da binding atual para exibir no tile."""
        if btn_key is None:
            return "—"
        bind = self.cfg["binds"].get(btn_key)
        if not bind:
            return "—"
        t = bind.get("type", "none")
        if t == "keyboard":
            key = bind.get("key", "")
            base = self._mouse_key_display().get(key, f'\u2328 {key}')
            if bind.get("macro_interval_ms"):
                base = f"⟳ {base}"
            elif bind.get("hold_while_pressed"):
                base = f"⬇ {base}"
            return base
        if t == "sequence":
            n = len(bind.get("steps", []))
            base = f'\u25b6 {n} {step_plural(n)}'
            if bind.get("macro_interval_ms"):
                base = f"⟳ {base}"
            return base
        if t == "mouse_combo":
            return "\U0001f5b1 mouse"
        if t == "none":
            return "—"
        return "—"

    def _on_btn_tile_click(self, vid: str) -> None:
        btn_key = self._layout.get(vid)
        existing = self.cfg["binds"].get(btn_key) if btn_key else None
        dlg = BindDialog(
            self.root,
            title=t("title_configure", label=vid),
            edit_key=btn_key,
            edit_bind=existing,
            existing_keys=[k for k in self.cfg["binds"] if k != btn_key],
        )
        self.root.wait_window(dlg.dialog)
        if dlg.clear_result:
            # Remove ação + mapeamento do botão do controle
            if btn_key and btn_key in self.cfg["binds"]:
                del self.cfg["binds"][btn_key]
            if vid in self._layout:
                del self._layout[vid]
            self._settings["btn_layout"] = dict(self._layout)
            presets.save_settings(self._settings)
            self._update_btn_tiles()
            self._save_current_preset()
        elif dlg.result:
            new_key = dlg.result["button"]
            if btn_key and btn_key in self.cfg["binds"] and btn_key != new_key:
                del self.cfg["binds"][btn_key]
            self.cfg["binds"][new_key] = dlg.result["bind"]
            self._layout[vid] = new_key
            self._settings["btn_layout"] = dict(self._layout)
            presets.save_settings(self._settings)
            self._update_btn_tiles()
            self._save_current_preset()

    def _update_btn_tiles(self) -> None:
        """Atualiza o texto de todos os tiles com as bindings atuais do cfg."""
        for vid, btn in self._btn_tiles.items():
            btn_key = self._layout.get(vid)
            key_label = btn_key if btn_key is not None else "—"
            btn.configure(text=f"{vid} ({key_label})\n{self._btn_tile_text(btn_key)}")
        self._update_analog_btn_states()

    def _on_clear_binds(self) -> None:
        """Limpa todos os mapeamentos e reseta os números de botão para o padrão."""
        if messagebox.askyesno(
            t("title_confirm"),
            t("msg_clear_binds"),
            parent=self.root,
        ):
            self.cfg["binds"] = {}
            self._layout = dict(_DEFAULT_LAYOUT)
            self._settings["btn_layout"] = dict(_DEFAULT_LAYOUT)
            presets.save_settings(self._settings)
            self._update_btn_tiles()
            self._save_current_preset()

    def _on_auto_map(self) -> None:
        """Abre o wizard de detecção automática de botões."""
        wizard = AutoMapWizard(self.root, _TILE_ORDER, self._layout.copy())
        self.root.wait_window(wizard.dialog)
        if wizard.result is not None:
            new_layout = wizard.result
            # Migra binds: move cfg["binds"][old_key] → cfg["binds"][new_key]
            old_binds = dict(self.cfg["binds"])
            self.cfg["binds"] = {}
            for vid, new_key in new_layout.items():
                old_key = self._layout.get(vid)
                if old_key in old_binds:
                    self.cfg["binds"][new_key] = old_binds.pop(old_key)
            # Mantém binds de chaves que não fazem parte de nenhum tile
            self.cfg["binds"].update(old_binds)
            self._layout = new_layout
            self._settings["btn_layout"] = new_layout
            presets.save_settings(self._settings)
            self._update_btn_tiles()
            self._save_current_preset()

    # ──────────────────────────────────────────────────────────────
    # Painel de analógico (cross pattern)
    # ──────────────────────────────────────────────────────────────

    def _build_stick_panel(self, parent: ctk.CTkFrame, stick_idx: int, stick_cfg: dict) -> dict:
        """Cria o conteúdo de um painel de analógico e retorna referências."""
        # Always use translated label based on index — ignores stored label for display
        if stick_idx == 0:
            label = t("sec_analog_left")
        elif stick_idx == 1:
            label = t("sec_analog_right")
        else:
            label = t("sec_analog_n", n=stick_idx + 1)
        defaults = _default_sticks()

        parent.grid_columnconfigure(0, weight=1)

        # Título
        ctk.CTkLabel(
            parent, text=label,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(pady=(10, 4))

        # Config de eixos
        ax_frame = ctk.CTkFrame(parent, fg_color="transparent")
        ax_frame.pack()

        def _make_ax_entry(label_text: str, default_val: int) -> ctk.CTkEntry:
            ctk.CTkLabel(ax_frame, text=label_text, font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 2))
            e = ctk.CTkEntry(ax_frame, width=36, justify="center")
            e.insert(0, str(default_val))
            e.pack(side="left", padx=(0, 8))
            return e

        default_ax = defaults[stick_idx]["axis_x"] if stick_idx < len(defaults) else stick_idx * 2
        default_ay = defaults[stick_idx]["axis_y"] if stick_idx < len(defaults) else stick_idx * 2 + 1
        axis_x_entry = _make_ax_entry("X:", stick_cfg.get("axis_x", default_ax))
        axis_y_entry = _make_ax_entry("Y:", stick_cfg.get("axis_y", default_ay))

        ctk.CTkLabel(ax_frame, text="DZ:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 2))
        dz_entry = ctk.CTkEntry(ax_frame, width=46, justify="center")
        dz_entry.insert(0, str(stick_cfg.get("deadzone", 0.15)))
        dz_entry.pack(side="left")

        default_sens = 600.0 if stick_idx == 0 else 8.0
        sens_unit    = "px/s" if stick_idx == 0 else "cl/s"
        ctk.CTkLabel(ax_frame, text="Sens.:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(8, 2))
        sens_entry = ctk.CTkEntry(ax_frame, width=52, justify="center")
        sens_entry.insert(0, str(stick_cfg.get("sensitivity", default_sens)))
        sens_entry.pack(side="left")
        ctk.CTkLabel(
            ax_frame, text=sens_unit, font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray55"),
        ).pack(side="left", padx=(2, 0))

        # Cross pattern: ↑ ← ⊙ → ↓
        cross = ctk.CTkFrame(parent, fg_color="transparent")
        cross.pack(pady=(12, 4), expand=True)

        dir_bindings: dict[str, dict] = {
            d: dict(stick_cfg.get(d, {"type": "none"}))
            for d in ("up", "down", "left", "right")
        }

        BTN_W, BTN_H = 88, 46
        dir_btns: dict[str, ctk.CTkButton] = {}

        for direction, row, col in [
            ("up",    0, 1),
            ("left",  1, 0),
            ("right", 1, 2),
            ("down",  2, 1),
        ]:
            binding = dir_bindings[direction]
            btn = ctk.CTkButton(
                cross,
                text=_dir_btn_text(direction, binding),
                width=BTN_W, height=BTN_H,
                fg_color=("gray68", "gray28"),
                hover_color=("gray58", "gray38"),
                command=lambda d=direction, si=stick_idx: self._on_dir_btn_click(si, d),
            )
            btn.grid(row=row, column=col, padx=4, pady=4)
            dir_btns[direction] = btn

        # Centro — ícone do analógico
        ctk.CTkLabel(
            cross, text="⊙", width=BTN_W, height=BTN_H,
            font=ctk.CTkFont(size=24), text_color=("gray45", "gray55"),
        ).grid(row=1, column=1, padx=4, pady=4)

        # Dica
        ctk.CTkLabel(
            parent, text=t("msg_click_dir"),
            font=ctk.CTkFont(size=10), text_color=("gray55", "gray55"),
        ).pack(pady=(0, 4))

        # Checkboxes de modo — mutuamente exclusivos
        # Esquerdo: "mouse" (cursor) | "game" (WASD)
        # Direito:  "scroll"         | "game" (câmera/mouse)
        if stick_idx == 0:
            mode_opts = [
                ("mouse", t("mode_mouse")),
                ("game",  t("mode_game_wasd")),
            ]
        else:
            mode_opts = [
                ("scroll", t("mode_scroll")),
                ("game",   t("mode_game_cam")),
            ]

        init_mode = stick_cfg.get("stick_mode", "none")
        stick_mode_var = ctk.StringVar(value=init_mode)
        cb_vars: dict[str, ctk.BooleanVar] = {}

        modes_frame = ctk.CTkFrame(parent, fg_color="transparent")
        modes_frame.pack(pady=(0, 8))

        for mode_val, mode_label in mode_opts:
            cb_var = ctk.BooleanVar(value=(init_mode == mode_val))

            def _make_cmd(mv=mode_val):
                def cmd():
                    if stick_mode_var.get() == mv:
                        stick_mode_var.set("none")
                        cb_vars[mv].set(False)
                    else:
                        stick_mode_var.set(mv)
                        cb_vars[mv].set(True)
                        for other in cb_vars:
                            if other != mv:
                                cb_vars[other].set(False)
                    self._on_analog_toggle()
                return cmd

            ctk.CTkCheckBox(
                modes_frame,
                text=mode_label,
                variable=cb_var,
                command=_make_cmd(mode_val),
                font=ctk.CTkFont(size=11),
            ).pack(anchor="w", padx=8, pady=(0, 2))
            cb_vars[mode_val] = cb_var

        # Auto-save nas entries de eixo
        for entry in (axis_x_entry, axis_y_entry, dz_entry, sens_entry):
            entry.bind("<FocusOut>", lambda e: self._save_analog_config())
            entry.bind("<Return>",   lambda e: self._save_analog_config())

        return {
            "axis_x_entry":   axis_x_entry,
            "axis_y_entry":   axis_y_entry,
            "dz_entry":       dz_entry,
            "sens_entry":     sens_entry,
            "dir_btns":       dir_btns,
            "dir_bindings":   dir_bindings,
            "stick_mode_var": stick_mode_var,
            "cb_vars":        cb_vars,
        }

    def _on_dir_btn_click(self, stick_idx: int, direction: str) -> None:
        panel = self._stick_panels[stick_idx]
        if panel is None:
            return

        dir_names = {
            "up":    t("dir_up"),
            "down":  t("dir_down"),
            "left":  t("dir_left"),
            "right": t("dir_right"),
        }
        if stick_idx == 0:
            stick_label = t("sec_analog_left")
        elif stick_idx == 1:
            stick_label = t("sec_analog_right")
        else:
            stick_label = t("sec_analog_n", n=stick_idx + 1)

        dlg = AnalogDirectionDialog(
            self.root,
            direction_label=f"{dir_names[direction]} — {stick_label}",
            current=panel["dir_bindings"][direction],
        )
        self.root.wait_window(dlg.dialog)

        if dlg.result is not None:
            panel["dir_bindings"][direction] = dlg.result
            panel["dir_btns"][direction].configure(text=_dir_btn_text(direction, dlg.result))
            self._save_analog_config()

    # ──────────────────────────────────────────────────────────────
    # Config analógica — leitura, escrita e renderização
    # ──────────────────────────────────────────────────────────────

    def _on_analog_toggle(self) -> None:
        """Chamado quando o modo de um analógico muda."""
        self._save_analog_config()
        self._update_analog_btn_states()

    def _update_analog_btn_states(self) -> None:
        """Escurece/desabilita botões de direção quando um modo automático está ativo."""
        for panel in self._stick_panels:
            if panel is None:
                continue
            dim = panel["stick_mode_var"].get() != "none" if "stick_mode_var" in panel else False
            for btn in panel["dir_btns"].values():
                if dim:
                    btn.configure(
                        fg_color=("gray50", "gray15"),
                        hover_color=("gray50", "gray15"),
                        text_color=("gray42", "gray38"),
                        state="disabled",
                    )
                else:
                    btn.configure(
                        fg_color=("gray68", "gray28"),
                        hover_color=("gray58", "gray38"),
                        text_color=("gray10", "#DCE4EE"),
                        state="normal",
                    )

    def _collect_analog_config(self) -> dict:
        sticks  = []
        labels  = [t("sec_analog_left"), t("sec_analog_right")]
        defs    = _default_sticks()

        for i, panel in enumerate(self._stick_panels):
            if panel is None:
                sticks.append(defs[i] if i < len(defs) else defs[0])
                continue
            try:
                ax = int(panel["axis_x_entry"].get())
            except (ValueError, TypeError):
                ax = i * 2
            try:
                ay = int(panel["axis_y_entry"].get())
            except (ValueError, TypeError):
                ay = i * 2 + 1
            try:
                dz = max(0.0, min(0.99, float(panel["dz_entry"].get())))
            except (ValueError, TypeError):
                dz = 0.15
            default_sens = 600.0 if i == 0 else 8.0
            try:
                sens = max(0.1, float(panel["sens_entry"].get()))
            except (ValueError, TypeError):
                sens = default_sens
            sticks.append({
                "label":       labels[i] if i < len(labels) else t("sec_analog_n", n=i + 1),
                "axis_x":      ax,
                "axis_y":      ay,
                "deadzone":    dz,
                "sensitivity": sens,
                "stick_mode":  panel["stick_mode_var"].get(),
                **panel["dir_bindings"],
            })
        return {"sticks": sticks}

    def _save_analog_config(self) -> None:
        self.cfg["analog"] = self._collect_analog_config()
        self._save_current_preset()

    def _render_analog_config(self) -> None:
        """Reconstrói os dois painéis de analógico a partir do cfg atual."""
        if self._left_stick_frame is None:
            return

        analog = self.cfg.get("analog", {})
        sticks = analog.get("sticks", [])
        defs   = _default_sticks()
        frames = [self._left_stick_frame, self._right_stick_frame]

        for i in range(2):
            frame     = frames[i]
            stick_cfg = sticks[i] if i < len(sticks) else defs[i]
            for widget in frame.winfo_children():
                widget.destroy()
            self._stick_panels[i] = self._build_stick_panel(frame, i, stick_cfg)

        self._update_analog_btn_states()

    # ──────────────────────────────────────────────────────────────
    # Processamento analógico — thread do controller
    # ──────────────────────────────────────────────────────────────

    # WASD hardcoded para Modo Jogo do analógico esquerdo
    _GAME_KEYS: dict[str, str] = {
        "up": "w", "down": "s", "left": "a", "right": "d",
    }

    def _on_axes_update(self, axis_values: list[float]) -> None:
        """
        Chamado a 60 Hz pela thread daemon do controller.
        Não toca em widgets — só pyautogui (thread-safe).

        Cada stick tem um modo independente (stick_mode):
          Esquerdo:
            "mouse"  → move o cursor do mouse
            "game"   → WASD (W/A/S/D mantidos/soltos por borda)
            "none"   → key bindings manuais por direção
          Direito:
            "scroll" → scroll vertical/horizontal
            "game"   → move o cursor (câmera no jogo)
            "none"   → key bindings manuais por direção
        """
        analog  = self.cfg.get("analog", {})
        sticks  = analog.get("sticks", [])
        dx = dy = sv = sh = 0.0

        for i, stick in enumerate(sticks):
            try:
                ax_idx = int(stick.get("axis_x", i * 2))
                ay_idx = int(stick.get("axis_y", i * 2 + 1))
                dz     = float(stick.get("deadzone", 0.15))
            except (ValueError, TypeError):
                continue
            if ax_idx >= len(axis_values) or ay_idx >= len(axis_values):
                continue

            sx = _apply_deadzone(axis_values[ax_idx], dz)
            sy = _apply_deadzone(axis_values[ay_idx], dz)
            mode = stick.get("stick_mode", "none")
            sens = float(stick.get("sensitivity", 600.0))

            if mode == "mouse":
                # Esquerdo: move o cursor
                dx += sx * sens / 60.0
                dy += sy * sens / 60.0
                self._release_stick_keys(i, stick)

            elif mode == "scroll":
                # Direito: scroll — sy negativo = cima → scroll positivo
                sv -= sy * sens / 60.0   # scroll vertical
                sh += sx * sens / 60.0   # scroll horizontal
                self._release_stick_keys(i, stick)

            elif mode == "game" and i == 0:
                # Esquerdo Modo Jogo: WASD edge-triggered
                for direction, axis_val in [
                    ("up",    -sy),
                    ("down",   sy),
                    ("left",  -sx),
                    ("right",  sx),
                ]:
                    is_active = axis_val > 0
                    k = (i, direction)
                    was_active = self._prev_dir_active.get(k, False)
                    self._prev_dir_active[k] = is_active
                    combo = self._GAME_KEYS[direction]
                    if is_active and not was_active:
                        actions.key_combo_down(combo)
                        self._held_keys.add(combo)
                    elif not is_active and was_active:
                        actions.key_combo_up(combo)
                        self._held_keys.discard(combo)

            elif mode == "game" and i == 1:
                # Direito Modo Jogo: move o cursor (câmera)
                dx += sx * sens / 60.0
                dy += sy * sens / 60.0
                self._release_stick_keys(i, stick)

            else:
                # Modo manual: key bindings e sequências por direção
                for direction, axis_val in [
                    ("up",    -sy),
                    ("down",   sy),
                    ("left",  -sx),
                    ("right",  sx),
                ]:
                    b = stick.get(direction, {"type": "none"})
                    is_active = axis_val > 0
                    k = (i, direction)
                    was_active = self._prev_dir_active.get(k, False)
                    self._prev_dir_active[k] = is_active

                    btype = b.get("type", "none")
                    if btype == "key" and b.get("key"):
                        combo = b["key"]
                        if is_active and not was_active:
                            actions.key_combo_down(combo)
                            self._held_keys.add(combo)
                        elif not is_active and was_active:
                            actions.key_combo_up(combo)
                            self._held_keys.discard(combo)

                    if btype == "sequence" and is_active and not was_active:
                        steps = b.get("steps", [])
                        if steps:
                            threading.Thread(
                                target=actions.execute_sequence,
                                args=(steps,),
                                daemon=True,
                                name=f"SeqDir-{i}-{direction}",
                            ).start()

        # Sub-pixel accumulation
        self._acc_x  += dx;  ix  = int(self._acc_x);  self._acc_x  -= ix
        self._acc_y  += dy;  iy  = int(self._acc_y);  self._acc_y  -= iy
        self._acc_sv += sv;  isv = int(self._acc_sv); self._acc_sv -= isv
        self._acc_sh += sh;  ish = int(self._acc_sh); self._acc_sh -= ish

        if ix != 0 or iy != 0:
            actions.move_mouse_relative(ix, iy)
        if isv != 0:
            actions.scroll_v_relative(isv)
        if ish != 0:
            actions.scroll_h_relative(ish)

    def _release_stick_keys(self, stick_idx: int, stick: dict) -> None:
        """Solta quaisquer teclas presas por este stick (ao trocar de modo)."""
        for direction in ("up", "down", "left", "right"):
            k = (stick_idx, direction)
            if self._prev_dir_active.get(k, False):
                b = stick.get(direction, {"type": "none"})
                if b.get("type") == "key" and b.get("key"):
                    actions.key_combo_up(b["key"])
                    self._held_keys.discard(b["key"])
                self._prev_dir_active[k] = False

    def _release_all_held_keys(self) -> None:
        for key in list(self._held_keys):
            try:
                actions.key_combo_up(key)
            except Exception:
                pass
        self._held_keys.clear()
        for key in list(self._held_btn_keys.values()):
            try:
                actions.hold_up(key)
            except Exception:
                pass
        self._held_btn_keys.clear()
        for evt in list(self._macro_stop_events.values()):
            try:
                evt.set()
            except Exception:
                pass
        self._macro_stop_events.clear()

    # ──────────────────────────────────────────────────────────────
    # Gerenciamento de Presets
    # ──────────────────────────────────────────────────────────────

    def _refresh_preset_dropdown(self) -> None:
        lst   = presets.list_presets(self._presets_dir)
        names = [p.stem for p in lst]
        if names:
            self._preset_combo.configure(values=names)
            current = self._current_preset_path.stem if self._current_preset_path else names[0]
            self._preset_var.set(current if current in names else names[0])
        else:
            self._preset_combo.configure(values=["—"])
            self._preset_var.set("—")

    def _on_preset_selected(self, name: str) -> None:
        if not name or name == "—":
            return
        if self._current_preset_path and self._current_preset_path.stem == name:
            return
        path = self._presets_dir / f"{name}.json"
        if path.exists():
            self._apply_preset(path)

    def _apply_preset(self, path: Path) -> None:
        self.cfg = self._ensure_defaults(presets.load_preset(path))
        self._current_preset_path = path
        self.root.title(f"JoyBind — {path.stem}")
        self._settings["last_preset"] = str(path)
        presets.save_settings(self._settings)
        self._update_btn_tiles()
        self._render_analog_config()

    def _new_preset(self) -> None:
        dlg  = ctk.CTkInputDialog(text=t("msg_preset_new_text"), title=t("title_new_preset"))
        name = dlg.get_input()
        if not name:
            return
        safe = _sanitize_filename(name)
        if not safe:
            messagebox.showerror(t("title_err_name"), t("msg_invalid_name"), parent=self.root)
            return
        path = self._presets_dir / f"{safe}.json"
        if path.exists():
            if not messagebox.askyesno(t("title_err_preset_exists"), t("msg_preset_replace", name=safe), parent=self.root):
                return
        cfg: dict = {"binds": {}, "analog": {"enabled": False, "sticks": _default_sticks()}}
        if presets.save_preset(path, cfg):
            self.cfg = cfg
            self._current_preset_path = path
            self._settings["last_preset"] = str(path)
            presets.save_settings(self._settings)
            self._refresh_preset_dropdown()
            self.root.title(f"JoyBind — {safe}")
            self._update_btn_tiles()
            self._render_analog_config()

    def _delete_current_preset(self) -> None:
        if not self._current_preset_path or not self._current_preset_path.exists():
            return
        name = self._current_preset_path.stem
        if not messagebox.askyesno(
            t("title_delete_preset"),
            t("msg_delete_preset", name=name),
            parent=self.root,
        ):
            return
        self._current_preset_path.unlink()
        # Carrega o próximo preset disponível; cria default se não houver nenhum
        lst = presets.list_presets(self._presets_dir)
        if lst:
            self._apply_preset(lst[0])
        else:
            dp = self._presets_dir / "default.json"
            cfg: dict = {"binds": {}, "analog": {"enabled": False, "sticks": _default_sticks()}}
            presets.save_preset(dp, cfg)
            self._apply_preset(dp)
        self._refresh_preset_dropdown()

    def _change_presets_folder(self) -> None:
        folder = filedialog.askdirectory(
            title=t("title_folder"),
            initialdir=str(self._presets_dir), parent=self.root,
        )
        if not folder:
            return
        self._presets_dir = Path(folder)
        self._settings["presets_dir"] = str(self._presets_dir)
        if self._current_preset_path and self._current_preset_path.parent == self._presets_dir:
            presets.save_settings(self._settings)
            self._refresh_preset_dropdown()
            return
        lst = presets.list_presets(self._presets_dir)
        if lst:
            self._settings["last_preset"] = str(lst[0])
            presets.save_settings(self._settings)
            self._apply_preset(lst[0])
        else:
            dp = self._presets_dir / "default.json"
            cfg: dict = {"binds": {}, "analog": {"enabled": False, "sticks": _default_sticks()}}
            presets.save_preset(dp, cfg)
            self._settings["last_preset"] = str(dp)
            presets.save_settings(self._settings)
            self._apply_preset(dp)
        self._refresh_preset_dropdown()

    def _save_current_preset(self) -> None:
        if self._current_preset_path is not None:
            presets.save_preset(self._current_preset_path, self.cfg)

    # ──────────────────────────────────────────────────────────────
    # Dropdown de joysticks
    # ──────────────────────────────────────────────────────────────

    def _refresh_joystick_dropdown(self) -> None:
        if self._is_listening:
            return
        names = ControllerListener.get_joystick_names()
        if names:
            self._joystick_combo.configure(values=names)
            self._joystick_var.set(names[0])
        else:
            self._joystick_combo.configure(values=[t("status_no_ctrl")])
            self._joystick_var.set(t("status_no_ctrl"))

    # ──────────────────────────────────────────────────────────────
    # Listener (Start / Stop)
    # ──────────────────────────────────────────────────────────────

    def _toggle_listener(self) -> None:
        if self._is_listening:
            self._stop_listener()
        else:
            self._start_listener()

    def _start_listener(self) -> None:
        names    = ControllerListener.get_joystick_names()
        selected = self._joystick_var.get()
        idx      = names.index(selected) if selected in names else 0
        self.listener.set_joystick_index(idx)

        ok, err_msg = self.listener.start()
        if not ok:
            messagebox.showerror(t("title_err_start"), err_msg)
            return

        self._is_listening = True
        self._toggle_btn.configure(
            text=t("btn_stop_listen"),
            fg_color=_COLOR_BTN_STOP, hover_color=_COLOR_BTN_STOP_HOVER,
        )
        self._status_label.configure(text=t("status_active"), text_color=_COLOR_ACTIVE)
        self._refresh_btn.configure(state="disabled")

    def _stop_listener(self) -> None:
        self.listener.stop()
        self._is_listening = False
        self._acc_x = self._acc_y = self._acc_sv = self._acc_sh = 0.0
        self._prev_dir_active = {}
        self._release_all_held_keys()
        self._toggle_btn.configure(
            text=t("btn_start_listen"),
            fg_color=_COLOR_BTN_START, hover_color=_COLOR_BTN_START_HOVER,
        )
        self._status_label.configure(text=t("status_stopped"), text_color=_COLOR_STOPPED)
        self._refresh_btn.configure(state="normal")

    # ──────────────────────────────────────────────────────────────
    # Ações de botão (thread do controller)
    # ──────────────────────────────────────────────────────────────

    def _on_button_press(self, button: int) -> None:
        key  = str(button)
        bind = self.cfg["binds"].get(key)
        if not bind:
            return

        def run() -> None:
            btype = bind["type"]
            if btype == "keyboard":
                macro_ms = bind.get("macro_interval_ms", 0)
                if macro_ms > 0:
                    stop_evt = threading.Event()
                    self._macro_stop_events[button] = stop_evt
                    key_name = bind["key"]
                    label_text = f"BTN {button}  →  ⟳ {key_name} ({macro_ms}ms)"
                    self.root.after(0, lambda t=label_text: self._last_action_label.configure(text=t))

                    def macro_loop(k: str, interval_ms: int, stop: threading.Event) -> None:
                        while not stop.is_set():
                            actions.execute_keyboard(k, bind.get("hold_ms", 0))
                            stop.wait(interval_ms / 1000.0)

                    threading.Thread(
                        target=macro_loop,
                        args=(key_name, macro_ms, stop_evt),
                        daemon=True,
                        name=f"Macro-BTN{button}",
                    ).start()
                    return
                elif bind.get("hold_while_pressed"):
                    actions.hold_down(bind["key"])
                    self._held_btn_keys[button] = bind["key"]
                    label_text = f"BTN {button}  →  ⬇ {bind['key']}"
                else:
                    actions.execute_keyboard(bind["key"], bind.get("hold_ms", 0))
                    label_text = f"BTN {button}  →  {bind['key']}"
            elif btype == "sequence":
                n = len(bind.get("steps", []))
                macro_ms = bind.get("macro_interval_ms", 0)
                if macro_ms > 0:
                    stop_evt = threading.Event()
                    self._macro_stop_events[button] = stop_evt
                    label_text = f"BTN {button}  →  ⟳ {t('word_sequence')} ({n} {step_plural(n)}) ({macro_ms}ms)"
                    self.root.after(0, lambda t=label_text: self._last_action_label.configure(text=t))

                    def seq_macro_loop(steps: list, interval_ms: int, stop: threading.Event) -> None:
                        while not stop.is_set():
                            actions.execute_sequence(steps)
                            stop.wait(interval_ms / 1000.0)

                    threading.Thread(
                        target=seq_macro_loop,
                        args=(bind["steps"], macro_ms, stop_evt),
                        daemon=True,
                        name=f"Macro-BTN{button}",
                    ).start()
                    return
                actions.execute_sequence(bind["steps"])
                label_text = f"BTN {button}  →  {t('word_sequence')} ({n} {step_plural(n)})"
            elif btype == "mouse_combo":
                actions.execute_mouse_combo(bind["x"], bind["y"])
                label_text = f"BTN {button}  →  mouse ({bind['x']}, {bind['y']})"
            else:
                return
            self.root.after(0, lambda t=label_text: self._last_action_label.configure(text=t))

        threading.Thread(target=run, daemon=True, name=f"Action-BTN{button}").start()

    def _on_button_release(self, button: int) -> None:
        # Para macro em loop se existir
        stop_evt = self._macro_stop_events.pop(button, None)
        if stop_evt is not None:
            stop_evt.set()

        key_name = self._held_btn_keys.pop(button, None)
        if key_name is None:
            return

        def run() -> None:
            actions.hold_up(key_name)
            self.root.after(0, lambda: self._last_action_label.configure(
                text=f"BTN {button}  →  ↑ {key_name}"
            ))

        threading.Thread(target=run, daemon=True, name=f"Release-BTN{button}").start()

    # (lista de binds e CRUD removidos — substituídos pelos tiles do layout visual)

    # ──────────────────────────────────────────────────────────────
    # Encerramento
    # ──────────────────────────────────────────────────────────────

    def _on_lang_change(self, lang: str) -> None:
        """Saves language preference and restarts the application."""
        if i18n._lang == lang:
            return  # Already active
        import subprocess
        import sys as _sys2
        s = presets.load_settings()
        s["language"] = lang
        presets.save_settings(s)
        if getattr(_sys2, "frozen", False):
            subprocess.Popen([_sys2.executable])
        else:
            subprocess.Popen([_sys2.executable] + _sys2.argv)
        self.shutdown()
        self.root.destroy()

    def shutdown(self) -> None:
        try:
            self._save_analog_config()
        except Exception:
            pass
        self._release_all_held_keys()
        if self._is_listening:
            self.listener.stop()
        pygame.quit()
