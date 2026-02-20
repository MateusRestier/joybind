"""
gui/app.py — Janela principal do JoyBind.

Layout (de cima para baixo):
  ┌─────────────────────────────────────────┐
  │ Header  (título + subtítulo)            │
  ├─────────────────────────────────────────┤
  │ Seleção de controle  [dropdown] [↻]     │
  ├─────────────────────────────────────────┤
  │ [▶ Iniciar Escuta]   ● Status           │
  ├─────────────────────────────────────────┤
  │ Lista de Mapeamentos (scrollable)       │
  │   Botão │ Tipo    │ Ação                │
  │   ───────────────────────────           │
  │   BTN 0 │ TECLADO │ enter               │
  │   BTN 1 │ MOUSE   │ X:500  Y:300        │
  ├─────────────────────────────────────────┤
  │ [+ Adicionar]  [Editar]  [Remover]      │
  └─────────────────────────────────────────┘

Thread safety:
  • O callback on_button_press é chamado da thread do controller.
  • Toda interação com widgets tkinter é feita via root.after(0, ...) para
    despachar para a thread principal, evitando race conditions.
"""
import threading
import pygame
import customtkinter as ctk
from tkinter import messagebox

import config
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
    "keyboard":   "TECLADO",
    "sequence":   "SEQUÊNCIA",
    "mouse_combo": "MOUSE",   # legado
}
_TYPE_COLORS: dict[str, str] = {
    "keyboard":   "#3498db",
    "sequence":   "#e67e22",
    "mouse_combo": "#9b59b6",  # legado
}


class App:
    """Classe principal que monta e gerencia a interface gráfica."""

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.title("JoyBind")
        self.root.geometry("640x560")
        self.root.minsize(560, 480)

        # Carrega configuração persistida em disco
        self.cfg = config.load()

        # Estado interno
        self._is_listening = False
        self._selected_btn_key: str | None = None  # Chave da linha selecionada na lista

        # Instancia o listener (ainda não inicia a escuta)
        self.listener = ControllerListener(on_button_press=self._on_button_press)

        self._build_ui()
        self._refresh_joystick_dropdown()
        self._render_bind_list()

    # ──────────────────────────────────────────────────────────────
    # Construção da Interface
    # ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        # Linha 3 (lista de binds) se expande verticalmente
        self.root.grid_rowconfigure(3, weight=1)

        self._build_header()
        self._build_controller_row()
        self._build_status_row()
        self._build_bind_list()
        self._build_action_buttons()

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

    def _build_controller_row(self) -> None:
        frame = ctk.CTkFrame(self.root)
        frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(10, 4))
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

        # Botão de refresh — desabilitado enquanto o listener estiver ativo
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
        frame.grid(row=2, column=0, sticky="ew", padx=12, pady=4)
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

        # Último botão disparado — feedback visual não-intrusivo
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
        outer.grid(row=3, column=0, sticky="nsew", padx=12, pady=4)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            outer,
            text="Mapeamentos",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")

        # Cabeçalho das colunas
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

        # Área rolável para as linhas de bind
        self._bind_scroll = ctk.CTkScrollableFrame(outer, corner_radius=6)
        self._bind_scroll.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._bind_scroll.grid_columnconfigure(0, weight=1)

        # Referências às linhas renderizadas: [{key, frame}, ...]
        self._bind_rows: list[dict] = []

    def _build_action_buttons(self) -> None:
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        frame.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 14))

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
    # Dropdown de joysticks
    # ──────────────────────────────────────────────────────────────

    def _refresh_joystick_dropdown(self) -> None:
        """Reenumera os controles conectados e atualiza o dropdown."""
        if self._is_listening:
            return  # Não re-enumera enquanto está escutando (invalida o joystick aberto)

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
        # Descobre o índice do joystick selecionado
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
        self._refresh_btn.configure(state="disabled")  # Protege re-enumeração

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

        # Executa ação em thread própria (pyautogui pode bloquear)
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
            # Atualiza o rótulo de feedback na GUI via thread principal
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

        # Coluna Botão
        lbl_btn = ctk.CTkLabel(row, text=f"BTN {btn_key}", width=90, anchor="w")
        lbl_btn.pack(side="left", padx=(12, 0), pady=8)

        # Coluna Tipo (colorida)
        lbl_type = ctk.CTkLabel(
            row,
            text=type_label,
            width=110,
            anchor="w",
            text_color=type_color,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        lbl_type.pack(side="left", padx=0, pady=8)

        # Coluna Ação
        lbl_action = ctk.CTkLabel(row, text=action_text, anchor="w")
        lbl_action.pack(side="left", padx=0, pady=8, fill="x", expand=True)

        # Registra clique em todos os widgets da linha
        for widget in (row, lbl_btn, lbl_type, lbl_action):
            widget.bind("<Button-1>", lambda e, k=btn_key: self._select_row(k))
            widget.bind("<Double-Button-1>", lambda e, k=btn_key: self._open_edit_dialog(k))

        self._bind_rows.append({"key": btn_key, "frame": row})

    def _select_row(self, btn_key: str) -> None:
        """Marca uma linha como selecionada e atualiza os botões de ação."""
        _NORMAL = ("gray88", "gray22")
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
        self.root.wait_window(dlg.dialog)  # Bloqueia até o diálogo fechar

        if dlg.result:
            btn_key = dlg.result["button"]
            self.cfg["binds"][btn_key] = dlg.result["bind"]
            config.save(self.cfg)
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
            # Remove a chave antiga caso o número de botão tenha mudado
            if key in self.cfg["binds"]:
                del self.cfg["binds"][key]
            new_key = dlg.result["button"]
            self.cfg["binds"][new_key] = dlg.result["bind"]
            config.save(self.cfg)
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
            config.save(self.cfg)
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
