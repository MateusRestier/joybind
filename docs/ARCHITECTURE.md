# Arquitetura Técnica — JoyBind

Documentação detalhada de cada arquivo do projeto, suas responsabilidades, decisões de design e como os componentes interagem.

Para convenções de código e guias de extensão, veja o [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Índice

1. [Visão geral do sistema](#visão-geral-do-sistema)
2. [Mapa de dependências](#mapa-de-dependências)
3. [Fluxo de uma ação — do botão ao sistema operacional](#fluxo-de-uma-ação)
4. [main.py](#mainpy)
5. [core/controller.py](#corecontrollerpy)
6. [core/actions.py](#coreactionspy)
7. [core/presets.py](#corepresetspy)
8. [core/config.py](#coreconfigpy)
9. [gui/app.py](#guiapppy)
10. [gui/bind_dialog.py](#guibind_dialogpy)
11. [Arquitetura de threads](#arquitetura-de-threads)
12. [Camada de input Win32 (SendInput)](#camada-de-input-win32)
13. [Sub-pixel accumulation (movimento analógico suave)](#sub-pixel-accumulation)
14. [Gerenciamento de estado: o que vai aonde](#gerenciamento-de-estado)

---

## Visão geral do sistema

O JoyBind é dividido em três camadas com separação clara de responsabilidades:

```
┌─────────────────────────────────────────────────────────┐
│                    CAMADA DE APRESENTAÇÃO               │
│  gui/app.py          — janela principal, state manager  │
│  gui/bind_dialog.py  — diálogos de configuração (modal) │
└───────────────────────────┬─────────────────────────────┘
                            │ chama
┌───────────────────────────▼─────────────────────────────┐
│                     CAMADA DE DOMÍNIO                    │
│  core/controller.py  — polling de hardware (gamepad)    │
│  core/actions.py     — execução de ações (kb/mouse)     │
│  core/presets.py     — persistência de configurações    │
└───────────────────────────┬─────────────────────────────┘
                            │ usa
┌───────────────────────────▼─────────────────────────────┐
│                    CAMADA DE PLATAFORMA                  │
│  pygame              — leitura de joystick               │
│  pyautogui           — teclado via INPUT_KEYBDINPUT      │
│  ctypes / SendInput  — mouse via Raw Input (Win32)      │
│  customtkinter       — widgets de interface              │
└─────────────────────────────────────────────────────────┘
```

**Princípio fundamental:** cada camada só conhece a camada abaixo. `controller.py` não sabe nada de GUI. `actions.py` não sabe nada de controller. `presets.py` não sabe nada de GUI nem de controller.

---

## Mapa de dependências

```
main.py
  └─ gui/app.py (App)
       ├─ core/controller.py (ControllerListener)
       ├─ core/actions.py
       ├─ core/presets.py
       └─ gui/bind_dialog.py (BindDialog, SequenceDialog)
            ├─ pygame          (captura de botão do controle)
            └─ pynput          (captura de teclas/mouse)
```

Nenhum módulo `core/` importa nada de `gui/`. Essa separação garante que a lógica de negócio seja testável e reutilizável independentemente da interface.

---

## Fluxo de uma ação

Exemplo: usuário pressiona o botão X do controle, que está mapeado para `mouse_left`.

```
Hardware (gamepad USB)
    │
    │  SDL2 / pygame.joystick
    ▼
ControllerListener._poll_loop()          [Thread: JoyBind-Listener, 60 Hz]
    │  detecta borda de subida (0 → 1) no botão X
    │  chama on_button_press(button=2)
    ▼
App._on_button_press(button=2)           [ainda na thread JoyBind-Listener]
    │  lê self.cfg["binds"]["2"] → {"type": "keyboard", "key": "mouse_left"}
    │  spawna nova thread para não bloquear o polling
    ▼
Thread "Action-BTN2"                     [Thread daemon, criada no momento]
    │  chama actions.execute_keyboard("mouse_left", hold_ms=0)
    ▼
actions._win_send_click("left")          [ainda em Action-BTN2]
    │  constrói estrutura _INPUT com MOUSEEVENTF_LEFTDOWN
    │  chama SendInput() via ctypes
    │  aguarda hold_ms (0 = imediato)
    │  constrói estrutura _INPUT com MOUSEEVENTF_LEFTUP
    │  chama SendInput() via ctypes
    ▼
Windows Raw Input pipeline
    │  entrega WM_LBUTTONDOWN + WM_LBUTTONUP à janela em foco
    ▼
Jogo / aplicativo recebe o clique
```

---

## main.py

**Responsabilidade:** bootstrap do processo — configura o ambiente antes de criar qualquer janela.

### Sequência de inicialização

```python
1. SetCurrentProcessExplicitAppUserModelID(...)   # Win32: agrupa na taskbar como app própria
2. ctk.set_appearance_mode("dark")               # tema CTk
3. pygame.init()                                 # subsistemas de joystick
4. root = ctk.CTk()                              # cria a janela principal
5. _apply_taskbar_icon(root, ico_path)           # ícone na barra de tarefas
6. app = App(root)                               # monta toda a UI e carrega preset
7. root.protocol("WM_DELETE_WINDOW", on_close)  # shutdown gracioso
8. root.mainloop()                               # loop de eventos do Tk
```

### Por que `SetCurrentProcessExplicitAppUserModelID`?

Sem isso, a janela aparece agrupada sob `python.exe` na taskbar em vez de ter seu próprio ícone e grupo. Deve ser chamado **antes** de qualquer janela ser criada.

### Ícone em dois destinos

O ícone precisar ser definido em dois lugares:
- `root.iconbitmap(ico_str)` → barra de título (titlebar) — API do Tkinter
- `WM_SETICON` via `ctypes` → barra de tarefas — o Tk não expõe isso; usa Win32 direto

O PNG é convertido para ICO multi-resolução em runtime e salvo em `%TEMP%` para evitar problemas de permissão.

### Compatibilidade com PyInstaller

```python
_BASE = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
```

`sys._MEIPASS` é o diretório temporário onde o PyInstaller extrai os recursos ao executar um `.exe` `--onefile`. Em desenvolvimento, `__file__` é o caminho real. Essa lógica aparece também em `gui/app.py`.

---

## core/controller.py

**Responsabilidade:** detectar eventos de hardware do gamepad e disparar callbacks. Não sabe nada sobre o que fazer com esses eventos.

### Por que polling em vez de eventos pygame?

O sistema de eventos do pygame (`pygame.event.get()`) tem restrições de thread em algumas plataformas — ele deve ser chamado da thread que inicializou o display. Como o JoyBind não tem janela pygame (usa CTk), a alternativa é polling direto de estado.

O truque é chamar `pygame.event.pump()` a cada iteração do loop. Isso atualiza o estado interno do pygame sem precisar de display ativo.

### Detecção de borda (edge detection)

O estado do joystick é binário por botão (0 ou 1). Para disparar callbacks apenas uma vez por pressionamento — e não 60 vezes por segundo enquanto o botão é mantido — o loop mantém um dicionário de estados anteriores:

```python
prev_states: dict[int, int] = {}

# A cada iteração:
current = joystick.get_button(btn)
previous = prev_states.get(btn, 0)

if current == 1 and previous == 0:   # borda de SUBIDA → press
    self.on_button_press(btn)
elif current == 0 and previous == 1: # borda de DESCIDA → release
    self.on_button_release(btn)

prev_states[btn] = current
```

### Botões virtuais

Alguns inputs de gamepad não são botões simples:

| Hardware | Índice virtual | Por que virtual? |
|---|---|---|
| Gatilhos L2/R2 (eixo 4/5) | 100, 101 | Gatilhos analógicos reportados como eixo, não botão, em controles PlayStation via SDL2 |
| D-pad cima/baixo/esq/dir (HAT 0) | 102, 103, 104, 105 | HAT switch retorna tupla `(x, y)`, não um botão por direção |

Os índices 100+ foram escolhidos para não colidir com botões digitais reais (máximo de ~20 em controles comuns). A App usa esses mesmos índices como chave no dicionário `binds`.

**Estado do HAT:** diferente dos botões, um HAT só pode ter uma direção ativa por vez. O loop compara o valor anterior da tupla `(hx, hy)` com o atual para cada direção mapeada em `_HAT_DIRECTION_TO_BTN`.

**Chave negativa para gatilhos:** para evitar colisão no dicionário `prev_states` com índices de botões reais, os gatilhos usam chaves negativas: `-(axis_idx + 1)` → eixo 4 vira chave `-5`, eixo 5 vira `-6`.

### Callbacks na thread daemon

Todos os três callbacks (`on_button_press`, `on_button_release`, `on_axes_update`) são chamados **dentro da thread daemon** do controller. Regra crítica: nunca chamar métodos de widgets Tk/CTk diretamente nesses callbacks.

---

## core/actions.py

**Responsabilidade:** executar ações de teclado e mouse de forma thread-safe. Único arquivo que toca o sistema de input do OS.

### Por que SendInput em vez de pyautogui para mouse?

`pyautogui.moveTo()` e `pyautogui.click()` usam `SetCursorPos` e `mouse_event` internamente, que são APIs de alto nível ignoradas por jogos que usam **Raw Input** (Win32 `WM_INPUT`). Minecraft, por exemplo, registra rotação de câmera via Raw Input e ignora `SetCursorPos` completamente.

`SendInput` com `MOUSEEVENTF_MOVE` gera o evento de hardware real que alimenta o pipeline Raw Input, sendo reconhecido por todos os jogos.

### Dois tipos de movimento de mouse

| Função | Flags SendInput | Quando usar |
|---|---|---|
| `_win_send_mouse_move(dx, dy)` | `MOUSEEVENTF_MOVE` (relativo) | Movimento analógico contínuo — o analógico esquerdo chama isso 60×/s |
| `_win_send_move_abs(x, y)` | `MOUSEEVENTF_MOVE \| MOUSEEVENTF_ABSOLUTE \| MOUSEEVENTF_VIRTUALDESK` | Sequências — teleporta o cursor para posição absoluta |

O movimento absoluto usa o desktop virtual completo (`SM_XVIRTUALSCREEN` etc.) para funcionar corretamente com múltiplos monitores. As coordenadas precisam ser normalizadas para o range 0–65535 que o SendInput espera.

### Dois tipos de clique

| Função | Mecanismo | Quando usar |
|---|---|---|
| `_win_send_click()` | `SendInput` | Uso geral — funciona em qualquer janela em foco |
| `_win_post_click()` | `PostMessage` ao HWND sob o cursor | Emuladores como Citra que têm janela Qt e não recebem foco normalmente |

`_win_post_click()` obtém o `HWND` sob o cursor via `WindowFromPoint`, converte coordenadas de tela para cliente via `ScreenToClient`, e envia `WM_MOUSEMOVE` + `WM_LBUTTONDOWN` + `WM_LBUTTONUP` diretamente na fila de mensagens da janela, sem precisar que ela tenha foco. É habilitado com `"direct": true` em um passo de sequência.

### Scroll dos botões vs scroll de sequência

Há dois caminhos para scroll no código:

- **Botão mapeado como `scroll_up`/`scroll_down`:** usa `_win_scroll(±120)` — um único `MOUSEEVENTF_WHEEL` com `WHEEL_DELTA = 120` (padrão Windows para 1 "clique" de roda)
- **Passo de sequência `scroll_up`/`scroll_down`:** usa `pyautogui.scroll(n)` — envia N cliques de roda

A distinção existe porque o scroll via botão foi adicionado depois para funcionar com Modo Macro (repetição rápida), e usa SendInput para consistência com os outros botões de mouse.

### Triplo de funções para cada tecla/botão

Para cada tipo de ação há três funções que formam uma interface consistente:

```
execute_keyboard(key)   — press + release em uma chamada (fire and forget)
hold_down(key)          — press sem release (deve ser seguido de hold_up)
hold_up(key)            — release correspondente ao hold_down
```

**Atenção para `scroll_up`/`scroll_down`:** scroll não tem estado "pressionado" no OS. `hold_down("scroll_up")` dispara um único evento e `hold_up` é no-op. Para scroll contínuo, use Modo Macro.

### Funções para analógico

```
move_mouse_relative(dx, dy)  — movimento relativo (analógico esquerdo)
scroll_v_relative(clicks)    — scroll vertical (analógico direito no modo scroll)
scroll_h_relative(clicks)    — scroll horizontal via Shift+scroll (mais compatível que hscroll)
key_down(key)                — pressiona tecla (analógico → tecla em modo manual)
key_up(key)                  — solta tecla
key_combo_down/up/press()    — variantes para combos com "+"
```

---

## core/presets.py

**Responsabilidade:** persistência de configurações no disco, sem nenhuma dependência de GUI.

### Onde os arquivos ficam

| Contexto | Localização |
|---|---|
| Presets (dev) | `<repo>/presets/*.json` |
| Presets (exe) | `%APPDATA%\JoyBind\presets\*.json` |
| settings.json | `%APPDATA%\JoyBind\settings.json` |

Em modo desenvolvimento (`sys.frozen == False`), os presets ficam no repositório para facilitar testes e versionamento. Em executável, ficam em `%APPDATA%` para não exigir permissão de escrita na pasta do exe.

### settings.json

Guarda configurações do app que não fazem parte do preset:

```json
{
  "presets_dir": "C:\\Users\\...\\JoyBind\\presets",
  "last_preset": "C:\\Users\\...\\JoyBind\\presets\\minecraft.json",
  "btn_layout": { "A": "0", "B": "1", "X": "2", "Y": "3", ... }
}
```

`btn_layout` mapeia os nomes visuais dos tiles (A, B, X, Y, LB...) para índices reais de botões do controle conectado. Isso é configurado pelo wizard de Auto-mapear.

### Escrita atômica

Todos os salvamentos usam o padrão `.tmp` → `rename`:

```python
tmp = path.with_suffix(".tmp")
with open(tmp, "w", ...) as f:
    json.dump(data, f, ...)
tmp.replace(path)   # atomic no mesmo volume de disco
```

`Path.replace()` é atômica no mesmo volume (uma chamada `rename()` do SO). Se o processo morrer durante a escrita, o `.tmp` fica corruptível mas o arquivo original permanece intacto.

---

## core/config.py

**Responsabilidade:** compatibilidade retroativa com o formato antigo `config.json`.

Este arquivo é legado. O sistema atual usa `core/presets.py`. O `config.json` era o formato original antes do sistema de presets ser introduzido. `App._ensure_defaults()` em `gui/app.py` ainda aceita presets que usem o formato antigo (com `mouse_combo`, `axes[]` em vez de `sticks[]`) e os converte silenciosamente.

Não adicione funcionalidades aqui. Se precisar de novos campos de configuração, adicione em `core/presets.py`.

---

## gui/app.py

**Responsabilidade:** cola tudo — gerencia a UI, recebe callbacks do controller, invoca actions, persiste via presets. É o módulo mais complexo do projeto.

### Estrutura da classe App

```
App.__init__()
  ├─ carrega settings + preset inicial
  ├─ carrega btn_layout (visual_id → btn_key)
  ├─ inicializa estado (_held_btn_keys, _macro_stop_events, etc.)
  ├─ cria ControllerListener (com callbacks apontando para métodos da App)
  ├─ _build_ui() → monta todos os widgets
  └─ _refresh_*() → popula dropdowns com dados reais

_build_ui()
  ├─ _build_header()         — título + botões de controle global
  ├─ _build_preset_bar()     — dropdown de preset + Novo/Pasta
  ├─ _build_device_row()     — dropdown de controle + botão ↻
  ├─ _build_status_row()     — indicador de status + label de última ação
  └─ TabView
       ├─ [Botões]     → _build_controller_layout()  — grid de tiles
       └─ [Analógicos] → _build_analog_tab()          — painéis de analógico
```

### Estado interno (dicionários-chave)

| Atributo | Tipo | Conteúdo |
|---|---|---|
| `self.cfg` | `dict` | Preset ativo: `{"binds": {...}, "analog": {...}}` |
| `self._layout` | `dict[str, str]` | `{"A": "0", "B": "1", ...}` — visual_id → btn_key |
| `self._held_btn_keys` | `dict[int, str]` | Botões com hold ativo: `{2: "shift"}` → btn 2 está segurando shift |
| `self._macro_stop_events` | `dict[int, threading.Event]` | Macros ativas: `{3: Event}` → btn 3 tem macro rodando |
| `self._held_keys` | `set[str]` | Teclas presas pelo analógico no modo manual |
| `self._prev_dir_active` | `dict[(int, str), bool]` | Estado anterior de cada direção analógica para edge detection |
| `self._acc_x/y/sv/sh` | `float` | Acumuladores de sub-pixel para movimento suave |

### Tratamento de botões: _on_button_press

Chamado na thread do controller. Nunca toca em widgets diretamente.

```
_on_button_press(button: int)
  │
  ├─ lê cfg["binds"][str(button)]  →  se não existe, retorna
  │
  ├─ spawna Thread "Action-BTN{button}"
  │       │
  │       ├─ type == "keyboard" e macro_interval_ms > 0
  │       │     → cria threading.Event, armazena em _macro_stop_events[button]
  │       │     → spawna Thread "Macro-BTN{button}" com loop:
  │       │           while not stop.is_set():
  │       │               execute_keyboard(key)
  │       │               stop.wait(interval_ms / 1000)  ← interrompível
  │       │
  │       ├─ type == "keyboard" e hold_while_pressed
  │       │     → actions.hold_down(key)
  │       │     → armazena key em _held_btn_keys[button]
  │       │
  │       ├─ type == "keyboard" (simples)
  │       │     → actions.execute_keyboard(key, hold_ms)
  │       │
  │       ├─ type == "sequence"
  │       │     → actions.execute_sequence(steps)
  │       │
  │       └─ atualiza label via root.after(0, ...)
  │
  └─ retorna (sem bloquear o polling)
```

**Por que uma thread separada para cada pressionamento?** Para não bloquear o loop de 60 Hz do controller enquanto uma sequência com `delay` estiver executando. Cada botão tem sua própria thread de ação, permitindo paralelismo.

### Tratamento de release: _on_button_release

```
_on_button_release(button: int)
  ├─ _macro_stop_events.pop(button) → stop_evt.set()  ← termina o macro loop
  └─ _held_btn_keys.pop(button) → se havia hold ativo:
       spawna Thread "Release-BTN{button}"
           → actions.hold_up(key_name)
           → atualiza label via root.after(0, ...)
```

### Tratamento de analógico: _on_axes_update

Chamado 60×/s na thread do controller. Processo:

1. Para cada stick, lê os índices de eixo X e Y, aplica deadzone
2. Verifica o `stick_mode` do stick:
   - `"mouse"` → acumula `dx`, `dy` para movimento relativo
   - `"scroll"` → acumula `sv`, `sh` para scroll
   - `"game"` (stick esquerdo) → edge-detection para teclas WASD
   - `"game"` (stick direito) → acumula `dx`, `dy` (câmera)
   - `"none"` → lê bindings por direção (`up`/`down`/`left`/`right`)
3. Aplica acumuladores de sub-pixel e envia movimentos reais

### AnalogDirectionDialog

Dialog modal para configurar uma direção de analógico. Padrão de uso:

```python
dlg = AnalogDirectionDialog(parent, "↑ Cima", current_binding)
parent.wait_window(dlg.dialog)  # bloqueia até fechar
if dlg.result is not None:
    # usa dlg.result (dict com type, sensitivity ou key ou steps)
```

### AutoMapWizard

Wizard que percorre os tiles do layout visual em sequência, aguardando o usuário pressionar o botão físico correspondente. Detecta botões digitais, gatilhos (eixo > 0.5) e HAT switch. Usa polling direto com timeout de 15 s por tile.

O resultado é um `dict[str, str]` mapeando `visual_id → btn_key` que é salvo em `settings.json["btn_layout"]`.

### _btn_tile_text: como os tiles são renderizados

```python
def _btn_tile_text(self, btn_key: str | None) -> str:
    bind = self.cfg["binds"].get(btn_key)
    if not bind or bind.get("type") == "none":
        return "—"
    t = bind["type"]
    if t == "keyboard":
        key = bind["key"]
        base = _MOUSE_KEY_DISPLAY.get(key, f"⌨ {key}")
        if bind.get("macro_interval_ms"):  return f"⟳ {base}"
        if bind.get("hold_while_pressed"): return f"⬇ {base}"
        return base
    if t == "sequence":
        return f"▶ ({len(bind['steps'])})"
    ...
```

### shutdown

Chamado pelo `WM_DELETE_WINDOW`. Sequência:

1. `_save_analog_config()` — persiste configurações de analógico
2. `_release_all_held_keys()` — para todas as macros e solta teclas presas
3. `listener.stop()` — para a thread de polling e libera o joystick
4. `pygame.quit()` — libera subsistemas pygame

---

## gui/bind_dialog.py

**Responsabilidade:** UI de configuração de um bind. Não persiste nada — retorna o `result` para quem a abriu.

### BindDialog

Dialog principal. Tem dois painéis em tabs (CTkTabview):

- **Teclado:** tecla/combo + duração + segurar/macro
- **Sequência:** editor de steps (linha do tempo)

O painel ativo ao abrir depende do tipo do bind existente (`_prefill`).

#### Captura de botão do controle

```python
def _capture_btn_into(self, entry: ctk.CTkEntry) -> None:
```

Spawna uma thread que faz polling do joystick (com pygame diretamente, não pelo ControllerListener) por até 10 s. Detecta a borda de subida do primeiro botão pressionado (incluindo gatilhos e HAT). Usa `dialog.after(0, ...)` para escrever o resultado no Entry.

#### Captura de tecla do teclado

Usa **pynput** `KeyListener`. O listener roda em thread separada. A lógica acumula modificadores em `active_mods: set[str]` e, ao detectar a tecla principal, monta o combo:

```python
parts = [m for m in _MOD_ORDER if m in active_mods] + [key_name]
combo = "+".join(parts)
# Exemplo: Ctrl+Shift pressionados → "D" → resultado: "ctrl+shift+d"
```

A ordem dos modificadores (`_MOD_ORDER = ["ctrl", "shift", "alt", "win"]`) garante strings canônicas consistentes.

#### Captura de botão de mouse

Usa **pynput** `MouseListener`. O `_mouse_map` mapeia constantes pynput para os nomes usados pelo JoyBind:

```python
_mouse_map = {
    Button.left:   "mouse_left",
    Button.right:  "mouse_right",
    Button.middle: "mouse_middle",
    Button.x1:     "mouse4",   # botão lateral traseiro
    Button.x2:     "mouse5",   # botão lateral dianteiro
}
```

Botões não mapeados resultam em `str(button)` (fallback seguro, não mapeia silenciosamente para um botão errado).

#### _MOUSE_KEYS frozenset

```python
_MOUSE_KEYS: frozenset[str] = frozenset({
    "mouse_left", "mouse_right", "mouse_middle",
    "mouse4", "mouse5",
    "scroll_up", "scroll_down",
})
```

Antes de salvar, o código valida se a tecla é reconhecida pelo pyautogui. Teclas de mouse não são nomes pyautogui válidos — o frozenset serve para bypas­sar essa validação para elas. Ao adicionar um novo tipo de botão de mouse, adicione-o aqui também.

#### Modo Macro vs Segurar: exclusão mútua

Os dois modos são incompatíveis porque:
- `hold_while_pressed`: chama `hold_down` (DOWN sem UP) — o OS recebe a tecla como pressionada continuamente
- `macro_interval_ms`: chama `execute_keyboard` (DOWN + UP) em loop — cada chamada é um press completo

Ter os dois ativos ao mesmo tempo resultaria em comportamento indefinido. A UI desativa `hold_while_pressed` automaticamente ao marcar Modo Macro (`_on_macro_toggle`), e no `_save` a lógica usa `if`/`elif` para garantir que apenas um vá para o JSON.

### SequenceDialog

Editor de linha do tempo. Cada linha é um "passo" (step) representado como um `CTkFrame` com widgets dinâmicos conforme o tipo de ação.

#### Captura de posição de mouse (para move_mouse)

```python
def _capture_pos_for_row(self, row_widgets: dict) -> None:
```

Spawna uma thread com contagem regressiva (5, 4, 3, 2, 1). O usuário posiciona o cursor durante a contagem. Ao chegar em 0, `pyautogui.position()` captura as coordenadas atuais e preenche os campos X e Y do passo.

---

## Arquitetura de threads

```
Thread principal (tkinter/CTk event loop)
│  Toda a UI vive aqui.
│  Regra: NUNCA chame widget.configure() de outra thread.
│  Use root.after(0, lambda: widget.configure(...)) de qualquer thread.
│
├─ Thread "JoyBind-Listener"  (daemon, pygame, 60 Hz)
│   │  Roda _poll_loop() continuamente.
│   │  Chama on_button_press / on_button_release / on_axes_update.
│   │  Morre automaticamente com o processo (daemon=True).
│   │
│   ├─ [spawna] Thread "Action-BTN{n}"  (daemon, por pressionamento)
│   │   Executa a ação mapeada (keyboard ou sequence).
│   │   Morre após a ação completar.
│   │
│   ├─ [spawna] Thread "Macro-BTN{n}"  (daemon, enquanto botão pressionado)
│   │   Loop: execute_keyboard + stop_event.wait(interval_ms).
│   │   Termina quando _on_button_release sinaliza o stop_event.
│   │
│   └─ [spawna] Thread "Release-BTN{n}"  (daemon, no release de hold)
│       Chama hold_up(key) e atualiza label.
│       Morre após soltar a tecla.
│
├─ Thread "SeqDir-{i}-{direction}"  (daemon, por borda de analógico)
│   execute_sequence(steps) — disparado uma vez ao cruzar o deadzone.
│   Morre após a sequência completar.
│
└─ Threads de captura (daemon, temporárias, em bind_dialog.py)
    Captura de botão, tecla ou posição de mouse durante configuração.
    Morrem após capturar ou timeout.
```

### Por que não reusar threads?

Criar uma nova thread por ação é simples e evita problemas de sincronização. O custo de criar uma thread no Python (GIL, overhead de ~1 ms) é desprezível comparado à duração de uma ação de teclado. Threads daemon morrem automaticamente quando o processo encerra, sem necessidade de join explícito na maioria dos casos.

---

## Camada de input Win32

### Por que ctypes em vez de uma biblioteca pronta?

Bibliotecas como `pyautogui` não expõem todos os campos do `SendInput` que precisamos (especialmente `mouseData` para wheel e XButtons, e os flags de virtual desktop para absoluto). Usar `ctypes` diretamente dá controle total sobre a estrutura `INPUT`.

### Estrutura _INPUT

```python
class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          ctypes.c_long),    # deslocamento X (relativo) ou posição (absoluto)
        ("dy",          ctypes.c_long),    # deslocamento Y
        ("mouseData",   ctypes.c_ulong),   # wheel delta ou XButton ID
        ("dwFlags",     ctypes.c_ulong),   # combinação de MOUSEEVENTF_* flags
        ("time",        ctypes.c_ulong),   # timestamp (0 = sistema preenche)
        ("dwExtraInfo", ctypes.c_size_t),  # ponteiro extra (0 = nenhum)
    ]

class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),  # INPUT_MOUSE = 0
        ("mi",   _MOUSEINPUT),
    ]
```

### Flags relevantes

| Flag | Valor | Uso |
|---|---|---|
| `MOUSEEVENTF_MOVE` | `0x0001` | Movimento relativo (analógico) |
| `MOUSEEVENTF_LEFTDOWN/UP` | `0x0002/0x0004` | Clique esquerdo |
| `MOUSEEVENTF_RIGHTDOWN/UP` | `0x0008/0x0010` | Clique direito |
| `MOUSEEVENTF_MIDDLEDOWN/UP` | `0x0020/0x0040` | Clique do meio |
| `MOUSEEVENTF_XDOWN/UP` | `0x0080/0x0100` | mouse4 (mouseData=1) e mouse5 (mouseData=2) |
| `MOUSEEVENTF_WHEEL` | `0x0800` | Scroll vertical (mouseData = ±120 por clique) |
| `MOUSEEVENTF_ABSOLUTE` | `0x8000` | Coordenada absoluta em dx/dy (0–65535) |
| `MOUSEEVENTF_VIRTUALDESK` | `0x4000` | Relativo ao desktop virtual completo (multi-monitor) |

---

## Sub-pixel accumulation

O analógico envia valores contínuos (float), mas `SendInput` aceita pixels inteiros. Se convertermos direto, movimentos lentos resultam em cursor parado (sempre arredonda para 0).

A solução é acumular a fração descartada:

```python
self._acc_x += dx_float   # acumula o movimento calculado
ix = int(self._acc_x)     # extrai a parte inteira
self._acc_x -= ix          # mantém o resto fracionário para o próximo frame
if ix != 0:
    actions.move_mouse_relative(ix, iy)
```

Com isso, um analógico na posição 30% de deflexão com `sensitivity=600` gera:
- `dx_float = 0.30 * 600 / 60 = 3.0 px/frame` → cursor move 3 px por frame
- Com `sensitivity=60` e deflexão 30%: `0.30 * 60 / 60 = 0.30 px/frame`
  - Frame 1: `acc=0.30`, `ix=0` → sem movimento
  - Frame 2: `acc=0.60`, `ix=0` → sem movimento
  - Frame 3: `acc=0.90`, `ix=0` → sem movimento
  - Frame 4: `acc=1.20`, `ix=1`, `acc=0.20` → move 1 px ✓

Isso garante movimento suave mesmo em sensibilidades baixas, sem stuttering.

---

## Gerenciamento de estado: o que vai aonde

| Dado | Onde fica | Por que |
|---|---|---|
| Mapeamentos de botões | `self.cfg["binds"]` (em memória) + preset `.json` | Configuração do usuário, persiste entre sessões |
| Layout visual (visual_id → btn_key) | `self._layout` (em memória) + `settings.json["btn_layout"]` | Específico do controle físico, não do preset |
| Teclas com hold ativo | `self._held_btn_keys` (dict em memória) | Estado de runtime, não persiste |
| Macros ativas | `self._macro_stop_events` (dict em memória) | Estado de runtime, não persiste |
| Teclas presas pelo analógico | `self._held_keys` (set em memória) | Estado de runtime, não persiste |
| Estado anterior do analógico | `self._prev_dir_active` (dict em memória) | Estado de runtime para edge detection |
| Acumuladores de sub-pixel | `self._acc_x/y/sv/sh` (float em memória) | Estado de runtime para interpolação |
| Último preset aberto | `settings.json["last_preset"]` | Persistido para restaurar na próxima abertura |
| Pasta de presets | `settings.json["presets_dir"]` | Configuração do app, não do preset |

**Regra de limpeza no shutdown:** `_release_all_held_keys()` itera sobre `_macro_stop_events` e `_held_btn_keys` para garantir que nenhuma tecla fique presa após fechar o programa. Isso é crítico porque o estado de teclas presas fica no OS, não no processo — se o processo morrer sem soltar, a tecla fica "travada" até o usuário pressionar fisicamente.
