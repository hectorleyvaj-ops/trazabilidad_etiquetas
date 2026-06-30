from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from ui.styles import card_style, indicator_style


class SensorCard(QWidget):
    """Tarjeta visual para un nido/scanner.

    Esta clase solo muestra datos; no valida códigos ni habla con dispositivos.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title

        self.frame = QFrame()
        self.frame.setStyleSheet(card_style("ESPERANDO"))

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold;")

        self.indicator = QLabel()
        self.indicator.setStyleSheet(indicator_style("ESPERANDO"))

        self.status_label = QLabel("ESPERANDO")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.code_label = QLabel("---")
        self.code_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.code_label.setAlignment(Qt.AlignCenter)
        self.code_label.setStyleSheet("font-size: 17px; font-family: Consolas, monospace;")

        self.length_label = QLabel("Longitud: --")
        self.time_label = QLabel("Última lectura: --")

        grid = QGridLayout()
        grid.addWidget(self.title_label, 0, 0, 1, 2)
        grid.addWidget(self.indicator, 1, 0, 2, 1, alignment=Qt.AlignCenter)
        grid.addWidget(self.status_label, 1, 1)
        grid.addWidget(self.code_label, 2, 1)
        grid.addWidget(self.length_label, 3, 0, 1, 2)
        grid.addWidget(self.time_label, 4, 0, 1, 2)
        grid.setColumnStretch(1, 1)
        grid.setVerticalSpacing(10)
        self.frame.setLayout(grid)

        layout = QVBoxLayout(self)
        layout.addWidget(self.frame)
        layout.setContentsMargins(0, 0, 0, 0)

    def set_status(self, status: str) -> None:
        self.status_label.setText(status)
        self.indicator.setStyleSheet(indicator_style(status))
        self.frame.setStyleSheet(card_style(status))

    def set_code(self, code: str, length: int, timestamp: str) -> None:
        self.code_label.setText(code or "---")
        self.length_label.setText(f"Longitud: {length}")
        self.time_label.setText(f"Última lectura: {timestamp}")

    def reset(self) -> None:
        self.set_status("ESPERANDO")
        self.set_code("---", 0, "--")
