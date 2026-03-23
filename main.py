import sys
import os

# ============================================================
# ELEVACAO DE PRIVILEGIOS (Windows only)
#
# Verifica se o processo ja possui privilegios de administrador.
# Caso contrario, relanca o executavel via ShellExecuteW com o
# verbo "runas", que aciona o prompt UAC do Windows.
# Encerra o processo atual imediatamente apos o relancamento para
# evitar duas instancias abertas simultaneamente.
# ============================================================
def _is_admin():
    """Returns True if the current process has administrator privileges."""
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _elevate():
    """
    Re-launches the current script/executable with UAC elevation.
    Works for both .py scripts (via python.exe) and PyInstaller EXE.
    """
    import ctypes
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller-compiled EXE
        executable = sys.executable
        params     = " ".join(f'"{a}"' for a in sys.argv[1:])
    else:
        # Running as a plain .py script
        executable = sys.executable
        script     = os.path.abspath(sys.argv[0])
        rest       = " ".join(f'"{a}"' for a in sys.argv[1:])
        params     = f'"{script}" {rest}'.strip()

    # SW_SHOWNORMAL = 1
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", executable, params, None, 1)
    sys.exit(0)


# Elevation check runs before any GUI or heavy imports
if sys.platform == "win32" and not _is_admin():
    _elevate()


import tkinter as tk
from gui import GUI
from app.main import MainApp


def main():
    root = tk.Tk()

    # MainApp composes all feature modules via multiple inheritance
    app_instance = MainApp()

    gui = GUI(root, app_instance)
    app_instance.set_gui(gui)

    # Display the fast-fetch banner once the GUI is ready
    app_instance.show_fetch()

    root.mainloop()


if __name__ == "__main__":
    main()