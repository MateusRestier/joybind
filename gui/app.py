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
from pathlib import Path
from tkinter import messagebox, filedialog

import pygame
import customtkinter as ctk
from pynput.keyboard import Listener as KeyListener

import presets
import actions
from controller import ControllerListener
from gui.bind_dialog import BindDialog

# ── Cores ──────────────────────────────────────────────────────────────────
_COLOR_ACTIVE          = "#2ecc71"
_COLOR_STOPPED         = "#e74c3c"
_COLOR_BTN_START       = "#2ecc71"
_COLOR_BTN_START_HOVER = "#27ae60"
_COLOR_BTN_STOP        = "#e67e22"
_COLOR_BTN_STOP_HOVER  = "#d35400"

_TYPE_LABELS: dict[str, str] = {
    "keyboard":    "TECLADO",
    "sequence":    "SEQUÊNCIA",
    "mouse_combo": "MOUSE",
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
            "label": "Esquerdo", "axis_x": 0, "axis_y": 1, "deadzone": 0.15,
            "up":    {"type": "mouse_y", "sensitivity": 600},
            "down":  {"type": "mouse_y", "sensitivity": 600},
            "left":  {"type": "mouse_x", "sensitivity": 600},
            "right": {"type": "mouse_x", "sensitivity": 600},
        },
        {
            "label": "Direito", "axis_x": 2, "axis_y": 3, "deadzone": 0.15,
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
    short = {
        "none":     "—",
        "mouse_x":  "Mouse X",
        "mouse_y":  "Mouse Y",
        "scroll_v": "Scroll ↕",
        "scroll_h": "Scroll ↔",
        "key":      binding.get("key", "?"),
    }.get(btype, "?")
    return f"{arrow}\n{short}"


def _sanitize_filename(name: str) -> str:
    return "".join(c for c in name if c not in r'\/:*?"<>|').strip()


# ── Diálogo de configuração de direção analógica ───────────────────────────

class AnalogDirectionDialog:
    """Dialog para configurar a ação de uma direção do analógico."""

    _TYPE_OPTS: dict[str, str] = {
        "none":     "— Nada",
        "mouse_x":  "Mouse X (horizontal)",
        "mouse_y":  "Mouse Y (vertical)",
        "scroll_v": "Scroll ↑↓ (vertical)",
        "scroll_h": "Scroll ←→ (horizontal)",
        "key":      "Tecla (segurar ao pressionar)",
    }
    _BY_LABEL: dict[str, str] = {v: k for k, v in _TYPE_OPTS.items()}

    def __init__(self, parent, direction_label: str, current: dict) -> None:
        self.result: dict | None = None
        self._capturing = False

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(f"Configurar — {direction_label}")
        self.dialog.geometry("400x200")
        self.dialog.resizable(False, False)
        self.dialog.after(80, self.dialog.grab_set)
        self.dialog.lift()

        cur_type = current.get("type", "none")
        self._cur_sens = str(int(float(current.get("sensitivity", 600))))
        self._cur_key  = current.get("key", "")

        # ── Tipo ──────────────────────────────────────────────────
        row_type = ctk.CTkFrame(self.dialog, fg_color="transparent")
        row_type.pack(fill="x", padx=20, pady=(16, 6))
        ctk.CTkLabel(row_type, text="Tipo:", width=90, anchor="w").pack(side="left")
        self._type_var = ctk.StringVar(value=self._TYPE_OPTS.get(cur_type, "— Nada"))
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
            btn_row, text="Cancelar", width=100,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            command=self.dialog.destroy,
        ).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="OK", width=100, command=self._on_ok).pack(side="left", padx=8)

        self.dialog.protocol("WM_DELETE_WINDOW", self.dialog.destroy)

    def _on_type_changed(self, label: str) -> None:
        for w in self._dyn.winfo_children():
            w.destroy()
        self._sens_entry = self._key_entry = None
        type_key = self._BY_LABEL.get(label, "none")

        if type_key in ("mouse_x", "mouse_y", "scroll_v", "scroll_h"):
            row = ctk.CTkFrame(self._dyn, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkLabel(row, text="Velocidade:", width=90, anchor="w").pack(side="left")
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
            ctk.CTkLabel(row, text="Tecla:", width=90, anchor="w").pack(side="left")
            self._key_entry = ctk.CTkEntry(row, width=100, justify="center")
            self._key_entry.insert(0, self._cur_key)
            self._key_entry.pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                row, text="Capturar", width=80,
                fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
                command=self._capture_key,
            ).pack(side="left")

    def _capture_key(self) -> None:
        if self._capturing:
            return
        self._capturing = True
        self._key_entry.delete(0, "end")
        self._key_entry.insert(0, "Aguardando…")

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
            if not key or key == "Aguardando…":
                self.result = {"type": "none"}
            else:
                self.result = {"type": "key", "key": key}
        else:
            self.result = {"type": "none"}
        self.dialog.destroy()


