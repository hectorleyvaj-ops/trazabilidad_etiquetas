from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.models import CycleResult, GeneralResult, NestSide
from ui.styles import APP_STYLESHEET, app_background_style, badge_style, result_panel_style
from ui.widgets import AlertBanner, ConnectionPill, CounterCard, SensorCard
from workers.traceability_worker import TraceabilityWorker


class MainWindow(QMainWindow):
    """Ventana principal enfocada en operación de producción.

    La interfaz no lee sockets, no escribe al PLC y no valida etiquetas.
    Solo muestra estado, contadores, alertas y manda señales de control al worker.
    """

    start_requested = Signal()
    stop_requested = Signal()
    reconnect_requested = Signal()
    simulate_once_requested = Signal()

    def __init__(self, config: dict, base_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.base_dir = base_dir

        self.good_count = 0
        self.error_count = 0
        self.duplicate_count = 0
        self.total_count = 0
        self.connection_states = {
            "PLC": False,
            "Scanner derecho": False,
            "Scanner izquierdo": False,
        }

        self.setWindowTitle(config["app"].get("title", "Sistema de trazabilidad"))
        self.resize(1180, 760)
        self.setMinimumSize(980, 640)
        self.setStyleSheet(APP_STYLESHEET)

        self._build_ui()
        self._setup_worker()
        self._apply_system_theme("DETENIDO")

        if config.get("app", {}).get("auto_start", False):
            QTimer.singleShot(300, self.start_requested.emit)

    def _build_ui(self) -> None:
        self.root_widget = QWidget()
        self.root_widget.setObjectName("appRoot")
        root = QVBoxLayout(self.root_widget)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel("SISTEMA DE TRAZABILIDAD")
        title.setStyleSheet("font-size: 30px; font-weight: 900; letter-spacing: 1px;")

        self.system_status_label = QLabel("DETENIDO")
        self.system_status_label.setStyleSheet(badge_style("DETENIDO"))

        header_row = QHBoxLayout()
        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(self.system_status_label)

        self.plc_pill = ConnectionPill("PLC")
        self.right_pill = ConnectionPill("Scanner derecho")
        self.left_pill = ConnectionPill("Scanner izquierdo")

        connections_row = QHBoxLayout()
        connections_row.setSpacing(10)
        connections_row.addWidget(self.plc_pill)
        connections_row.addWidget(self.right_pill)
        connections_row.addWidget(self.left_pill)
        connections_row.addStretch()

        self.alert_banner = AlertBanner()

        self.result_panel = QFrame()
        self.result_panel.setStyleSheet(result_panel_style("ESPERANDO"))
        result_layout = QHBoxLayout(self.result_panel)
        result_layout.setContentsMargins(20, 16, 20, 16)
        result_layout.setSpacing(18)

        result_caption = QLabel("Resultado del ciclo")
        result_caption.setStyleSheet("font-size: 15px; color: rgba(238, 242, 248, 0.72); font-weight: 700;")
        self.cycle_result_label = QLabel("ESPERANDO")
        self.cycle_result_label.setStyleSheet("font-size: 42px; font-weight: 950;")
        self.cycle_result_label.setMinimumHeight(54)

        result_text_col = QVBoxLayout()
        result_text_col.addWidget(result_caption)
        result_text_col.addWidget(self.cycle_result_label)

        self.total_counter = CounterCard("TOTAL", "info")
        self.good_counter = CounterCard("BUENAS", "ok")
        self.error_counter = CounterCard("ERRORES", "error")
        self.duplicate_counter = CounterCard("DUPLICADAS", "warning")

        counters_row = QHBoxLayout()
        counters_row.setSpacing(10)
        counters_row.addWidget(self.total_counter)
        counters_row.addWidget(self.good_counter)
        counters_row.addWidget(self.error_counter)
        counters_row.addWidget(self.duplicate_counter)

        result_layout.addLayout(result_text_col, stretch=3)
        result_layout.addLayout(counters_row, stretch=4)

        self.right_card = SensorCard("NIDO DERECHO")
        self.left_card = SensorCard("NIDO IZQUIERDO")

        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        cards_row.addWidget(self.right_card)
        cards_row.addWidget(self.left_card)

        log_title = QLabel("Eventos recientes")
        log_title.setStyleSheet("font-size: 13px; font-weight: 800; color: rgba(238, 242, 248, 0.68);")

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(180)
        self.log_view.setFixedHeight(128)
        self.log_view.setPlaceholderText("Eventos recientes del sistema...")

        self.start_button = QPushButton("Iniciar")
        self.start_button.setObjectName("primaryButton")
        self.stop_button = QPushButton("Detener")
        self.stop_button.setObjectName("dangerButton")
        self.reconnect_button = QPushButton("Reconectar")
        self.clear_log_button = QPushButton("Limpiar log")
        self.reset_counters_button = QPushButton("Reiniciar contadores")
        self.simulate_button = QPushButton("Simular ciclo")

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)
        buttons_row.addWidget(self.start_button)
        buttons_row.addWidget(self.stop_button)
        buttons_row.addWidget(self.reconnect_button)
        buttons_row.addWidget(self.reset_counters_button)
        buttons_row.addWidget(self.clear_log_button)
        buttons_row.addStretch()
        buttons_row.addWidget(self.simulate_button)

        root.addLayout(header_row)
        root.addLayout(connections_row)
        root.addWidget(self.alert_banner)
        root.addWidget(self.result_panel)
        root.addLayout(cards_row, stretch=1)
        root.addWidget(log_title)
        root.addWidget(self.log_view)
        root.addLayout(buttons_row)

        self.setCentralWidget(self.root_widget)

        self.start_button.clicked.connect(self.start_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.reconnect_button.clicked.connect(self.reconnect_requested.emit)
        self.simulate_button.clicked.connect(self.simulate_once_requested.emit)
        self.clear_log_button.clicked.connect(self.log_view.clear)
        self.reset_counters_button.clicked.connect(self.reset_counters)

    def _setup_worker(self) -> None:
        self.worker_thread = QThread(self)
        self.worker = TraceabilityWorker(config=self.config, base_dir=self.base_dir)
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
        self.result_panel.setStyleSheet(result_panel_style(status))
        self._apply_system_theme(status)
        self._update_counters(result.general_result)

    @Slot(str)
    def on_system_status_changed(self, status: str) -> None:
        self.system_status_label.setText(status)
        self.system_status_label.setStyleSheet(badge_style(status))
        self._apply_system_theme(status)
        if status == "DETENIDO":
            self._set_all_connections(False)
            self.alert_banner.clear_alert()

    @Slot(str, str)
    def on_log_message(self, level: str, message: str) -> None:
        self._append_log(level, message)

    @Slot(str, bool, str)
    def on_connection_status_changed(self, device: str, connected: bool, message: str) -> None:
        normalized = self._normalize_device_name(device)
        if normalized:
            self.connection_states[normalized] = connected
            self._update_connection_pill(normalized, connected, message)

        state = "CONECTADO" if connected else "SIN CONEXIÓN"
        level = "INFO" if connected else "ERROR"
        self._append_log(level, f"{device}: {state} ({message})")

        if not connected:
            self.alert_banner.show_alert(f"{device} sin conexión. Revisa cableado, red, alimentación o puerto configurado.")
            self._apply_system_theme("SIN CONEXIÓN")
        else:
            self._refresh_alert_banner()

    @Slot()
    def reset_counters(self) -> None:
        self.good_count = 0
        self.error_count = 0
        self.duplicate_count = 0
        self.total_count = 0
        self._refresh_counter_labels()
        self._append_log("INFO", "Contadores reiniciados desde interfaz.")

    def _update_counters(self, general_result: GeneralResult) -> None:
        self.total_count += 1
        if general_result == GeneralResult.OK:
            self.good_count += 1
        elif general_result == GeneralResult.DUPLICATE:
            self.duplicate_count += 1
        else:
            self.error_count += 1
        self._refresh_counter_labels()

    def _refresh_counter_labels(self) -> None:
        self.total_counter.set_value(self.total_count)
        self.good_counter.set_value(self.good_count)
        self.error_counter.set_value(self.error_count)
        self.duplicate_counter.set_value(self.duplicate_count)

    def _normalize_device_name(self, device: str) -> str | None:
        device_lower = device.lower()
        if "plc" in device_lower:
            return "PLC"
        if "derecho" in device_lower:
            return "Scanner derecho"
        if "izquierdo" in device_lower:
            return "Scanner izquierdo"
        return None

    def _update_connection_pill(self, device: str, connected: bool, message: str) -> None:
        if device == "PLC":
            self.plc_pill.set_connected(connected, message)
        elif device == "Scanner derecho":
            self.right_pill.set_connected(connected, message)
        elif device == "Scanner izquierdo":
            self.left_pill.set_connected(connected, message)

    def _set_all_connections(self, connected: bool) -> None:
        for device in self.connection_states:
            self.connection_states[device] = connected
            self._update_connection_pill(device, connected, "Sistema detenido" if not connected else "")

    def _refresh_alert_banner(self) -> None:
        disconnected = [name for name, ok in self.connection_states.items() if not ok]
        if disconnected:
            self.alert_banner.show_alert("Dispositivo sin conexión: " + ", ".join(disconnected))
        else:
            self.alert_banner.clear_alert()

    def _apply_system_theme(self, status: str) -> None:
        self.root_widget.setStyleSheet(app_background_style(status))

    def _append_log(self, level: str, message: str) -> None:
        self.log_view.appendPlainText(f"[{level}] {message}")
        self.log_view.moveCursor(QTextCursor.End)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt usa camelCase
        self.stop_requested.emit()
        self.worker_thread.quit()
        self.worker_thread.wait(1500)
        super().closeEvent(event)
