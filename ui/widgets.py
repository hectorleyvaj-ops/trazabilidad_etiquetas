from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.styles import (
    card_style,
    connection_pill_style,
    counter_card_style,
    indicator_style,
    result_text_style,
    small_dot_style,
)


class SensorCard(QWidget):
    """Tarjeta limpia para operador.

    Solo muestra:
    - título del nido
    - indicador grande
    - texto principal: espera o código recibido
    - resultado de evaluación
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.current_status = "ESPERANDO"

        self.frame = QFrame()
        self.frame.setStyleSheet(card_style("ESPERANDO"))

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 32px; font-weight: 950; letter-spacing: 0.8px;")

        self.indicator = QLabel()
        self.indicator.setAlignment(Qt.AlignCenter)
        self.indicator.setStyleSheet(indicator_style("ESPERANDO"))

        self.main_label = QLabel("ESPERANDO PIEZA")
        self.main_label.setAlignment(Qt.AlignCenter)
        self.main_label.setWordWrap(True)
        self.main_label.setStyleSheet("font-size: 30px; font-weight: 900;")

        self.result_label = QLabel("ESPERANDO LECTURA")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet(result_text_style("ESPERANDO"))

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(20)
        layout.addWidget(self.title_label)
        layout.addStretch(1)
        layout.addWidget(self.indicator, alignment=Qt.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(self.main_label)
        layout.addWidget(self.result_label)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.frame)

    def set_status(self, status: str) -> None:
        self.current_status = status
        self.indicator.setStyleSheet(indicator_style(status))
        self.frame.setStyleSheet(card_style(status))
        self.result_label.setStyleSheet(result_text_style(status))
        self.result_label.setText(self._friendly_status(status))

        if status == "ESPERANDO":
            self.main_label.setText("ESPERANDO PIEZA")
        elif status == "COOLDOWN":
            self.main_label.setText("LIMPIANDO CICLO")
        elif status == "SIN CONEXIÓN":
            self.main_label.setText("SIN CONEXIÓN")
        elif status == "LECTURA RECIBIDA" and self.main_label.text() in {"ESPERANDO PIEZA", "LIMPIANDO CICLO", "SIN CONEXIÓN"}:
            self.main_label.setText("LECTURA RECIBIDA")

    def set_code(self, code: str, length: int, timestamp: str) -> None:
        del length, timestamp  # La pantalla de producción no muestra datos técnicos.
        self.main_label.setText(code or "---")
        if self.current_status in {"ESPERANDO", "LECTURA RECIBIDA"}:
            self.result_label.setText("LECTURA RECIBIDA")
            self.result_label.setStyleSheet(result_text_style("LECTURA RECIBIDA"))

    def reset(self) -> None:
        self.current_status = "ESPERANDO"
        self.main_label.setText("ESPERANDO PIEZA")
        self.result_label.setText("ESPERANDO LECTURA")
        self.result_label.setStyleSheet(result_text_style("ESPERANDO"))
        self.indicator.setStyleSheet(indicator_style("ESPERANDO"))
        self.frame.setStyleSheet(card_style("ESPERANDO"))

    @staticmethod
    def _friendly_status(status: str) -> str:
        labels = {
            "ESPERANDO": "ESPERANDO LECTURA",
            "LECTURA RECIBIDA": "LECTURA RECIBIDA",
            "NUEVO": "NUEVO / OK",
            "OK": "OK",
            "DUPLICADO": "DUPLICADO",
            "ERROR LONGITUD": "ERROR DE CÓDIGO",
            "ERROR SCANNER": "ERROR DE LECTURA",
            "SIN CONEXIÓN": "SIN CONEXIÓN",
            "COOLDOWN": "LIMPIANDO CICLO",
        }
        return labels.get(status, status)


class ConnectionPill(QWidget):
    """Indicador compacto para PLC/scanners.

    Es deliberadamente discreto: los errores críticos se muestran en popup.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame = QFrame()
        self.frame.setStyleSheet(connection_pill_style(False))

        self.dot = QLabel()
        self.dot.setStyleSheet(small_dot_style(False))

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 850;")

        self.state_label = QLabel("SIN CONEXIÓN")
        self.state_label.setStyleSheet("font-size: 12px; color: rgba(226, 232, 240, 0.76); font-weight: 750;")

        layout = QHBoxLayout(self.frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.addWidget(self.dot)
        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.state_label)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.frame)

    def set_connected(self, connected: bool, message: str = "") -> None:
        self.frame.setStyleSheet(connection_pill_style(connected))
        self.dot.setStyleSheet(small_dot_style(connected))
        self.state_label.setText("EN LÍNEA" if connected else "SIN CONEXIÓN")
        if message:
            self.setToolTip(message)


class CounterCard(QWidget):
    """Contador compacto para métricas de producción."""

    def __init__(self, title: str, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame = QFrame()
        self.frame.setStyleSheet(counter_card_style(kind))

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 12px; color: rgba(226, 232, 240, 0.76); font-weight: 900;")

        self.value_label = QLabel("0")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet("font-size: 40px; font-weight: 950;")

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(3)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.frame)

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))
