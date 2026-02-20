#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
0RG
Creado por olinformatico.org

Backup manual a Google Drive usando rclone (asistente interactivo).
- Interfaz con colores y paneles
- Muestra HELP al inicio y accesible con H
- Navegación recursiva por carpetas (Documentos/Escritorio o ruta manual)
- Opción B) COMENZAR BACKUP dentro del explorador
- Detecta token vacío/caducado y ofrece reconectar: rclone config reconnect <remote>:
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path


# ============================================================
# ESTILO / COLORES (ANSI)
# ============================================================

ANSI = sys.stdout.isatty()

def c(s: str, code: str) -> str:
    if not ANSI:
        return s
    return f"\033[{code}m{s}\033[0m"

def bold(s: str) -> str: return c(s, "1")
def dim(s: str) -> str: return c(s, "2")
def red(s: str) -> str: return c(s, "31")
def green(s: str) -> str: return c(s, "32")
def yellow(s: str) -> str: return c(s, "33")
def blue(s: str) -> str: return c(s, "34")
def magenta(s: str) -> str: return c(s, "35")
def cyan(s: str) -> str: return c(s, "36")

def hr(n: int = 60) -> str:
    line = "─" * n
    return c(line, "90") if ANSI else line

def clear() -> None:
    try:
        subprocess.call(["clear"])
    except Exception:
        pass


# ============================================================
# HELP
# ============================================================

HELP_TEXT = f"""
{bold("0RG")}
{dim("Creado por olinformatico.org")}
{hr()}

{cyan("¿Qué realiza?")}
- Copia manual a Google Drive usando {bold("rclone copy")} (no se usa sync).
- Permite navegar por carpetas y elegir qué copiar.
- Opción de {bold("PRUEBA")} (dry-run) para no subir nada.
- Opción de {bold("versionado por fecha")} con --backup-dir.

{cyan("¿Cuándo se inicia sesión en Google?")}
- Si no existe configuración, se ejecuta {bold("rclone config")}.
- En ese momento se abre el navegador: se inicia sesión si hace falta y se aceptan permisos.
- Si un remote tiene el token vacío/caducado, se ofrece {bold("rclone config reconnect <remote>:")}.

{cyan("Controles")}
- {bold("H")} = ver ayuda
- {bold("Q")} = salir/cancelar
- Explorador: {bold("B")} = COMENZAR BACKUP con la carpeta actual
{hr()}
""".strip()


def pause(msg: str = "Pulsa ENTER para continuar...") -> None:
    input(dim(msg))


def show_help() -> None:
    clear()
    print(HELP_TEXT)
    pause()


def ask(prompt: str, default: str | None = None) -> str:
    if default:
        text = f"{bold(prompt)} {dim('[' + default + ']')}: "
    else:
        text = f"{bold(prompt)}: "
    ans = input(text).strip()
    if ans.lower() in ("h", "help", "?"):
        show_help()
        return ""
    return ans if ans else (default or "")


