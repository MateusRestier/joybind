"""
i18n.py — Internationalization module for JoyBind.

Usage:
    from i18n import t, set_lang

    set_lang("en")          # or "pt"
    label = t("btn_save")   # → "Save" or "Salvar"
"""

_lang: str = "en"


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang.lower()


def t(key: str, **kw) -> str:
    """Return the translated string for *key*, formatted with **kw."""
    table = _EN if _lang == "en" else _PT
    s = table.get(key, _PT.get(key, key))
    if kw:
        try:
            s = s.format(**kw)
        except (KeyError, IndexError):
            pass
    return s


def step_plural(n: int) -> str:
    """Return 'step' or 'steps' (singular/plural) in the current language."""
    return t("word_step") if n == 1 else t("word_steps")


# ── Keyboard suggestions list ─────────────────────────────────────────────────

def kb_suggestions() -> list[tuple[str, str]]:
    """Return the keyboard suggestions list in the current language."""
    return _SUGG_EN if _lang == "en" else _SUGG_PT


# ── Step action labels ────────────────────────────────────────────────────────

def step_action_labels() -> dict[str, str]:
    """Return the step action labels dict in the current language."""
    return _SAL_EN if _lang == "en" else _SAL_PT


# ── Analog direction type options ─────────────────────────────────────────────

def analog_type_opts() -> dict[str, str]:
    """Return the analog direction type options dict in the current language."""
    return _ATO_EN if _lang == "en" else _ATO_PT


# ── String tables ─────────────────────────────────────────────────────────────

