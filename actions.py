"""
actions.py — Execução das ações mapeadas.

Funções thread-safe chamáveis a partir da thread do controller ou de workers.
"""
import time
import pyautogui

# Remove o delay padrão de 0.1 s entre cada chamada pyautogui.
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True


# ── Ações simples ─────────────────────────────────────────────────────────────

def execute_keyboard(key: str) -> None:
    """Pressiona e solta uma tecla. Ex: 'enter', 'space', 'f5', 'ctrl'."""
    try:
        pyautogui.press(key)
    except pyautogui.FailSafeException:
        pass
    except Exception as e:
        print(f"[Actions] Erro ao pressionar tecla '{key}': {e}")


def execute_mouse_combo(x: int, y: int) -> None:
    """
    Compatibilidade retroativa com o tipo mouse_combo antigo.
    Equivale a: save_mouse → move_mouse(x,y) → click_left → restore_mouse.
    """
    execute_sequence([
        {"action": "save_mouse"},
        {"action": "move_mouse", "x": x, "y": y},
        {"action": "click_left"},
        {"action": "restore_mouse"},
    ])


# ── Sequência de ações (timeline) ─────────────────────────────────────────────

def execute_sequence(steps: list[dict]) -> None:
    """
    Executa uma lista ordenada de passos.

    Passos suportados:
      save_mouse    — Salva a posição atual do cursor em variável local.
      restore_mouse — Restaura o cursor para a posição salva.
      move_mouse    — Teleporta o cursor para {"x": int, "y": int}.
      click_left    — Clique esquerdo na posição atual.
      click_right   — Clique direito na posição atual.
      click_middle  — Clique do meio na posição atual.
      double_click  — Clique duplo esquerdo na posição atual.
      scroll_up     — Rola para cima {"clicks": int} vezes (padrão 3).
      scroll_down   — Rola para baixo {"clicks": int} vezes (padrão 3).
      key           — Pressiona uma tecla {"key": str}.
      delay         — Pausa {"ms": int} milissegundos (padrão 100).
    """
    saved_pos = None  # Posição salva pelo passo save_mouse

    for step in steps:
        action = step.get("action", "")
        try:
            if action == "save_mouse":
                saved_pos = pyautogui.position()

            elif action == "restore_mouse":
                if saved_pos is not None:
                    pyautogui.moveTo(saved_pos.x, saved_pos.y, duration=0)

            elif action == "move_mouse":
                pyautogui.moveTo(step["x"], step["y"], duration=0)

            elif action == "click_left":
                pyautogui.click(button="left")

            elif action == "click_right":
                pyautogui.click(button="right")

            elif action == "click_middle":
                pyautogui.click(button="middle")

            elif action == "double_click":
                pyautogui.doubleClick()

            elif action == "scroll_up":
                pyautogui.scroll(step.get("clicks", 3))

            elif action == "scroll_down":
                pyautogui.scroll(-step.get("clicks", 3))

            elif action == "key":
                pyautogui.press(step["key"])

            elif action == "delay":
                time.sleep(step.get("ms", 100) / 1000.0)

            else:
                print(f"[Actions] Ação desconhecida ignorada: '{action}'")

        except pyautogui.FailSafeException:
            return  # Aborta a sequência inteira silenciosamente
        except Exception as e:
            print(f"[Actions] Erro no passo '{action}': {e}")
