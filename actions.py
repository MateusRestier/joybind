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

    # Auto-restaura a posição do mouse se save_restore foi ativado
    # e nenhum passo restore_mouse explícito foi executado.
    if saved_pos is not None:
        try:
            pyautogui.moveTo(saved_pos.x, saved_pos.y, duration=0)
        except Exception as e:
            print(f"[Actions] Erro ao restaurar posição: {e}")
