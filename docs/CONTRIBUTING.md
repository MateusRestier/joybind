# Guia para Desenvolvedores — JoyBind

Documentação técnica do projeto: arquitetura, estrutura do código, convenções e como estender o JoyBind.

Para o guia do usuário final, consulte o [README.md](../README.md).

---

## Formato do arquivo de preset (JSON)

Cada preset é um `.json` com a seguinte estrutura completa:

```jsonc
{
  "binds": {
    // chave = índice do botão como string; valor = objeto de bind
    "0": { "type": "keyboard", "key": "enter" },
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
    "enabled": true,           // true = modo mouse; false = modo manual
    "sticks": [
      {
        "label": "Esquerdo",
        "axis_x": 0,           // índice pygame do eixo horizontal
        "axis_y": 1,           // índice pygame do eixo vertical
        "deadzone": 0.15,      // zona morta [0.0, 0.99]
        "sensitivity": 600.0,  // px/s (mouse) ou cl/s (scroll)
        "up":    { "type": "mouse_y", "sensitivity": 600 },
        "down":  { "type": "mouse_y", "sensitivity": 600 },
        "left":  { "type": "mouse_x", "sensitivity": 600 },
        "right": { "type": "mouse_x", "sensitivity": 600 }
      },
      {
        "label": "Direito",
        "axis_x": 2, "axis_y": 3,
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

**Tipos de bind de botão:**

| `type` | Campos obrigatórios | Descrição |
|---|---|---|
| `keyboard` | `key` | Pressiona e solta uma tecla/combo |
| `sequence` | `steps` | Executa lista ordenada de passos |

**Ações de sequência (`steps[].action`):**

| Ação | Campos | Descrição |
|---|---|---|
| `move_mouse` | `x`, `y`, `save_restore` | Teleporta o cursor; restaura posição ao fim se `save_restore: true` |
| `click_left` / `click_right` / `click_middle` | — | Clique na posição atual |
| `double_click` | — | Clique duplo |
| `scroll_up` / `scroll_down` | `clicks` (padrão 3) | Rola a página |
| `key` | `key` | Pressiona e solta tecla/combo |
| `delay` | `ms` (padrão 100) | Pausa em milissegundos |

**Tipos de direção analógica (`sticks[].{up,down,left,right}.type`):**

| Tipo | Campos extras | Comportamento |
|---|---|---|
| `none` | — | Sem ação |
| `mouse_x` / `mouse_y` | `sensitivity` (px/s) | Move cursor |
| `scroll_v` / `scroll_h` | `sensitivity` (cl/s) | Rola página |
| `key` | `key` | Repete tecla/combo enquanto ativo (~15×/s) |
| `sequence` | `steps` | Dispara sequência na borda de entrada |

---

## Configuração do ambiente

### Pré-requisitos

- Python 3.11+
- Windows 10/11 (o projeto usa APIs específicas do Windows via pyautogui)
- Git

### Setup

```bash
git clone <url-do-repo>
cd joybind

# Ambiente virtual (recomendado)
python -m venv .venv
.venv\Scripts\activate

# Dependências
pip install -r requirements.txt

# Executar
python main.py
```

---

## Estrutura do projeto

```
joybind/
├── core/
│   ├── __init__.py
│   ├── controller.py      # Thread de polling do joystick (pygame, 60 Hz)
│   ├── actions.py         # Execução de ações (pyautogui)
│   ├── presets.py         # Gerenciamento de presets e settings.json
│   └── config.py          # Compatibilidade com config.json legado
├── gui/
│   ├── __init__.py
│   ├── app.py             # Janela principal (UI + lógica de analógico)
│   └── bind_dialog.py     # Diálogos modais de configuração
├── docs/
│   └── CONTRIBUTING.md    # Este arquivo
├── presets/
│   └── default.json       # Preset padrão incluído no repositório
├── main.py                # Ponto de entrada
└── requirements.txt
```

### Responsabilidades por camada

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | Bootstrap: pygame, CTk, janela, shutdown |
| `core/controller.py` | Hardware → callbacks (sem dependência de GUI ou ações) |
| `core/actions.py` | pyautogui → teclado/mouse (sem dependência de GUI ou controller) |
| `core/presets.py` | JSON → disco (sem dependência de GUI) |
| `core/config.py` | Compatibilidade com config.json legado |
| `gui/app.py` | Cola tudo: recebe callbacks do controller, chama actions, persiste via presets |
| `gui/bind_dialog.py` | Só UI — retorna `result` dict; não persiste nada |

---

## Arquitetura de threads

```
Thread principal (tkinter/CTk)
  └─ App — toda a UI e gerenciamento de estado

