"""
gui/bind_dialog.py — Diálogo modal para adicionar ou editar um mapeamento.

Tipos de bind:
  keyboard  → Pressiona uma tecla ao detectar o botão do controle.
  sequence  → Executa uma sequência de ações definidas em "linha do tempo".

Fluxo:
  1. Usuário informa o Nº do botão (digitando ou capturando via controle).
  2. Escolhe o tipo: Teclado ou Sequência de Ações.
  3. Preenche os parâmetros.
  4. Clica em Salvar → self.result é preenchido e o diálogo fecha.

A janela pai acessa `dlg.result` após `root.wait_window(dlg.dialog)`.
"""
import time
import threading
import pygame
import pyautogui
import customtkinter as ctk
from tkinter import messagebox


# ── Normalização de teclas pynput → pyautogui ─────────────────────────────────

_PYNPUT_TO_PYAUTOGUI: dict[str, str] = {
    "shift_l": "shiftleft",    "shift_r": "shiftright",
    "ctrl_l":  "ctrlleft",     "ctrl_r":  "ctrlright",
    "alt_l":   "altleft",      "alt_r":   "altright",
    "alt_gr":  "altright",
    "cmd": "win", "cmd_l": "win", "cmd_r": "win",
    "page_up": "pageup",        "page_down": "pagedown",
    "num_lock": "numlock",      "caps_lock": "capslock",
    "scroll_lock": "scrolllock","print_screen": "printscreen",
    "enter": "enter",           "return": "enter",
}


def _normalize_key(key) -> str:
    """Converte um objeto pynput Key/KeyCode para nome compatível com pyautogui."""
    try:
        char = key.char
        if char:
            return char.lower()
    except AttributeError:
        pass
    raw = str(key).replace("Key.", "").lower()
    return _PYNPUT_TO_PYAUTOGUI.get(raw, raw)


# ── Definição das ações disponíveis na timeline ───────────────────────────────

# Mapeamento action_id → rótulo exibido na UI
# save_mouse / restore_mouse não aparecem no dropdown:
# são gerenciados automaticamente pela checkbox de "Mover mouse".
_STEP_ACTION_LABELS: dict[str, str] = {
    "move_mouse":    "Mover mouse → X, Y",
    "click_left":    "Clique esquerdo",
    "click_right":   "Clique direito",
    "click_middle":  "Clique do meio",
    "double_click":  "Clique duplo",
    "key":           "Pressionar tecla",
    "delay":         "Intervalo (ms)",
    "scroll_up":     "Rolar para cima",
    "scroll_down":   "Rolar para baixo",
}

_STEP_LABELS     = list(_STEP_ACTION_LABELS.values())
_LABEL_TO_ACTION = {v: k for k, v in _STEP_ACTION_LABELS.items()}


# ── Classe principal ──────────────────────────────────────────────────────────