# ── Classe principal ───────────────────────────────────────────────────────

class App:
    """Classe principal que monta e gerencia a interface gráfica."""

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.geometry("660x660")
        self.root.minsize(580, 560)

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

        # ── Estado geral ──────────────────────────────────────────────
        self._is_listening    = False
        self._selected_btn_key: str | None = None

        # ── Estado analógico ──────────────────────────────────────────
        self._acc_x:  float = 0.0
        self._acc_y:  float = 0.0
        self._acc_sv: float = 0.0
        self._acc_sh: float = 0.0
        self._held_keys: set[str] = set()

        # Placeholders — populados em _build_analogicos_tab
        self._analog_enabled_var:   ctk.BooleanVar | None        = None
        self._left_stick_frame:     ctk.CTkFrame   | None        = None
        self._right_stick_frame:    ctk.CTkFrame   | None        = None
        self._stick_panels:         list[dict | None]            = [None, None]

        self.listener = ControllerListener(
            on_button_press=self._on_button_press,
            on_axes_update=self._on_axes_update,
        )

        self._build_ui()
        self._refresh_joystick_dropdown()
        self._refresh_preset_dropdown()
        self._render_bind_list()
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
        for stick in analog["sticks"]:
            stick.setdefault("deadzone", 0.15)
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
        self._build_tabview()

    def _build_header(self) -> None:
        frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color=("gray85", "gray17"))
        frame.grid(row=0, column=0, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            frame, text="JoyBind",
            font=ctk.CTkFont(size=24, weight="bold"), anchor="w",
        ).grid(row=0, column=0, padx=20, pady=(14, 2), sticky="w")
        ctk.CTkLabel(
            frame, text="Mapeador de Controle  →  Teclado / Mouse",
            font=ctk.CTkFont(size=11), text_color=("gray55", "gray60"), anchor="w",
        ).grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

    def _build_preset_bar(self) -> None:
        frame = ctk.CTkFrame(self.root)
        frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(10, 0))
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="Preset:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(14, 8), pady=10,
        )
        self._preset_var = ctk.StringVar()
        self._preset_combo = ctk.CTkComboBox(
            frame, variable=self._preset_var, state="readonly",
            command=self._on_preset_selected,
        )
        self._preset_combo.grid(row=0, column=1, padx=4, pady=10, sticky="ew")
        ctk.CTkButton(
            frame, text="Novo", width=70, command=self._new_preset,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
        ).grid(row=0, column=2, padx=(4, 0), pady=10)
        ctk.CTkButton(
            frame, text="Pasta...", width=80, command=self._change_presets_folder,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
        ).grid(row=0, column=3, padx=(4, 14), pady=10)

    def _build_controller_row(self) -> None:
        frame = ctk.CTkFrame(self.root)
        frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(10, 4))
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="Controle:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(14, 8), pady=12,
        )
        self._joystick_var = ctk.StringVar()
        self._joystick_combo = ctk.CTkComboBox(
            frame, variable=self._joystick_var, state="readonly",
        )
        self._joystick_combo.grid(row=0, column=1, padx=4, pady=12, sticky="ew")
        self._refresh_btn = ctk.CTkButton(
            frame, text="↻", width=38, command=self._refresh_joystick_dropdown,
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
        )
        self._refresh_btn.grid(row=0, column=2, padx=(4, 14), pady=12)

    def _build_status_row(self) -> None:
        frame = ctk.CTkFrame(self.root)
        frame.grid(row=3, column=0, sticky="ew", padx=12, pady=4)
        frame.grid_columnconfigure(1, weight=1)
        self._toggle_btn = ctk.CTkButton(
            frame, text="  Iniciar Escuta", width=170,
            fg_color=_COLOR_BTN_START, hover_color=_COLOR_BTN_START_HOVER,
            command=self._toggle_listener,
        )
        self._toggle_btn.grid(row=0, column=0, padx=14, pady=12)
        self._status_label = ctk.CTkLabel(
            frame, text="  Parado", text_color=_COLOR_STOPPED,
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
    # TabView
    # ──────────────────────────────────────────────────────────────

    def _build_tabview(self) -> None:
        self._tabview = ctk.CTkTabview(self.root)
        self._tabview.grid(row=4, column=0, sticky="nsew", padx=12, pady=4)
        self._tabview.add("Botões")
        self._tabview.add("Analógicos")
        self._build_botoes_tab(self._tabview.tab("Botões"))
        self._build_analogicos_tab(self._tabview.tab("Analógicos"))

    # ── Tab Botões ────────────────────────────────────────────────

    def _build_botoes_tab(self, tab: ctk.CTkFrame) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        col_hdr = ctk.CTkFrame(tab, fg_color=("gray75", "gray28"), corner_radius=6)
        col_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        for col_idx, (text, width) in enumerate([("Botão", 90), ("Tipo", 110), ("Ação", 300)]):
            ctk.CTkLabel(
                col_hdr, text=text, width=width,
                font=ctk.CTkFont(size=11, weight="bold"), anchor="w",
            ).grid(row=0, column=col_idx, padx=10, pady=5, sticky="w")

        self._bind_scroll = ctk.CTkScrollableFrame(tab, corner_radius=6)
        self._bind_scroll.grid(row=1, column=0, sticky="nsew", pady=(0, 4))
        self._bind_scroll.grid_columnconfigure(0, weight=1)
        self._bind_rows: list[dict] = []

        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkButton(
            btn_frame, text="+ Adicionar", width=130,
            command=self._open_add_dialog,
        ).pack(side="left", padx=(0, 6))
        self._edit_btn = ctk.CTkButton(
            btn_frame, text="Editar", width=110,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            state="disabled", command=self._open_edit_dialog,
        )
        self._edit_btn.pack(side="left", padx=6)
        self._del_btn = ctk.CTkButton(
            btn_frame, text="Remover", width=110,
            fg_color="#c0392b", hover_color="#a93226",
            state="disabled", command=self._delete_selected,
        )
        self._del_btn.pack(side="left", padx=6)

    # ── Tab Analógicos ────────────────────────────────────────────

    def _build_analogicos_tab(self, tab: ctk.CTkFrame) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Toggle
        analog_cfg = self.cfg.get("analog", {})
        self._analog_enabled_var = ctk.BooleanVar(value=analog_cfg.get("enabled", False))
        hdr = ctk.CTkFrame(tab, fg_color="transparent")
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(6, 4))
        ctk.CTkSwitch(
            hdr, text="Ativar analógico como mouse",
            variable=self._analog_enabled_var,
            command=self._save_analog_config,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", padx=4)

        # Painéis dos dois analógicos
        self._left_stick_frame  = ctk.CTkFrame(tab)
        self._right_stick_frame = ctk.CTkFrame(tab)
        self._left_stick_frame.grid(row=1,  column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))
        self._right_stick_frame.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))

    # ──────────────────────────────────────────────────────────────
    # Painel de analógico (cross pattern)
    # ──────────────────────────────────────────────────────────────

    def _build_stick_panel(self, parent: ctk.CTkFrame, stick_idx: int, stick_cfg: dict) -> dict:
        """Cria o conteúdo de um painel de analógico e retorna referências."""
        label    = stick_cfg.get("label", f"Analógico {stick_idx + 1}")
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
        axis_x_entry = _make_ax_entry("Eixo X:", stick_cfg.get("axis_x", default_ax))
        axis_y_entry = _make_ax_entry("Eixo Y:", stick_cfg.get("axis_y", default_ay))

        ctk.CTkLabel(ax_frame, text="DZ:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 2))
        dz_entry = ctk.CTkEntry(ax_frame, width=46, justify="center")
        dz_entry.insert(0, str(stick_cfg.get("deadzone", 0.15)))
        dz_entry.pack(side="left")

        # Cross pattern: ↑ ← ⊙ → ↓
        cross = ctk.CTkFrame(parent, fg_color="transparent")
        cross.pack(pady=(12, 4), expand=True)

        dir_bindings: dict[str, dict] = {
            d: dict(stick_cfg.get(d, {"type": "none"}))
            for d in ("up", "down", "left", "right")
        }

        BTN_W, BTN_H = 88, 54
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
            parent, text="Clique em uma direção para configurar",
            font=ctk.CTkFont(size=10), text_color=("gray55", "gray55"),
        ).pack(pady=(0, 8))

        # Auto-save nas entries de eixo
        for entry in (axis_x_entry, axis_y_entry, dz_entry):
            entry.bind("<FocusOut>", lambda e: self._save_analog_config())
            entry.bind("<Return>",   lambda e: self._save_analog_config())

        return {
            "axis_x_entry": axis_x_entry,
            "axis_y_entry": axis_y_entry,
            "dz_entry":     dz_entry,
            "dir_btns":     dir_btns,
            "dir_bindings": dir_bindings,
        }

    def _on_dir_btn_click(self, stick_idx: int, direction: str) -> None:
        panel = self._stick_panels[stick_idx]
        if panel is None:
            return

        dir_names = {
            "up":    "↑ Cima",
            "down":  "↓ Baixo",
            "left":  "← Esquerda",
            "right": "→ Direita",
        }
        stick_labels = ["Analógico Esquerdo", "Analógico Direito"]
        stick_label  = stick_labels[stick_idx] if stick_idx < len(stick_labels) else f"Analógico {stick_idx+1}"

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

    def _collect_analog_config(self) -> dict:
        sticks  = []
        labels  = ["Esquerdo", "Direito"]
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
            sticks.append({
                "label":    labels[i] if i < len(labels) else f"Analógico {i+1}",
                "axis_x":   ax,
                "axis_y":   ay,
                "deadzone": dz,
                **panel["dir_bindings"],
            })
        return {
            "enabled": bool(self._analog_enabled_var.get()) if self._analog_enabled_var else False,
            "sticks":  sticks,
        }

    def _save_analog_config(self) -> None:
        self.cfg["analog"] = self._collect_analog_config()
        self._save_current_preset()

    def _render_analog_config(self) -> None:
        """Reconstrói os dois painéis de analógico a partir do cfg atual."""
        if self._analog_enabled_var is None:
            return

        analog = self.cfg.get("analog", {})
        self._analog_enabled_var.set(analog.get("enabled", False))
        sticks = analog.get("sticks", [])
        defs   = _default_sticks()
        frames = [self._left_stick_frame, self._right_stick_frame]

        for i in range(2):
            frame     = frames[i]
            stick_cfg = sticks[i] if i < len(sticks) else defs[i]
            for widget in frame.winfo_children():
                widget.destroy()
            self._stick_panels[i] = self._build_stick_panel(frame, i, stick_cfg)

    # ──────────────────────────────────────────────────────────────
    # Processamento analógico — thread do controller
    # ──────────────────────────────────────────────────────────────

    def _on_axes_update(self, axis_values: list[float]) -> None:
        """
        Chamado a 60 Hz pela thread daemon do controller.
        Não toca em widgets — só pyautogui (thread-safe).

        Separação de responsabilidades:
          • Key bindings: sempre ativos enquanto o listener rodar.
          • Mouse/scroll:  só ativos quando "enabled" for True.
        """
        analog = self.cfg.get("analog", {})
        mouse_enabled = analog.get("enabled", False)

        if not mouse_enabled:
            self._acc_x = self._acc_y = self._acc_sv = self._acc_sh = 0.0

        dx = dy = sv = sh = 0.0
        new_held: set[str] = set()

        for stick in analog.get("sticks", []):
            try:
                ax_idx = int(stick.get("axis_x", 0))
                ay_idx = int(stick.get("axis_y", 1))
                dz     = float(stick.get("deadzone", 0.15))
            except (ValueError, TypeError):
                continue
            if ax_idx >= len(axis_values) or ay_idx >= len(axis_values):
                continue

            sx = _apply_deadzone(axis_values[ax_idx], dz)
            sy = _apply_deadzone(axis_values[ay_idx], dz)

            # Papéis contínuos (mouse/scroll): só quando enabled
            if mouse_enabled:
                for scaled, neg_b, pos_b in [
                    (sx, stick.get("left", {"type":"none"}), stick.get("right", {"type":"none"})),
                    (sy, stick.get("up",   {"type":"none"}), stick.get("down",  {"type":"none"})),
                ]:
                    for binding in (pos_b, neg_b):
                        btype = binding.get("type", "none")
                        if btype in ("mouse_x", "mouse_y", "scroll_v", "scroll_h"):
                            try:
                                sens = max(0.1, float(binding.get("sensitivity", 600)))
                            except (ValueError, TypeError):
                                sens = 600.0
                            delta = scaled * sens / 60.0
                            if   btype == "mouse_x":  dx += delta
                            elif btype == "mouse_y":  dy += delta
                            elif btype == "scroll_v": sv += delta
                            elif btype == "scroll_h": sh += delta
                            break  # um único role por eixo

            # Teclas por direção: sempre ativas (independente de mouse_enabled)
            for direction, axis_val in [
                ("up",    -sy),   # Y negativo = cima
                ("down",   sy),   # Y positivo = baixo
                ("left",  -sx),   # X negativo = esquerda
                ("right",  sx),   # X positivo = direita
            ]:
                b = stick.get(direction, {"type": "none"})
                if b.get("type") == "key" and b.get("key") and axis_val > 0:
                    new_held.add(b["key"])

        # Mantém/solta combos de tecla
        for key in self._held_keys - new_held:
            actions.key_combo_up(key)
        for key in new_held - self._held_keys:
            actions.key_combo_down(key)
        self._held_keys = new_held

        # Sub-pixel + movimento (só quando mouse_enabled)
        if mouse_enabled:
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

    def _release_all_held_keys(self) -> None:
        for key in list(self._held_keys):
            try:
                actions.key_combo_up(key)
            except Exception:
                pass
        self._held_keys.clear()

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
        self._render_bind_list()
        self._render_analog_config()

    def _new_preset(self) -> None:
        dlg  = ctk.CTkInputDialog(text="Nome do novo preset:", title="Novo Preset")
        name = dlg.get_input()
        if not name:
            return
        safe = _sanitize_filename(name)
        if not safe:
            messagebox.showerror("Nome inválido", "O nome contém apenas caracteres inválidos.", parent=self.root)
            return
        path = self._presets_dir / f"{safe}.json"
        if path.exists():
            if not messagebox.askyesno("Preset já existe", f"Substituir '{safe}'?", parent=self.root):
                return
        cfg: dict = {"binds": {}, "analog": {"enabled": False, "sticks": _default_sticks()}}
        if presets.save_preset(path, cfg):
            self.cfg = cfg
            self._current_preset_path = path
            self._settings["last_preset"] = str(path)
            presets.save_settings(self._settings)
            self._refresh_preset_dropdown()
            self.root.title(f"JoyBind — {safe}")
            self._render_bind_list()
            self._render_analog_config()

    def _change_presets_folder(self) -> None:
        folder = filedialog.askdirectory(
            title="Escolher pasta de presets",
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
            self._joystick_combo.configure(values=["Nenhum controle encontrado"])
            self._joystick_var.set("Nenhum controle encontrado")

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
            messagebox.showerror("Erro ao iniciar", err_msg)
            return

        self._is_listening = True
        self._toggle_btn.configure(
            text="  Pausar Escuta",
            fg_color=_COLOR_BTN_STOP, hover_color=_COLOR_BTN_STOP_HOVER,
        )
        self._status_label.configure(text="  Ativo", text_color=_COLOR_ACTIVE)
        self._refresh_btn.configure(state="disabled")

    def _stop_listener(self) -> None:
        self.listener.stop()
        self._is_listening = False
        self._acc_x = self._acc_y = self._acc_sv = self._acc_sh = 0.0
        self._release_all_held_keys()
        self._toggle_btn.configure(
            text="  Iniciar Escuta",
            fg_color=_COLOR_BTN_START, hover_color=_COLOR_BTN_START_HOVER,
        )
        self._status_label.configure(text="  Parado", text_color=_COLOR_STOPPED)
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
                actions.execute_keyboard(bind["key"])
                label_text = f"BTN {button}  →  {bind['key']}"
            elif btype == "sequence":
                n = len(bind.get("steps", []))
                actions.execute_sequence(bind["steps"])
                label_text = f"BTN {button}  →  sequência ({n} passo{'s' if n != 1 else ''})"
            elif btype == "mouse_combo":
                actions.execute_mouse_combo(bind["x"], bind["y"])
                label_text = f"BTN {button}  →  mouse ({bind['x']}, {bind['y']})"
            else:
                return
            self.root.after(0, lambda t=label_text: self._last_action_label.configure(text=t))

        threading.Thread(target=run, daemon=True, name=f"Action-BTN{button}").start()

    # ──────────────────────────────────────────────────────────────
    # Lista de binds (Tab Botões)
    # ──────────────────────────────────────────────────────────────

    def _render_bind_list(self) -> None:
        for widget in self._bind_scroll.winfo_children():
            widget.destroy()
        self._bind_rows.clear()
        self._selected_btn_key = None
        self._update_row_buttons()

        binds = self.cfg["binds"]
        if not binds:
            ctk.CTkLabel(
                self._bind_scroll,
                text='Nenhum mapeamento configurado.\nClique em "+ Adicionar" para começar.',
                font=ctk.CTkFont(size=12), text_color=("gray55", "gray55"), justify="center",
            ).pack(pady=30)
            return

        for btn_key in sorted(binds, key=lambda k: int(k)):
            self._add_bind_row(btn_key, binds[btn_key])

    def _add_bind_row(self, btn_key: str, bind: dict) -> None:
        type_label = _TYPE_LABELS.get(bind["type"], bind["type"].upper())
        type_color = _TYPE_COLORS.get(bind["type"], "white")
        btype = bind["type"]
        if   btype == "keyboard": action_text = bind.get("key", "?")
        elif btype == "sequence":
            n = len(bind.get("steps", []))
            action_text = f"{n} passo{'s' if n != 1 else ''}"
        else:
            action_text = f"X: {bind.get('x', 0)}    Y: {bind.get('y', 0)}"

        row = ctk.CTkFrame(
            self._bind_scroll, corner_radius=6,
            fg_color=("gray88", "gray22"), cursor="hand2",
        )
        row.pack(fill="x", padx=4, pady=2)
        lbl_btn = ctk.CTkLabel(row, text=f"BTN {btn_key}", width=90, anchor="w")
        lbl_btn.pack(side="left", padx=(12, 0), pady=8)
        lbl_type = ctk.CTkLabel(
            row, text=type_label, width=110, anchor="w",
            text_color=type_color, font=ctk.CTkFont(size=11, weight="bold"),
        )
        lbl_type.pack(side="left", pady=8)
        lbl_action = ctk.CTkLabel(row, text=action_text, anchor="w")
        lbl_action.pack(side="left", pady=8, fill="x", expand=True)

        for widget in (row, lbl_btn, lbl_type, lbl_action):
            widget.bind("<Button-1>",        lambda e, k=btn_key: self._select_row(k))
            widget.bind("<Double-Button-1>", lambda e, k=btn_key: self._open_edit_dialog(k))
        self._bind_rows.append({"key": btn_key, "frame": row})

    def _select_row(self, btn_key: str) -> None:
        _N = ("gray88", "gray22")
        _S = ("gray70", "gray35")
        for row in self._bind_rows:
            row["frame"].configure(fg_color=_S if row["key"] == btn_key else _N)
        self._selected_btn_key = btn_key
        self._update_row_buttons()

    def _update_row_buttons(self) -> None:
        state = "normal" if self._selected_btn_key else "disabled"
        self._edit_btn.configure(state=state)
        self._del_btn.configure(state=state)

    # ──────────────────────────────────────────────────────────────
    # Diálogos CRUD de binds
    # ──────────────────────────────────────────────────────────────

    def _open_add_dialog(self) -> None:
        dlg = BindDialog(
            self.root, title="Novo Mapeamento",
            existing_keys=list(self.cfg["binds"].keys()),
        )
        self.root.wait_window(dlg.dialog)
        if dlg.result:
            self.cfg["binds"][dlg.result["button"]] = dlg.result["bind"]
            self._save_current_preset()
            self._render_bind_list()

    def _open_edit_dialog(self, force_key: str | None = None) -> None:
        key  = force_key or self._selected_btn_key
        bind = self.cfg["binds"].get(key) if key else None
        if not key or not bind:
            return
        dlg = BindDialog(
            self.root, title="Editar Mapeamento",
            edit_key=key, edit_bind=bind,
            existing_keys=list(self.cfg["binds"].keys()),
        )
        self.root.wait_window(dlg.dialog)
        if dlg.result:
            if key in self.cfg["binds"]:
                del self.cfg["binds"][key]
            self.cfg["binds"][dlg.result["button"]] = dlg.result["bind"]
            self._save_current_preset()
            self._render_bind_list()

    def _delete_selected(self) -> None:
        if not self._selected_btn_key:
            return
        if messagebox.askyesno(
            "Confirmar remoção",
            f"Remover o mapeamento do BTN {self._selected_btn_key}?",
            parent=self.root,
        ):
            del self.cfg["binds"][self._selected_btn_key]
            self._save_current_preset()
            self._selected_btn_key = None
            self._render_bind_list()

    # ──────────────────────────────────────────────────────────────
    # Encerramento
    # ──────────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        try:
            self._save_analog_config()
        except Exception:
            pass
        self._release_all_held_keys()
        if self._is_listening:
            self.listener.stop()
        pygame.quit()
