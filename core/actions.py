"""
core/actions.py — Execução das ações mapeadas.

Funções thread-safe chamáveis a partir da thread do controller ou de workers.
"""
import sys
import time
import ctypes
import pyautogui

# Remove o delay padrão de 0.1 s entre cada chamada pyautogui.
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True

# ── SendInput (Windows) — movimento relativo compatível com Raw Input ─────────
# pyautogui.move() usa SetCursorPos, que jogos como Minecraft ignoram porque
# registram WM_INPUT (Raw Input API). SendInput com MOUSEEVENTF_MOVE gera o
# evento real de hardware que o Raw Input consome.

if sys.platform == "win32":
    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx",          ctypes.c_long),
            ("dy",          ctypes.c_long),
            ("mouseData",   ctypes.c_ulong),
            ("dwFlags",     ctypes.c_ulong),
            ("time",        ctypes.c_ulong),
            ("dwExtraInfo", ctypes.c_size_t),  # ULONG_PTR
        ]

    class _INPUT(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.c_ulong),
            ("mi",   _MOUSEINPUT),
        ]

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    _INPUT_MOUSE = 0

    # ── Flags SendInput ───────────────────────────────────────────────────
    _MOUSEEVENTF_MOVE        = 0x0001
    _MOUSEEVENTF_LEFTDOWN    = 0x0002
    _MOUSEEVENTF_LEFTUP      = 0x0004
    _MOUSEEVENTF_RIGHTDOWN   = 0x0008
    _MOUSEEVENTF_RIGHTUP     = 0x0010
    _MOUSEEVENTF_MIDDLEDOWN  = 0x0020
    _MOUSEEVENTF_MIDDLEUP    = 0x0040
    _MOUSEEVENTF_WHEEL       = 0x0800  # roda vertical
    _MOUSEEVENTF_HWHEEL      = 0x1000  # roda horizontal
    _MOUSEEVENTF_XDOWN       = 0x0080  # botões laterais (mouse4/mouse5)
    _MOUSEEVENTF_XUP         = 0x0100
    _MOUSEEVENTF_ABSOLUTE    = 0x8000
    _MOUSEEVENTF_VIRTUALDESK = 0x4000
    _WHEEL_DELTA             = 120     # 1 "clique" de roda
    _XBUTTON1                = 1       # mouse4 (botão traseiro)
    _XBUTTON2                = 2       # mouse5 (botão frontal)

    # ── Mensagens Win32 ───────────────────────────────────────────────────
    _WM_MOUSEMOVE     = 0x0200
    _WM_LBUTTONDOWN   = 0x0201
    _WM_LBUTTONUP     = 0x0202
    _WM_LBUTTONDBLCLK = 0x0203
    _WM_RBUTTONDOWN   = 0x0204
    _WM_RBUTTONUP     = 0x0205
    _WM_MBUTTONDOWN   = 0x0207
    _WM_MBUTTONUP     = 0x0208
    _MK_LBUTTON = 0x0001
    _MK_RBUTTON = 0x0002
    _MK_MBUTTON = 0x0010

    # GetSystemMetrics IDs
    _SM_XVIRTUALSCREEN  = 76
    _SM_YVIRTUALSCREEN  = 77
    _SM_CXVIRTUALSCREEN = 78
    _SM_CYVIRTUALSCREEN = 79

    def _win_sendinput(flags: int, dx: int = 0, dy: int = 0) -> None:
        """Envia um único evento de mouse via SendInput."""
        inp = _INPUT(type=_INPUT_MOUSE)
        inp.mi.dx      = dx
        inp.mi.dy      = dy
        inp.mi.dwFlags = flags
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _win_send_mouse_move(dx: int, dy: int) -> None:
        """Movimento relativo — compatível com Raw Input (Minecraft, etc.)."""
        _win_sendinput(_MOUSEEVENTF_MOVE, dx, dy)

    def _win_scroll(delta: int) -> None:
        """Rola a roda do mouse via SendInput. delta positivo = cima, negativo = baixo."""
        inp = _INPUT(type=_INPUT_MOUSE)
        inp.mi.dwFlags   = _MOUSEEVENTF_WHEEL
        inp.mi.mouseData = ctypes.c_ulong(delta & 0xFFFFFFFF)
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _win_hscroll(delta: int) -> None:
        """Rola horizontalmente via SendInput. delta positivo = direita, negativo = esquerda."""
        inp = _INPUT(type=_INPUT_MOUSE)
        inp.mi.dwFlags   = _MOUSEEVENTF_HWHEEL
        inp.mi.mouseData = ctypes.c_ulong(delta & 0xFFFFFFFF)
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _win_xbutton(which: int, down: bool) -> None:
        """Pressiona/solta mouse4 (which=1) ou mouse5 (which=2) via SendInput."""
        inp = _INPUT(type=_INPUT_MOUSE)
        inp.mi.dwFlags   = _MOUSEEVENTF_XDOWN if down else _MOUSEEVENTF_XUP
        inp.mi.mouseData = ctypes.c_ulong(which)
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _win_send_move_abs(x: int, y: int) -> None:
        """Move cursor via SendInput ABSOLUTE gerando WM_MOUSEMOVE.

        Usa o desktop virtual completo para suportar múltiplos monitores.
        Essencial para emuladores que rastreiam cursor via WM_MOUSEMOVE
        (SetCursorPos é silencioso e não gera essa mensagem).
        """
        gm = ctypes.windll.user32.GetSystemMetrics
        vx = gm(_SM_XVIRTUALSCREEN)
        vy = gm(_SM_YVIRTUALSCREEN)
        vw = max(gm(_SM_CXVIRTUALSCREEN), 1)
        vh = max(gm(_SM_CYVIRTUALSCREEN), 1)
        nx = (x - vx) * 65535 // (vw - 1) if vw > 1 else 0
        ny = (y - vy) * 65535 // (vh - 1) if vh > 1 else 0
        _win_sendinput(
            _MOUSEEVENTF_MOVE | _MOUSEEVENTF_ABSOLUTE | _MOUSEEVENTF_VIRTUALDESK,
            nx, ny,
        )

    def _win_send_click(button: str = "left", hold_ms: int = 0) -> None:
        """Clique via SendInput sem coordenadas — usa posição atual do cursor.

        Gera WM_INPUT + WM_LBUTTONDOWN corretamente. Mais limpo que
        pyautogui.click() que re-normaliza coordenadas absolutas.
        """
        _btns = {
            "left":   (_MOUSEEVENTF_LEFTDOWN,   _MOUSEEVENTF_LEFTUP),
            "right":  (_MOUSEEVENTF_RIGHTDOWN,  _MOUSEEVENTF_RIGHTUP),
            "middle": (_MOUSEEVENTF_MIDDLEDOWN, _MOUSEEVENTF_MIDDLEUP),
        }
        f_down, f_up = _btns.get(button, _btns["left"])
        _win_sendinput(f_down)
        if hold_ms > 0:
            time.sleep(hold_ms / 1000.0)
        _win_sendinput(f_up)

    def _win_post_click(button: str = "left", hold_ms: int = 0) -> None:
        """Envia WM_MOUSEMOVE + WM_BUTTON* via PostMessage ao HWND sob o cursor.

        Não requer foco — contorna o 'focus click' de emuladores como o Citra.
        Inclui WM_MOUSEMOVE antes do botão para apps que rastreiam posição
        via mensagem (ex: Qt render widget do Citra).
        """
        if button == "right":
            down_msg, up_msg, mk = _WM_RBUTTONDOWN, _WM_RBUTTONUP, _MK_RBUTTON
        elif button == "middle":
            down_msg, up_msg, mk = _WM_MBUTTONDOWN, _WM_MBUTTONUP, _MK_MBUTTON
        elif button == "double":
            down_msg, up_msg, mk = _WM_LBUTTONDBLCLK, _WM_LBUTTONUP, _MK_LBUTTON
        else:
            down_msg, up_msg, mk = _WM_LBUTTONDOWN, _WM_LBUTTONUP, _MK_LBUTTON

        pt = _POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        hwnd = ctypes.windll.user32.WindowFromPoint(pt)
        ctypes.windll.user32.ScreenToClient(hwnd, ctypes.byref(pt))
        # MAKELPARAM(x, y): x nos 16 bits baixos, y nos 16 bits altos
        lparam = ((pt.y & 0xFFFF) << 16) | (pt.x & 0xFFFF)
        ctypes.windll.user32.PostMessageW(hwnd, _WM_MOUSEMOVE, 0, lparam)
        ctypes.windll.user32.PostMessageW(hwnd, down_msg, mk, lparam)
        if hold_ms > 0:
            time.sleep(hold_ms / 1000.0)
        ctypes.windll.user32.PostMessageW(hwnd, up_msg, 0, lparam)

    _HAS_SENDINPUT = True