class BindDialog:
    """
    Attributes:
        result (dict | None): {'button': str, 'bind': dict} ao salvar. None se cancelado.
        dialog (CTkToplevel): A janela do diálogo.
    """

    def __init__(
        self,
        parent: ctk.CTk,
        *,
        title: str = "Mapeamento",
        edit_key: str | None = None,
        edit_bind: dict | None = None,
        existing_keys: list[str] | None = None,
    ) -> None:
        self.result: dict | None = None
        self._edit_key = edit_key
        self._existing_keys = set(existing_keys or [])
        self._capturing_btn = False

        # Lista de dicts de controle de cada passo da timeline:
        # [{"row", "num_lbl", "action_var", "param_frame", "widgets"}, ...]
        self._seq_steps: list[dict] = []

        # ── Janela ────────────────────────────────────────────────
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("530x520")
        self.dialog.resizable(False, True)   # Redimensionável verticalmente
        self.dialog.minsize(530, 420)
        self.dialog.grab_set()
        self.dialog.lift()
        self.dialog.focus_force()
        self.dialog.grid_columnconfigure(0, weight=1)
        self.dialog.grid_rowconfigure(3, weight=1)  # Área de conteúdo expande
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

        if edit_key is not None and edit_bind is not None:
            self._prefill(edit_key, edit_bind)

        self._on_type_change()

    # ──────────────────────────────────────────────────────────────
    # CONSTRUÇÃO DA UI PRINCIPAL
    # ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Linha: Nº do Botão ────────────────────────────────────
        btn_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        btn_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 4))
        btn_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            btn_frame, text="Nº do Botão:", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, padx=(0, 10))

        self._btn_entry = ctk.CTkEntry(btn_frame, placeholder_text="Ex: 0, 1, 2 ...")
        self._btn_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        self._capture_btn_btn = ctk.CTkButton(
            btn_frame, text="Capturar", width=90,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            command=self._start_btn_capture,
        )
        self._capture_btn_btn.grid(row=0, column=2)

        # ── Separador ─────────────────────────────────────────────
        ctk.CTkFrame(self.dialog, height=1, fg_color=("gray70", "gray35")).grid(
            row=1, column=0, sticky="ew", padx=16, pady=4
        )

        # ── Linha: Seletor de tipo ────────────────────────────────
        type_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        type_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=6)

        ctk.CTkLabel(
            type_frame, text="Tipo de Ação:", font=ctk.CTkFont(weight="bold")
        ).pack(side="left", padx=(0, 14))

        self._type_var = ctk.StringVar(value="keyboard")
        ctk.CTkRadioButton(
            type_frame, text="Teclado",
            variable=self._type_var, value="keyboard",
            command=self._on_type_change,
        ).pack(side="left", padx=6)
        ctk.CTkRadioButton(
            type_frame, text="Sequência de Ações",
            variable=self._type_var, value="sequence",
            command=self._on_type_change,
        ).pack(side="left", padx=6)

        # ── Área de conteúdo condicional ──────────────────────────
        self._fields_container = ctk.CTkFrame(self.dialog, fg_color="transparent")
        self._fields_container.grid(row=3, column=0, sticky="nsew", padx=16, pady=4)
        self._fields_container.grid_columnconfigure(0, weight=1)
        self._fields_container.grid_rowconfigure(0, weight=1)

        self._build_keyboard_panel()
        self._build_sequence_panel()

        # ── Separador + botões de confirmação ─────────────────────
        ctk.CTkFrame(self.dialog, height=1, fg_color=("gray70", "gray35")).grid(
            row=4, column=0, sticky="ew", padx=16, pady=(6, 4)
        )
        action_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        action_frame.grid(row=5, column=0, sticky="ew", padx=16, pady=(4, 16))

        ctk.CTkButton(
            action_frame, text="Cancelar", width=110,
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
            command=self._on_close,
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            action_frame, text="  Salvar", width=120,
            command=self._save,
        ).pack(side="right")

    # ──────────────────────────────────────────────────────────────
    # PAINEL DE TECLADO
    # ──────────────────────────────────────────────────────────────

    def _build_keyboard_panel(self) -> None:
        self._kb_frame = ctk.CTkFrame(self._fields_container)
        self._kb_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self._kb_frame, text="Tecla:", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, padx=(12, 8), pady=14)

        self._key_entry = ctk.CTkEntry(
            self._kb_frame, placeholder_text="Ex: enter, space, f5, a, ctrl ..."
        )
        self._key_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=14)

        self._capture_key_btn = ctk.CTkButton(
            self._kb_frame, text="Capturar", width=90,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            command=lambda: self._capture_key_into(self._key_entry, self._capture_key_btn),
        )
        self._capture_key_btn.grid(row=0, column=2, padx=(4, 12), pady=14)

        ctk.CTkLabel(
            self._kb_frame,
            text="Nomes aceitos: enter · space · tab · esc · f1-f12 · a-z · 0-9 · ctrl · alt · shift ...",
            font=ctk.CTkFont(size=10), text_color=("gray50", "gray60"),
            wraplength=440, justify="left",
        ).grid(row=1, column=0, columnspan=3, padx=12, pady=(0, 10), sticky="w")

    # ──────────────────────────────────────────────────────────────
    # PAINEL DE SEQUÊNCIA (TIMELINE)
    # ──────────────────────────────────────────────────────────────

    def _build_sequence_panel(self) -> None:
        self._seq_frame = ctk.CTkFrame(self._fields_container)
        self._seq_frame.grid_columnconfigure(0, weight=1)
        self._seq_frame.grid_rowconfigure(0, weight=1)

        # Área rolável — exibe os passos da timeline
        self._seq_scroll = ctk.CTkScrollableFrame(
            self._seq_frame,
            label_text="Linha do Tempo",
            label_font=ctk.CTkFont(size=12, weight="bold"),
            height=240,
        )
        self._seq_scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 6))
        self._seq_scroll.grid_columnconfigure(0, weight=1)

        # Placeholder mostrado quando não há passos
        self._seq_empty_label = ctk.CTkLabel(
            self._seq_scroll,
            text="Nenhuma ação ainda.\nUse o menu abaixo para adicionar passos.",
            font=ctk.CTkFont(size=11),
            text_color=("gray55", "gray55"),
            justify="center",
        )
        self._seq_empty_label.pack(pady=30)

        # ── Barra de adição de passo ──────────────────────────────
        add_bar = ctk.CTkFrame(self._seq_frame, fg_color="transparent")
        add_bar.grid(row=1, column=0, sticky="ew", padx=0, pady=(0, 4))

        self._new_action_var = ctk.StringVar(value=_STEP_LABELS[0])
        ctk.CTkOptionMenu(
            add_bar,
            variable=self._new_action_var,
            values=_STEP_LABELS,
            width=260,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            add_bar, text="+ Adicionar Passo", width=140,
            command=self._add_seq_step,
        ).pack(side="left")

    def _on_type_change(self) -> None:
        """Alterna entre o painel de teclado e o de sequência."""
        self._kb_frame.pack_forget()
        self._seq_frame.pack_forget()
        if self._type_var.get() == "keyboard":
            self._kb_frame.pack(fill="both", expand=True)
        else:
            self._seq_frame.pack(fill="both", expand=True)

    # ──────────────────────────────────────────────────────────────
    # GERENCIAMENTO DE PASSOS DA TIMELINE
    # ──────────────────────────────────────────────────────────────

    def _add_seq_step(self) -> None:
        """Adiciona um novo passo a partir do menu de seleção."""
        action_label = self._new_action_var.get()
        action = _LABEL_TO_ACTION.get(action_label, "click_left")
        self._render_step({"action": action})

    def _render_step(self, step_data: dict) -> None:
        """
        Constrói uma linha de passo na timeline com layout de 2 linhas:

          Linha 0: [nº]  [Seletor de tipo de ação ▼]  [↑][↓][✕]
          Linha 1:       [Parâmetros — largura total disponível   ]

        Isso evita o problema de widgets de parâmetros ficarem sem espaço
        e se sobrepondo aos botões de controle quando há um layout só de 1 linha.
        """
        idx = len(self._seq_steps)

        row = ctk.CTkFrame(self._seq_scroll, corner_radius=6, fg_color=("gray85", "gray23"))
        row.pack(fill="x", padx=4, pady=3)
        row.grid_columnconfigure(1, weight=1)  # Coluna do action_menu expande

        # ── Linha 0 ───────────────────────────────────────────────
        num_lbl = ctk.CTkLabel(
            row, text=str(idx + 1), width=22,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("gray50", "gray50"),
        )
        num_lbl.grid(row=0, column=0, padx=(8, 2), pady=(7, 2), sticky="n")

        action = step_data.get("action", "click_left")
        action_var = ctk.StringVar(value=_STEP_ACTION_LABELS.get(action, action))

        # ── Linha 1: parâmetros com largura total (menos o badge) ─
        param_frame = ctk.CTkFrame(row, fg_color="transparent")
        param_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=(34, 8), pady=(0, 7))

        widgets: dict = {}
        self._render_step_params(param_frame, action, step_data, widgets)

        entry = {
            "row": row,
            "num_lbl": num_lbl,
            "action_var": action_var,
            "param_frame": param_frame,
            "widgets": widgets,
        }

        def on_action_change(label: str, e: dict = entry) -> None:
            new_action = _LABEL_TO_ACTION.get(label, "click_left")
            self._render_step_params(e["param_frame"], new_action, {}, e["widgets"])

        action_menu = ctk.CTkOptionMenu(
            row, variable=action_var,
            values=_STEP_LABELS,
            command=on_action_change,
        )
        action_menu.grid(row=0, column=1, sticky="ew", padx=(2, 6), pady=(7, 2))

        # Botões de controle (↑ ↓ ✕) — coluna fixa à direita
        ctrl = ctk.CTkFrame(row, fg_color="transparent")
        ctrl.grid(row=0, column=2, padx=(0, 8), pady=(7, 2))

        ctk.CTkButton(
            ctrl, text="↑", width=28, height=26,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            command=lambda e=entry: self._move_step(e, -1),
        ).pack(side="left", padx=1)

        ctk.CTkButton(
            ctrl, text="↓", width=28, height=26,
            fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            command=lambda e=entry: self._move_step(e, +1),
        ).pack(side="left", padx=1)

        ctk.CTkButton(
            ctrl, text="✕", width=28, height=26,
            fg_color="#c0392b", hover_color="#a93226",
            command=lambda e=entry: self._remove_seq_step(e),
        ).pack(side="left", padx=(3, 0))

        self._seq_steps.append(entry)
        self._update_empty_state()

    def _render_step_params(
        self,
        parent: ctk.CTkFrame,
        action: str,
        step_data: dict,
        widgets: dict,
    ) -> None:
        """
        Renderiza widgets de parâmetro inline para o tipo de ação.
        Limpa o frame pai antes de renderizar.
        """
        for w in parent.winfo_children():
            w.destroy()
        widgets.clear()

        if action == "move_mouse":
            # X ──────────────────────────────────────────────────────
            ctk.CTkLabel(parent, text="X:").pack(side="left", padx=(0, 4))
            x_e = ctk.CTkEntry(parent, width=80, placeholder_text="0")
            if "x" in step_data:
                x_e.insert(0, str(step_data["x"]))
            x_e.pack(side="left", padx=(0, 16))
            widgets["x"] = x_e

            # Y ──────────────────────────────────────────────────────
            ctk.CTkLabel(parent, text="Y:").pack(side="left", padx=(0, 4))
            y_e = ctk.CTkEntry(parent, width=80, placeholder_text="0")
            if "y" in step_data:
                y_e.insert(0, str(step_data["y"]))
            y_e.pack(side="left", padx=(0, 16))
            widgets["y"] = y_e

            # Botão de captura de posição ────────────────────────────
            cap = ctk.CTkButton(
                parent, text="📍 Capturar", width=110,
                fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            )
            cap.configure(command=lambda b=cap: self._capture_pos_into(
                widgets["x"], widgets["y"], b
            ))
            cap.pack(side="left", padx=(0, 20))

            # Checkbox: salvar posição antes e restaurar ao fim ──────
            save_var = ctk.BooleanVar(value=bool(step_data.get("save_restore", False)))
            ctk.CTkCheckBox(
                parent,
                text="Salvar e restaurar posição do mouse",
                variable=save_var,
                height=20,
            ).pack(side="left")
            widgets["save_restore"] = save_var

        elif action == "key":
            e = ctk.CTkEntry(parent, width=110, placeholder_text="enter")
            if "key" in step_data:
                e.insert(0, step_data["key"])
            e.pack(side="left", padx=(0, 4))
            widgets["key"] = e

            cap = ctk.CTkButton(
                parent, text="Capturar", width=80,
                fg_color=("gray65", "gray30"), hover_color=("gray55", "gray40"),
            )
            cap.configure(command=lambda en=e, b=cap: self._capture_key_into(en, b))
            cap.pack(side="left", padx=2)

        elif action == "delay":
            e = ctk.CTkEntry(parent, width=70, placeholder_text="100")
            if "ms" in step_data:
                e.insert(0, str(step_data["ms"]))
            e.pack(side="left", padx=(0, 4))
            ctk.CTkLabel(parent, text="ms").pack(side="left")
            widgets["ms"] = e

        elif action in ("scroll_up", "scroll_down"):
            ctk.CTkLabel(parent, text="Cliques:").pack(side="left", padx=(0, 4))
            e = ctk.CTkEntry(parent, width=50, placeholder_text="3")
            if "clicks" in step_data:
                e.insert(0, str(step_data["clicks"]))
            e.pack(side="left")
            widgets["clicks"] = e

        # Ações sem parâmetros:
        # save_mouse, restore_mouse, click_left, click_right, click_middle, double_click

    def _extract_step_data(self, entry: dict) -> dict:
        """Lê os valores atuais dos widgets e retorna o dict do passo."""
        action = _LABEL_TO_ACTION.get(entry["action_var"].get(), "click_left")
        step: dict = {"action": action}
        w = entry["widgets"]

        if action == "move_mouse":
            try:    step["x"] = int(w["x"].get() or 0)
            except ValueError: step["x"] = 0
            try:    step["y"] = int(w["y"].get() or 0)
            except ValueError: step["y"] = 0
            # BooleanVar da checkbox; .get() = True/False
            step["save_restore"] = bool(w.get("save_restore") and w["save_restore"].get())

        elif action == "key":
            step["key"] = w["key"].get().strip() or "enter"

        elif action == "delay":
            try:    step["ms"] = int(w["ms"].get() or 100)
            except ValueError: step["ms"] = 100

        elif action in ("scroll_up", "scroll_down"):
            try:    step["clicks"] = int(w["clicks"].get() or 3)
            except ValueError: step["clicks"] = 3

        return step

    def _move_step(self, entry: dict, direction: int) -> None:
        """Move um passo para cima (−1) ou para baixo (+1) na timeline."""
        idx = self._seq_steps.index(entry)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self._seq_steps):
            return
        current_data = [self._extract_step_data(e) for e in self._seq_steps]
        current_data[idx], current_data[new_idx] = current_data[new_idx], current_data[idx]
        self._rebuild_seq_ui(current_data)

    def _remove_seq_step(self, entry: dict) -> None:
        """Remove um passo da timeline."""
        data = [self._extract_step_data(e) for e in self._seq_steps if e is not entry]
        self._rebuild_seq_ui(data)

    def _rebuild_seq_ui(self, data: list[dict]) -> None:
        """Destrói e reconstrói toda a UI da timeline a partir de uma lista de dados."""
        for e in self._seq_steps:
            e["row"].destroy()
        self._seq_steps.clear()
        for step_data in data:
            self._render_step(step_data)
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        """Exibe ou oculta o placeholder de 'sem ações'."""
        if self._seq_steps:
            self._seq_empty_label.pack_forget()
        else:
            self._seq_empty_label.pack(pady=30)

    # ──────────────────────────────────────────────────────────────
    # CAPTURA DE TECLA (genérica — usada no painel de teclado e nos steps)
    # ──────────────────────────────────────────────────────────────

    def _capture_key_into(self, entry: ctk.CTkEntry, btn: ctk.CTkButton) -> None:
        """Aguarda o próximo pressionamento de tecla via pynput e preenche o entry."""
        try:
            from pynput import keyboard as pynput_kb
        except ImportError:
            messagebox.showwarning(
                "pynput ausente", "Instale pynput:\n  pip install pynput",
                parent=self.dialog,
            )
            return

        btn.configure(text="Pressione...", state="disabled")
        entry.delete(0, "end")

        def on_press(key):
            key_name = _normalize_key(key)
            self.dialog.after(0, lambda: (
                entry.delete(0, "end"),
                entry.insert(0, key_name),
                btn.configure(text="Capturar", state="normal"),
            ))
            return False  # Para o listener após a primeira tecla

        lst = pynput_kb.Listener(on_press=on_press, suppress=False)
        lst.daemon = True
        lst.start()

    # ──────────────────────────────────────────────────────────────
    # CAPTURA DE POSIÇÃO DO MOUSE (genérica — usada nos steps move_mouse)
    # ──────────────────────────────────────────────────────────────

    def _capture_pos_into(
        self,
        x_entry: ctk.CTkEntry,
        y_entry: ctk.CTkEntry,
        btn: ctk.CTkButton,
    ) -> None:
        """Countdown de 3 s e preenche as coordenadas do cursor nos entries dados."""
        btn.configure(state="disabled")
        self._pos_countdown(3, x_entry, y_entry, btn)

    def _pos_countdown(
        self,
        remaining: int,
        x_entry: ctk.CTkEntry,
        y_entry: ctk.CTkEntry,
        btn: ctk.CTkButton,
    ) -> None:
        if remaining > 0:
            btn.configure(text=f"{remaining}s...")
            self.dialog.after(
                1000,
                lambda: self._pos_countdown(remaining - 1, x_entry, y_entry, btn),
            )
        else:
            pos = pyautogui.position()
            x_entry.delete(0, "end"); x_entry.insert(0, str(pos.x))
            y_entry.delete(0, "end"); y_entry.insert(0, str(pos.y))
            btn.configure(text="📍", state="normal")

    # ──────────────────────────────────────────────────────────────
    # CAPTURA DE BOTÃO DO CONTROLE (pygame polling em thread daemon)
    # ──────────────────────────────────────────────────────────────

    def _start_btn_capture(self) -> None:
        """
        Aguarda o próximo pressionamento no controle e preenche o campo
        'Nº do Botão'. Roda em thread daemon para não bloquear a GUI.
        """
        self._capturing_btn = True
        self._capture_btn_btn.configure(text="Pressione um botão...", state="disabled")
        self._btn_entry.delete(0, "end")

        def capture() -> None:
            try:
                if not pygame.joystick.get_init():
                    pygame.joystick.init()

                if pygame.joystick.get_count() == 0:
                    self.dialog.after(
                        0, lambda: self._on_btn_capture_failed("Nenhum controle conectado.")
                    )
                    return

                joy = pygame.joystick.Joystick(0)
                joy.init()
                num_buttons = joy.get_numbuttons()
                prev = {b: joy.get_button(b) for b in range(num_buttons)}
                deadline = time.monotonic() + 10.0

                while time.monotonic() < deadline and self._capturing_btn:
                    try:
                        pygame.event.pump()
                    except Exception:
                        pass
                    for b in range(num_buttons):
                        curr = joy.get_button(b)
                        if curr == 1 and prev.get(b, 0) == 0:
                            try: joy.quit()
                            except Exception: pass
                            self.dialog.after(0, lambda btn=b: self._on_btn_captured(btn))
                            return
                        prev[b] = curr
                    time.sleep(1 / 60)

                try: joy.quit()
                except Exception: pass

                if self._capturing_btn:
                    self.dialog.after(
                        0,
                        lambda: self._on_btn_capture_failed("Tempo esgotado (10 s). Tente novamente."),
                    )
            except Exception as exc:
                self.dialog.after(0, lambda e=str(exc): self._on_btn_capture_failed(e))

        threading.Thread(target=capture, daemon=True, name="BtnCapture").start()

    def _on_btn_captured(self, btn: int) -> None:
        self._capturing_btn = False
        self._btn_entry.delete(0, "end")
        self._btn_entry.insert(0, str(btn))
        self._capture_btn_btn.configure(text="Capturar", state="normal")

    def _on_btn_capture_failed(self, msg: str) -> None:
        self._capturing_btn = False
        self._capture_btn_btn.configure(text="Capturar", state="normal")
        messagebox.showwarning("Captura falhou", msg, parent=self.dialog)

    # ──────────────────────────────────────────────────────────────
    # PRÉ-PREENCHIMENTO (modo edição)
    # ──────────────────────────────────────────────────────────────

    def _prefill(self, key: str, bind: dict) -> None:
        """Popula os campos com os dados de um bind existente."""
        self._btn_entry.insert(0, key)
        bind_type = bind.get("type", "keyboard")

        if bind_type == "keyboard":
            self._type_var.set("keyboard")
            self._key_entry.insert(0, bind.get("key", ""))

        elif bind_type == "sequence":
            self._type_var.set("sequence")
            for step in bind.get("steps", []):
                self._render_step(step)

        elif bind_type == "mouse_combo":
            # Compatibilidade retroativa: converte para sequência equivalente.
            # "Salvar e restaurar posição" vira a checkbox do move_mouse.
            self._type_var.set("sequence")
            self._rebuild_seq_ui([
                {"action": "move_mouse", "x": bind.get("x", 0), "y": bind.get("y", 0),
                 "save_restore": True},
                {"action": "click_left"},
            ])

    # ──────────────────────────────────────────────────────────────
    # ENCERRAMENTO
    # ──────────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        self._capturing_btn = False
        self.dialog.destroy()

    # ──────────────────────────────────────────────────────────────
    # VALIDAÇÃO E SALVAMENTO
    # ──────────────────────────────────────────────────────────────

    def _save(self) -> None:
        # ── Valida número do botão ─────────────────────────────────
        raw_btn = self._btn_entry.get().strip()
        if not raw_btn.isdigit():
            messagebox.showerror(
                "Erro de validação",
                "O número do botão deve ser um inteiro não-negativo (ex: 0, 1, 2).",
                parent=self.dialog,
            )
            return

        btn_key = raw_btn

        if btn_key in self._existing_keys and btn_key != self._edit_key:
            if not messagebox.askyesno(
                "Sobrescrever?",
                f"O botão {btn_key} já possui um mapeamento.\nDeseja substituí-lo?",
                parent=self.dialog,
            ):
                return

        # ── Valida e monta o bind por tipo ────────────────────────
        bind_type = self._type_var.get()

        if bind_type == "keyboard":
            key = self._key_entry.get().strip().lower()
            if not key:
                messagebox.showerror(
                    "Erro de validação",
                    "Informe o nome da tecla ou use o botão 'Capturar'.",
                    parent=self.dialog,
                )
                return
            bind_data: dict = {"type": "keyboard", "key": key}

        elif bind_type == "sequence":
            if not self._seq_steps:
                messagebox.showerror(
                    "Erro de validação",
                    "Adicione pelo menos uma ação na sequência.",
                    parent=self.dialog,
                )
                return
            steps = [self._extract_step_data(e) for e in self._seq_steps]
            bind_data = {"type": "sequence", "steps": steps}

        else:
            return

        self.result = {"button": btn_key, "bind": bind_data}
        self.dialog.destroy()
