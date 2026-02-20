"""
config.py — Gerenciamento do arquivo de configuração (config.json).

Estrutura do config.json:
{
  "binds": {
    "0": {"type": "keyboard",   "key": "enter"},
    "1": {"type": "mouse_combo", "x": 500, "y": 300}
  }
}
A chave de cada bind é o índice do botão como string (JSON só aceita str como chave).
"""
import json
from pathlib import Path

# Arquivo salvo ao lado deste script
CONFIG_FILE = Path(__file__).parent / "config.json"

_DEFAULT: dict = {
    "binds": {}
}


def load() -> dict:
    """Carrega a configuração do disco. Retorna o padrão se o arquivo não existir ou estiver corrompido."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data: dict = json.load(f)
            # Garante que todas as chaves obrigatórias existam
            for key, default_value in _DEFAULT.items():
                data.setdefault(key, default_value)
            return data
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Config] Erro ao carregar config.json: {e}. Usando padrão.")

    return {k: (v.copy() if isinstance(v, dict) else v) for k, v in _DEFAULT.items()}


def save(cfg: dict) -> None:
    """Persiste a configuração no disco de forma atômica via arquivo temporário."""
    try:
        tmp = CONFIG_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        tmp.replace(CONFIG_FILE)  # Operação atômica no mesmo volume
    except OSError as e:
        print(f"[Config] Erro ao salvar config.json: {e}")