else:
    _HAS_SENDINPUT = False


# ── Ações simples ─────────────────────────────────────────────────────────────

def execute_keyboard(key: str, hold_ms: int = 0) -> None:
    """Pressiona e solta uma tecla ou executa um clique de mouse.

    Ex: 'enter', 'space', 'f5', 'ctrl+c', 'mouse_left', 'mouse_right'.

    hold_ms — tempo em ms que a tecla fica pressionada antes de soltar.
    Útil para jogos que usam polling de estado por frame (ex: Minecraft/GLFW),
    onde DOWN+UP instantâneos podem ser ignorados entre dois glfwPollEvents().
    """
    try:
        if key == "scroll_up":
            if _HAS_SENDINPUT:
                _win_scroll(_WHEEL_DELTA)
            else:
                pyautogui.scroll(1)
        elif key == "scroll_down":
            if _HAS_SENDINPUT:
                _win_scroll(-_WHEEL_DELTA)
            else:
                pyautogui.scroll(-1)
        elif key == "scroll_right":
            if _HAS_SENDINPUT:
                _win_hscroll(_WHEEL_DELTA)
            else:
                pyautogui.keyDown("shift"); pyautogui.scroll(-1); pyautogui.keyUp("shift")
        elif key == "scroll_left":
            if _HAS_SENDINPUT:
                _win_hscroll(-_WHEEL_DELTA)
            else:
                pyautogui.keyDown("shift"); pyautogui.scroll(1); pyautogui.keyUp("shift")
        elif key == "mouse4":
            if _HAS_SENDINPUT:
                _win_xbutton(_XBUTTON1, True)
                if hold_ms > 0:
                    time.sleep(hold_ms / 1000.0)
                _win_xbutton(_XBUTTON1, False)
            else:
                pyautogui.click(button="left")  # fallback
        elif key == "mouse5":
            if _HAS_SENDINPUT:
                _win_xbutton(_XBUTTON2, True)
                if hold_ms > 0:
                    time.sleep(hold_ms / 1000.0)
                _win_xbutton(_XBUTTON2, False)
            else:
                pyautogui.click(button="right")  # fallback
        elif key == "mouse_left":
            if _HAS_SENDINPUT:
                _win_send_click("left", hold_ms)
            else:
                pyautogui.click(button="left")
        elif key == "mouse_right":
            if _HAS_SENDINPUT:
                _win_send_click("right", hold_ms)
            else:
                pyautogui.click(button="right")
        elif key == "mouse_middle":
            if _HAS_SENDINPUT:
                _win_send_click("middle", hold_ms)
            else:
                pyautogui.click(button="middle")
        elif "+" in key:
            # Combo como "ctrl+c": pressiona todas as partes, aguarda, solta na ordem inversa.
            parts = [p.strip() for p in key.split("+") if p.strip()]
            for p in parts:
                pyautogui.keyDown(p)
            if hold_ms > 0:
                time.sleep(hold_ms / 1000.0)
            for p in reversed(parts):
                pyautogui.keyUp(p)
        else:
            if hold_ms > 0:
                pyautogui.keyDown(key)
                time.sleep(hold_ms / 1000.0)
                pyautogui.keyUp(key)
            else:
                pyautogui.press(key)
    except pyautogui.FailSafeException:
        pass
    except Exception as e:
        print(f"[Actions] Erro ao executar '{key}': {e}")


