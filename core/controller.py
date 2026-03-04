"""
core/controller.py — Listener de controle rodando em thread de background via pygame.

Design:
  • Não usa o sistema de eventos do pygame (pygame.event.get) porque ele tem
    restrições de thread em algumas plataformas.
  • Em vez disso, usa polling direto de estado (joystick.get_button) a 60 Hz,
    detectando a borda de subida (0 → 1) para disparar o callback apenas uma
    vez por pressionamento físico.
  • pygame.event.pump() é chamado a cada iteração para manter o estado interno
    do pygame atualizado sem precisar de uma janela de display.
"""
import threading
import pygame
from typing import Callable, Optional
import i18n

# Threshold para considerar um eixo de gatilho como "pressionado".
# Gatilhos PS geralmente vão de -1.0 (solto) a +1.0 (pressionado).
_TRIGGER_THRESHOLD: float = 0.5

# Mapeamento eixo de gatilho → índice de botão virtual.
# Eixos 4 e 5 são L2/R2 em controles PlayStation via SDL2/pygame no Windows.
# Usa índices 100+ para evitar colisão com botões digitais reais (0-13 em PS4).
_TRIGGER_AXIS_TO_BTN: dict[int, int] = {
    4: 100,   # L2 analógico → botão virtual L2
    5: 101,   # R2 analógico → botão virtual R2
}

# Mapeamento de direção do HAT switch → índice de botão virtual.
# O HAT 0 é como a maioria dos controles PlayStation reporta o D-pad.
# Usa índices 102+ para evitar colisão com botões digitais reais.
_HAT_DIRECTION_TO_BTN: dict[tuple[int, int], int] = {
    (0,  1): 102,   # ↑ cima
    (0, -1): 103,   # ↓ baixo
    (-1, 0): 104,   # ← esquerda
    (1,  0): 105,   # → direita
}


