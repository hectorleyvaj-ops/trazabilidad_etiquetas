from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.styles import (
    alert_dialog_style,
    card_style,
    connection_pill_style,
    indicator_style,
    production_counter_strip_style,
    result_text_style,
    small_dot_style,
    stat_chip_style,
)


class SensorCard(QWidget):
    """Tarjeta minimalista de nido para operador.

    Muestra: título, indicador circular y una sola línea de estado/código.
    El objetivo es evitar solapes y no repetir información técnica.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.current_status = "ESPERANDO"
        self.current_code = ""

        self.frame = QFrame()
        self.frame.setStyleSheet(card_style("ESPERANDO"))
        self.frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(
            "font-size: 28px; font-weight: 900; letter-spacing: 0.6px; "
            "border: none; background: transparent; color: rgba(243, 246, 248, 0.96);"
        )
        self.title_label.setFixedHeight(40)

        self.indicator = QLabel()
        self.indicator.setAlignment(Qt.AlignCenter)
        self.indicator.setStyleSheet(indicator_style("ESPERANDO"))
        self.indicator.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.status_code_label = QLabel("ESPERANDO")
        self.status_code_label.setAlignment(Qt.AlignCenter)
        self.status_code_label.setWordWrap(True)
        self.status_code_label.setMinimumHeight(108)
        self.status_code_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.status_code_label.setStyleSheet(result_text_style("ESPERANDO"))

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(30, 24, 30, 28)
        layout.setSpacing(0)
        layout.addWidget(self.title_label)
        layout.addStretch(1)
        layout.addWidget(self.indicator, alignment=Qt.AlignCenter)
        layout.addSpacing(34)
        layout.addWidget(self.status_code_label)
        layout.addStretch(2)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.frame)

    def set_status(self, status: str) -> None:
        self.current_status = status
        self.indicator.setStyleSheet(indicator_style(status))
        self.frame.setStyleSheet(card_style(status))
        self.status_code_label.setStyleSheet(result_text_style(status))
        self._refresh_text()

    def set_code(self, code: str, length: int, timestamp: str) -> None:
        del length, timestamp  # La pantalla de producción no muestra datos técnicos.
        self.current_code = (code or "").strip()
        if self.current_status in {"ESPERANDO", "COOLDOWN"}:
            self.current_status = "LECTURA RECIBIDA"
        self.status_code_label.setStyleSheet(result_text_style(self.current_status))
        self._refresh_text()

    def reset(self) -> None:
        self.current_status = "ESPERANDO"
        self.current_code = ""
        self.status_code_label.setText("ESPERANDO")
        self.status_code_label.setStyleSheet(result_text_style("ESPERANDO"))
        self.indicator.setStyleSheet(indicator_style("ESPERANDO"))
        self.frame.setStyleSheet(card_style("ESPERANDO"))

    def _refresh_text(self) -> None:
        status_text = self._friendly_status(self.current_status)
        if self.current_code:
            self.status_code_label.setText(f"{status_text} - {self.current_code}")
        else:
            self.status_code_label.setText(status_text)

    @staticmethod
    def _friendly_status(status: str) -> str:
        labels = {
            "ESPERANDO": "ESPERANDO",
            "ESPERANDO LECTURAS": "ESPERANDO",
            "LECTURA RECIBIDA": "RECIBIDO",
            "NUEVO": "CORRECTO",
            "OK": "CORRECTO",
            "LECTURA OK": "CORRECTO",
            "DUPLICADO": "DUPLICADO",
            "ERROR LONGITUD": "ERROR CÓDIGO",
            "ERROR DE LONGITUD": "ERROR CÓDIGO",
            "ERROR SCANNER": "ERROR LECTURA",
            "ERROR DE LECTURA": "ERROR LECTURA",
            "SIN CONEXIÓN": "SIN CONEXIÓN",
            "COOLDOWN": "LIMPIANDO",
        }
        return labels.get(status, status)


class ConnectionPill(QWidget):
    """Indicador compacto de conexión: texto + punto de color."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame = QFrame()
        self.frame.setStyleSheet(connection_pill_style(False))

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "font-size: 13px; font-weight: 850; border: none; background: transparent; "
            "color: rgba(243, 246, 248, 0.88);"
        )

        self.dot = QLabel()
        self.dot.setStyleSheet(small_dot_style(False))

        layout = QHBoxLayout(self.frame)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(9)
        layout.addWidget(self.title_label)
        layout.addWidget(self.dot)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.frame)

    def set_connected(self, connected: bool, message: str = "") -> None:
        self.frame.setStyleSheet(connection_pill_style(connected))
        self.dot.setStyleSheet(small_dot_style(connected))
        if message:
            self.setToolTip(message)