_PT: dict[str, str] = {
    # ── Buttons ───────────────────────────────────────────────────────────────
    "btn_new":          "Novo",
    "btn_delete":       "Apagar",
    "btn_folder":       "Pasta...",
    "btn_save":         "Salvar",
    "btn_cancel":       "Cancelar",
    "btn_capture":      "Capturar",
    "btn_skip":         "Pular",
    "btn_ok":           "OK",
    "btn_start_listen": "  Iniciar Escuta",
    "btn_stop_listen":  "  Pausar Escuta",
    "btn_clear_binds":  "Limpar Mapeamentos",
    "btn_auto_map":     "Auto-mapear Botões",
    "btn_feedback":     "Feedback",
    "btn_add_step":     "+ Adicionar Passo",
    "btn_map_btn":      "Mapear botão",
    "btn_clear":        "Limpar",
    "btn_edit_seq":     "Editar Sequência...",

    # ── Labels ────────────────────────────────────────────────────────────────
    "lbl_preset":       "Preset:",
    "lbl_controller":   "Controle:",
    "lbl_btn_num":      "Nº do Botão:",
    "lbl_action":       "Ação:",
    "lbl_suggestions":  "Sugestões:",
    "lbl_key":          "Tecla:",
    "lbl_hold_ms":      "Segurar (ms):",
    "lbl_hold_while":   "Segurar enquanto pressionado",
    "lbl_macro_kb":     "Modo Macro (auto-click)",
    "lbl_macro_seq":    "Modo Macro (repetir sequência)",
    "lbl_interval":     "  intervalo:",
    "lbl_type":         "Tipo:",
    "lbl_speed":        "Velocidade:",
    "lbl_clicks":       "Cliques:",
    "lbl_timeline":     "Linha do Tempo",
    "lbl_save_restore": "Salvar e restaurar posição do mouse",
    "lbl_ms":           "ms",

    # ── Section headers ───────────────────────────────────────────────────────
    "sec_dpad":         "D-Pad",
    "sec_buttons":      "Botões",
    "sec_central":      "Central",
    "sec_analog_left":  "Analógico Esquerdo",
    "sec_analog_right": "Analógico Direito",
    "sec_analog_n":     "Analógico {n}",

    # ── Status ────────────────────────────────────────────────────────────────
    "status_stopped":   "  Parado",
    "status_active":    "  Ativo",
    "status_paused":    "  Pausado",
    "status_no_ctrl":   "Nenhum controle encontrado",
    "status_waiting":   "Aguardando…",
    "status_press_btn": "Pressione um botão...",
    "status_press_key": "Pressione...",

    # ── Header ────────────────────────────────────────────────────────────────
    "header_subtitle":  "Mapeador de Controle  →  Teclado / Mouse",

    # ── Dialog titles ─────────────────────────────────────────────────────────
    "title_configure":      "Configurar — {label}",
    "title_auto_map":       "Auto-mapear Botões",
    "title_mapping":        "Mapeamento",
    "title_sequence":       "Sequência de Ações",
    "title_new_preset":     "Novo Preset",
    "title_delete_preset":  "Apagar preset",
    "title_folder":         "Escolher pasta de presets",
    "title_err_start":      "Erro ao iniciar",
    "title_err_validation": "Erro de validação",
    "title_err_name":       "Nome inválido",
    "title_err_preset_exists": "Preset já existe",
    "title_err_key":        "Tecla inválida",
    "title_confirm":        "Confirmar",
    "title_overwrite":      "Sobrescrever?",
    "title_capture_failed": "Captura falhou",

    # ── Messages ──────────────────────────────────────────────────────────────
    "msg_clear_binds":
        "Limpar todos os mapeamentos e restaurar os números de botão padrão?",
    "msg_preset_new_text":  "Nome do novo preset:",
    "msg_invalid_name":     "O nome contém apenas caracteres inválidos.",
    "msg_preset_replace":   "Substituir '{name}'?",
    "msg_delete_preset":
        "Apagar o preset '{name}'?\n\nEsta ação não pode ser desfeita.",
    "msg_btn_num_invalid":
        "O número do botão deve ser um inteiro não-negativo (ex: 0, 1, 2).",
    "msg_btn_overwrite":
        "O botão {btn} já possui um mapeamento.\nDeseja substituí-lo?",
    "msg_key_empty":
        "Informe o nome da tecla ou use o botão 'Capturar'.",
    "msg_key_invalid":
        "Nome(s) de tecla não reconhecido(s): {invalid}\n\n"
        "Use o botão 'Capturar' para detectar o nome correto,\n"
        "ou consulte a lista de teclas válidas no README.",
    "msg_seq_empty":        "Adicione pelo menos uma ação na sequência.",
    "msg_no_ctrl":
        "Nenhum controle detectado. Conecte um joystick/gamepad e tente novamente.",
    "msg_ctrl_not_found":
        "Controle de índice {idx} não encontrado (apenas {total} controle(s) conectado(s)).",
    "msg_ctrl_init_error":  "Erro ao inicializar controle: {exc}",
    "msg_no_ctrl_connected": "Nenhum controle conectado.",
    "msg_timeout_automap":  "Tempo esgotado (15 s).",
    "msg_timeout_capture":  "Tempo esgotado (10 s). Tente novamente.",
    "msg_analog_no_steps":  "Nenhuma ação configurada ainda.",
    "msg_analog_steps_n":
        "{n} passo{s} configurado{s}.",   # {s} = "s" or ""
    "msg_seq_empty_hint":
        "Nenhuma ação ainda.\nUse o menu abaixo para adicionar passos.",
    "msg_no_action_hint":
        "Nenhuma ação — o botão é mapeado sem executar nada.",
    "msg_toggle_pause_hint":
        "⏸  Pausar / Retomar JoyBind\n\n"
        "Ao pressionar este botão, todas as outras binds param de funcionar "
        "(teclado, mouse e analógico).\n"
        "Pressionar novamente retoma tudo normalmente.\n\n"
        "Útil para usar o controle normalmente num jogo sem o JoyBind interferir.",
    "msg_click_dir":        "Clique em uma direção para configurar",
    "msg_automap_hint":
        "Pressione cada botão no controle quando solicitado.",
    "msg_automap_tile":     "Tile {idx} de {total}",
    "msg_automap_waiting":  "Aguardando... (atual: btn {btn})",
    "msg_automap_detected": "Detectado: botão {btn} ✓",
    "msg_automap_failed":   "Falhou: {msg}",

    # ── Hints / descriptions ──────────────────────────────────────────────────
    "hint_game_hold":
        "(se tiver problemas em jogos, aumente este valor)",
    "hint_hold_while":
        "(mantém a tecla/botão do mouse pressionado enquanto o botão do controle estiver seguro)",
    "hint_macro_kb":
        "(dispara repetidamente enquanto o botão estiver pressionado)",
    "hint_macro_seq":
        "(repete a sequência enquanto o botão estiver pressionado)",
    "hint_key_names":
        "Nomes aceitos: enter · space · escape · tab · f1-f12 · a-z · 0-9"
        " · ctrl · alt · shift · mouse_left · mouse_right"
        " · scroll_up · scroll_down · mouse4 · mouse5 ...",
    "hint_emulator":        "(útil para emuladores como Citra)",

    # ── Analog stick modes ────────────────────────────────────────────────────
    "mode_mouse":     "🖱 Modo Mouse  (move o cursor)",
    "mode_game_wasd": "🎮 Modo Jogo   (WASD automático)",
    "mode_scroll":    "↕ Modo Scroll  (rolar página)",
    "mode_game_cam":  "🎮 Modo Jogo   (câmera / mouse)",

    # ── Directions ────────────────────────────────────────────────────────────
    "dir_up":    "↑ Cima",
    "dir_down":  "↓ Baixo",
    "dir_left":  "← Esquerda",
    "dir_right": "→ Direita",

    # ── Bind type badges (shown on tiles) ─────────────────────────────────────
    "type_keyboard": "TECLADO",
    "type_sequence": "SEQUÊNCIA",
    "type_mouse":    "MOUSE",

    # ── Action type radio buttons ─────────────────────────────────────────────
    "action_none":          "Nenhuma",
    "action_key":           "Tecla / Clique",
    "action_sequence":      "Sequência de Ações",
    "action_toggle_pause":  "Pausar JoyBind",
    "tile_toggle_pause":    "⏸ pausar",

    # ── Word parts ────────────────────────────────────────────────────────────
    "word_step":     "passo",
    "word_steps":    "passos",
    "word_sequence": "sequência",

    # ── Controller fallback name ──────────────────────────────────────────────
    "ctrl_name_fallback": "Controle #{n}",

    # ── Mouse display abbreviations ───────────────────────────────────────────
    "mouse_display_left":   "🖱 Esq.",
    "mouse_display_right":  "🖱 Dir.",
    "mouse_display_middle": "🖱 Meio",

    # ── pynput ────────────────────────────────────────────────────────────────
    "title_pynput_missing": "pynput ausente",
    "msg_pynput_missing":   "Instale pynput:\n  pip install pynput",

    # ── Icon errors (main.py) ─────────────────────────────────────────────────
    "err_icon_taskbar": "[Icon] Erro ao definir ícone na taskbar: {e}",
    "err_icon":         "[Icon] Erro ao definir ícone: {e}",

    # ── Layout warning ────────────────────────────────────────────────────────
    "warn_layout_unverified":
        "⚠ Mapeamento de botões não verificado — os tiles usam o layout Xbox padrão."
        " Use Auto-mapear para confirmar os botões do seu controle.",

    # ── Admin mode ────────────────────────────────────────────────────────────
    "btn_admin":       "🛡 Admin",
    "msg_admin_title": "Modo Administrador",
    "msg_admin_body":
        "O JoyBind precisa de permissão de administrador para controlar apps protegidos"
        " pelo Windows, como o teclado virtual (osk.exe).\n\n"
        "Deseja reiniciar como administrador agora?",
}

