# Changelog — JoyBind

Todas as mudanças notáveis do projeto são documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [Não lançado]

### Adicionado
- **Scroll do mouse como bind de botão** — `scroll_up` e `scroll_down` podem ser mapeados diretamente a botões do controle (ex: trocar hotbar no Minecraft). Usa `SendInput` com `MOUSEEVENTF_WHEEL` (WHEEL_DELTA = 120).
- **Mouse4 e Mouse5 (botões laterais)** — botões laterais do mouse mapeáveis via `MOUSEEVENTF_XDOWN/XUP`. Capturáveis no wizard via `pynput Button.x1` / `Button.x2`.
- **Modo Macro (auto-click)** — ao manter o botão do controle pressionado, a ação dispara repetidamente no intervalo configurado em ms. Mutuamente exclusivo com "Segurar enquanto pressionado". Usa `threading.Event.wait()` para parada imediata ao soltar.
- Tile do layout exibe prefixo `⟳` para binds em Modo Macro e `⬇` para "Segurar enquanto pressionado".

### Corrigido
- Tile exibia `"mapeado"` ao salvar um bind com tipo "Nenhuma" — agora exibe `"—"` consistentemente.

### Documentação
- README reescrito como landing page para usuários: screenshot da interface, botão de download em destaque, seção de casos de uso (Minecraft, emuladores, GOW2, navegação no PC).
- `docs/ARCHITECTURE.md` criado: documentação técnica de cada arquivo, fluxo de uma ação do botão ao OS, decisões de design, camada Win32, sub-pixel accumulation, arquitetura de threads.
- `docs/CONTRIBUTING.md` atualizado com novos campos de bind e seção "Como adicionar um novo botão/tecla de mouse".
- `CHANGELOG.md` criado.

---

## [v1.1.1] — 2026-02-23

### Adicionado
- **Botão Apagar preset** na barra de presets — remove o arquivo `.json` com confirmação.

### Corrigido
- Ícone da janela gerado com LANCZOS e `append_images` — elimina desfoque no tamanho 16×16.
- Build do `.exe`: logo.ico embutido no executável e processo de build auto-elevado via UAC para bypass do Defender.

---

## [v1.1.0] — 2026-02-23

### Adicionado
- **Modo por stick independente** — cada analógico tem seu modo configurável separadamente: esquerdo (mouse / game / manual), direito (scroll / game / manual).
- **Modo Game** — analógico esquerdo em modo game aciona WASD com edge-detection; analógico direito em modo game move o cursor (câmera).
- **Captura de clique de mouse no BindDialog** — detecta `mouse_left`, `mouse_right`, `mouse_middle` via `pynput MouseListener`.
- **Dropdown de sugestões** de teclas populares no BindDialog (Enter, Espaço, setas, F1–F12, combos comuns, mídia).
- **Ícone do programa** (`img/logo.png`) — aplicado no titlebar e na barra de tarefas via `AppUserModelID + WM_SETICON`; imagem exibida no header da janela.
- Script de build (`scripts/`) e spec do PyInstaller para gerar `.exe` standalone.

### Alterado
- Labels dos botões migrados de PlayStation (○△□×, L1/L2/R1/R2) para **Xbox** (A/B/X/Y, LB/LT/RB/RT).
- Dados do usuário (`settings.json` e pasta de presets) movidos para `%APPDATA%\JoyBind\`.

### Corrigido
- **Movimento de mouse** agora usa `SendInput` com `MOUSEEVENTF_MOVE` relativo — compatível com Raw Input de jogos como Minecraft, que ignoravam `SetCursorPos`.
- Stuttering visual ao rolar o layout eliminado com debounce nas atualizações.
- Caminho de presets e `settings.json` corrigido no executável compilado.

---

## [v1.0.0] — 2026-02-23

Primeira versão pública.

### Adicionado
- **Core backend**:
  - `core/controller.py` — `ControllerListener`: polling de joystick a 60 Hz em thread daemon, detecção de borda de subida por botão, sem dependência de display pygame.
  - `core/actions.py` — `execute_keyboard` (teclas e combos `ctrl+c`), `execute_sequence` (timeline de passos).
  - `core/presets.py` — sistema de presets nomeados com arquivos `.json` independentes; escrita atômica via `.tmp` + rename.
- **Interface gráfica** — janela principal com dropdown de controle, botão Iniciar/Parar Escuta e indicador de status.
- **BindDialog** — diálogo modal para criar/editar binds:
  - Painel Teclado: tecla simples, combo com `+`, botão **Capturar** (pynput KeyListener com acumulação de modificadores).
  - Painel Sequência: editor de linha do tempo com `move_mouse`, `click_*`, `scroll_up/down`, `key`, `delay`; captura de posição de mouse com contagem regressiva; reordenação de passos com ↑/↓.
  - Captura de botão do controle via polling pygame.
- **Layout visual de gamepad** — silhueta do controle com tiles clicáveis substituindo lista tabular de binds.
- **Layout configurável** — cada tile pode ser associado a qualquer índice de botão físico, persistido em `settings.json`.
- **Wizard Auto-mapear** — percorre cada tile em sequência e detecta o botão físico pressionado (timeout de 15 s por tile, botão Pular).
- **Suporte a L2/R2 analógicos** — detectados como botões virtuais 100/101 ao cruzar threshold de 0,5.
- **Suporte a D-pad via HAT switch** — direções mapeadas como botões virtuais 102–105 (↑↓←→).
- **Analógicos**:
  - Analógico esquerdo como mouse (movimento relativo, sub-pixel accumulation).
  - Analógico direito como scroll vertical/horizontal em modo mouse.
  - Modo manual por direção: `mouse_x/y`, `scroll_v/h`, `key` (segurar ~15×/s), `sequence` (disparar na borda de entrada).
  - Deadzone e sensibilidade configuráveis por stick.
- Scrollbar horizontal na área do layout do controle.
- Botão de feedback (abre página de issues do GitHub).
- Documentação inicial: README e `docs/CONTRIBUTING.md`.
