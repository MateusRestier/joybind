"""
core/presets.py — Gerenciamento de presets nomeados.

Cada preset é um arquivo .json independente com a estrutura:
  {"binds": {"0": {"type": "keyboard", "key": "enter"}, ...}}

Modo portátil (executável PyInstaller):
  settings.json e presets/ ficam ao lado do .exe — viajam com o app no Google Drive.

Modo desenvolvimento:
  - settings.json : %APPDATA%\JoyBind\ (Windows) ou ~/.joybind/
  - presets/      : raiz do repositório
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

if getattr(sys, "frozen", False):
    # Executável PyInstaller: settings e presets ficam ao lado do .exe.
    # Isso torna o app portátil (ex: Google Drive, pen drive).
    _EXE_DIR = Path(sys.executable).parent
    DEFAULT_PRESETS_DIR = _EXE_DIR / "presets"
    SETTINGS_FILE = _EXE_DIR / "settings.json"
else:
    # Desenvolvimento: presets na raiz do repositório; settings no %APPDATA%.
    DEFAULT_PRESETS_DIR = Path(__file__).parent.parent / "presets"
    SETTINGS_FILE = _CONFIG_DIR / "settings.json"


# ── Portabilidade de caminhos ──────────────────────────────────────────────
# Em modo portátil (exe), caminhos são armazenados relativos ao diretório do
# exe. Assim o app funciona em qualquer PC, independente de onde o Google
# Drive ou pen drive estiver montado.

def _to_portable(path_str: str) -> str:
    """Converte caminho absoluto para relativo ao exe (se possível)."""
    if not getattr(sys, "frozen", False):
        return path_str
    try:
        return str(Path(path_str).relative_to(_EXE_DIR))
    except ValueError:
        return path_str  # fora do diretório do exe → mantém absoluto


def _from_portable(path_str: str) -> str:
    """Resolve caminho (relativo ou absoluto) para absoluto usando o exe como base."""
    if not getattr(sys, "frozen", False):
        return path_str
    p = Path(path_str)
    if p.is_absolute():
        return path_str
    return str(_EXE_DIR / p)


# ── Settings ───────────────────────────────────────────────────────────────

def load_settings() -> dict:
    """Carrega settings.json. Retorna valores padrão se não existir."""
    defaults: dict = {
        "presets_dir": str(DEFAULT_PRESETS_DIR),
        "last_preset": None,
        "language":    "en",
    }
    source = SETTINGS_FILE
    # Em modo portátil (exe), tenta migrar settings antigos do %APPDATA% se o
    # settings.json ao lado do exe ainda não existe.
    if getattr(sys, "frozen", False) and not SETTINGS_FILE.exists():
        _legacy = _CONFIG_DIR / "settings.json"
        if _legacy.exists():
            source = _legacy
    if source.exists():
        try:
            with open(source, "r", encoding="utf-8") as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception as e:
            print(f"[Presets] Erro ao carregar settings.json: {e}")

    # Resolve caminhos relativos (formato portátil) para absolutos.
    if defaults.get("presets_dir"):
        defaults["presets_dir"] = _from_portable(defaults["presets_dir"])
    if defaults.get("last_preset"):
        defaults["last_preset"] = _from_portable(defaults["last_preset"])

    # Valida caminhos — podem ser inválidos em outro PC (settings com caminhos
    # absolutos antigos). Se não existir, volta ao padrão.
    presets_dir = Path(defaults["presets_dir"])
    if not presets_dir.exists():
        print(f"[Presets] presets_dir não encontrado ({presets_dir}), usando padrão.")
        defaults["presets_dir"] = str(DEFAULT_PRESETS_DIR)

    last = defaults.get("last_preset")
    if last and not Path(last).exists():
        last_name = Path(last).name
        candidate = Path(defaults["presets_dir"]) / last_name
        if candidate.exists():
            defaults["last_preset"] = str(candidate)
            print(f"[Presets] last_preset relocado para {candidate}")
        else:
            defaults["last_preset"] = None
            print(f"[Presets] last_preset não encontrado ({last}), ignorado.")

    return defaults


def _hide_file(path: Path) -> None:
    """Marca arquivo como oculto no Windows (não aparece no Explorer)."""
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x2)  # FILE_ATTRIBUTE_HIDDEN
    except Exception:
        pass


def save_settings(settings: dict) -> None:
    """Salva settings.json de forma atômica.
    Em modo portátil, converte caminhos para relativos ao exe."""
    to_save = dict(settings)
    if getattr(sys, "frozen", False):
        if to_save.get("presets_dir"):
            to_save["presets_dir"] = _to_portable(to_save["presets_dir"])
        if to_save.get("last_preset"):
            to_save["last_preset"] = _to_portable(to_save["last_preset"])
    try:
        tmp = SETTINGS_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=2, ensure_ascii=False)
        tmp.replace(SETTINGS_FILE)
        _hide_file(SETTINGS_FILE)
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