_EN: dict[str, str] = {
    # ── Buttons ───────────────────────────────────────────────────────────────
    "btn_new":          "New",
    "btn_delete":       "Delete",
    "btn_folder":       "Folder...",
    "btn_save":         "Save",
    "btn_cancel":       "Cancel",
    "btn_capture":      "Capture",
    "btn_skip":         "Skip",
    "btn_ok":           "OK",
    "btn_start_listen": "  Start Listening",
    "btn_stop_listen":  "  Stop Listening",
    "btn_clear_binds":  "Clear Mappings",
    "btn_auto_map":     "Auto-map Buttons",
    "btn_feedback":     "Feedback",
    "btn_add_step":     "+ Add Step",
    "btn_map_btn":      "Map button",
    "btn_clear":        "Clear",
    "btn_edit_seq":     "Edit Sequence...",

    # ── Labels ────────────────────────────────────────────────────────────────
    "lbl_preset":       "Preset:",
    "lbl_controller":   "Controller:",
    "lbl_btn_num":      "Button No.:",
    "lbl_action":       "Action:",
    "lbl_suggestions":  "Suggestions:",
    "lbl_key":          "Key:",
    "lbl_hold_ms":      "Hold (ms):",
    "lbl_hold_while":   "Hold while pressed",
    "lbl_macro_kb":     "Macro Mode (auto-click)",
    "lbl_macro_seq":    "Macro Mode (repeat sequence)",
    "lbl_interval":     "  interval:",
    "lbl_type":         "Type:",
    "lbl_speed":        "Speed:",
    "lbl_clicks":       "Clicks:",
    "lbl_timeline":     "Timeline",
    "lbl_save_restore": "Save and restore mouse position",
    "lbl_ms":           "ms",

    # ── Section headers ───────────────────────────────────────────────────────
    "sec_dpad":         "D-Pad",
    "sec_buttons":      "Buttons",
    "sec_central":      "Center",
    "sec_analog_left":  "Left Analog",
    "sec_analog_right": "Right Analog",
    "sec_analog_n":     "Analog {n}",

    # ── Status ────────────────────────────────────────────────────────────────
    "status_stopped":   "  Stopped",
    "status_active":    "  Active",
    "status_paused":    "  Paused",
    "status_no_ctrl":   "No controller found",
    "status_waiting":   "Waiting…",
    "status_press_btn": "Press a button...",
    "status_press_key": "Press...",

    # ── Header ────────────────────────────────────────────────────────────────
    "header_subtitle":  "Controller Mapper  →  Keyboard / Mouse",

    # ── Dialog titles ─────────────────────────────────────────────────────────
    "title_configure":      "Configure — {label}",
    "title_auto_map":       "Auto-map Buttons",
    "title_mapping":        "Mapping",
    "title_sequence":       "Action Sequence",
    "title_new_preset":     "New Preset",
    "title_delete_preset":  "Delete preset",
    "title_folder":         "Choose presets folder",
    "title_err_start":      "Start error",
    "title_err_validation": "Validation error",
    "title_err_name":       "Invalid name",
    "title_err_preset_exists": "Preset already exists",
    "title_err_key":        "Invalid key",
    "title_confirm":        "Confirm",
    "title_overwrite":      "Overwrite?",
    "title_capture_failed": "Capture failed",

    # ── Messages ──────────────────────────────────────────────────────────────
    "msg_clear_binds":
        "Clear all mappings and restore default button numbers?",
    "msg_preset_new_text":  "New preset name:",
    "msg_invalid_name":     "The name contains only invalid characters.",
    "msg_preset_replace":   "Replace '{name}'?",
    "msg_delete_preset":
        "Delete preset '{name}'?\n\nThis action cannot be undone.",
    "msg_btn_num_invalid":
        "The button number must be a non-negative integer (e.g., 0, 1, 2).",
    "msg_btn_overwrite":
        "Button {btn} already has a mapping.\nDo you want to replace it?",
    "msg_key_empty":
        "Enter the key name or use the 'Capture' button.",
    "msg_key_invalid":
        "Unrecognized key name(s): {invalid}\n\n"
        "Use the 'Capture' button to detect the correct name,\n"
        "or check the list of valid keys in the README.",
    "msg_seq_empty":        "Add at least one action to the sequence.",
    "msg_no_ctrl":
        "No controller detected. Connect a joystick/gamepad and try again.",
    "msg_ctrl_not_found":
        "Controller index {idx} not found (only {total} controller(s) connected).",
    "msg_ctrl_init_error":  "Error initializing controller: {exc}",
    "msg_no_ctrl_connected": "No controller connected.",
    "msg_timeout_automap":  "Timeout (15 s).",
    "msg_timeout_capture":  "Timeout (10 s). Try again.",
    "msg_analog_no_steps":  "No action configured yet.",
    "msg_analog_steps_n":   "{n} step{s} configured.",   # {s} = "s" or ""
    "msg_seq_empty_hint":
        "No actions yet.\nUse the menu below to add steps.",
    "msg_no_action_hint":
        "No action — the button is mapped without executing anything.",
    "msg_toggle_pause_hint":
        "⏸  Pause / Resume JoyBind\n\n"
        "Pressing this button stops all other binds from working "
        "(keyboard, mouse and analog).\n"
        "Pressing it again resumes everything normally.\n\n"
        "Useful for using the controller normally in a game without JoyBind interfering.",
    "msg_click_dir":        "Click a direction to configure",
    "msg_automap_hint":
        "Press each button on the controller when prompted.",
    "msg_automap_tile":     "Tile {idx} of {total}",
    "msg_automap_waiting":  "Waiting... (current: btn {btn})",
    "msg_automap_detected": "Detected: button {btn} ✓",
    "msg_automap_failed":   "Failed: {msg}",

    # ── Hints / descriptions ──────────────────────────────────────────────────
    "hint_game_hold":
        "(if you have issues in games, increase this value)",
    "hint_hold_while":
        "(keeps the key/mouse button pressed while the controller button is held)",
    "hint_macro_kb":
        "(fires repeatedly while the button is pressed)",
    "hint_macro_seq":
        "(repeats the sequence while the button is pressed)",
    "hint_key_names":
        "Accepted names: enter · space · escape · tab · f1-f12 · a-z · 0-9"
        " · ctrl · alt · shift · mouse_left · mouse_right"
        " · scroll_up · scroll_down · mouse4 · mouse5 ...",
    "hint_emulator":        "(useful for emulators like Citra)",

    # ── Analog stick modes ────────────────────────────────────────────────────
    "mode_mouse":     "🖱 Mouse Mode  (moves cursor)",
    "mode_game_wasd": "🎮 Game Mode   (auto WASD)",
    "mode_scroll":    "↕ Scroll Mode  (scroll page)",
    "mode_game_cam":  "🎮 Game Mode   (camera / mouse)",

    # ── Directions ────────────────────────────────────────────────────────────
    "dir_up":    "↑ Up",
    "dir_down":  "↓ Down",
    "dir_left":  "← Left",
    "dir_right": "→ Right",

    # ── Bind type badges (shown on tiles) ─────────────────────────────────────
    "type_keyboard": "KEYBOARD",
    "type_sequence": "SEQUENCE",
    "type_mouse":    "MOUSE",

    # ── Action type radio buttons ─────────────────────────────────────────────
    "action_none":          "None",
    "action_key":           "Key / Click",
    "action_sequence":      "Action Sequence",
    "action_toggle_pause":  "Pause JoyBind",
    "tile_toggle_pause":    "⏸ pause",

    # ── Word parts ────────────────────────────────────────────────────────────
    "word_step":     "step",
    "word_steps":    "steps",
    "word_sequence": "sequence",

    # ── Controller fallback name ──────────────────────────────────────────────
    "ctrl_name_fallback": "Controller #{n}",

    # ── Mouse display abbreviations ───────────────────────────────────────────
    "mouse_display_left":   "🖱 L.",
    "mouse_display_right":  "🖱 R.",
    "mouse_display_middle": "🖱 M.",

    # ── pynput ────────────────────────────────────────────────────────────────
    "title_pynput_missing": "pynput missing",
    "msg_pynput_missing":   "Install pynput:\n  pip install pynput",

    # ── Icon errors (main.py) ─────────────────────────────────────────────────
    "err_icon_taskbar": "[Icon] Error setting taskbar icon: {e}",
    "err_icon":         "[Icon] Error setting icon: {e}",

    # ── Layout warning ────────────────────────────────────────────────────────
    "warn_layout_unverified":
        "⚠ Button mapping not verified — tiles use the default Xbox layout."
        " Run Auto-map to confirm your controller's buttons.",

    # ── Admin mode ────────────────────────────────────────────────────────────
    "btn_admin":       "🛡 Admin",
    "msg_admin_title": "Administrator Mode",
    "msg_admin_body":
        "JoyBind needs administrator permission to control apps protected by Windows,"
        " such as the on-screen keyboard (osk.exe).\n\n"
        "Restart as administrator now?",
}


