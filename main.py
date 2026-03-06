import tkinter as tk
from gui import GUI
from app.main import MainApp


def main():
    root = tk.Tk()

    # MainApp une todos os modulos via heranca multipla
    app_instance = MainApp()

    gui = GUI(root, app_instance)
    app_instance.set_gui(gui)

    # Exibe o fetch inicial apos a GUI estar pronta
    app_instance.show_fetch()

    root.mainloop()


if __name__ == "__main__":
    main()