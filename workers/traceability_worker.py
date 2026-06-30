from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from core.models import CycleResult, GeneralResult, NestSide, ReadingStatus, ValidationResult

logger = logging.getLogger(__name__)


class TraceabilityWorker(QObject):
    """Worker de trazabilidad.

    Esta primera versión trabaja en modo simulación para probar la interfaz,
    las señales y el hilo sin depender todavía de scanners ni PLC.
    """

    scanner_status_changed = Signal(str, str)       # side, status
    code_received = Signal(str, str, int, str)      # side, code, length, timestamp
    cycle_result = Signal(object)                   # CycleResult
    system_status_changed = Signal(str)             # status
    log_message = Signal(str, str)                  # level, message
    connection_status_changed = Signal(str, bool, str)  # device, connected, message

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.config = config
        self._running = False
        self._timer: QTimer | None = None
        self._cycle_counter = 0

    @Slot()
    def start(self) -> None:
        if self._running:
            self._emit_log("WARNING", "El sistema ya está iniciado.")
            return

        self._running = True
        self._cycle_counter = 0
        self.system_status_changed.emit("INICIANDO")
        self._emit_log("INFO", "Inicio del sistema en modo simulación.")
        self._simulate_connections()

        interval = int(self.config.get("simulation", {}).get("cycle_interval_ms", 3500))
        self._timer = QTimer(self)
        self._timer.setInterval(interval)
        self._timer.timeout.connect(self._simulate_cycle)
        self._timer.start()

        self.system_status_changed.emit("ESPERANDO LECTURAS")
        self._emit_log("INFO", f"Worker simulado ejecutándose cada {interval} ms.")

    @Slot()
    def stop(self) -> None:
        if not self._running:
            self._emit_log("WARNING", "El sistema ya está detenido.")
            return

        self._running = False
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None

        self.system_status_changed.emit("DETENIDO")
        self.scanner_status_changed.emit(NestSide.RIGHT.value, "ESPERANDO")
        self.scanner_status_changed.emit(NestSide.LEFT.value, "ESPERANDO")
        self._emit_log("INFO", "Sistema detenido de forma segura.")

    @Slot()
    def reconnect_devices(self) -> None:
        self.system_status_changed.emit("INICIANDO")
        self._emit_log("INFO", "Reconexión simulada de dispositivos solicitada.")
        self._simulate_connections()
        if self._running:
            self.system_status_changed.emit("ESPERANDO LECTURAS")
        else:
            self.system_status_changed.emit("LISTO")

    @Slot()
    def simulate_once(self) -> None:
        if not self._running:
            self._emit_log("WARNING", "Simulación manual ejecutada con el sistema detenido.")
        self._simulate_cycle()

    def _simulate_connections(self) -> None:
        right_cfg = self.config["scanners"]["right"]
        left_cfg = self.config["scanners"]["left"]
        plc_cfg = self.config["plc"]

        self.connection_status_changed.emit("Scanner derecho", True, f"{right_cfg['ip']}:{right_cfg['port']}")
        self.connection_status_changed.emit("Scanner izquierdo", True, f"{left_cfg['ip']}:{left_cfg['port']}")
        self.connection_status_changed.emit("PLC", True, f"{plc_cfg['port']} @ {plc_cfg['baudrate']}")

        self.scanner_status_changed.emit(NestSide.RIGHT.value, "ESPERANDO")
        self.scanner_status_changed.emit(NestSide.LEFT.value, "ESPERANDO")

        self._emit_log("INFO", f"Scanner derecho conectado a {right_cfg['ip']}:{right_cfg['port']}.")
        self._emit_log("INFO", f"Scanner izquierdo conectado a {left_cfg['ip']}:{left_cfg['port']}.")
        self._emit_log("INFO", f"PLC conectado en {plc_cfg['port']} @ {plc_cfg['baudrate']}.")

    def _simulate_cycle(self) -> None:
        self._cycle_counter += 1
        now = datetime.now()
        timestamp = now.strftime("%H:%M:%S")

        self.system_status_changed.emit("VALIDANDO")

        right_result, left_result = self._build_simulated_results(timestamp)

        for result in (right_result, left_result):
            self.code_received.emit(result.side.value, result.code, result.length, timestamp)
            self.scanner_status_changed.emit(result.side.value, result.status.value)
            self._emit_log("INFO", f"{result.side.value.upper()} → {result.status.value}: {result.message}")

        if right_result.status == ReadingStatus.NEW and left_result.status == ReadingStatus.NEW:
            general = GeneralResult.OK
            plc_value = self.config["plc"]["d0_values"]["ok"]
            self.system_status_changed.emit("ENVIANDO OK AL PLC")
            self._emit_log("INFO", f"Ciclo OK. Valor simulado al PLC: K1 / {plc_value}.")
        else:
            general = self._general_error_from_results(right_result, left_result)
            plc_value = self.config["plc"]["d0_values"]["error"]
            self.system_status_changed.emit("ENVIANDO ERROR AL PLC")
            self._emit_log("WARNING", f"Ciclo con error. Valor simulado al PLC: K2 / {plc_value}.")

        cycle = CycleResult(
            right=right_result,
            left=left_result,
            general_result=general,
            plc_value=plc_value,
            finished_at=now,
        )
        self.cycle_result.emit(cycle)

        self.system_status_changed.emit("RESET PLC")
        reset_value = self.config["plc"]["d0_values"]["reset"]
        self._emit_log("INFO", f"Reset simulado al PLC: K0 / {reset_value}.")

        self.system_status_changed.emit("COOLDOWN")
        self.scanner_status_changed.emit(NestSide.RIGHT.value, "COOLDOWN")
        self.scanner_status_changed.emit(NestSide.LEFT.value, "COOLDOWN")
        self._emit_log("INFO", "Cooldown simulado; lecturas tardías serían ignoradas.")

        QTimer.singleShot(
            int(self.config.get("cycle", {}).get("cooldown_ms", 1000)),
            self._finish_cooldown,
        )

    def _build_simulated_results(self, timestamp: str) -> tuple[ValidationResult, ValidationResult]:
        valid_code = "A024C393CBLK2615312139"
        duplicate_code = "A024C393CBLK2615312139"
        long_code = "A024C393CBLK2615312139A024C393CBLK2615312139"
        no_read_code = "NOREAD"

        pattern = self._cycle_counter % 4

        if pattern == 1:
            return (
                self._result(NestSide.RIGHT, valid_code, ReadingStatus.NEW, "Lectura simulada válida."),
                self._result(NestSide.LEFT, valid_code, ReadingStatus.NEW, "Lectura simulada válida."),
            )
        if pattern == 2:
            return (
                self._result(NestSide.RIGHT, duplicate_code, ReadingStatus.DUPLICATE, "Código ya existe con estado NUEVO."),
                self._result(NestSide.LEFT, valid_code, ReadingStatus.NEW, "Lectura simulada válida."),
            )
        if pattern == 3:
            display_code = f"ERROR_LONGITUD_{len(long_code)}"
            return (
                self._result(NestSide.RIGHT, display_code, ReadingStatus.LENGTH_ERROR, "Lectura empalmada simulada; no se recorta."),
                self._result(NestSide.LEFT, valid_code, ReadingStatus.NEW, "Lectura simulada válida."),
            )

        return (
            self._result(NestSide.RIGHT, valid_code, ReadingStatus.NEW, "Lectura simulada válida."),
            self._result(NestSide.LEFT, no_read_code, ReadingStatus.SCANNER_ERROR, "Token explícito de error del scanner."),
        )

    @staticmethod
    def _result(side: NestSide, code: str, status: ReadingStatus, message: str) -> ValidationResult:
        return ValidationResult(
            side=side,
            code=code,
            status=status,
            message=message,
            length=len(code),
            is_accepted=status == ReadingStatus.NEW,
        )

    @staticmethod
    def _general_error_from_results(right: ValidationResult, left: ValidationResult) -> GeneralResult:
        statuses = {right.status, left.status}
        if ReadingStatus.DUPLICATE in statuses:
            return GeneralResult.DUPLICATE
        if ReadingStatus.LENGTH_ERROR in statuses:
            return GeneralResult.LENGTH_ERROR
        if ReadingStatus.SCANNER_ERROR in statuses:
            return GeneralResult.READ_ERROR
        if ReadingStatus.NO_CONNECTION in statuses:
            return GeneralResult.CONNECTION_ERROR
        return GeneralResult.ERROR

    @Slot()
    def _finish_cooldown(self) -> None:
        if not self._running:
            return
        self.scanner_status_changed.emit(NestSide.RIGHT.value, "ESPERANDO")
        self.scanner_status_changed.emit(NestSide.LEFT.value, "ESPERANDO")
        self.system_status_changed.emit("ESPERANDO LECTURAS")

    def _emit_log(self, level: str, message: str) -> None:
        level_name = level.upper()
        log_method = getattr(logger, level_name.lower(), logger.info)
        log_method(message)
        self.log_message.emit(level_name, message)
