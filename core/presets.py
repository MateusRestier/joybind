"""
core/presets.py — Gerenciamento de presets nomeados.

Cada preset é um arquivo .json independente com a estrutura:
  {"binds": {"0": {"type": "keyboard", "key": "enter"}, ...}}

Dados do usuário ficam em %APPDATA%\JoyBind\ (Windows) ou ~/.joybind/ (outros):
  - settings.json : configurações internas (pasta de presets, último preset)
  - presets/      : pasta padrão dos presets (pode ser alterada pelo usuário)
"""
import json
import os
import sys
from pathlib import Path

# Diretório de dados do usuário — invisível para o usuário comum.
# Windows : %APPDATA%\JoyBind\
# Outros  : ~/.joybind/
_APPDATA = os.environ.get("APPDATA")
if _APPDATA:
    _CONFIG_DIR = Path(_APPDATA) / "JoyBind"
else:
    _CONFIG_DIR = Path.home() / ".joybind"

_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# Em desenvolvimento, presets ficam na raiz do repositório para facilitar testes.
if getattr(sys, "frozen", False):
    DEFAULT_PRESETS_DIR = _CONFIG_DIR / "presets"
else:
    DEFAULT_PRESETS_DIR = Path(__file__).parent.parent / "presets"

# Arquivo de configurações do app
SETTINGS_FILE = _CONFIG_DIR / "settings.json"


# ── Settings ───────────────────────────────────────────────────────────────

def load_settings() -> dict:
    """Carrega settings.json. Retorna valores padrão se não existir."""
    defaults: dict = {
        "presets_dir": str(DEFAULT_PRESETS_DIR),
        "last_preset": None,
    }
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception as e:
            print(f"[Presets] Erro ao carregar settings.json: {e}")
    return defaults


def save_settings(settings: dict) -> None:
    """Salva settings.json de forma atômica."""
    try:
        tmp = SETTINGS_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        tmp.replace(SETTINGS_FILE)
    except OSError as e:
        print(f"[Presets] Erro ao salvar settings.json: {e}")


# ── Listagem ───────────────────────────────────────────────────────────────

def list_presets(folder: Path) -> list[Path]:
    """Retorna arquivos .json da pasta, ordenados alfabeticamente pelo nome."""
    if not folder.exists():
        return []
    return sorted(folder.glob("*.json"), key=lambda p: p.stem.lower())


# ── Carregamento ───────────────────────────────────────────────────────────

def load_preset(path: Path) -> dict:
    """
    Carrega um preset de um arquivo .json.
    Retorna {"binds": {}} se o arquivo não existir ou estiver corrompido.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("binds", {})
        return data
    except Exception as e:
        print(f"[Presets] Erro ao carregar '{path.name}': {e}")
    return {"binds": {}}


# ── Salvamento ─────────────────────────────────────────────────────────────

def save_preset(path: Path, cfg: dict) -> bool:
    """
    Salva um preset de forma atômica. Cria a pasta pai se necessário.
    Retorna True em sucesso, False em falha.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        tmp.replace(path)
        return True
    except OSError as e:
        print(f"[Presets] Erro ao salvar '{path.name}': {e}")
        return False