def hold_down(key: str) -> None:
    """Pressiona e mantém uma tecla ou botão do mouse sem soltar.

    Usado para binds de botão com 'Segurar enquanto pressionado':
    chamado no press do botão do controle; hold_up() é chamado no release.
    """
    try:
        if key in ("scroll_up", "scroll_down"):
            # scroll não tem estado "pressionado" — dispara uma vez
            execute_keyboard(key)
        elif key == "mouse4":
            if _HAS_SENDINPUT:
                _win_xbutton(_XBUTTON1, True)
            else:
                pyautogui.mouseDown(button="left")
        elif key == "mouse5":
            if _HAS_SENDINPUT:
                _win_xbutton(_XBUTTON2, True)
            else:
                pyautogui.mouseDown(button="right")
        elif key == "mouse_left":
            if _HAS_SENDINPUT:
                _win_sendinput(_MOUSEEVENTF_LEFTDOWN)
            else:
                pyautogui.mouseDown(button="left")
        elif key == "mouse_right":
            if _HAS_SENDINPUT:
                _win_sendinput(_MOUSEEVENTF_RIGHTDOWN)
            else:
                pyautogui.mouseDown(button="right")
        elif key == "mouse_middle":
            if _HAS_SENDINPUT:
                _win_sendinput(_MOUSEEVENTF_MIDDLEDOWN)
            else:
                pyautogui.mouseDown(button="middle")
        elif "+" in key:
            parts = [p.strip() for p in key.split("+") if p.strip()]
            for p in parts:
                pyautogui.keyDown(p)
        else:
            pyautogui.keyDown(key)
    except pyautogui.FailSafeException:
        pass
    except Exception as e:
        print(f"[Actions] Erro ao pressionar (hold) '{key}': {e}")