def ask_yes_no(prompt: str, default_yes: bool = True) -> bool:
    default = "S/n" if default_yes else "s/N"
    while True:
        ans = input(f"{bold(prompt)} {dim('(' + default + ')')}: ").strip().lower()
        if ans in ("h", "help", "?"):
            show_help()
            continue
        if not ans:
            return default_yes
        if ans in ("s", "si", "sí", "y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print(yellow("Responde S o N (o H para ayuda)."))


# ============================================================
# RCLONE
# ============================================================

def require_rclone() -> str:
    rclone = shutil.which("rclone")
    if not rclone:
        clear()
        print(red("[ERROR]") + " No se encuentra 'rclone'.\n")
        print("Instálalo y vuelve a ejecutar este programa.")
        print(dim("Ejemplo habitual: sudo apt update && sudo apt install rclone\n"))
        raise SystemExit(2)
    return rclone


def get_remotes(rclone: str) -> list[str]:
    try:
        out = subprocess.check_output([rclone, "listremotes"], text=True).splitlines()
        return [x.strip().rstrip(":") for x in out if x.strip()]
    except Exception:
        return []


def pick_remote(remotes: list[str]) -> str:
    while True:
        clear()
        print(bold(cyan("0RG")) + dim(" · Remotes"))
        print(hr())
        for i, r in enumerate(remotes, 1):
            print(f"  {cyan(str(i)+')')} {r}")
        print("\n" + dim("H=help · Q=salir"))

        choice = input(bold("Elige número o nombre: ")).strip()
        if choice.lower() in ("h", "help", "?"):
            show_help()
            continue
        if choice.lower() in ("q", "quit", "salir"):
            return ""

        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(remotes):
                return remotes[idx - 1]
        else:
            if choice in remotes:
                return choice

        print(yellow("Opción no válida."))
        pause()


def remote_ok_or_fix(rclone: str, remote: str) -> None:
    """
    Verifica que el remote puede listar Drive. Si falla por token vacío/caducado,
    ofrece ejecutar 'rclone config reconnect <remote>:' y vuelve a probar.
    """
    try:
        subprocess.check_output([rclone, "lsd", f"{remote}:"], text=True, stderr=subprocess.STDOUT)
        return
    except subprocess.CalledProcessError as e:
        msg = (e.output or "").lower()

        needs_reconnect = (
            "empty token" in msg
            or "reconnect" in msg
            or "failed to create oauth client" in msg
            or "invalid_grant" in msg
        )

        clear()
        print(bold(cyan("0RG")) + dim(" · Verificación de acceso"))
        print(hr())

        if needs_reconnect:
            print(yellow("Se detecta que el remote necesita reautorizarse (token vacío/caducado)."))
            print("Se abrirá el navegador para iniciar sesión y renovar permisos.\n")

            if not ask_yes_no(f"¿Deseas ejecutar ahora: rclone config reconnect {remote}: ?", True):
                raise SystemExit(2)

            rc = subprocess.call([rclone, "config", "reconnect", f"{remote}:"])
            if rc != 0:
                print(red("\n[ERROR]") + f" La reconexión falla (código {rc}).")
                raise SystemExit(rc)

            # Re-test
            subprocess.check_output([rclone, "lsd", f"{remote}:"], text=True, stderr=subprocess.STDOUT)
            print(green("\nRemote reautorizado correctamente."))
            pause()
            return

        print(red("[ERROR]") + " No se puede acceder a Google Drive con este remote.\n")
        print("Detalle del error:\n")
        print(e.output or str(e))
        pause()
        raise SystemExit(2)


# ============================================================
# EXPLORADOR DE CARPETAS (RECURSIVO)
# ============================================================

def list_subfolders(path: Path) -> list[Path]:
    try:
        return sorted(
            [p for p in path.iterdir() if p.is_dir() and not p.name.startswith(".")],
            key=lambda x: x.name.lower(),
        )
    except Exception:
        return []


def folder_browser(start_path: Path) -> Path | None:
    current = start_path

    while True:
        clear()
        print(bold(cyan("0RG")) + dim(" · Explorador"))
        print(hr())
        print(bold("Ubicación: ") + blue(str(current)))
        print(hr())

        subs = list_subfolders(current)
        if subs:
            for i, f in enumerate(subs, 1):
                print(f"  {cyan(str(i).rjust(2)+')')} {f.name}")
        else:
            print(dim("  (No hay subcarpetas visibles)"))

        print("\n" + bold("Opciones:"))
        print(f"  {green('B)')} {bold('COMENZAR BACKUP')}  " + dim("(usar esta carpeta como origen)"))
        print(f"  {yellow('U)')} Subir al nivel anterior")
        print(f"  {magenta('H)')} HELP")
        print(f"  {red('Q)')} Cancelar")

        choice = input(bold("Elige opción (número/B/U/H/Q): ")).strip().lower()

        if choice in ("h", "help", "?"):
            show_help()
            continue
        if choice in ("q", "quit"):
            return None
        if choice == "u":
            if current.parent != current:
                current = current.parent
            continue
        if choice == "b":
            return current

        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(subs):
                current = subs[idx - 1]
            else:
                print(yellow("Número fuera de rango."))
                pause()
            continue

        print(yellow("Opción no válida."))
        pause()


def choose_source_folder() -> Path | None:
    home = Path.home()
    docs_candidates = [home / "Documentos", home / "Documents"]
    desk_candidates = [home / "Escritorio", home / "Desktop"]

    docs = next((p for p in docs_candidates if p.exists()), None)
    desk = next((p for p in desk_candidates if p.exists()), None)

    while True:
        clear()
        print(bold(cyan("0RG")) + dim(" · Origen"))
        print(hr())
        if docs:
            print(f"  {cyan('1)')} Documentos  {dim(str(docs))}")
        if desk:
            print(f"  {cyan('2)')} Escritorio  {dim(str(desk))}")
        print(f"  {cyan('3)')} Ruta manual")
        print(f"  {magenta('H)')} HELP")
        print(f"  {red('Q)')} Salir")

        default = "1" if docs else "3"
        choice = input(bold(f"Opción [{default}]: ")).strip().lower() or default

        if choice in ("h", "help", "?"):
            show_help()
            continue
        if choice in ("q", "quit"):
            return None

        if choice == "1" and docs:
            return folder_browser(docs)
        if choice == "2" and desk:
            return folder_browser(desk)
        if choice == "3":
            manual = input(bold("Introduce ruta completa: ")).strip()
            if manual.lower() in ("h", "help", "?"):
                show_help()
                continue
            manual = os.path.expandvars(os.path.expanduser(manual))
            p = Path(manual)
            if p.exists() and p.is_dir():
                return folder_browser(p)
            print(yellow("Ruta no válida o no es carpeta."))
            pause()
            continue

        print(yellow("Opción no válida."))
        pause()


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    clear()
    print(HELP_TEXT)
    pause()

    rclone = require_rclone()

    remotes = get_remotes(rclone)
    if not remotes:
        clear()
        print(bold(cyan("0RG")) + dim(" · Configuración inicial"))
        print(hr())
        print("No se detecta ningún remote configurado.")
        print("Se abre el asistente rclone config.")
        print(dim("En ese momento se abre el navegador para iniciar sesión/autorizar si es necesario.\n"))

        if not ask_yes_no("¿Abrir ahora rclone config?", True):
            return

        rc = subprocess.call([rclone, "config"])
        if rc != 0:
            print(red("\n[ERROR]") + f" rclone config termina con código {rc}.")
            raise SystemExit(rc)

        remotes = get_remotes(rclone)
        if not remotes:
            print(red("\n[ERROR]") + " No se detecta ningún remote tras la configuración.")
            raise SystemExit(2)

    # Selección de remote
    default_remote = "gdrive" if "gdrive" in remotes else remotes[0]
    clear()
    print(bold(cyan("0RG")) + dim(" · Remote"))
    print(hr())
    print("Remote por defecto: " + green(default_remote))
    print(dim("Si no es el que quieres, elige otro."))
    print(dim("H=help · Q=salir\n"))

    ans = input(bold(f"¿Usar '{default_remote}'? (S/N/H/Q) [S]: ")).strip().lower() or "s"
    if ans in ("h", "help", "?"):
        show_help()
        return
    if ans in ("q", "quit"):
        return

    if ans in ("n", "no"):
        remote = pick_remote(remotes)
        if not remote:
            return
    else:
        remote = default_remote

    # Verifica acceso al remote (y repara token si hace falta)
    remote_ok_or_fix(rclone, remote)

    # Elegir origen
    source_path = choose_source_folder()
    if not source_path:
        return

    # Configuración backup
    clear()
    print(bold(cyan("0RG")) + dim(" · Configuración backup"))
    print(hr())
    print(bold("Origen: ") + blue(str(source_path)))
    print(hr())

    dest = input(bold("Carpeta destino en Drive [Backup0RG]: ")).strip() or "Backup0RG"
    dest = dest.strip("/")

    use_versions = ask_yes_no("¿Activar versionado por fecha?", True)
    versions_base = "Backup0RG_Versiones"
    if use_versions:
        custom = input(bold(f"Carpeta de versiones en Drive [{versions_base}]: ")).strip()
        if custom.lower() in ("h", "help", "?"):
            show_help()
            custom = input(bold(f"Carpeta de versiones en Drive [{versions_base}]: ")).strip()
        versions_base = (custom or versions_base).strip("/")

    dry_run = ask_yes_no("¿Hacer primero una prueba (no se sube nada)?", True)
    show_progress = ask_yes_no("¿Mostrar progreso en pantalla?", True)

    cmd = [rclone, "copy", str(source_path), f"{remote}:{dest}", "--fast-list"]
    if use_versions:
        today = dt.datetime.now().strftime("%Y-%m-%d")
        cmd += ["--backup-dir", f"{remote}:{versions_base}/{today}"]
    if dry_run:
        cmd.append("--dry-run")
    if show_progress:
        cmd.append("--progress")

    # Resumen
    clear()
    print(bold(cyan("0RG")) + dim(" · Resumen"))
    print(hr())
    print(bold("Remote:  ") + green(remote))
    print(bold("Origen:  ") + blue(str(source_path)))
    print(bold("Destino: ") + green(f"{remote}:{dest}"))
    if use_versions:
        print(bold("Versiones: ") + green(f"{remote}:{versions_base}/AAAA-MM-DD"))
    print(bold("Modo:    ") + (yellow("PRUEBA (dry-run)") if dry_run else green("REAL (subida)")))
    print(hr())
    print(dim("H=help · Q=cancelar\n"))

    go = input(bold("¿Iniciar copia ahora? (S/N/H/Q) [S]: ")).strip().lower() or "s"
    if go in ("h", "help", "?"):
        show_help()
        return
    if go in ("n", "no", "q", "quit"):
        return

    # Ejecutar
    clear()
    print(bold(cyan("0RG")) + dim(" · Ejecutando"))
    print(hr())
    rc = subprocess.call(cmd)
    print(hr())

    if rc != 0:
        print(red("[ERROR]") + f" La copia falla (código {rc}).")
        raise SystemExit(rc)

    print(green("✅ Copia finalizada."))
    if dry_run:
        print(dim("Era una simulación. Ejecuta de nuevo y responde NO a la prueba para subir realmente."))
    else:
        print(dim("Revisa Google Drive en el navegador y abre la carpeta de destino."))
    pause()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n" + yellow("Interrumpido por el usuario.") + "\n")
        sys.exit(0)