class ProductionCounterStrip(QWidget):
    """Contadores globales por lectura individual de sensor."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame = QFrame()
        self.frame.setStyleSheet(production_counter_strip_style())
        self.frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.total_chip = StatChip("TOTAL", "neutral")
        self.good_chip = StatChip("OK", "ok")
        self.duplicate_chip = StatChip("DUP", "warning")
        self.read_error_chip = StatChip("LECT", "error")

        layout = QGridLayout(self.frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(0)
        layout.addWidget(self.total_chip, 0, 0)
        layout.addWidget(self.good_chip, 0, 1)
        layout.addWidget(self.duplicate_chip, 0, 2)
        layout.addWidget(self.read_error_chip, 0, 3)
        for col in range(4):
            layout.setColumnStretch(col, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.frame)

    def set_values(self, total: int, good: int, duplicate: int, read_error: int) -> None:
        self.total_chip.set_value(total)
        self.good_chip.set_value(good)
        self.duplicate_chip.set_value(duplicate)
        self.read_error_chip.set_value(read_error)


class StatChip(QWidget):
    """Contador compacto: número grande + etiqueta corta."""

    def __init__(self, label: str, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame = QFrame()
        self.frame.setStyleSheet(stat_chip_style(kind))
        self.frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.value = QLabel("0")
        self.value.setAlignment(Qt.AlignCenter)
        self.value.setStyleSheet("font-size: 25px; font-weight: 950; border: none; background: transparent;")

        self.label = QLabel(label)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            "font-size: 9px; color: rgba(226, 232, 240, 0.66); "
            "font-weight: 900; border: none; background: transparent; letter-spacing: 0.5px;"
        )

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(8, 4, 8, 5)
        layout.setSpacing(0)
        layout.addWidget(self.value)
        layout.addWidget(self.label)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.frame)

    def set_value(self, value: int) -> None:
        self.value.setText(str(value))


class ConnectionAlertDialog(QDialog):
    """Popup industrial no bloqueante para errores de conexión."""

    def __init__(self, device: str, detail: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Máquina detenida")
        self.setModal(False)
        self.setMinimumWidth(520)
        self.setStyleSheet(alert_dialog_style())

        title = QLabel("MÁQUINA DETENIDA")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 30px; font-weight: 950; letter-spacing: 1px;")

        device_label = QLabel(f"{device} SIN CONEXIÓN")
        device_label.setAlignment(Qt.AlignCenter)
        device_label.setWordWrap(True)
        device_label.setStyleSheet("font-size: 22px; font-weight: 900; color: rgb(254, 226, 226);")

        detail_label = QLabel(
            "Revisa alimentación, cableado, red, puerto configurado y que el dispositivo esté encendido.\n\n"
            f"Detalle: {detail or 'No se pudo establecer comunicación.'}\n\n"
            "El sistema intentará reconectar automáticamente."
        )
        detail_label.setAlignment(Qt.AlignCenter)
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet("font-size: 14px; color: rgba(255, 255, 255, 0.84); line-height: 1.35;")

        ok_button = QPushButton("ENTENDIDO")
        ok_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(device_label)
        layout.addWidget(detail_label)
        layout.addWidget(ok_button, alignment=Qt.AlignCenter)
