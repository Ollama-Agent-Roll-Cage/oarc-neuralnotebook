import sys
from PyQt6.QtWidgets import QApplication
from neural_notebook_ui import NotebookApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NotebookApp()
    window.show()
    sys.exit(app.exec())
