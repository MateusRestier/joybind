"""
gui/bind_dialog.py — Diálogo modal para adicionar ou editar um mapeamento.

Fluxo:
  1. Usuário informa o número do botão do controle.
  2. Escolhe o tipo de ação: Teclado ou Combo de Mouse.
  3. Preenche os parâmetros (tecla ou coordenadas X/Y).
  4. Opcionalmente usa os botões de "captura" para preencher automaticamente.
  5. Clica em Salvar → self.result é preenchido e o diálogo fecha.
     Clica em Cancelar → self.result permanece None.

A janela pai acessa `dlg.result` após `root.wait_window(dlg.dialog)`.
"""
import time
import threading
import pygame
import pyautogui
import customtkinter as ctk
from tkinter import messagebox


# Mapeamento de nomes de tecla pynput → pyautogui
# pynput usa nomes como "shift_l", "ctrl_l"; pyautogui espera "shiftleft", "ctrlleft".
_PYNPUT_TO_PYAUTOGUI: dict[str, str] = {
    "shift_l": "shiftleft",
    "shift_r": "shiftright",
    "ctrl_l": "ctrlleft",
    "ctrl_r": "ctrlright",
    "alt_l": "altleft",
    "alt_r": "altright",
    "alt_gr": "altright",
    "cmd": "win",
    "cmd_l": "win",
    "cmd_r": "win",
    "page_up": "pageup",
    "page_down": "pagedown",
    "num_lock": "numlock",
    "caps_lock": "capslock",
    "scroll_lock": "scrolllock",
    "print_screen": "printscreen",
    "enter": "enter",
    "return": "enter",
}


def _normalize_key(key) -> str:
    """
    Converte um objeto pynput.keyboard.Key / KeyCode para um nome
    compatível com pyautogui.press().
    """
    try:
        # Tecla de caractere imprimível (a, b, 1, !, ...)
        char = key.char
        if char:
            return char.lower()
    except AttributeError:
        pass

    # Tecla especial: pynput representa como Key.enter, Key.shift_l, etc.
    raw = str(key).replace("Key.", "").lower()
    return _PYNPUT_TO_PYAUTOGUI.get(raw, raw)


