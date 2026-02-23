# JoyBind

Mapeador de controle (joystick/gamepad) para teclado e mouse no Windows.
Conecte qualquer controle USB ou Bluetooth e associe cada botão a uma tecla, combinação, sequência de ações ou movimento de mouse — tudo sem instalar drivers.

---

## Funcionalidades

- **Mapeamento de botões** — associa qualquer botão físico a:
  - Uma tecla simples (`enter`, `f5`, `ctrl+z`, etc.)
  - Uma sequência de ações com temporização (mover mouse, clicar, pressionar tecla, aguardar, rolar)
- **Analógico como mouse** — o analógico esquerdo controla o cursor com sensibilidade configurável
- **Analógico como scroll** — o analógico direito rola a página vertical e horizontalmente
- **Modo manual de analógico** — mapeia cada direção (↑↓←→) de cada analógico a uma tecla, combo ou sequência
- **Presets** — salva e carrega configurações nomeadas; troca de preset sem reiniciar
- **Layout visual de gamepad** — todos os botões exibidos como silhueta do controle; clique no botão para configurar
- **Captura de botão** — detecta automaticamente qual botão físico foi pressionado ao configurar
- **Captura de posição de mouse** — grava a posição XY do cursor com contagem regressiva para uso em sequências
- **Salvamento atômico** — sem risco de corrupção de arquivo em caso de queda

---

## Pré-requisitos

- Python 3.11+
- Windows 10/11

---

## Instalação

```bash
git clone <url-do-repo>
cd joybind
pip install -r requirements.txt
```

### Dependências

| Pacote | Versão mínima | Uso |
|---|---|---|
| `customtkinter` | 5.2.0 | Interface gráfica moderna |
| `pygame` | 2.5.0 | Leitura de joystick/gamepad |
| `pyautogui` | 0.9.54 | Simulação de teclado e mouse |
| `pynput` | 1.7.6 | Captura de teclas no wizard de bind |

---

## Uso

```bash
python main.py
```

### Fluxo básico

1. Conecte o controle antes de abrir o programa (ou use o botão **↻** para redetectar)
2. Selecione o controle no dropdown **Controle**
3. Clique em um botão do layout visual para configurar o mapeamento
4. Clique em **Iniciar Escuta** — o programa começa a interceptar os inputs
5. Pressione os botões físicos; as ações são executadas em background

---

## Configuração de Botões

Clique em qualquer tile do layout visual de gamepad para abrir o diálogo de configuração.

### Tipo: Teclado

Pressiona e solta uma tecla ou combinação de teclas.

| Campo | Exemplo | Descrição |
|---|---|---|
| Tecla | `enter` | Nome pyautogui da tecla |
| Tecla | `ctrl+z` | Combinação separada por `+` |

Use o botão **Capturar** para detectar a tecla diretamente do teclado.

### Tipo: Sequência de Ações

Executa uma lista ordenada de passos. Útil para macros complexas.

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
    // Bind simples: botão 0 → tecla Enter
    "0": { "type": "keyboard", "key": "enter" },

    // Bind sequência: botão 3 → move mouse, clica e pressiona F5
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
        // Analógico esquerdo como mouse (modo mouse ativo)
        "label": "Esquerdo", "axis_x": 0, "axis_y": 1,
        "deadzone": 0.15, "sensitivity": 600.0,
        "up":    { "type": "mouse_y", "sensitivity": 600 },
        "down":  { "type": "mouse_y", "sensitivity": 600 },
        "left":  { "type": "mouse_x", "sensitivity": 600 },
        "right": { "type": "mouse_x", "sensitivity": 600 }
      },

      {
        // Analógico direito em modo manual com tipos variados
        "label": "Direito", "axis_x": 2, "axis_y": 3,
        "deadzone": 0.15, "sensitivity": 10000.0,

        // Tecla simples — repete ~15×/s enquanto o analógico estiver ativo
        "up":    { "type": "key", "key": "w" },

        // Combo de teclas — mesma sintaxe, separe com "+"
        "down":  { "type": "key", "key": "ctrl+z" },

        // Scroll horizontal via pyautogui (Shift+scroll internamente)
        "left":  { "type": "scroll_h", "sensitivity": 8 },

        // Sequência — dispara UMA VEZ ao cruzar o deadzone (borda de entrada)
        "right": {
          "type": "sequence",
          "steps": [
            { "action": "key", "key": "ctrl+tab" }
          ]
        }
      }
    ]
  }
}
```

---

## Observações

- **FailSafe:** mova o mouse para o canto superior esquerdo da tela para abortar qualquer sequência em execução (comportamento padrão do pyautogui).
- **Scroll horizontal:** implementado via `Shift + scroll` para máxima compatibilidade com aplicativos Windows (Chrome, VS Code, Office, etc.).
- **Eixos com valores "diagonais":** alguns controles mapeiam eixos em 45°. Se o analógico direito responder de forma incorreta, troque os valores de Eixo X e Eixo Y ou inverta o sinal de sensibilidade.

---

## Solução de Problemas

### Controle não aparece no dropdown

1. Conecte o controle **antes** de abrir o programa, ou clique em **↻** após conectar.
2. Verifique se o controle é reconhecido pelo Windows (Painel de Controle → Dispositivos de Jogo).
3. Alguns controles Bluetooth requerem alguns segundos para aparecer após pareamento.
4. Se o controle aparece mas com nome genérico ("Controle #0"), o pygame pode não ter o driver completo; ainda funcionará para leitura de botões e eixos.

### Botão não responde ao pressionar

- Confirme que **Iniciar Escuta** está ativo (indicador verde).
- O número do botão configurado pode não corresponder ao botão físico. Abra o diálogo de configuração e use **Capturar** com o botão pressionado para detectar o índice correto.
- Pressionar e soltar rapidamente pode falhar se o polling (60 Hz ≈ 16 ms) não capturar a borda. Pressione o botão por pelo menos 50 ms.

### Ações de teclado não funcionam no jogo/aplicativo

- Algumas aplicações usam hooks de baixo nível que ignoram `pyautogui`. Tente executar o JoyBind como Administrador.
- Para jogos com anti-cheat, o mapeamento via software pode ser bloqueado por design.

### Analógico move o mouse de forma errática ou invertida

- Verifique os índices **Eixo X** e **Eixo Y** — troque-os se os eixos estiverem invertidos.
- Aumente o valor de **DZ** (deadzone) se o cursor se mover mesmo com o analógico solto.
- Se o eixo estiver espelhado (esquerda/direita trocadas), defina sensibilidade negativa no campo correspondente.
- Ative o listener e mova o analógico — o console exibe os valores brutos dos eixos para diagnóstico.

### Sequência interrompida no meio

- O mouse pode ter atingido o canto superior esquerdo da tela (FailSafe do pyautogui). Desative o FailSafe com cuidado se necessário — adicione `pyautogui.FAILSAFE = False` em `actions.py`.
- Um passo com `delay` muito longo pode parecer que travou. Verifique o valor de `ms`.

### Preset não salva / arquivo corrompido

- O programa salva automaticamente usando escrita atômica (arquivo `.tmp` → `rename`). Se `settings.json` sumir, o programa recria com os padrões ao abrir.
- Verifique se a pasta de presets tem permissão de escrita.

---

## Referência de Nomes de Teclas

Utilize os nomes abaixo nos campos de tecla. Eles são compatíveis com o pyautogui.

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



Consulte o [CONTRIBUTING.md](docs/CONTRIBUTING.md) para informações sobre arquitetura, estrutura do projeto, convenções de código e como estender o JoyBind.

