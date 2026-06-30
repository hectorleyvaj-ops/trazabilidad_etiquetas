from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.models import CycleResult
from ui.styles import APP_STYLESHEET, badge_style
from ui.widgets import SensorCard
from workers.traceability_worker import TraceabilityWorker


class MainWindow(QMainWindow):
    """Ventana principal de producción.

    Importante: esta ventana no lee sockets, no escribe al PLC y no valida etiquetas.
    Solo muestra datos y manda señales de control al worker.
    """

    start_requested = Signal()
    stop_requested = Signal()
    reconnect_requested = Signal()
    simulate_once_requested = Signal()

    def __init__(self, config: dict, base_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.base_dir = base_dir

        self.setWindowTitle(config["app"].get("title", "Sistema de trazabilidad"))
        self.resize(1100, 720)
        self.setStyleSheet(APP_STYLESHEET)

        self._build_ui()
        self._setup_worker()

        if config.get("app", {}).get("auto_start", False):
            QTimer.singleShot(300, self.start_requested.emit)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        title = QLabel("SISTEMA DE TRAZABILIDAD")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")

        self.system_status_label = QLabel("DETENIDO")
        self.system_status_label.setStyleSheet(badge_style("DETENIDO"))

        self.cycle_result_label = QLabel("ESPERANDO")
        self.cycle_result_label.setStyleSheet(badge_style("ESPERANDO"))

        top_row = QHBoxLayout()
        top_row.addWidget(title)
        top_row.addStretch()
        top_row.addWidget(QLabel("Estado general:"))
        top_row.addWidget(self.system_status_label)
        top_row.addWidget(QLabel("Resultado ciclo:"))
        top_row.addWidget(self.cycle_result_label)

        self.right_card = SensorCard("NIDO DERECHO")
        self.left_card = SensorCard("NIDO IZQUIERDO")

        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        cards_row.addWidget(self.right_card)
        cards_row.addWidget(self.left_card)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setPlaceholderText("Log de eventos del sistema...")

        self.start_button = QPushButton("Iniciar sistema")
        self.stop_button = QPushButton("Detener sistema")
        self.reconnect_button = QPushButton("Reconectar dispositivos")
        self.clear_log_button = QPushButton("Limpiar log")
        self.simulate_button = QPushButton("Simular ciclo")

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(self.start_button)
        buttons_row.addWidget(self.stop_button)
        buttons_row.addWidget(self.reconnect_button)
        buttons_row.addWidget(self.clear_log_button)
        buttons_row.addStretch()
        buttons_row.addWidget(self.simulate_button)

        root.addLayout(top_row)
        root.addLayout(cards_row, stretch=2)
        root.addWidget(QLabel("LOG"))
        root.addWidget(self.log_view, stretch=3)
        root.addLayout(buttons_row)

        self.setCentralWidget(central)

        self.start_button.clicked.connect(self.start_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.reconnect_button.clicked.connect(self.reconnect_requested.emit)
        self.simulate_button.clicked.connect(self.simulate_once_requested.emit)
        self.clear_log_button.clicked.connect(self.log_view.clear)

    def _setup_worker(self) -> None:
        self.worker_thread = QThread(self)
        self.worker = TraceabilityWorker(config=self.config)
        self.worker.moveToThread(self.worker_thread)

        self.start_requested.connect(self.worker.start)
        self.stop_requested.connect(self.worker.stop)
        self.reconnect_requested.connect(self.worker.reconnect_devices)
        self.simulate_once_requested.connect(self.worker.simulate_once)

        self.worker.scanner_status_changed.connect(self.on_scanner_status_changed)
        self.worker.code_received.connect(self.on_code_received)
        self.worker.cycle_result.connect(self.on_cycle_result)
        self.worker.system_status_changed.connect(self.on_system_status_changed)
        self.worker.log_message.connect(self.on_log_message)
        self.worker.connection_status_changed.connect(self.on_connection_status_changed)

        self.worker_thread.start()

    @Slot(str, str)
    def on_scanner_status_changed(self, side: str, status: str) -> None:
        if side == "right":
            self.right_card.set_status(status)
        elif side == "left":
            self.left_card.set_status(status)

    @Slot(str, str, int, str)
    def on_code_received(self, side: str, code: str, length: int, timestamp: str) -> None:
        if side == "right":
            self.right_card.set_code(code, length, timestamp)
        elif side == "left":
            self.left_card.set_code(code, length, timestamp)

    @Slot(object)
    def on_cycle_result(self, result: CycleResult) -> None:
        status = result.general_result.value
        self.cycle_result_label.setText(status)
        self.cycle_result_label.setStyleSheet(badge_style(status))

    @Slot(str)
    def on_system_status_changed(self, status: str) -> None:
        self.system_status_label.setText(status)
        self.system_status_label.setStyleSheet(badge_style(status))

    @Slot(str, str)
    def on_log_message(self, level: str, message: str) -> None:
        self._append_log(level, message)

    @Slot(str, bool, str)
    def on_connection_status_changed(self, device: str, connected: bool, message: str) -> None:
        state = "CONECTADO" if connected else "SIN CONEXIÓN"
        level = "INFO" if connected else "ERROR"
        self._append_log(level, f"{device}: {state} ({message})")

    def _append_log(self, level: str, message: str) -> None:
        self.log_view.appendPlainText(f"[{level}] {message}")
        self.log_view.moveCursor(QTextCursor.End)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt usa camelCase
        self.stop_requested.emit()
        self.worker_thread.quit()
        self.worker_thread.wait(1500)
        super().closeEvent(event)
