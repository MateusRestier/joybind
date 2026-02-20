"""
gui/app.py — Janela principal do JoyBind.

Layout (de cima para baixo):
  ┌─────────────────────────────────────────┐
  │ Header  (título + subtítulo)            │
  ├─────────────────────────────────────────┤
  │ Preset  [dropdown] [Novo] [Pasta...]    │
  ├─────────────────────────────────────────┤
  │ Seleção de controle  [dropdown] [↻]     │
  ├─────────────────────────────────────────┤
  │ [▶ Iniciar Escuta]   ● Status           │
  ├─────────────────────────────────────────┤
  │ Lista de Mapeamentos (scrollable)       │
  │   Botão │ Tipo    │ Ação                │
  │   ───────────────────────────           │
  │   BTN 0 │ TECLADO │ enter               │
  ├─────────────────────────────────────────┤
  │ [+ Adicionar]  [Editar]  [Remover]      │
  └─────────────────────────────────────────┘

Thread safety:
  • O callback on_button_press é chamado da thread do controller.
  • Toda interação com widgets tkinter é feita via root.after(0, ...) para
    despachar para a thread principal, evitando race conditions.
"""
import threading
from pathlib import Path
from tkinter import messagebox, filedialog

import pygame
import customtkinter as ctk

import presets
import actions
from controller import ControllerListener
from gui.bind_dialog import BindDialog

# Cores de status
_COLOR_ACTIVE = "#2ecc71"    # Verde
_COLOR_STOPPED = "#e74c3c"   # Vermelho
_COLOR_BTN_START = "#2ecc71"
_COLOR_BTN_START_HOVER = "#27ae60"
_COLOR_BTN_STOP = "#e67e22"
_COLOR_BTN_STOP_HOVER = "#d35400"

# Rótulos exibidos na lista para cada tipo de bind
_TYPE_LABELS: dict[str, str] = {
    "keyboard":    "TECLADO",
    "sequence":    "SEQUÊNCIA",
    "mouse_combo": "MOUSE",   # legado
}
_TYPE_COLORS: dict[str, str] = {
    "keyboard":    "#3498db",
    "sequence":    "#e67e22",
    "mouse_combo": "#9b59b6",  # legado
}


