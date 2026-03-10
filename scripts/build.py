"""
scripts/build.py — Compila o JoyBind em um executável standalone (.exe).

Uso:
    python scripts/build.py

Requisitos:
    pip install pyinstaller

Nota: O script se auto-eleva para administrador se necessário (Windows Defender
      bloqueia a escrita de recursos no .exe durante a compilação).
"""
import ctypes
import os
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

ROOT  = Path(__file__).resolve().parent.parent
SPEC  = ROOT / "JoyBind.spec"
# Compila em pasta local (fora do Google Drive) para evitar travamento de arquivo
# pelo cliente de sync durante a escrita do .exe. Depois copia para ROOT/dist.
_LOCAL_TMP = Path(tempfile.gettempdir()) / "joybind_build"
DIST_LOCAL = _LOCAL_TMP / "dist"
BUILD_LOCAL = _LOCAL_TMP / "build"
DIST  = ROOT / "dist"
BUILD = ROOT / "build"
EXE   = DIST / "JoyBind.exe"
EXE_LOCAL = DIST_LOCAL / "JoyBind.exe"

# Variável de ambiente que sinaliza que fomos relançados como admin
_RELAUNCHED_AS_ADMIN = "JOYBIND_BUILD_RELAUNCHED"


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _relaunch_as_admin() -> None:
    """
    Cria um .bat temporário que roda este script como admin e pausa ao fim,
    então relança via ShellExecuteW (UAC) e encerra o processo atual.
    """
    script  = Path(__file__).resolve()
    python  = sys.executable
    bat     = Path(tempfile.gettempdir()) / "joybind_build_admin.bat"

    bat.write_text(
        "@echo off\n"
        f'cd /d "{ROOT}"\n'
        f'set {_RELAUNCHED_AS_ADMIN}=1\n'
        f'"{python}" "{script}"\n'
        "@echo.\n"
        "@pause\n",
        encoding="mbcs",
    )

    print("Compilação requer administrador (Windows Defender).")
    print("Confirme o prompt UAC — a janela de build será aberta em seguida.")

    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", "cmd.exe",
        f'/c "{bat}"',
        str(ROOT),
        1,  # SW_SHOWNORMAL
    )
    sys.exit(0)


def _defender_exclusion(action: str, path: Path) -> None:
    """Adiciona ou remove exclusão do Windows Defender (requer admin)."""
    pref = "Add-MpPreference" if action == "add" else "Remove-MpPreference"
    subprocess.run(
        ["powershell", "-Command", f'{pref} -ExclusionPath "{path}"'],
        capture_output=True,
    )


def main() -> None:
    # ── Garante que roda como administrador ───────────────────────────────
    if not _is_admin():
        _relaunch_as_admin()
        return  # nunca chega aqui (sys.exit acima)

    # ── Verifica PyInstaller ───────────────────────────────────────────────
    if shutil.which("pyinstaller") is None:
        print("PyInstaller não encontrado. Instale com:")
        print("    pip install pyinstaller")
        sys.exit(1)

    print("=== JoyBind Build ===")
    print(f"Raiz do projeto : {ROOT}")
    print(f"Spec            : {SPEC}")
    print()

    # ── Limpa builds anteriores ───────────────────────────────────────────
    for folder in (BUILD_LOCAL, DIST_LOCAL, BUILD, DIST):
        if folder.exists():
            print(f"Removendo {folder}...")
            shutil.rmtree(folder)
    DIST_LOCAL.mkdir(parents=True, exist_ok=True)

    # ── Exclusão temporária no Defender ───────────────────────────────────
    print("Adicionando exclusão temporária no Windows Defender...")
    _defender_exclusion("add", _LOCAL_TMP)

    # ── Compilação em pasta local (fora do Google Drive) ──────────────────
    print(f"Compilando em pasta local: {_LOCAL_TMP}\n")
    result = subprocess.run(
        [
            "pyinstaller", str(SPEC),
            "--distpath", str(DIST_LOCAL),
            "--workpath", str(BUILD_LOCAL),
        ],
        cwd=ROOT,
    )

    # ── Remove exclusão ───────────────────────────────────────────────────
    print("\nRemovendo exclusão do Windows Defender...")
    _defender_exclusion("remove", _LOCAL_TMP)

    # ── Resultado ─────────────────────────────────────────────────────────
    if result.returncode != 0:
        print("\nErro na compilação.")
        sys.exit(result.returncode)

    # ── Copia para ROOT/dist ──────────────────────────────────────────────
    print(f"\nCopiando resultado para {DIST}...")
    DIST.mkdir(parents=True, exist_ok=True)
    shutil.copy2(EXE_LOCAL, EXE)

    size_mb = EXE.stat().st_size / (1024 * 1024)
    print(f"Executável gerado: {EXE}  ({size_mb:.1f} MB)")
    print("Pronto!")


if __name__ == "__main__":
    main()
