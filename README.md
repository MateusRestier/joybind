<div align="center">

# JoyBind

**Mapeie qualquer controle (joystick/gamepad) para teclado e mouse no Windows — sem instalar drivers**

[![Download Latest Release](https://img.shields.io/badge/⬇%20Download-Última%20Versão-0078D6?style=for-the-badge&logo=github)](https://github.com/MateusRestier/joybind/releases)

</div>

---

<div align="center">
<img src="img/painel.png" alt="Interface do JoyBind" width="820">
</div>

---

## O que é o JoyBind?

O JoyBind transforma qualquer controle USB ou Bluetooth em teclado e mouse completo no Windows. Conecte o controle, configure os botões pela interface visual e clique em **Iniciar Escuta** — pronto.

Nenhum driver especial. Funciona com qualquer jogo ou programa que aceite teclado e mouse.

---

## Casos de uso

| Cenário | Exemplo de configuração |
|---|---|
| **Minecraft** | Analógico esquerdo → mouse, botões → hotbar (`1`–`9`), pulo (`space`), inventário (`e`); scroll do inventário com `scroll_up` / `scroll_down` |
| **Emuladores (PCSX2, RPCS3, Dolphin...)** | Jogue títulos sem suporte nativo a controle, mapeando cliques e movimentos de mouse a botões físicos |
| **GOW2 / cliques rápidos** | *Modo Macro*: segure um botão e ele dispara cliques automaticamente no intervalo que você definir (ex: 60 ms) |
| **Botões laterais do mouse** | Mapeie `mouse4` e `mouse5` (botões laterais do mouse) a botões do controle |
| **Navegação no PC** | Use o controle como mouse completo para streaming, YouTube e navegação geral sem sair do sofá |

---

## Download e Instalação

### Executável pronto para uso *(recomendado)*

Baixe o `.exe` na página de releases — não requer Python instalado:

<div align="center">

[![Download Latest Release](https://img.shields.io/badge/⬇%20Download-Última%20Versão-0078D6?style=for-the-badge&logo=github)](https://github.com/MateusRestier/joybind/releases)

</div>

### Via código-fonte

Requer Python 3.11+ e Windows 10/11:

```bash
git clone https://github.com/MateusRestier/joybind.git
cd joybind
pip install -r requirements.txt
python main.py
```

#### Dependências

| Pacote | Versão mínima | Uso |
|---|---|---|
| `customtkinter` | 5.2.0 | Interface gráfica moderna |
| `pygame` | 2.5.0 | Leitura de joystick/gamepad |
| `pyautogui` | 0.9.54 | Simulação de teclado e mouse |
| `pynput` | 1.7.6 | Captura de teclas no wizard de bind |

---

## Como usar

1. Conecte o controle antes de abrir o programa (ou clique **↻** após conectar)
2. Selecione o controle no dropdown **Controle**
3. Clique em qualquer tile do layout visual para configurar o mapeamento
4. Feche o diálogo — a configuração é salva automaticamente no preset ativo
5. Clique em **Iniciar Escuta** e comece a usar

---

## Funcionalidades

- **Mapeamento de botões** — associa cada botão físico a:
  - Tecla simples ou combinação (`enter`, `f5`, `ctrl+z`, ...)
  - Botões de mouse, incluindo laterais (`mouse4`, `mouse5`) e scroll (`scroll_up`, `scroll_down`)
  - Sequência de ações com temporização (mover cursor, clicar, pressionar tecla, aguardar)
- **Segurar enquanto pressionado** — mantém a tecla pressionada enquanto o botão físico estiver segurado (ideal para correr em jogos)
- **Modo Macro (auto-click)** — dispara a ação repetidamente no intervalo definido em ms enquanto o botão estiver pressionado
- **Analógico como mouse** — o analógico esquerdo controla o cursor com sensibilidade configurável
- **Analógico como scroll** — o analógico direito rola a página vertical e horizontalmente
- **Modo manual de analógico** — mapeia cada direção (↑↓←→) de cada analógico a uma tecla, combo ou sequência
- **Presets** — salva e carrega configurações nomeadas; troca sem reiniciar
- **Layout visual de gamepad** — silhueta do controle com todos os botões clicáveis
- **Captura automática** — detecta o botão físico ou tecla ao pressionar, sem digitar índices manualmente

---

## Configuração de Botões

Clique em qualquer tile do layout visual para abrir o diálogo de configuração. O tile exibe um ícone conforme o modo:

| Ícone | Significado |
|---|---|
| `⌨ tecla` | Tecla simples (press e release) |
| `⬇ tecla` | Segurar enquanto pressionado |
| `⟳ tecla` | Modo Macro (auto-click) |
| `▶` | Sequência de ações |
| `—` | Sem mapeamento |

### Tipo: Teclado

Pressiona e solta uma tecla, combinação ou botão de mouse.

| Opção | Descrição |
|---|---|
| **Tecla** | Nome da tecla (ex: `enter`, `f5`, `ctrl+z`) ou botão de mouse (ver tabela abaixo) |
| **Duração (ms)** | Tempo entre press e release (0 = instantâneo) |
| **Segurar enquanto pressionado** | Mantém a tecla pressionada enquanto o botão do controle estiver segurado |
| **Modo Macro** | Dispara a tecla repetidamente no intervalo definido (ms) enquanto o botão estiver pressionado |

Use o botão **Capturar** para detectar a tecla ou botão de mouse automaticamente — inclusive `mouse4` e `mouse5`.

**Teclas de mouse disponíveis:**

| Valor | Ação |
|---|---|
| `mouse_left` | Clique esquerdo |
| `mouse_right` | Clique direito |
| `mouse_middle` | Clique do meio |
| `mouse4` | Botão lateral traseiro |
| `mouse5` | Botão lateral dianteiro |
| `scroll_up` | Rolar para cima (1 clique de roda) |
| `scroll_down` | Rolar para baixo (1 clique de roda) |

> Para scroll contínuo ao segurar um botão, use *Modo Macro* com `scroll_up` ou `scroll_down` e um intervalo curto (ex: 80 ms).

### Tipo: Sequência de Ações

Executa uma lista ordenada de passos. Útil para macros complexas com múltiplos cliques, movimentos de mouse e esperas.

| Ação | Parâmetros | Descrição |
|---|---|---|
| `move_mouse` | X, Y, Salvar/Restaurar | Teleporta o cursor para a posição |
| `click_left` | — | Clique esquerdo na posição atual |
| `click_right` | — | Clique direito na posição atual |
| `click_middle` | — | Clique do meio na posição atual |
| `double_click` | — | Clique duplo na posição atual |
| `scroll_up` | Cliques (padrão 3) | Rola para cima |
| `scroll_down` | Cliques (padrão 3) | Rola para baixo |
| `key` | Nome da tecla | Pressiona e solta uma tecla |
| `delay` | Milissegundos (padrão 100) | Pausa entre passos |

> **Salvar/Restaurar posição:** quando ativado em um passo `move_mouse`, o cursor retorna ao ponto de origem ao final da sequência — ideal para clicar em elementos fixos da tela sem perder a posição de trabalho.

---

## Configuração Analógica

Ative com o toggle **Mouse Mode** na seção central do layout.

### Modo Mouse (ativado)

| Analógico | Comportamento |
|---|---|
| Esquerdo (eixos 0/1) | Move o cursor — sensibilidade em px/s |
| Direito (eixos 2/3) | Rola a página — sensibilidade em cl/s |

### Modo Manual (desativado)

Cada direção de cada analógico pode ser mapeada independentemente para:

| Tipo | Parâmetros extras | Descrição |
|---|---|---|
| `none` | — | Sem ação |
| `mouse_x` | `sensitivity` (px/s) | Move o cursor horizontalmente |
| `mouse_y` | `sensitivity` (px/s) | Move o cursor verticalmente |
| `scroll_v` | `sensitivity` (cl/s) | Rola vertical |
| `scroll_h` | `sensitivity` (cl/s) | Rola horizontal |
| `key` | `key` (nome da tecla ou combo `ctrl+c`) | Repete a tecla/combo enquanto o analógico está ativo (~15×/s) |
| `sequence` | `steps` (lista de passos) | Dispara a sequência uma vez ao cruzar o limite de deflexão |

### Parâmetros por analógico

| Campo | Descrição |
|---|---|
| **Eixo X** | Índice pygame do eixo horizontal |
| **Eixo Y** | Índice pygame do eixo vertical |
| **DZ** | Deadzone — fração da deflexão máxima ignorada (0.0–0.99) |
| **Sens.** | Sensibilidade em px/s (mouse) ou cl/s (scroll) |

> **Encontrando os eixos:** ative o listener, mova o analógico e observe os prints no console — os eixos com maior variação são os corretos.

---

## Sistema de Presets

Cada preset é um arquivo `.json` independente. A pasta de presets pode ser alterada pelo botão **Pasta...**.

| Operação | Como fazer |
|---|---|
| Criar novo preset | Botão **Novo** → insira o nome |
| Trocar de preset | Dropdown **Preset** |
| Salvar alteração | Automático ao fechar diálogos de configuração |
| Mudar pasta | **Pasta...** → escolha o diretório |

O último preset aberto é lembrado entre sessões.

---

## Formato dos Presets (JSON)

```jsonc
{
  "binds": {
    // Tecla simples: botão 0 → Enter
    "0": { "type": "keyboard", "key": "enter" },

    // Segurar enquanto pressionado: botão 1 → Shift segurado
    "1": { "type": "keyboard", "key": "shift", "hold_while_pressed": true },

    // Modo Macro: botão 2 → clique esquerdo a cada 60 ms enquanto pressionado
    "2": { "type": "keyboard", "key": "mouse_left", "macro_interval_ms": 60 },

    // Scroll para cima via botão do controle
    "4": { "type": "keyboard", "key": "scroll_up" },

    // Botão lateral do mouse (mouse4)
    "5": { "type": "keyboard", "key": "mouse4" },

    // Sequência: botão 3 → move mouse, clica e pressiona F5
    "3": {
      "type": "sequence",
      "steps": [
        { "action": "move_mouse", "x": 960, "y": 540, "save_restore": true },
        { "action": "click_left" },
        { "action": "delay", "ms": 200 },
        { "action": "key", "key": "f5" }
      ]
    }
  },

  "analog": {
    // true = modo mouse (esq→cursor, dir→scroll); false = modo manual por direção
    "enabled": true,

    "sticks": [
      {
        "label": "Esquerdo", "axis_x": 0, "axis_y": 1,
        "deadzone": 0.15, "sensitivity": 600.0,
        "up":    { "type": "mouse_y", "sensitivity": 600 },
        "down":  { "type": "mouse_y", "sensitivity": 600 },
        "left":  { "type": "mouse_x", "sensitivity": 600 },
        "right": { "type": "mouse_x", "sensitivity": 600 }
      },
      {
        "label": "Direito", "axis_x": 2, "axis_y": 3,
        "deadzone": 0.15, "sensitivity": 10000.0,
        "up":    { "type": "key",      "key": "w" },
        "down":  { "type": "key",      "key": "ctrl+z" },
        "left":  { "type": "scroll_h", "sensitivity": 8 },
        "right": { "type": "sequence", "steps": [{ "action": "key", "key": "ctrl+tab" }] }
      }
    ]
  }
}
```

---

## Observações

- **FailSafe:** mova o mouse para o canto superior esquerdo da tela para abortar qualquer sequência em execução (comportamento padrão do pyautogui).
- **Scroll horizontal:** implementado via `Shift + scroll` para máxima compatibilidade com aplicativos Windows (Chrome, VS Code, Office, etc.).
- **Raw Input / jogos:** botões de mouse e scroll usam `SendInput` do Windows, garantindo compatibilidade com jogos que leem input por Raw Input.
- **Eixos com valores "diagonais":** alguns controles mapeiam eixos em 45°. Se o analógico responder de forma incorreta, troque os valores de Eixo X e Eixo Y ou use sensibilidade negativa para inverter o sinal.

---

## Solução de Problemas

### Controle não aparece no dropdown

1. Conecte o controle **antes** de abrir o programa, ou clique **↻** após conectar.
2. Verifique se o controle é reconhecido pelo Windows (Painel de Controle → Dispositivos de Jogo).
3. Alguns controles Bluetooth requerem alguns segundos após o pareamento.
4. Se o controle aparece com nome genérico ("Controle #0"), ainda funcionará normalmente para leitura de botões e eixos.

### Botão não responde ao pressionar

- Confirme que **Iniciar Escuta** está ativo (indicador verde).
- O índice configurado pode não corresponder ao botão físico — use **Capturar** no diálogo para detectar o índice correto.
- Pressione o botão por pelo menos 50 ms (o polling roda a 60 Hz ≈ 16 ms por frame).

### Ações de teclado não funcionam no jogo/aplicativo

- Execute o JoyBind como **Administrador**.
- Para jogos com anti-cheat, o mapeamento via software pode ser bloqueado por design.

### Analógico move o mouse de forma errática ou invertida

- Verifique os índices **Eixo X** e **Eixo Y** — troque-os se os eixos estiverem invertidos.
- Aumente o valor de **DZ** (deadzone) se o cursor se mover com o analógico solto.
- Sensibilidade negativa inverte a direção do eixo.
- Ative o listener e mova o analógico — o console exibe os valores brutos para diagnóstico.

### Sequência interrompida no meio

- O mouse pode ter atingido o canto superior esquerdo da tela (FailSafe do pyautogui). Desative com `pyautogui.FAILSAFE = False` em `actions.py` se necessário.
- Verifique se algum passo tem `delay` muito longo.

### Preset não salva / arquivo corrompido

- O programa salva com escrita atômica (`.tmp` → `rename`). Verifique se a pasta tem permissão de escrita.
- Se `settings.json` sumir, o programa recria com os padrões ao abrir.

---

## Referência de Nomes de Teclas

Utilize os nomes abaixo nos campos de tecla. Compatíveis com o pyautogui.

### Teclas especiais

| Nome | Tecla |
|---|---|
| `enter` | Enter / Return |
| `space` | Barra de espaço |
| `tab` | Tab |
| `backspace` | Backspace |
| `delete` | Delete |
| `escape` | Escape |
| `up` / `down` / `left` / `right` | Setas direcionais |
| `home` / `end` | Home / End |
| `pageup` / `pagedown` | Page Up / Page Down |
| `insert` | Insert |
| `f1` … `f12` | Teclas de função |
| `printscreen` | Print Screen |
| `scrolllock` | Scroll Lock |
| `pause` | Pause/Break |
| `capslock` | Caps Lock |
| `numlock` | Num Lock |

### Modificadores

| Nome | Tecla |
|---|---|
| `ctrl` / `ctrlleft` / `ctrlright` | Control |
| `shift` / `shiftleft` / `shiftright` | Shift |
| `alt` / `altleft` / `altright` | Alt |
| `win` | Windows / Super |

### Teclado numérico

| Nome | Tecla |
|---|---|
| `num0` … `num9` | Numpad 0–9 |
| `add` | Numpad + |
| `subtract` | Numpad − |
| `multiply` | Numpad × |
| `divide` | Numpad ÷ |
| `decimal` | Numpad . |
| `numpadenter` | Numpad Enter |

### Combos

Combine modificadores com `+`:

```
ctrl+c          → Copiar
ctrl+shift+esc  → Gerenciador de tarefas
alt+f4          → Fechar janela
win+d           → Mostrar área de trabalho
ctrl+alt+delete → (funciona apenas parcialmente via software)
```

> **Dica:** use o botão **Capturar** no diálogo de bind para detectar o nome correto automaticamente ao pressionar a tecla desejada.

---

## Para Desenvolvedores

- [CHANGELOG.md](CHANGELOG.md) — histórico de versões e mudanças
- [CONTRIBUTING.md](docs/CONTRIBUTING.md) — convenções de código, formato de preset, guias de extensão
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — como cada arquivo funciona, por que as decisões foram tomadas, fluxo completo de uma ação do botão ao OS
