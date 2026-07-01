from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.styles import (
    card_style,
    connection_pill_style,
    indicator_style,
    result_text_style,
    sensor_counter_strip_style,
    small_dot_style,
    stat_chip_style,
)


class SensorCard(QWidget):
    """Tarjeta minimalista para operador.

    Solo muestra título del nido, indicador grande, código recibido y resultado.
    En espera los campos de código y resultado permanecen vacíos para reducir ruido.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.current_status = "ESPERANDO"

        self.frame = QFrame()
        self.frame.setStyleSheet(card_style("ESPERANDO"))

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(
            "font-size: 34px; font-weight: 950; letter-spacing: 0.8px; "
            "border: none; background: transparent;"
        )

        self.indicator = QLabel()
        self.indicator.setAlignment(Qt.AlignCenter)
        self.indicator.setStyleSheet(indicator_style("ESPERANDO"))

        self.main_label = QLabel("")
        self.main_label.setAlignment(Qt.AlignCenter)
        self.main_label.setWordWrap(True)
        self.main_label.setMinimumHeight(68)
        self.main_label.setStyleSheet(
            "font-size: 30px; font-weight: 900; border: none; background: transparent;"
        )

        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setMinimumHeight(38)
        self.result_label.setStyleSheet(result_text_style("ESPERANDO"))

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)
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

        # En espera no se muestra texto. El operador solo ve el indicador.
        if status in {"ESPERANDO", "COOLDOWN", "LECTURA RECIBIDA"}:
            if not self.main_label.text():
                self.result_label.setText("")
            elif status == "LECTURA RECIBIDA":
                self.result_label.setText("RECIBIDO")
            return

        if status == "SIN CONEXIÓN":
            # El popup de conexión es el mensaje principal; aquí solo se mantiene un estado discreto.
            self.result_label.setText("SIN CONEXIÓN")
            return

        self.result_label.setText(self._friendly_status(status))

    def set_code(self, code: str, length: int, timestamp: str) -> None:
        del length, timestamp  # La pantalla de producción no muestra datos técnicos.
        self.main_label.setText(code or "---")
        if self.current_status in {"ESPERANDO", "LECTURA RECIBIDA", "COOLDOWN"}:
            self.result_label.setText("RECIBIDO")
            self.result_label.setStyleSheet(result_text_style("LECTURA RECIBIDA"))

    def reset(self) -> None:
        self.current_status = "ESPERANDO"
        self.main_label.setText("")
        self.result_label.setText("")
        self.result_label.setStyleSheet(result_text_style("ESPERANDO"))
        self.indicator.setStyleSheet(indicator_style("ESPERANDO"))
        self.frame.setStyleSheet(card_style("ESPERANDO"))

    @staticmethod
    def _friendly_status(status: str) -> str:
        labels = {
            "ESPERANDO": "",
            "LECTURA RECIBIDA": "RECIBIDO",
            "NUEVO": "OK",
            "OK": "OK",
            "DUPLICADO": "DUPLICADO",
            "ERROR LONGITUD": "ERROR CÓDIGO",
            "ERROR SCANNER": "ERROR LECTURA",
            "SIN CONEXIÓN": "SIN CONEXIÓN",
            "COOLDOWN": "",
        }
        return labels.get(status, status)


class ConnectionPill(QWidget):
    """Indicador compacto para PLC/scanners."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame = QFrame()
        self.frame.setStyleSheet(connection_pill_style(False))

        self.dot = QLabel()
        self.dot.setStyleSheet(small_dot_style(False))

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 850; border: none; background: transparent;")

        self.state_label = QLabel("SIN CONEXIÓN")
        self.state_label.setStyleSheet(
            "font-size: 12px; color: rgba(226, 232, 240, 0.76); "
            "font-weight: 750; border: none; background: transparent;"
        )

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


class SensorCounterStrip(QWidget):
    """Contadores por sensor en una sola línea compacta.

    Mantiene la información necesaria sin tarjetas grandes ni títulos redundantes.
    """

    def __init__(self, side_label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame = QFrame()
        self.frame.setStyleSheet(sensor_counter_strip_style())

        self.side_label = QLabel(side_label)
        self.side_label.setAlignment(Qt.AlignCenter)
        self.side_label.setStyleSheet("font-size: 18px; font-weight: 950; border: none; background: transparent;")

        self.total_chip = StatChip("T", "neutral")
        self.good_chip = StatChip("OK", "ok")
        self.duplicate_chip = StatChip("DUP", "warning")
        self.read_error_chip = StatChip("LECT", "error")

        layout = QHBoxLayout(self.frame)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)
        layout.addWidget(self.side_label)
        layout.addWidget(self.total_chip)
        layout.addWidget(self.good_chip)
        layout.addWidget(self.duplicate_chip)
        layout.addWidget(self.read_error_chip)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.frame)

    def set_values(self, total: int, good: int, duplicate: int, read_error: int) -> None:
        self.total_chip.set_value(total)
        self.good_chip.set_value(good)
        self.duplicate_chip.set_value(duplicate)
        self.read_error_chip.set_value(read_error)


class StatChip(QWidget):
    """Pequeño contador con etiqueta corta y valor."""

    def __init__(self, label: str, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame = QFrame()
        self.frame.setStyleSheet(stat_chip_style(kind))

        self.label = QLabel(label)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            "font-size: 10px; color: rgba(226, 232, 240, 0.72); "
            "font-weight: 900; border: none; background: transparent;"
        )

        self.value = QLabel("0")
        self.value.setAlignment(Qt.AlignCenter)
        self.value.setStyleSheet("font-size: 28px; font-weight: 950; border: none; background: transparent;")

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(10, 5, 10, 6)
        layout.setSpacing(0)
        layout.addWidget(self.label)
        layout.addWidget(self.value)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.frame)

    def set_value(self, value: int) -> None:
        self.value.setText(str(value))
