# Changelog — JoyBind

Todas as mudanças notáveis do projeto são documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [v2.1.0] — 2026-03-04

### Adicionado

- **Internacionalização (EN/PT)** — toda a interface do JoyBind foi traduzida para inglês. O idioma é selecionável diretamente no cabeçalho da janela por dois botões `[EN]` `[PT]`; a troca salva a preferência e reinicia o aplicativo automaticamente.
- **Módulo `i18n.py`** — dicionários completos PT/EN com ~150 strings, função `t(key)` para tradução com suporte a formatação, funções auxiliares `kb_suggestions()`, `step_action_labels()` e `analog_type_opts()` para listas e dicionários sensíveis ao idioma.
- **Preferência de idioma persistida** — salva como chave `"language"` no `settings.json` via `%APPDATA%\JoyBind\`; padrão: inglês (`"en"`).

### Alterado

- Idioma padrão do aplicativo alterado de **Português** para **Inglês**.
- Strings de sugestões de teclas, rótulos de ações de sequência e opções de tipo analógico agora são instanciadas dinamicamente por diálogo (em vez de constantes de módulo), garantindo atualização correta ao trocar idioma.

---

## [v2.0.0] — 2026-02-28

Primeiro lançamento estável — versão oficial não pré-release.

Esta versão marca a maturidade do JoyBind: a interface ganhou novos controles de bind, o backend ficou compatível com emuladores exigentes, e surgiram dois modos de repetição automática independentes.

### Adicionado

- **Segurar enquanto pressionado** — mantém a tecla ou botão de mouse segurado enquanto o botão do controle estiver pressionado; solta automaticamente ao soltar o controle. Ideal para andar, mirar, ou qualquer ação contínua.
- **Modo Macro (auto-click por tecla)** — ao segurar o botão do controle, a ação de teclado ou mouse dispara repetidamente no intervalo configurado (ms). Mutuamente exclusivo com "Segurar enquanto pressionado". Parada imediata ao soltar via `threading.Event`.
- **Macro de Sequência** — sequências de ações também suportam modo macro: a sequência inteira repete em loop enquanto o botão do controle estiver pressionado. Checkbox + campo de intervalo no painel de sequência.
- **Scroll do mouse como bind** — `scroll_up` e `scroll_down` mapeáveis a botões do controle via `SendInput MOUSEEVENTF_WHEEL`. Compatível com modo macro para scroll contínuo.
- **Mouse4 e Mouse5 (botões laterais)** — botões laterais do mouse mapeáveis via `MOUSEEVENTF_XDOWN/XUP`; capturáveis no wizard "Capturar" via `pynput Button.x1/x2`.
- **Captura de scroll no wizard** — `scroll_up` e `scroll_down` agora são detectados pelo botão "Capturar" via callback `on_scroll` do pynput (antes apenas cliques eram detectados).
- **Tipo "Nenhuma"** — permite mapear um botão do controle sem vincular nenhuma ação; tile exibe `—` em vez de ficar vazio.
- **Botão "Limpar" no BindDialog** — remove o bind e a entrada de layout do botão com um clique, sem precisar reconfigurar o preset inteiro.
- **Botão "Mapear botão" no BindDialog** — captura o índice do botão físico do controle diretamente dentro da janela de bind, sem precisar sair para o wizard separado.
- **Prefixos nos tiles** — `⟳` para Modo Macro, `⬇` para "Segurar enquanto pressionado", `—` para tipo "Nenhuma".
- **Painel do controle** — nova imagem do painel traseiro do controle (`img/painel.png`).
- **Labels dos analógicos** renomeados para "Analógico Esquerdo" e "Analógico Direito"; retrocompatibilidade automática com presets criados em versões anteriores.

### Corrigido

- **Compatibilidade com emuladores** — cliques e movimentos de mouse agora usam `SendInput` com `WM_MOUSEMOVE` e `hold_ms` (padrão 50 ms); resolve input ignorado em emuladores Qt como Citra, RetroArch e outros que processam input a cada frame (~16 ms).
- **Release de botão** — `on_button_release` implementado para botões digitais, gatilhos analógicos (L2/R2 via threshold) e HAT switches (D-pad); necessário para "Segurar enquanto pressionado" e parada de macros funcionarem corretamente.
- **Tile "mapeado" para tipo Nenhuma** — tile agora exibe `"—"` corretamente (antes exibia `"mapeado"`).
- **Botão "Limpar" remove entrada de layout** — antes removia apenas o bind do `binds` mas deixava a entrada em `layout`, causando inconsistência no `settings.json`.

### Documentação

- README reescrito como landing page: screenshot da interface, botão de download em destaque, seção de casos de uso (Minecraft, emuladores, God of War 2, mouse4/mouse5, scroll, navegação no PC), tabela de ícones dos tiles.
- `docs/ARCHITECTURE.md` criado — documentação técnica de cada módulo, fluxo completo de uma ação (botão → SendInput → Raw Input), camada Win32 detalhada, sub-pixel accumulation, arquitetura de threads com diagrama ASCII.
- `docs/CONTRIBUTING.md` atualizado — tabela de campos opcionais de bind (`hold_while_pressed`, `macro_interval_ms`), tabela de teclas de mouse válidas, diagrama de threads atualizado, guia "Como adicionar um novo botão/tecla de mouse".
- `CHANGELOG.md` criado com histórico completo baseado nas tags reais do repositório.

### Commits

- `ba9f858` fix: SendInput com WM_MOUSEMOVE e hold_ms para compatibilidade com emuladores
- `8f2daf3` feat: BindDialog com Limpar, Mapear botão, tipo Nenhuma e layout grid no footer
- `ee3ee3f` fix: labels analógicos completos e suporte a clear_result e tipo none
- `b2b2a20` feat: hold while pressed + on_button_release + img painel
- `1b01082` feat: scroll/mouse4/mouse5 como bind, modo macro e fix tile none
- `27017ad` docs: landing page, ARCHITECTURE.md, CONTRIBUTING atualizado, CHANGELOG
- `a3fd5fe` docs(changelog): adiciona hashes dos commits ao [Não lançado]
- `5fde5d1` feat: macro de sequência e captura de scroll no Capturar

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
