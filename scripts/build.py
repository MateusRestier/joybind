"""
scripts/build.py — Compila o JoyBind em um executável standalone (.exe).

Uso:
    python scripts/build.py

Requisitos:
    pip install pyinstaller
"""
import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "JoyBind.spec"
DIST = ROOT / "dist"
EXE  = DIST / "JoyBind.exe"


def main() -> None:
    # Verifica se o PyInstaller está instalado
    if shutil.which("pyinstaller") is None:
        print("PyInstaller não encontrado. Instale com:")
        print("    pip install pyinstaller")
        sys.exit(1)

    print("=== JoyBind Build ===")
    print(f"Raiz do projeto : {ROOT}")
    print(f"Spec            : {SPEC}")
    print()

    # Limpa build anterior
    for folder in ("build", "dist"):
        path = ROOT / folder
        if path.exists():
            print(f"Removendo {folder}/...")
            shutil.rmtree(path)

    # Executa o PyInstaller com o .spec existente
    print("Compilando...\n")
    result = subprocess.run(
        ["pyinstaller", str(SPEC), "--distpath", str(DIST)],
        cwd=ROOT,
    )

    if result.returncode != 0:
        print("\nErro na compilação.")
        sys.exit(result.returncode)

    size_mb = EXE.stat().st_size / (1024 * 1024)
    print(f"\nExecutável gerado: {EXE}  ({size_mb:.1f} MB)")
    print("Pronto!")


if __name__ == "__main__":
    main()