class BindDialog:
    """
    Cria e gerencia a janela de diálogo para configurar um bind.

    Attributes:
        result (dict | None): Preenchido com {'button': str, 'bind': dict}
                              ao salvar. None se cancelado.
        dialog (CTkToplevel): A janela do diálogo em si.
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
        """
        :param parent:       Janela pai (necessária para criar CTkToplevel).
        :param title:        Título da janela.
        :param edit_key:     Índice do botão sendo editado (None = novo bind).
        :param edit_bind:    Dados do bind existente para pré-preencher os campos.
        :param existing_keys: Lista de chaves já mapeadas (para validação de duplicatas).
        """
        self.result: dict | None = None
        self._edit_key = edit_key
        self._existing_keys = set(existing_keys or [])
        self._key_capture_thread: threading.Thread | None = None
        self._capturing_btn = False  # Flag para a thread de captura de botão

        # ── Cria a janela ──────────────────────────────────────────
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("460x370")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()   # Torna a janela modal (bloqueia a janela pai)
        self.dialog.lift()
        self.dialog.focus_force()
        self.dialog.grid_columnconfigure(0, weight=1)
        # Cancela captura de botão se o usuário fechar o diálogo
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

        # ── Pré-preenche campos se for edição ─────────────────────
        if edit_key is not None and edit_bind is not None:
            self._prefill(edit_key, edit_bind)

        # Exibe o painel correto conforme o tipo inicial
        self._on_type_change()

    # ──────────────────────────────────────────────────────────────
    # Construção da UI
    # ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        pad = {"padx": 16, "pady": 6}

        # ── Número do botão ───────────────────────────────────────
        btn_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        btn_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 4))
        btn_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            btn_frame, text="Nº do Botão:", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, padx=(0, 10))

        self._btn_entry = ctk.CTkEntry(
            btn_frame, placeholder_text="Ex: 0, 1, 2, 3 ..."
        )
        self._btn_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        # Botão para capturar automaticamente o próximo pressionamento no controle
        self._capture_btn_btn = ctk.CTkButton(
            btn_frame,
            text="Capturar",
            width=90,
            fg_color=("gray65", "gray30"),
            hover_color=("gray55", "gray40"),
            command=self._start_btn_capture,
        )
        self._capture_btn_btn.grid(row=0, column=2)

        # ── Separador ─────────────────────────────────────────────
        ctk.CTkFrame(self.dialog, height=1, fg_color=("gray70", "gray35")).grid(
            row=1, column=0, sticky="ew", padx=16, pady=4
        )

        # ── Seletor de tipo ───────────────────────────────────────
        type_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        type_frame.grid(row=2, column=0, sticky="ew", **pad)

        ctk.CTkLabel(type_frame, text="Tipo de Ação:", font=ctk.CTkFont(weight="bold")).pack(
            side="left", padx=(0, 14)
        )

        self._type_var = ctk.StringVar(value="keyboard")
        ctk.CTkRadioButton(
            type_frame,
            text="Teclado",
            variable=self._type_var,
            value="keyboard",
            command=self._on_type_change,
        ).pack(side="left", padx=6)
        ctk.CTkRadioButton(
            type_frame,
            text="Combo de Mouse",
            variable=self._type_var,
            value="mouse_combo",
            command=self._on_type_change,
        ).pack(side="left", padx=6)

        # ── Container para painéis condicionais ───────────────────
        # Ambos os painéis (teclado e mouse) vivem aqui.
        # _on_type_change alterna qual está visível via pack/pack_forget.
        self._fields_container = ctk.CTkFrame(self.dialog, fg_color="transparent")
        self._fields_container.grid(row=3, column=0, sticky="ew", padx=16, pady=4)
        self._fields_container.grid_columnconfigure(0, weight=1)

        self._build_keyboard_panel()
        self._build_mouse_panel()

        # ── Botões de ação ────────────────────────────────────────
        ctk.CTkFrame(self.dialog, height=1, fg_color=("gray70", "gray35")).grid(
            row=4, column=0, sticky="ew", padx=16, pady=(8, 4)
        )

        action_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        action_frame.grid(row=5, column=0, sticky="ew", padx=16, pady=(4, 16))

        ctk.CTkButton(
            action_frame,
            text="Cancelar",
            width=110,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            command=self.dialog.destroy,
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            action_frame,
            text="  Salvar",
            width=120,
            command=self._save,
        ).pack(side="right")

    def _build_keyboard_panel(self) -> None:
        """Painel de configuração para bind de teclado."""
        self._kb_frame = ctk.CTkFrame(self._fields_container)
        self._kb_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self._kb_frame, text="Tecla:", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, padx=(12, 8), pady=14)

        self._key_entry = ctk.CTkEntry(
            self._kb_frame,
            placeholder_text="Ex: enter, space, f5, a, ctrl ...",
        )
        self._key_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=14)

        self._capture_key_btn = ctk.CTkButton(
            self._kb_frame,
            text="Capturar",
            width=90,
            fg_color=("gray65", "gray30"),
            hover_color=("gray55", "gray40"),
            command=self._start_key_capture,
        )
        self._capture_key_btn.grid(row=0, column=2, padx=(4, 12), pady=14)

        ctk.CTkLabel(
            self._kb_frame,
            text="Nomes aceitos: enter · space · tab · esc · f1-f12 · a-z · 0-9 · ctrl · alt · shift · up · down ...",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray60"),
            wraplength=400,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, padx=12, pady=(0, 10), sticky="w")

    def _build_mouse_panel(self) -> None:
        """Painel de configuração para bind de combo de mouse."""
        self._mouse_frame = ctk.CTkFrame(self._fields_container)
        self._mouse_frame.grid_columnconfigure((1, 3), weight=1)

        # Linha de coordenadas
        for col, label_text, attr in [(0, "X:", "_x_entry"), (2, "Y:", "_y_entry")]:
            ctk.CTkLabel(
                self._mouse_frame, text=label_text, font=ctk.CTkFont(weight="bold")
            ).grid(row=0, column=col, padx=(12 if col == 0 else 10, 6), pady=14)

            entry = ctk.CTkEntry(self._mouse_frame, placeholder_text="0", width=90)
            entry.grid(row=0, column=col + 1, sticky="ew", padx=4, pady=14)
            setattr(self, attr, entry)

        self._capture_pos_btn = ctk.CTkButton(
            self._mouse_frame,
            text="Capturar Pos.",
            width=120,
            fg_color=("gray65", "gray30"),
            hover_color=("gray55", "gray40"),
            command=self._start_pos_capture,
        )
        self._capture_pos_btn.grid(row=0, column=4, padx=(6, 12), pady=14)

        ctk.CTkLabel(
            self._mouse_frame,
            text=(
                "Clique em 'Capturar Pos.' e posicione o mouse no ponto de destino.\n"
                "A posição será registrada automaticamente após 3 segundos."
            ),
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray60"),
            wraplength=400,
            justify="left",
        ).grid(row=1, column=0, columnspan=5, padx=12, pady=(0, 10), sticky="w")

    # ──────────────────────────────────────────────────────────────
    # Lógica de exibição condicional
    # ──────────────────────────────────────────────────────────────

    def _on_type_change(self) -> None:
        """Alterna entre o painel de teclado e o de mouse."""
        # Remove ambos e reexibe somente o adequado
        self._kb_frame.pack_forget()
        self._mouse_frame.pack_forget()

        if self._type_var.get() == "keyboard":
            self._kb_frame.pack(fill="x", padx=0, pady=2)
        else:
            self._mouse_frame.pack(fill="x", padx=0, pady=2)

    # ──────────────────────────────────────────────────────────────
    # Captura de tecla (pynput)
    # ──────────────────────────────────────────────────────────────

    def _start_key_capture(self) -> None:
        """
        Ativa o modo de captura: o próximo pressionamento de tecla é registrado.
        Usa pynput em uma thread separada para não bloquear a GUI.
        """
        try:
            from pynput import keyboard as pynput_kb
        except ImportError:
            messagebox.showwarning(
                "pynput ausente",
                "Instale pynput para usar a captura de tecla:\n  pip install pynput",
                parent=self.dialog,
            )
            return

        self._capture_key_btn.configure(text="Pressione uma tecla...", state="disabled")
        self._key_entry.delete(0, "end")

        def on_press(key):
            key_name = _normalize_key(key)
            # Agenda atualização da GUI na thread principal
            self.dialog.after(0, lambda: self._on_key_captured(key_name))
            return False  # Retornar False para o pynput Listener sinaliza para parar

        listener = pynput_kb.Listener(on_press=on_press, suppress=False)
        listener.daemon = True
        listener.start()

    def _on_key_captured(self, key_name: str) -> None:
        """Atualiza o campo de tecla após a captura."""
        self._key_entry.delete(0, "end")
        self._key_entry.insert(0, key_name)
        self._capture_key_btn.configure(text="Capturar", state="normal")

    # ──────────────────────────────────────────────────────────────
    # Captura de botão do controle (pygame polling)
    # ──────────────────────────────────────────────────────────────

    def _start_btn_capture(self) -> None:
        """
        Aguarda o próximo pressionamento de qualquer botão no controle e
        preenche o campo 'Nº do Botão' automaticamente.

        Roda em uma thread daemon para não bloquear a GUI. A atualização
        do widget é despachada para a thread principal via dialog.after().

        Não reinicializa o subsistema de joystick do pygame — apenas abre
        um objeto Joystick adicional para leitura de estado, o que é seguro
        mesmo que o listener principal esteja ativo em paralelo.
        """
        self._capturing_btn = True
        self._capture_btn_btn.configure(text="Pressione um botão...", state="disabled")
        self._btn_entry.delete(0, "end")

        def capture() -> None:
            try:
                # Garante que o subsistema está inicializado sem reiniciá-lo
                if not pygame.joystick.get_init():
                    pygame.joystick.init()

                if pygame.joystick.get_count() == 0:
                    self.dialog.after(
                        0,
                        lambda: self._on_btn_capture_failed("Nenhum controle conectado."),
                    )
                    return

                joy = pygame.joystick.Joystick(0)
                joy.init()
                num_buttons = joy.get_numbuttons()

                # Snapshot inicial — ignora botões já pressionados ao abrir o modo
                prev = {b: joy.get_button(b) for b in range(num_buttons)}

                deadline = time.monotonic() + 10.0  # Timeout de 10 segundos

                while time.monotonic() < deadline and self._capturing_btn:
                    try:
                        # Atualiza o estado interno do pygame sem bloquear
                        pygame.event.pump()
                    except Exception:
                        pass  # Se o pump falhar (raro), continuamos pelo estado anterior

                    for b in range(num_buttons):
                        curr = joy.get_button(b)
                        # Borda de subida: botão acabou de ser pressionado
                        if curr == 1 and prev.get(b, 0) == 0:
                            try:
                                joy.quit()
                            except Exception:
                                pass
                            self.dialog.after(0, lambda btn=b: self._on_btn_captured(btn))
                            return
                        prev[b] = curr

                    time.sleep(1 / 60)  # ~60 Hz, igual ao controller principal

                # Chegou aqui = timeout ou cancelamento pelo usuário
                try:
                    joy.quit()
                except Exception:
                    pass

                if self._capturing_btn:  # Não foi cancelado — foi timeout
                    self.dialog.after(
                        0,
                        lambda: self._on_btn_capture_failed("Tempo esgotado (10 s). Tente novamente."),
                    )

            except Exception as exc:
                self.dialog.after(0, lambda e=str(exc): self._on_btn_capture_failed(e))

        threading.Thread(target=capture, daemon=True, name="BtnCapture").start()

    def _on_btn_captured(self, btn: int) -> None:
        """Preenche o campo com o índice do botão capturado."""
        self._capturing_btn = False
        self._btn_entry.delete(0, "end")
        self._btn_entry.insert(0, str(btn))
        self._capture_btn_btn.configure(text="Capturar", state="normal")

    def _on_btn_capture_failed(self, msg: str) -> None:
        """Restaura o botão de captura e exibe o aviso de falha."""
        self._capturing_btn = False
        self._capture_btn_btn.configure(text="Capturar", state="normal")
        messagebox.showwarning("Captura falhou", msg, parent=self.dialog)

    # ──────────────────────────────────────────────────────────────
    # Captura de posição do mouse
    # ──────────────────────────────────────────────────────────────

    def _start_pos_capture(self) -> None:
        """
        Inicia um countdown de 3 segundos e então captura as coordenadas
        atuais do mouse usando pyautogui.position().
        O countdown roda via root.after() para não bloquear a GUI.
        """
        self._capture_pos_btn.configure(state="disabled")
        self._countdown(3)

    def _countdown(self, remaining: int) -> None:
        if remaining > 0:
            self._capture_pos_btn.configure(text=f"Capturando em {remaining}s...")
            self.dialog.after(1000, lambda: self._countdown(remaining - 1))
        else:
            # Captura a posição atual do cursor
            pos = pyautogui.position()
            self._x_entry.delete(0, "end")
            self._y_entry.delete(0, "end")
            self._x_entry.insert(0, str(pos.x))
            self._y_entry.insert(0, str(pos.y))
            self._capture_pos_btn.configure(text="Capturar Pos.", state="normal")

    # ──────────────────────────────────────────────────────────────
    # Pré-preenchimento (modo edição)
    # ──────────────────────────────────────────────────────────────

    def _prefill(self, key: str, bind: dict) -> None:
        """Popula os campos com os dados de um bind existente."""
        self._btn_entry.insert(0, key)
        # Campo permanece editável para permitir reatribuição via captura ou digitação

        bind_type = bind.get("type", "keyboard")
        self._type_var.set(bind_type)

        if bind_type == "keyboard":
            self._key_entry.insert(0, bind.get("key", ""))
        elif bind_type == "mouse_combo":
            self._x_entry.insert(0, str(bind.get("x", 0)))
            self._y_entry.insert(0, str(bind.get("y", 0)))

    # ──────────────────────────────────────────────────────────────
    # Encerramento do diálogo
    # ──────────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        """Cancela qualquer captura em andamento e fecha o diálogo."""
        self._capturing_btn = False  # Sinaliza para a thread de captura parar
        self.dialog.destroy()

    # ──────────────────────────────────────────────────────────────
    # Validação e salvamento
    # ──────────────────────────────────────────────────────────────

    def _save(self) -> None:
        """Valida os campos e preenche self.result antes de fechar o diálogo."""

        # ── Valida número do botão ─────────────────────────────────
        raw_btn = self._btn_entry.get().strip()
        if not raw_btn.isdigit():
            messagebox.showerror(
                "Erro de validação",
                "O número do botão deve ser um inteiro não-negativo (ex: 0, 1, 2).",
                parent=self.dialog,
            )
            return

        btn_key = raw_btn  # String, pois JSON usa str como chave

        # Verifica duplicata apenas ao adicionar (não ao editar o próprio bind)
        if btn_key in self._existing_keys and btn_key != self._edit_key:
            if not messagebox.askyesno(
                "Sobrescrever?",
                f"O botão {btn_key} já possui um mapeamento.\nDeseja substituí-lo?",
                parent=self.dialog,
            ):
                return

        # ── Valida campos por tipo ─────────────────────────────────
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

        elif bind_type == "mouse_combo":
            try:
                x = int(self._x_entry.get().strip())
                y = int(self._y_entry.get().strip())
            except ValueError:
                messagebox.showerror(
                    "Erro de validação",
                    "As coordenadas X e Y devem ser números inteiros.",
                    parent=self.dialog,
                )
                return
            bind_data = {"type": "mouse_combo", "x": x, "y": y}

        else:
            return  # Caso improvável

        self.result = {"button": btn_key, "bind": bind_data}
        self.dialog.destroy()
