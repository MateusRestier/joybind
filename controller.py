"""
controller.py — Listener de controle rodando em thread de background via pygame.

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
    ) -> None:
        """
        :param on_button_press: Chamado quando um botão é pressionado.
                                Recebe o índice inteiro do botão.
        :param on_axes_update:  Chamado a cada iteração de polling com a lista de
                                valores de todos os eixos analógicos (float -1.0..1.0).
                                Ambos os callbacks rodam na thread daemon do controller;
                                nunca interaja diretamente com a GUI dentro deles.
        """
        self.on_button_press = on_button_press
        self.on_axes_update = on_axes_update
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
                names.append(f"Controle #{i}")
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
            return False, "Nenhum controle detectado. Conecte um joystick/gamepad e tente novamente."
        if self._joystick_index >= total:
            return False, (
                f"Controle de índice {self._joystick_index} não encontrado "
                f"(apenas {total} controle(s) conectado(s))."
            )

        try:
            self._joystick = pygame.joystick.Joystick(self._joystick_index)
            self._joystick.init()
        except pygame.error as exc:
            return False, f"Erro ao inicializar controle: {exc}"

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

                    # Borda de subida: botão acabou de ser pressionado
                    if current == 1 and previous == 0:
                        self.on_button_press(btn)

                    prev_states[btn] = current

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
