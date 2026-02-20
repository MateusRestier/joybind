"""
actions.py — Execução das ações mapeadas: tecla de teclado e combo de mouse.

Todas as funções são thread-safe para chamada a partir da thread do controller.
"""
import pyautogui

# Remove o delay padrão de 0.1 s que o pyautogui insere entre cada ação.
# Isso é fundamental para que o combo de mouse seja instantâneo.
pyautogui.PAUSE = 0

# FailSafe: mover o mouse para o canto superior-esquerdo (0, 0) levanta
# FailSafeException. Mantemos True durante o desenvolvimento; se for
# indesejável, mude para False — mas perca o safety net.
pyautogui.FAILSAFE = True


def execute_keyboard(key: str) -> None:
    """
    Simula o pressionamento e soltura de uma tecla.

    :param key: Nome da tecla no formato pyautogui.
                Exemplos: 'enter', 'space', 'esc', 'f5', 'a', 'ctrl', 'shift'.
                Lista completa: pyautogui.KEYBOARD_KEYS
    """
    try:
        pyautogui.press(key)
    except pyautogui.FailSafeException:
        pass  # Mouse no canto: ignorar silenciosamente
    except Exception as e:
        print(f"[Actions] Erro ao pressionar tecla '{key}': {e}")


def execute_mouse_combo(x: int, y: int) -> None:
    """
    Executa o combo de mouse em 4 passos atômicos e instantâneos:

      1. Captura a posição atual do cursor.
      2. Teleporta o cursor para a coordenada alvo (x, y).
      3. Executa um clique com o botão esquerdo.
      4. Retorna o cursor para a posição capturada no passo 1.

    Com pyautogui.PAUSE = 0 e duration=0, a operação inteira é
    executada em microssegundos — imperceptível para o usuário.

    :param x: Coordenada X do ponto de clique na tela.
    :param y: Coordenada Y do ponto de clique na tela.
    """
    try:
        # Passo 1 — Salva posição original
        origin = pyautogui.position()

        # Passo 2 — Teleporta para o alvo (duration=0 = sem animação)
        pyautogui.moveTo(x, y, duration=0)

        # Passo 3 — Clique esquerdo
        pyautogui.click()

        # Passo 4 — Retorna à posição original
        pyautogui.moveTo(origin.x, origin.y, duration=0)

    except pyautogui.FailSafeException:
        pass  # Mouse estava no canto: aborta o combo silenciosamente
    except Exception as e:
        print(f"[Actions] Erro no combo de mouse ({x}, {y}): {e}")
