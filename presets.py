"""
presets.py — Gerenciamento de presets nomeados.

Cada preset é um arquivo .json independente com a estrutura:
  {"binds": {"0": {"type": "keyboard", "key": "enter"}, ...}}

O arquivo settings.json (ao lado do programa) persiste:
  - presets_dir  : caminho da pasta de presets escolhida pelo usuário
  - last_preset  : caminho absoluto do último preset carregado
"""
import json
from pathlib import Path

_BASE_DIR = Path(__file__).parent

# Pasta padrão: <dir_do_programa>/presets/
DEFAULT_PRESETS_DIR = _BASE_DIR / "presets"

# Arquivo de configurações do app (não versionado)
SETTINGS_FILE = _BASE_DIR / "settings.json"


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