def hold_up(key: str) -> None:
    """Solta uma tecla ou botão do mouse mantido por hold_down."""
    try:
        if key in ("scroll_up", "scroll_down"):
            pass  # scroll não tem estado — nada a soltar
        elif key == "mouse4":
            if _HAS_SENDINPUT:
                _win_xbutton(_XBUTTON1, False)
            else:
                pyautogui.mouseUp(button="left")
        elif key == "mouse5":
            if _HAS_SENDINPUT:
                _win_xbutton(_XBUTTON2, False)
            else:
                pyautogui.mouseUp(button="right")
        elif key == "mouse_left":
            if _HAS_SENDINPUT:
                _win_sendinput(_MOUSEEVENTF_LEFTUP)
            else:
                pyautogui.mouseUp(button="left")
        elif key == "mouse_right":
            if _HAS_SENDINPUT:
                _win_sendinput(_MOUSEEVENTF_RIGHTUP)
            else:
                pyautogui.mouseUp(button="right")
        elif key == "mouse_middle":
            if _HAS_SENDINPUT:
                _win_sendinput(_MOUSEEVENTF_MIDDLEUP)
            else:
                pyautogui.mouseUp(button="middle")
        elif "+" in key:
            parts = [p.strip() for p in key.split("+") if p.strip()]
            for p in reversed(parts):
                pyautogui.keyUp(p)
        else:
            pyautogui.keyUp(key)
    except pyautogui.FailSafeException:
        pass
    except Exception as e:
        print(f"[Actions] Erro ao soltar (hold) '{key}': {e}")