# ── Keyboard suggestion lists ─────────────────────────────────────────────────

_SUGG_PT: list[tuple[str, str]] = [
    ("— Sugestões —", ""),
    ("🖱 Clique Esquerdo",         "mouse_left"),
    ("🖱 Clique Direito",          "mouse_right"),
    ("🖱 Clique do Meio",          "mouse_middle"),
    ("🖱 Mouse 4 (lateral tras.)", "mouse4"),
    ("🖱 Mouse 5 (lateral front.)", "mouse5"),
    ("🖱 Scroll para Cima",        "scroll_up"),
    ("🖱 Scroll para Baixo",       "scroll_down"),
    ("🖱 Scroll para Direita",     "scroll_right"),
    ("🖱 Scroll para Esquerda",    "scroll_left"),
    ("↵ Enter",                    "enter"),
    ("␣ Espaço",                   "space"),
    ("⎋ Escape",                   "escape"),
    ("⇥ Tab",                      "tab"),
    ("⌫ Backspace",                "backspace"),
    ("⌦ Delete",                   "delete"),
    ("F1", "f1"),   ("F2",  "f2"),  ("F3",  "f3"),  ("F4",  "f4"),
    ("F5", "f5"),   ("F6",  "f6"),  ("F7",  "f7"),  ("F8",  "f8"),
    ("F9", "f9"),   ("F10", "f10"), ("F11", "f11"), ("F12", "f12"),
    ("↑ Seta Cima",      "up"),
    ("↓ Seta Baixo",     "down"),
    ("← Seta Esq.",      "left"),
    ("→ Seta Dir.",      "right"),
    ("Page Up",          "pageup"),
    ("Page Down",        "pagedown"),
    ("Home",             "home"),
    ("End",              "end"),
    ("Ctrl+C — Copiar",      "ctrl+c"),
    ("Ctrl+V — Colar",       "ctrl+v"),
    ("Ctrl+Z — Desfazer",    "ctrl+z"),
    ("Ctrl+S — Salvar",      "ctrl+s"),
    ("Ctrl+A — Sel. tudo",   "ctrl+a"),
    ("Alt+Tab — Alternar",   "alt+tab"),
    ("Alt+F4 — Fechar",      "alt+f4"),
    ("Win — Início",         "winleft"),
    ("Volume +",             "volumeup"),
    ("Volume −",             "volumedown"),
    ("Mudo / Desmudo",       "volumemute"),
]

