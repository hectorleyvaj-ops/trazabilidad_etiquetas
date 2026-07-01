from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.styles import (
    alert_banner_style,
    card_style,
    connection_pill_style,
    counter_card_style,
    indicator_style,
    small_dot_style,
)


class SensorCard(QWidget):
    """Tarjeta grande y simple para producción.

    La tarjeta muestra solo lo que necesita el operador:
    nido, indicador visual, estado y último código.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title

        self.frame = QFrame()
        self.frame.setStyleSheet(card_style("ESPERANDO"))

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 22px; font-weight: 800; letter-spacing: 1px;")

        self.indicator = QLabel()
        self.indicator.setStyleSheet(indicator_style("ESPERANDO"))

        self.status_label = QLabel("ESPERANDO")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 30px; font-weight: 900;")

        self.code_caption = QLabel("Código leído")
        self.code_caption.setAlignment(Qt.AlignCenter)
        self.code_caption.setStyleSheet("font-size: 13px; color: rgba(238, 242, 248, 0.70);")

        self.code_label = QLabel("---")
        self.code_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.code_label.setAlignment(Qt.AlignCenter)
        self.code_label.setStyleSheet("font-size: 24px; font-weight: 700; font-family: Consolas, monospace;")
        self.code_label.setWordWrap(True)

        self.detail_label = QLabel("Longitud: --   ·   Última lectura: --")
        self.detail_label.setAlignment(Qt.AlignCenter)
        self.detail_label.setStyleSheet("font-size: 12px; color: rgba(238, 242, 248, 0.66);")

        grid = QGridLayout()
        grid.setContentsMargins(22, 22, 22, 22)
        grid.setVerticalSpacing(12)
        grid.addWidget(self.title_label, 0, 0, 1, 2)
        grid.addWidget(self.indicator, 1, 0, 3, 1, alignment=Qt.AlignCenter)
        grid.addWidget(self.status_label, 1, 1)
        grid.addWidget(self.code_caption, 2, 1)
        grid.addWidget(self.code_label, 3, 1)
        grid.addWidget(self.detail_label, 4, 0, 1, 2)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
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
        self.detail_label.setText(f"Longitud: {length}   ·   Última lectura: {timestamp}")

    def reset(self) -> None:
        self.set_status("ESPERANDO")
        self.set_code("---", 0, "--")


class ConnectionPill(QWidget):
    """Indicador compacto para PLC/scanners."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame = QFrame()
        self.frame.setStyleSheet(connection_pill_style(False))

        self.dot = QLabel()
        self.dot.setStyleSheet(small_dot_style(False))

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 800;")

        self.state_label = QLabel("SIN CONEXIÓN")
        self.state_label.setStyleSheet("font-size: 12px; color: rgba(238, 242, 248, 0.75);")

        layout = QHBoxLayout(self.frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.addWidget(self.dot)
        layout.addWidget(self.title_label)
        layout.addWidget(self.state_label)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.frame)

    def set_connected(self, connected: bool, message: str = "") -> None:
        self.frame.setStyleSheet(connection_pill_style(connected))
        self.dot.setStyleSheet(small_dot_style(connected))
        self.state_label.setText("CONECTADO" if connected else "SIN CONEXIÓN")
        if message:
            self.setToolTip(message)


class CounterCard(QWidget):
    def __init__(self, title: str, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame = QFrame()
        self.frame.setStyleSheet(counter_card_style(kind))

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 13px; color: rgba(238, 242, 248, 0.75); font-weight: 700;")

        self.value_label = QLabel("0")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet("font-size: 34px; font-weight: 900;")

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(4)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.frame)

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))


class AlertBanner(QWidget):
    """Banner persistente para alertas de producción.

    Se usa en lugar de ventanas modales para no bloquear operación ni repetir popups.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame = QFrame()
        self.frame.setStyleSheet(alert_banner_style("critical"))

        self.title_label = QLabel("ALERTA DE SISTEMA")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 900;")

        self.message_label = QLabel("---")
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("font-size: 14px; font-weight: 600;")

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(2)
        layout.addWidget(self.title_label)
        layout.addWidget(self.message_label)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.frame)
        self.hide()

    def show_alert(self, message: str, level: str = "critical") -> None:
        self.frame.setStyleSheet(alert_banner_style(level))
        self.message_label.setText(message)
        self.show()

    def clear_alert(self) -> None:
        self.message_label.setText("---")
        self.hide()