def execute_mouse_combo(x: int, y: int) -> None:
    """Compatibilidade retroativa com o tipo mouse_combo antigo."""
    execute_sequence([
        {"action": "move_mouse", "x": x, "y": y, "save_restore": True},
        {"action": "click_left"},
    ])


# ── Sequência de ações (timeline) ─────────────────────────────────────────────

def execute_sequence(steps: list[dict]) -> None:
    """
    Executa uma lista ordenada de passos.

    Passos suportados:
      move_mouse    — Teleporta o cursor para {"x": int, "y": int}.
                      Com "save_restore": true, salva a posição ANTES de mover
                      e a restaura automaticamente ao FIM da sequência.
      click_left    — Clique esquerdo na posição atual.
      click_right   — Clique direito na posição atual.
      click_middle  — Clique do meio na posição atual.
      double_click  — Clique duplo esquerdo na posição atual.
      scroll_up     — Rola para cima {"clicks": int} vezes (padrão 3).
      scroll_down   — Rola para baixo {"clicks": int} vezes (padrão 3).
      key           — Pressiona uma tecla {"key": str}.
      delay         — Pausa {"ms": int} milissegundos (padrão 100).

    Compatibilidade retroativa (config.json antigos):
      save_mouse    — Salva a posição atual do cursor.
      restore_mouse — Restaura o cursor para a posição salva.
    """
    # Posição a restaurar ao fim (None = nenhuma restauração pendente)
    saved_pos = None

    for step in steps:
        action = step.get("action", "")
        try:
            # ── Compatibilidade com configs antigos ─────────────────
            if action == "save_mouse":
                saved_pos = pyautogui.position()
                continue

            elif action == "restore_mouse":
                if saved_pos is not None:
                    pyautogui.moveTo(saved_pos.x, saved_pos.y, duration=0)
                    saved_pos = None
                continue

            elif action == "move_mouse":
                # Se save_restore=True, salva posição atual antes de mover
                if step.get("save_restore") and saved_pos is None:
                    saved_pos = pyautogui.position()
                x_t, y_t = step["x"], step["y"]
                if _HAS_SENDINPUT:
                    # SendInput(MOVE+ABS) gera WM_MOUSEMOVE — essencial para
                    # emuladores (Citra/Qt) que rastreiam cursor via mensagem.
                    _win_send_move_abs(x_t, y_t)
                else:
                    pyautogui.moveTo(x_t, y_t, duration=0)

            elif action == "click_left":
                hold_ms = step.get("hold_ms", 0)
                if _HAS_SENDINPUT:
                    if step.get("direct"):
                        _win_post_click("left", hold_ms)
                    else:
                        _win_send_click("left", hold_ms)
                else:
                    pyautogui.click(button="left")

            elif action == "click_right":
                hold_ms = step.get("hold_ms", 0)
                if _HAS_SENDINPUT:
                    if step.get("direct"):
                        _win_post_click("right", hold_ms)
                    else:
                        _win_send_click("right", hold_ms)
                else:
                    pyautogui.click(button="right")

            elif action == "click_middle":
                hold_ms = step.get("hold_ms", 0)
                if _HAS_SENDINPUT:
                    if step.get("direct"):
                        _win_post_click("middle", hold_ms)
                    else:
                        _win_send_click("middle", hold_ms)
                else:
                    pyautogui.click(button="middle")

            elif action == "double_click":
                hold_ms = step.get("hold_ms", 0)
                if _HAS_SENDINPUT:
                    if step.get("direct"):
                        _win_post_click("double", hold_ms)
                    else:
                        _win_send_click("left", hold_ms)
                        time.sleep(0.05)
                        _win_send_click("left", hold_ms)
                else:
                    pyautogui.doubleClick()

            elif action == "scroll_up":
                pyautogui.scroll(step.get("clicks", 3))

            elif action == "scroll_down":
                pyautogui.scroll(-step.get("clicks", 3))

            elif action == "key":
                execute_keyboard(step["key"], step.get("hold_ms", 0))

            elif action == "delay":
                time.sleep(step.get("ms", 100) / 1000.0)

            else:
                print(f"[Actions] Ação desconhecida ignorada: '{action}'")

        except pyautogui.FailSafeException:
            return  # Aborta a sequência inteira silenciosamente
        except Exception as e:
            print(f"[Actions] Erro no passo '{action}': {e}")

    # Auto-restaura a posição do mouse se save_restore foi ativado
    # e nenhum passo restore_mouse explícito foi executado.
    if saved_pos is not None:
        try:
            pyautogui.moveTo(saved_pos.x, saved_pos.y, duration=0)
        except Exception as e:
            print(f"[Actions] Erro ao restaurar posição: {e}")