_SUGG_EN: list[tuple[str, str]] = [
    ("— Suggestions —", ""),
    ("🖱 Left Click",             "mouse_left"),
    ("🖱 Right Click",            "mouse_right"),
    ("🖱 Middle Click",           "mouse_middle"),
    ("🖱 Mouse 4 (back side)",    "mouse4"),
    ("🖱 Mouse 5 (front side)",   "mouse5"),
    ("🖱 Scroll Up",              "scroll_up"),
    ("🖱 Scroll Down",            "scroll_down"),
    ("🖱 Scroll Right",           "scroll_right"),
    ("🖱 Scroll Left",            "scroll_left"),
    ("↵ Enter",                   "enter"),
    ("␣ Space",                   "space"),
    ("⎋ Escape",                  "escape"),
    ("⇥ Tab",                     "tab"),
    ("⌫ Backspace",               "backspace"),
    ("⌦ Delete",                  "delete"),
    ("F1", "f1"),   ("F2",  "f2"),  ("F3",  "f3"),  ("F4",  "f4"),
    ("F5", "f5"),   ("F6",  "f6"),  ("F7",  "f7"),  ("F8",  "f8"),
    ("F9", "f9"),   ("F10", "f10"), ("F11", "f11"), ("F12", "f12"),
    ("↑ Arrow Up",       "up"),
    ("↓ Arrow Down",     "down"),
    ("← Arrow Left",     "left"),
    ("→ Arrow Right",    "right"),
    ("Page Up",          "pageup"),
    ("Page Down",        "pagedown"),
    ("Home",             "home"),
    ("End",              "end"),
    ("Ctrl+C — Copy",        "ctrl+c"),
    ("Ctrl+V — Paste",       "ctrl+v"),
    ("Ctrl+Z — Undo",        "ctrl+z"),
    ("Ctrl+S — Save",        "ctrl+s"),
    ("Ctrl+A — Select all",  "ctrl+a"),
    ("Alt+Tab — Switch",     "alt+tab"),
    ("Alt+F4 — Close",       "alt+f4"),
    ("Win — Start",          "winleft"),
    ("Volume +",             "volumeup"),
    ("Volume −",             "volumedown"),
    ("Mute / Unmute",        "volumemute"),
]