def _sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos para nomes de arquivo no Windows/Linux/macOS."""
    return "".join(c for c in name if c not in r'\/:*?"<>|').strip()


class App:
    """Classe principal que monta e gerencia a interface gráfica."""

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.geometry("640x620")
        self.root.minsize(560, 520)

        # ── Presets ──────────────────────────────────────────────────
        self._settings = presets.load_settings()
        self._presets_dir = Path(self._settings["presets_dir"])
        self._current_preset_path: Path | None = None

        self.cfg = self._load_initial_preset()

        title = (
            f"JoyBind — {self._current_preset_path.stem}"
            if self._current_preset_path
            else "JoyBind"
        )
        self.root.title(title)

        # ── Estado interno ────────────────────────────────────────────
        self._is_listening = False
        self._selected_btn_key: str | None = None

        # Instancia o listener (ainda não inicia a escuta)
        self.listener = ControllerListener(on_button_press=self._on_button_press)

        self._build_ui()
        self._refresh_joystick_dropdown()
        self._refresh_preset_dropdown()
        self._render_bind_list()

    # ──────────────────────────────────────────────────────────────
    # Preset inicial
    # ──────────────────────────────────────────────────────────────

    def _load_initial_preset(self) -> dict:
        """
        Determina e carrega o preset inicial.
        Prioridade: último preset salvo → primeiro da pasta → cria 'default'.
        """
        last = self._settings.get("last_preset")
        if last:
            path = Path(last)
            if path.exists():
                self._current_preset_path = path
                self._presets_dir = path.parent
                return presets.load_preset(path)

        preset_list = presets.list_presets(self._presets_dir)
        if preset_list:
            self._current_preset_path = preset_list[0]
            return presets.load_preset(preset_list[0])

        # Primeira execução — cria preset padrão vazio
        default_path = self._presets_dir / "default.json"
        cfg: dict = {"binds": {}}
        presets.save_preset(default_path, cfg)
        self._current_preset_path = default_path
        self._settings["last_preset"] = str(default_path)
        presets.save_settings(self._settings)
        return cfg

    # ──────────────────────────────────────────────────────────────
    # Construção da Interface
    # ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        # Linha 4 (lista de binds) se expande verticalmente
        self.root.grid_rowconfigure(4, weight=1)

        self._build_header()          # row 0
        self._build_preset_bar()      # row 1  ← novo
        self._build_controller_row()  # row 2
        self._build_status_row()      # row 3
        self._build_bind_list()       # row 4
        self._build_action_buttons()  # row 5

    def _build_header(self) -> None:
        frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color=("gray85", "gray17"))
        frame.grid(row=0, column=0, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text="JoyBind",
            font=ctk.CTkFont(size=24, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=20, pady=(14, 2), sticky="w")

        ctk.CTkLabel(
            frame,
            text="Mapeador de Controle  →  Teclado / Mouse",
            font=ctk.CTkFont(size=11),
            text_color=("gray55", "gray60"),
            anchor="w",
        ).grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

    def _build_preset_bar(self) -> None:
        frame = ctk.CTkFrame(self.root)
        frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(10, 0))
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            frame, text="Preset:", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, padx=(14, 8), pady=10)

        self._preset_var = ctk.StringVar()
        self._preset_combo = ctk.CTkComboBox(
            frame,
            variable=self._preset_var,
            state="readonly",
            command=self._on_preset_selected,
        )
        self._preset_combo.grid(row=0, column=1, padx=4, pady=10, sticky="ew")

        ctk.CTkButton(
            frame,
            text="Novo",
            width=70,
            command=self._new_preset,
            fg_color=("gray65", "gray30"),
            hover_color=("gray55", "gray40"),
        ).grid(row=0, column=2, padx=(4, 0), pady=10)

        ctk.CTkButton(
            frame,
            text="Pasta...",
            width=80,
            command=self._change_presets_folder,
            fg_color=("gray65", "gray30"),
            hover_color=("gray55", "gray40"),
        ).grid(row=0, column=3, padx=(4, 14), pady=10)

    def _build_controller_row(self) -> None:
        frame = ctk.CTkFrame(self.root)
        frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(10, 4))
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Controle:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(14, 8), pady=12
        )

        self._joystick_var = ctk.StringVar()
        self._joystick_combo = ctk.CTkComboBox(
            frame,
            variable=self._joystick_var,
            state="readonly",
        )
        self._joystick_combo.grid(row=0, column=1, padx=4, pady=12, sticky="ew")

        self._refresh_btn = ctk.CTkButton(
            frame,
            text="↻",
            width=38,
            command=self._refresh_joystick_dropdown,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
        )
        self._refresh_btn.grid(row=0, column=2, padx=(4, 14), pady=12)

    def _build_status_row(self) -> None:
        frame = ctk.CTkFrame(self.root)
        frame.grid(row=3, column=0, sticky="ew", padx=12, pady=4)
        frame.grid_columnconfigure(1, weight=1)

        self._toggle_btn = ctk.CTkButton(
            frame,
            text="  Iniciar Escuta",
            width=170,
            fg_color=_COLOR_BTN_START,
            hover_color=_COLOR_BTN_START_HOVER,
            command=self._toggle_listener,
        )
        self._toggle_btn.grid(row=0, column=0, padx=14, pady=12)

        self._status_label = ctk.CTkLabel(
            frame,
            text="  Parado",
            text_color=_COLOR_STOPPED,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._status_label.grid(row=0, column=1, padx=8, pady=12, sticky="w")

        self._last_action_label = ctk.CTkLabel(
            frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=("gray55", "gray55"),
            anchor="e",
        )
        self._last_action_label.grid(row=0, column=2, padx=14, pady=12, sticky="e")
        frame.grid_columnconfigure(2, weight=1)

    def _build_bind_list(self) -> None:
        outer = ctk.CTkFrame(self.root)
        outer.grid(row=4, column=0, sticky="nsew", padx=12, pady=4)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            outer,
            text="Mapeamentos",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")

        col_hdr = ctk.CTkFrame(outer, fg_color=("gray75", "gray28"), corner_radius=6)
        col_hdr.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 2))

        for col_idx, (text, width) in enumerate([("Botão", 90), ("Tipo", 110), ("Ação", 300)]):
            ctk.CTkLabel(
                col_hdr,
                text=text,
                width=width,
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w",
            ).grid(row=0, column=col_idx, padx=10, pady=5, sticky="w")

        self._bind_scroll = ctk.CTkScrollableFrame(outer, corner_radius=6)
        self._bind_scroll.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._bind_scroll.grid_columnconfigure(0, weight=1)

        self._bind_rows: list[dict] = []

    def _build_action_buttons(self) -> None:
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        frame.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 14))

        ctk.CTkButton(
            frame,
            text="+ Adicionar",
            width=130,
            command=self._open_add_dialog,
        ).pack(side="left", padx=(0, 6))

        self._edit_btn = ctk.CTkButton(
            frame,
            text="Editar",
            width=110,
            fg_color=("gray65", "gray30"),
            hover_color=("gray55", "gray40"),
            state="disabled",
            command=self._open_edit_dialog,
        )
        self._edit_btn.pack(side="left", padx=6)

        self._del_btn = ctk.CTkButton(
            frame,
            text="Remover",
            width=110,
            fg_color="#c0392b",
            hover_color="#a93226",
            state="disabled",
            command=self._delete_selected,
        )
        self._del_btn.pack(side="left", padx=6)

    # ──────────────────────────────────────────────────────────────
    # Gerenciamento de Presets
    # ──────────────────────────────────────────────────────────────

    def _refresh_preset_dropdown(self) -> None:
        """Atualiza o dropdown com os presets disponíveis na pasta atual."""
        preset_list = presets.list_presets(self._presets_dir)
        names = [p.stem for p in preset_list]
        if names:
            self._preset_combo.configure(values=names)
            current_stem = (
                self._current_preset_path.stem if self._current_preset_path else names[0]
            )
            self._preset_var.set(current_stem if current_stem in names else names[0])
        else:
            self._preset_combo.configure(values=["—"])
            self._preset_var.set("—")

    def _on_preset_selected(self, name: str) -> None:
        """Chamado pelo CTkComboBox quando o usuário seleciona um item."""
        if not name or name == "—":
            return
        # Evita recarregar o preset que já está ativo
        if self._current_preset_path and self._current_preset_path.stem == name:
            return
        path = self._presets_dir / f"{name}.json"
        if path.exists():
            self._apply_preset(path)

    def _apply_preset(self, path: Path) -> None:
        """Carrega um arquivo de preset e atualiza toda a interface."""
        self.cfg = presets.load_preset(path)
        self._current_preset_path = path
        self.root.title(f"JoyBind — {path.stem}")
        self._settings["last_preset"] = str(path)
        presets.save_settings(self._settings)
        self._render_bind_list()

    def _new_preset(self) -> None:
        """Cria um novo preset vazio após solicitar um nome ao usuário."""
        dlg = ctk.CTkInputDialog(text="Nome do novo preset:", title="Novo Preset")
        name = dlg.get_input()
        if not name:
            return

        safe = _sanitize_filename(name)
        if not safe:
            messagebox.showerror(
                "Nome inválido",
                "O nome contém apenas caracteres inválidos.",
                parent=self.root,
            )
            return

        path = self._presets_dir / f"{safe}.json"
        if path.exists():
            if not messagebox.askyesno(
                "Preset já existe",
                f"O preset '{safe}' já existe. Deseja substituí-lo?",
                parent=self.root,
            ):
                return

        cfg: dict = {"binds": {}}
        if presets.save_preset(path, cfg):
            self.cfg = cfg
            self._current_preset_path = path
            self._settings["last_preset"] = str(path)
            presets.save_settings(self._settings)
            self._refresh_preset_dropdown()
            self.root.title(f"JoyBind — {safe}")
            self._render_bind_list()

    def _change_presets_folder(self) -> None:
        """Permite ao usuário escolher uma pasta diferente para os presets."""
        folder = filedialog.askdirectory(
            title="Escolher pasta de presets",
            initialdir=str(self._presets_dir),
            parent=self.root,
        )
        if not folder:
            return

        self._presets_dir = Path(folder)
        self._settings["presets_dir"] = str(self._presets_dir)

        # Se o preset atual já está na nova pasta, apenas atualiza o dropdown
        if (
            self._current_preset_path
            and self._current_preset_path.parent == self._presets_dir
        ):
            presets.save_settings(self._settings)
            self._refresh_preset_dropdown()
            return

        # Caso contrário: carrega o primeiro preset disponível ou cria 'default'
        preset_list = presets.list_presets(self._presets_dir)
        if preset_list:
            self._settings["last_preset"] = str(preset_list[0])
            presets.save_settings(self._settings)
            self._apply_preset(preset_list[0])
        else:
            default_path = self._presets_dir / "default.json"
            cfg: dict = {"binds": {}}
            presets.save_preset(default_path, cfg)
            self._settings["last_preset"] = str(default_path)
            presets.save_settings(self._settings)
            self._apply_preset(default_path)

        self._refresh_preset_dropdown()

    def _save_current_preset(self) -> None:
        """Persiste o preset ativo em disco."""
        if self._current_preset_path is not None:
            presets.save_preset(self._current_preset_path, self.cfg)

    # ──────────────────────────────────────────────────────────────
    # Dropdown de joysticks
    # ──────────────────────────────────────────────────────────────

    def _refresh_joystick_dropdown(self) -> None:
        """Reenumera os controles conectados e atualiza o dropdown."""
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
        names = ControllerListener.get_joystick_names()
        selected = self._joystick_var.get()
        idx = names.index(selected) if selected in names else 0
        self.listener.set_joystick_index(idx)

        ok, err_msg = self.listener.start()
        if not ok:
            messagebox.showerror("Erro ao iniciar", err_msg)
            return

        self._is_listening = True
        self._toggle_btn.configure(
            text="  Pausar Escuta",
            fg_color=_COLOR_BTN_STOP,
            hover_color=_COLOR_BTN_STOP_HOVER,
        )
        self._status_label.configure(text="  Ativo", text_color=_COLOR_ACTIVE)
        self._refresh_btn.configure(state="disabled")

    def _stop_listener(self) -> None:
        self.listener.stop()
        self._is_listening = False
        self._toggle_btn.configure(
            text="  Iniciar Escuta",
            fg_color=_COLOR_BTN_START,
            hover_color=_COLOR_BTN_START_HOVER,
        )
        self._status_label.configure(text="  Parado", text_color=_COLOR_STOPPED)
        self._refresh_btn.configure(state="normal")

    # ──────────────────────────────────────────────────────────────
    # Despacho de ações (chamado da thread do controller)
    # ──────────────────────────────────────────────────────────────

    def _on_button_press(self, button: int) -> None:
        """
        Recebido da thread daemon do controller.
        NÃO manipula widgets diretamente — usa root.after() para thread safety.
        Lança a ação mapeada em uma thread separada para não bloquear o controller.
        """
        key = str(button)
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
            elif btype == "mouse_combo":  # compatibilidade com configs antigas
                actions.execute_mouse_combo(bind["x"], bind["y"])
                label_text = f"BTN {button}  →  mouse ({bind['x']}, {bind['y']})"
            else:
                return
            self.root.after(0, lambda t=label_text: self._last_action_label.configure(text=t))

        threading.Thread(target=run, daemon=True, name=f"Action-BTN{button}").start()

    # ──────────────────────────────────────────────────────────────
    # Renderização da lista de binds
    # ──────────────────────────────────────────────────────────────

    def _render_bind_list(self) -> None:
        """Destrói e reconstrói todas as linhas do bind list."""
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
                font=ctk.CTkFont(size=12),
                text_color=("gray55", "gray55"),
                justify="center",
            ).pack(pady=30)
            return

        for btn_key in sorted(binds, key=lambda k: int(k)):
            self._add_bind_row(btn_key, binds[btn_key])

    def _add_bind_row(self, btn_key: str, bind: dict) -> None:
        """Cria e adiciona uma linha de bind ao scroll frame."""
        type_label = _TYPE_LABELS.get(bind["type"], bind["type"].upper())
        type_color = _TYPE_COLORS.get(bind["type"], "white")

        btype = bind["type"]
        if btype == "keyboard":
            action_text = bind.get("key", "?")
        elif btype == "sequence":
            steps = bind.get("steps", [])
            n = len(steps)
            action_text = f"{n} passo{'s' if n != 1 else ''}"
        else:  # mouse_combo legado
            action_text = f"X: {bind.get('x', 0)}    Y: {bind.get('y', 0)}"

        row = ctk.CTkFrame(
            self._bind_scroll,
            corner_radius=6,
            fg_color=("gray88", "gray22"),
            cursor="hand2",
        )
        row.pack(fill="x", padx=4, pady=2)

        lbl_btn = ctk.CTkLabel(row, text=f"BTN {btn_key}", width=90, anchor="w")
        lbl_btn.pack(side="left", padx=(12, 0), pady=8)

        lbl_type = ctk.CTkLabel(
            row,
            text=type_label,
            width=110,
            anchor="w",
            text_color=type_color,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        lbl_type.pack(side="left", padx=0, pady=8)

        lbl_action = ctk.CTkLabel(row, text=action_text, anchor="w")
        lbl_action.pack(side="left", padx=0, pady=8, fill="x", expand=True)

        for widget in (row, lbl_btn, lbl_type, lbl_action):
            widget.bind("<Button-1>", lambda e, k=btn_key: self._select_row(k))
            widget.bind("<Double-Button-1>", lambda e, k=btn_key: self._open_edit_dialog(k))

        self._bind_rows.append({"key": btn_key, "frame": row})

    def _select_row(self, btn_key: str) -> None:
        """Marca uma linha como selecionada e atualiza os botões de ação."""
        _NORMAL   = ("gray88", "gray22")
        _SELECTED = ("gray70", "gray35")

        for row in self._bind_rows:
            color = _SELECTED if row["key"] == btn_key else _NORMAL
            row["frame"].configure(fg_color=color)

        self._selected_btn_key = btn_key
        self._update_row_buttons()

    def _update_row_buttons(self) -> None:
        """Habilita/desabilita os botões Editar e Remover conforme seleção."""
        state = "normal" if self._selected_btn_key else "disabled"
        self._edit_btn.configure(state=state)
        self._del_btn.configure(state=state)

    # ──────────────────────────────────────────────────────────────
    # Diálogos de CRUD de binds
    # ──────────────────────────────────────────────────────────────

    def _open_add_dialog(self) -> None:
        dlg = BindDialog(
            self.root,
            title="Novo Mapeamento",
            existing_keys=list(self.cfg["binds"].keys()),
        )
        self.root.wait_window(dlg.dialog)

        if dlg.result:
            btn_key = dlg.result["button"]
            self.cfg["binds"][btn_key] = dlg.result["bind"]
            self._save_current_preset()
            self._render_bind_list()

    def _open_edit_dialog(self, force_key: str | None = None) -> None:
        key = force_key or self._selected_btn_key
        if not key:
            return
        bind = self.cfg["binds"].get(key)
        if not bind:
            return

        dlg = BindDialog(
            self.root,
            title="Editar Mapeamento",
            edit_key=key,
            edit_bind=bind,
            existing_keys=list(self.cfg["binds"].keys()),
        )
        self.root.wait_window(dlg.dialog)

        if dlg.result:
            if key in self.cfg["binds"]:
                del self.cfg["binds"][key]
            new_key = dlg.result["button"]
            self.cfg["binds"][new_key] = dlg.result["bind"]
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
        """Chamado pelo handler WM_DELETE_WINDOW antes de destruir a janela."""
        if self._is_listening:
            self.listener.stop()
        pygame.quit()