class ControllerListener:
    """
    Gerencia a detecção de inputs de um joystick/gamepad em uma thread daemon.

    Uso básico:
        listener = ControllerListener(on_button_press=minha_funcao)
        listener.start()
        ...
        listener.stop()
    """

    # Taxa de polling em Hz — 60 é mais que suficiente para input humano
    _POLL_RATE_HZ = 60

    def __init__(
        self,
        on_button_press: Callable[[int], None],
        on_axes_update: Optional[Callable[[list[float]], None]] = None,
        on_button_release: Optional[Callable[[int], None]] = None,
    ) -> None:
        """
        :param on_button_press:   Chamado quando um botão é pressionado (borda de subida).
                                  Recebe o índice inteiro do botão.
        :param on_axes_update:    Chamado a cada iteração de polling com a lista de
                                  valores de todos os eixos analógicos (float -1.0..1.0).
        :param on_button_release: Chamado quando um botão é solto (borda de descida).
                                  Recebe o índice inteiro do botão.
                                  Todos os callbacks rodam na thread daemon do controller;
                                  nunca interaja diretamente com a GUI dentro deles.
        """
        self.on_button_press = on_button_press
        self.on_axes_update = on_axes_update
        self.on_button_release = on_button_release
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._joystick: Optional[pygame.joystick.Joystick] = None
        self._joystick_index: int = 0

    # ──────────────────────────────────────────────────────────────
    # Métodos estáticos de utilidade
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _reinit_joystick_subsystem() -> None:
        """Re-inicializa o subsistema de joystick para detectar dispositivos recém-conectados."""
        pygame.joystick.quit()
        pygame.joystick.init()

    @staticmethod
    def get_joystick_names() -> list[str]:
        """
        Retorna os nomes de todos os joysticks/gamepads conectados.
        Força re-enumeração do hardware a cada chamada.
        """
        ControllerListener._reinit_joystick_subsystem()
        names: list[str] = []
        for i in range(pygame.joystick.get_count()):
            try:
                names.append(pygame.joystick.Joystick(i).get_name())
            except pygame.error:
                names.append(i18n.t("ctrl_name_fallback", n=i))
        return names

    # ──────────────────────────────────────────────────────────────
    # Configuração
    # ──────────────────────────────────────────────────────────────

    def set_joystick_index(self, index: int) -> None:
        """Define qual joystick usar pelo seu índice na lista enumerada."""
        self._joystick_index = index

    def get_button_count(self) -> int:
        """
        Retorna quantos botões o joystick selecionado possui.
        Útil para popular dropdowns na GUI sem precisar iniciar o listener.
        Retorna 0 se não houver joystick disponível.
        """
        if self._joystick and self._joystick.get_init():
            return self._joystick.get_numbuttons()
        try:
            ControllerListener._reinit_joystick_subsystem()
            if pygame.joystick.get_count() > self._joystick_index:
                j = pygame.joystick.Joystick(self._joystick_index)
                j.init()
                count = j.get_numbuttons()
                j.quit()
                return count
        except pygame.error:
            pass
        return 0

    # ──────────────────────────────────────────────────────────────
    # Ciclo de vida
    # ──────────────────────────────────────────────────────────────

    def start(self) -> tuple[bool, str]:
        """
        Inicia a thread de escuta.

        :return: (sucesso: bool, mensagem_de_erro: str)
                 Se sucesso=True a mensagem é string vazia.
        """
        if self._running:
            return True, ""  # Já está rodando

        ControllerListener._reinit_joystick_subsystem()
        total = pygame.joystick.get_count()

        if total == 0:
            return False, i18n.t("msg_no_ctrl")
        if self._joystick_index >= total:
            return False, i18n.t("msg_ctrl_not_found", idx=self._joystick_index, total=total)

        try:
            self._joystick = pygame.joystick.Joystick(self._joystick_index)
            self._joystick.init()
        except pygame.error as exc:
            return False, i18n.t("msg_ctrl_init_error", exc=exc)

        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,          # Morre com o processo principal automaticamente
            name="JoyBind-Listener",
        )
        self._thread.start()
        return True, ""

    def stop(self) -> None:
        """Para a thread de escuta e libera o joystick."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

        if self._joystick:
            try:
                self._joystick.quit()
            except pygame.error:
                pass
            self._joystick = None

    @property
    def is_running(self) -> bool:
        return self._running

    # ──────────────────────────────────────────────────────────────
    # Loop interno
    # ──────────────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        """
        Loop de polling que roda na thread daemon.

        Estratégia de detecção:
          • Mantém um dicionário {índice_botão: estado_anterior}.
          • A cada iteração, compara o estado atual com o anterior.
          • Se estado passou de 0 para 1 → botão acabou de ser pressionado.
          • Isso evita múltiplos disparos enquanto o botão é mantido pressionado.
        """
        prev_states: dict[int, int] = {}
        prev_hat_states: dict[int, tuple[int, int]] = {}
        clock = pygame.time.Clock()

        while self._running:
            try:
                # Necessário para que o pygame atualize os estados de hardware
                # sem uma janela de display ativa.
                pygame.event.pump()

                if not (self._joystick and self._joystick.get_init()):
                    print("[Controller] Joystick desconectado inesperadamente.")
                    break

                num_buttons = self._joystick.get_numbuttons()
                for btn in range(num_buttons):
                    current = self._joystick.get_button(btn)
                    previous = prev_states.get(btn, 0)

                    if current == 1 and previous == 0:
                        # Borda de subida: botão acabou de ser pressionado
                        self.on_button_press(btn)
                    elif current == 0 and previous == 1 and self.on_button_release:
                        # Borda de descida: botão acabou de ser solto
                        self.on_button_release(btn)

                    prev_states[btn] = current

                # Poll eixos de gatilho como botões (L2/R2 em controles PlayStation).
                # Ativa o botão virtual quando o eixo cruza _TRIGGER_THRESHOLD.
                n_axes = self._joystick.get_numaxes()
                for axis_idx, vbtn in _TRIGGER_AXIS_TO_BTN.items():
                    if axis_idx >= n_axes:
                        continue
                    axis_val = self._joystick.get_axis(axis_idx)
                    current  = 1 if axis_val > _TRIGGER_THRESHOLD else 0
                    previous = prev_states.get(-(axis_idx + 1), 0)  # chave negativa evita colisão
                    if current == 1 and previous == 0:
                        self.on_button_press(vbtn)
                    elif current == 0 and previous == 1 and self.on_button_release:
                        self.on_button_release(vbtn)
                    prev_states[-(axis_idx + 1)] = current

                # Poll HAT switches (D-pad em controles PlayStation e similares).
                # Cada direção ativa dispara on_button_press com o índice virtual
                # definido em _HAT_DIRECTION_TO_BTN.
                n_hats = self._joystick.get_numhats()
                for hat_idx in range(n_hats):
                    hx, hy = self._joystick.get_hat(hat_idx)
                    prev_hat = prev_hat_states.get(hat_idx, (0, 0))
                    for (dx, dy), vbtn in _HAT_DIRECTION_TO_BTN.items():
                        current_active = (hx == dx and hy == dy)
                        prev_active    = (prev_hat[0] == dx and prev_hat[1] == dy)
                        if current_active and not prev_active:
                            self.on_button_press(vbtn)
                        elif not current_active and prev_active and self.on_button_release:
                            self.on_button_release(vbtn)
                    prev_hat_states[hat_idx] = (hx, hy)

                # Envia estado atual de todos os eixos analógicos
                if self.on_axes_update is not None:
                    n_axes = self._joystick.get_numaxes()
                    axis_values = [self._joystick.get_axis(i) for i in range(n_axes)]
                    self.on_axes_update(axis_values)

            except pygame.error as exc:
                print(f"[Controller] Erro pygame no loop: {exc}")
                break
            except Exception as exc:
                print(f"[Controller] Erro inesperado no loop: {exc}")
                break

            # Limita o uso de CPU a ~60 verificações por segundo
            clock.tick(self._POLL_RATE_HZ)

        # Garante que o flag reflita o estado real ao sair do loop
        self._running = False