# ── Movimento analógico contínuo ───────────────────────────────────────────

def move_mouse_relative(dx: int, dy: int) -> None:
    """Move o mouse de forma relativa.

    Usa SendInput no Windows (compatível com Raw Input de jogos como Minecraft).
    Fallback para pyautogui.move() em outras plataformas.
    """
    try:
        if _HAS_SENDINPUT:
            _win_send_mouse_move(dx, dy)
        else:
            pyautogui.move(dx, dy)
    except pyautogui.FailSafeException:
        pass
    except Exception as e:
        print(f"[Actions] Erro ao mover mouse: {e}")


def scroll_v_relative(clicks: int) -> None:
    """Rola verticalmente. Positivo = cima, negativo = baixo."""
    try:
        pyautogui.scroll(clicks)
    except pyautogui.FailSafeException:
        pass
    except Exception as e:
        print(f"[Actions] Erro ao rolar verticalmente: {e}")


def scroll_h_relative(clicks: int) -> None:
    """Rola horizontalmente via Shift+scroll (mais compatível no Windows que hscroll).
    Positivo = direita, negativo = esquerda.
    Shift+scroll_down = direita, Shift+scroll_up = esquerda."""
    try:
        pyautogui.keyDown("shift")
        pyautogui.scroll(-clicks)  # negado: scroll_down+Shift = direita
        pyautogui.keyUp("shift")
    except pyautogui.FailSafeException:
        pass
    except Exception as e:
        print(f"[Actions] Erro ao rolar horizontalmente: {e}")


# ── Teclas mantidas pressionadas (analógico → tecla) ───────────────────────

def key_down(key: str) -> None:
    """Mantém uma tecla pressionada enquanto o analógico está na direção."""
    try:
        pyautogui.keyDown(key)
    except pyautogui.FailSafeException:
        pass
    except Exception as e:
        print(f"[Actions] Erro ao pressionar '{key}': {e}")


def key_up(key: str) -> None:
    """Solta uma tecla mantida por key_down."""
    try:
        pyautogui.keyUp(key)
    except pyautogui.FailSafeException:
        pass
    except Exception as e:
        print(f"[Actions] Erro ao soltar '{key}': {e}")


def _parse_combo(combo: str) -> list[str]:
    """Divide 'ctrl+shift+d' em ['ctrl', 'shift', 'd']."""
    return [k.strip() for k in combo.split("+") if k.strip()]


def key_combo_down(combo: str) -> None:
    """Mantém pressionado um combo de teclas (ex: 'ctrl+d')."""
    for key in _parse_combo(combo):
        key_down(key)


def key_combo_up(combo: str) -> None:
    """Solta um combo de teclas na ordem inversa."""
    for key in reversed(_parse_combo(combo)):
        key_up(key)


def key_combo_press(combo: str) -> None:
    """Pressiona e solta um combo de teclas de uma vez (usado para auto-repeat analógico)."""
    parts = _parse_combo(combo)
    try:
        pyautogui.hotkey(*parts)
    except pyautogui.FailSafeException:
        pass
    except Exception as e:
        print(f"[Actions] Erro ao pressionar combo '{combo}': {e}")