Thread daemon "JoyBind-Listener" (pygame, 60 Hz)
  ├─ on_button_press(btn)  → spawna Thread "Action-BTNn"
  └─ on_axes_update(axes)  → chama pyautogui diretamente
                             → GUI via root.after(0, ...)

Threads de ação "Action-BTNn" (uma por pressionamento)
  └─ execute_sequence() ou execute_keyboard()

Threads de sequência de direção "SeqDir-i-direction"
  └─ execute_sequence() — disparado na borda de entrada do analógico
```

**Regra de ouro:** qualquer interação com widgets tkinter a partir de threads não-principais deve usar `root.after(0, callback)`.

---

## Convenções de código

### Estilo geral

- Python 3.11+ com type hints onde ajuda a entender (não obrigatório em todo lugar)
- Nomes em snake_case; constantes em UPPER_SNAKE_CASE
- Separadores visuais `# ── Seção ───...` para dividir blocos grandes em arquivos longos
- Docstrings em português (padrão do projeto)

### Salvamento de arquivos

Todo salvamento deve ser atômico via arquivo temporário:

```python
tmp = path.with_suffix(".tmp")
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
tmp.replace(path)  # operação atômica no mesmo volume
```

### Atualizações de GUI a partir de threads

```python
# Correto
root.after(0, lambda: label.configure(text="novo valor"))

# Errado — pode causar crash ou comportamento indefinido
label.configure(text="novo valor")  # chamado direto da thread daemon
```

---

## Como adicionar um novo tipo de ação de sequência

1. **`core/actions.py`** — adicione o bloco `elif action == "meu_tipo":` dentro de `execute_sequence()`.
2. **`gui/bind_dialog.py`** — adicione a entrada em `_STEP_ACTION_LABELS` e implemente os widgets de parâmetro em `_build_step_row()`.
3. **`README.md`** — documente o novo tipo na tabela da seção *Sequência de Ações* e no exemplo JSON.

---

## Como adicionar um novo tipo de direção analógica

1. **`gui/app.py`** — adicione o tratamento em `_on_axes_update()` dentro do bloco `else` (modo manual).
2. **`gui/app.py → AnalogDirectionDialog._TYPE_OPTS`** — adicione o novo tipo ao dicionário de opções do diálogo.
3. **`gui/app.py → _dir_btn_text()`** — adicione o rótulo curto para o botão de direção.
4. **`README.md`** — documente o novo tipo na tabela da seção *Modo Manual*.

---

## Testando manualmente

Não há suite de testes automatizados. Para validar alterações:

1. Execute `python main.py`
2. Conecte um controle e clique **↻** se necessário
3. Configure um bind e teste com **Iniciar Escuta**
4. Verifique se o preset foi salvo corretamente (abra o `.json` no editor)
5. Feche e reabra o programa — confirme que o último preset foi restaurado

### Casos de borda importantes

- Fechar o programa enquanto o listener está ativo (`shutdown()` deve parar a thread)
- Desconectar o controle durante a escuta (o loop de polling deve detectar e parar)
- Arquivo de preset corrompido (deve carregar `{"binds": {}}` sem travar)
- Pasta de presets sem permissão de escrita (deve logar erro e não travar)

---

## Reportando problemas

Abra uma issue com:

- Versão do Python (`python --version`)
- Nome e modelo do controle
- Descrição do comportamento esperado vs observado
- Trecho do output do console (se houver mensagens de erro)