# ── Step action label dicts ───────────────────────────────────────────────────

_SAL_PT: dict[str, str] = {
    "move_mouse":   "Mover mouse → X, Y",
    "click_left":   "Clique esquerdo",
    "click_right":  "Clique direito",
    "click_middle": "Clique do meio",
    "double_click": "Clique duplo",
    "key":          "Pressionar tecla",
    "delay":        "Intervalo (ms)",
    "scroll_up":    "Rolar para cima",
    "scroll_down":  "Rolar para baixo",
    "scroll_right": "Rolar para direita",
    "scroll_left":  "Rolar para esquerda",
}

_SAL_EN: dict[str, str] = {
    "move_mouse":   "Move mouse → X, Y",
    "click_left":   "Left click",
    "click_right":  "Right click",
    "click_middle": "Middle click",
    "double_click": "Double click",
    "key":          "Press key",
    "delay":        "Delay (ms)",
    "scroll_up":    "Scroll up",
    "scroll_down":  "Scroll down",
    "scroll_right": "Scroll right",
    "scroll_left":  "Scroll left",
}


# ── Analog direction type option dicts ────────────────────────────────────────

_ATO_PT: dict[str, str] = {
    "none":     "— Nada",
    "mouse_x":  "Mouse X (horizontal)",
    "mouse_y":  "Mouse Y (vertical)",
    "scroll_v": "Scroll ↑↓ (vertical)",
    "scroll_h": "Scroll ←→ (horizontal)",
    "key":      "Tecla (segurar ao pressionar)",
    "sequence": "Sequência de ações (ao cruzar limite)",
}

_ATO_EN: dict[str, str] = {
    "none":     "— Nothing",
    "mouse_x":  "Mouse X (horizontal)",
    "mouse_y":  "Mouse Y (vertical)",
    "scroll_v": "Scroll ↑↓ (vertical)",
    "scroll_h": "Scroll ←→ (horizontal)",
    "key":      "Key (hold while pressing)",
    "sequence": "Action sequence (on threshold cross)",
}
