from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.models import CycleResult, GeneralResult, NestSide
from ui.styles import APP_STYLESHEET, app_background_style, result_panel_style
from ui.widgets import ConnectionPill, SensorCard, SensorCounterStrip
from workers.traceability_worker import TraceabilityWorker


class MainWindow(QMainWindow):
    """Ventana principal V5 para operador.

    Está basada visualmente en la idea del panel oscuro del script Tkinter
    compartido por el usuario, pero mantiene la arquitectura PySide6 modular:
    la interfaz solo visualiza señales; no lee sockets, no escribe Excel y no
    manda comandos al PLC.
    """

    start_requested = Signal()
    stop_requested = Signal()
    simulate_once_requested = Signal()

    def __init__(self, config: dict, base_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.base_dir = base_dir

        self.right_counts = {"total": 0, "good": 0, "duplicate": 0, "read_error": 0}
        self.left_counts = {"total": 0, "good": 0, "duplicate": 0, "read_error": 0}
        self.connection_states = {
            "PLC": False,
            "Scanner derecho": False,
            "Scanner izquierdo": False,
        }
        self.connection_alerts: dict[str, QMessageBox] = {}
        self.notified_disconnected_devices: set[str] = set()

        self.setWindowTitle(config["app"].get("title", "Sistema de trazabilidad"))
        self.resize(1180, 720)
        self.setMinimumSize(980, 620)
        self.setStyleSheet(APP_STYLESHEET)

        self._build_ui()
        self._setup_worker()
        self._apply_system_theme("DETENIDO")

        # Producción: al abrir, el sistema inicia conexiones automáticamente.
        QTimer.singleShot(400, self.start_requested.emit)

    def _build_ui(self) -> None:
        self.root_widget = QWidget()
        self.root_widget.setObjectName("appRoot")
        root = QVBoxLayout(self.root_widget)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # Panel superior: resultado directo + contadores por sensor, sin títulos redundantes.
        self.result_panel = QFrame()
        self.result_panel.setStyleSheet(result_panel_style("ESPERANDO"))
        result_layout = QHBoxLayout(self.result_panel)
        result_layout.setContentsMargins(24, 16, 24, 16)
        result_layout.setSpacing(16)

        self.cycle_result_label = QLabel("ESPERANDO")
        self.cycle_result_label.setStyleSheet(
            "font-size: 54px; font-weight: 950; letter-spacing: 1px; "
            "border: none; background: transparent;"
        )
        self.cycle_result_label.setMinimumHeight(74)

        self.left_counter_strip = SensorCounterStrip("IZQ")
        self.right_counter_strip = SensorCounterStrip("DER")

        counters_col = QVBoxLayout()
        counters_col.setSpacing(8)
        counters_col.addWidget(self.left_counter_strip)
        counters_col.addWidget(self.right_counter_strip)

        result_layout.addWidget(self.cycle_result_label, stretch=3)
        result_layout.addLayout(counters_col, stretch=5)

        # Panel central: dos nidos, indicadores grandes y texto mínimo.
        self.left_card = SensorCard("NIDO IZQUIERDO")
        self.right_card = SensorCard("NIDO DERECHO")

        cards_row = QHBoxLayout()
        cards_row.setSpacing(18)
        cards_row.addWidget(self.left_card)
        cards_row.addWidget(self.right_card)

        # Fila inferior: conexiones discretas + controles mínimos.
        self.plc_pill = ConnectionPill("PLC")
        self.left_pill = ConnectionPill("Izquierdo")
        self.right_pill = ConnectionPill("Derecho")

        connections_row = QHBoxLayout()
        connections_row.setSpacing(8)
        connections_row.addWidget(self.plc_pill)
        connections_row.addWidget(self.left_pill)
        connections_row.addWidget(self.right_pill)

        self.stop_button = QPushButton("Detener")
        self.stop_button.setObjectName("dangerButton")
        self.start_button = QPushButton("Reanudar")
        self.start_button.setObjectName("primaryButton")
        self.reset_counters_button = QPushButton("Reiniciar contadores")
        self.clear_log_button = QPushButton("Limpiar log")
        self.simulate_button = QPushButton("Simular")

        if not self.config.get("app", {}).get("simulation_enabled", False):
            self.simulate_button.hide()

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        buttons_row.addWidget(self.stop_button)
        buttons_row.addWidget(self.start_button)
        buttons_row.addWidget(self.reset_counters_button)
        buttons_row.addWidget(self.clear_log_button)
        buttons_row.addWidget(self.simulate_button)

        footer_row = QHBoxLayout()
        footer_row.setSpacing(12)
        footer_row.addLayout(connections_row, stretch=4)
        footer_row.addStretch(1)
        footer_row.addLayout(buttons_row, stretch=4)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(100)
        self.log_view.setFixedHeight(58)
        self.log_view.setPlaceholderText("Eventos recientes...")

        root.addWidget(self.result_panel)
        root.addLayout(cards_row, stretch=1)
        root.addLayout(footer_row)
        root.addWidget(self.log_view)

        self.setCentralWidget(self.root_widget)

        self.start_button.clicked.connect(self.start_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.simulate_button.clicked.connect(self.simulate_once_requested.emit)
        self.clear_log_button.clicked.connect(self.log_view.clear)
        self.reset_counters_button.clicked.connect(self.reset_counters)

    def _setup_worker(self) -> None:
        self.worker_thread = QThread(self)
        self.worker = TraceabilityWorker(config=self.config, base_dir=self.base_dir)
        self.worker.moveToThread(self.worker_thread)

        self.start_requested.connect(self.worker.start)
        self.stop_requested.connect(self.worker.stop)
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
        if side == NestSide.RIGHT.value:
            self.right_card.set_status(status)
        elif side == NestSide.LEFT.value:
            self.left_card.set_status(status)

    @Slot(str, str, int, str)
    def on_code_received(self, side: str, code: str, length: int, timestamp: str) -> None:
        if side == NestSide.RIGHT.value:
            self.right_card.set_code(code, length, timestamp)
        elif side == NestSide.LEFT.value:
            self.left_card.set_code(code, length, timestamp)

    @Slot(object)
    def on_cycle_result(self, result: CycleResult) -> None:
        status = result.general_result.value
        self.cycle_result_label.setText(self._friendly_general_result(result.general_result))
        self.result_panel.setStyleSheet(result_panel_style(status))
        self._apply_system_theme(status)
        self._update_counters(result)

    @Slot(str)
    def on_system_status_changed(self, status: str) -> None:
        # La pantalla superior queda enfocada al resultado del ciclo, no al estado técnico.
        self._apply_system_theme(status)
        if status == "DETENIDO":
            self.cycle_result_label.setText("DETENIDO")
            self.result_panel.setStyleSheet(result_panel_style(status))
            self._set_all_connections(False)
            self.right_card.reset()
            self.left_card.reset()
        elif status in {"ESPERANDO LECTURAS", "INICIANDO", "LISTO"} and self.cycle_result_label.text() in {"DETENIDO", "INICIANDO"}:
            self.cycle_result_label.setText("ESPERANDO")
            self.result_panel.setStyleSheet(result_panel_style("ESPERANDO"))

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
            self._apply_system_theme("SIN CONEXIÓN")
            self._show_connection_popup(normalized or device, message)
        else:
            self._close_connection_popup(normalized or device)

    @Slot()
    def reset_counters(self) -> None:
        self.right_counts = {"total": 0, "good": 0, "duplicate": 0, "read_error": 0}
        self.left_counts = {"total": 0, "good": 0, "duplicate": 0, "read_error": 0}
        self._refresh_counter_labels()
        self._append_log("INFO", "Contadores reiniciados desde interfaz.")

    def _update_counters(self, result: CycleResult) -> None:
        self._update_sensor_counter(result.right, self.right_counts)
        self._update_sensor_counter(result.left, self.left_counts)
        self._refresh_counter_labels()

    @staticmethod
    def _update_sensor_counter(side_result, counters: dict[str, int]) -> None:
        if side_result is None:
            return

        status = side_result.status.value
        counters["total"] += 1

        if status in {"NUEVO", "OK"}:
            counters["good"] += 1
        elif status == "DUPLICADO":
            counters["duplicate"] += 1
        elif status in {"ERROR SCANNER", "ERROR LONGITUD"}:
            counters["read_error"] += 1

    def _refresh_counter_labels(self) -> None:
        self.left_counter_strip.set_values(
            self.left_counts["total"],
            self.left_counts["good"],
            self.left_counts["duplicate"],
            self.left_counts["read_error"],
        )
        self.right_counter_strip.set_values(
            self.right_counts["total"],
            self.right_counts["good"],
            self.right_counts["duplicate"],
            self.right_counts["read_error"],
        )

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

    def _show_connection_popup(self, device: str, message: str) -> None:
        if device in self.notified_disconnected_devices:
            return
        self.notified_disconnected_devices.add(device)
        detail = message or "No se pudo establecer comunicación."
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("Error de conexión")
        box.setText(f"{device} sin conexión")
        box.setInformativeText(
            "Revisa alimentación, cableado, red, puerto configurado y que el dispositivo esté encendido.\n\n"
            f"Detalle: {detail}"
        )
        box.setStandardButtons(QMessageBox.Ok)
        box.setModal(False)
        box.finished.connect(lambda _result, name=device: self.connection_alerts.pop(name, None))
        self.connection_alerts[device] = box
        box.show()

    def _close_connection_popup(self, device: str) -> None:
        self.notified_disconnected_devices.discard(device)
        box = self.connection_alerts.pop(device, None)
        if box is not None:
            box.close()

    @staticmethod
    def _friendly_general_result(result: GeneralResult) -> str:
        labels = {
            GeneralResult.WAITING: "ESPERANDO",
            GeneralResult.OK: "OK",
            GeneralResult.ERROR: "ERROR",
            GeneralResult.DUPLICATE: "DUPLICADO",
            GeneralResult.READ_ERROR: "ERROR LECTURA",
            GeneralResult.LENGTH_ERROR: "ERROR CÓDIGO",
            GeneralResult.CONNECTION_ERROR: "SIN CONEXIÓN",
        }
        return labels.get(result, result.value)

    def _apply_system_theme(self, status: str) -> None:
        self.root_widget.setStyleSheet(app_background_style(status))

    def _append_log(self, level: str, message: str) -> None:
        self.log_view.appendPlainText(f"[{level}] {message}")
        self.log_view.moveCursor(QTextCursor.End)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt usa camelCase
        self.stop_requested.emit()
        for box in list(self.connection_alerts.values()):
            box.close()
        self.connection_alerts.clear()
        self.notified_disconnected_devices.clear()
        self.worker_thread.quit()
        self.worker_thread.wait(1500)
        super().closeEvent(event)
