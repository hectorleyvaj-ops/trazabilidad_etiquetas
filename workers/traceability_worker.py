from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from core.cycle_manager import CycleManager
from core.models import CycleResult, GeneralResult, NestSide, ReadingStatus, ValidationResult

logger = logging.getLogger(__name__)


class TraceabilityWorker(QObject):
    scanner_status_changed = Signal(str, str)
    code_received = Signal(str, str, int, str)
    cycle_result = Signal(object)
    system_status_changed = Signal(str)
    log_message = Signal(str, str)
    connection_status_changed = Signal(str, bool, str)

    def __init__(self, config: dict, base_dir: Path) -> None:
        super().__init__()
        self.config = config
        self.base_dir = base_dir
        self._running = False
        self._busy = False
        self._timer: QTimer | None = None
        self._manager: CycleManager | None = None
        self._cycle_counter = 0

    @Slot()
    def start(self) -> None:
        if self._running:
            self._emit_log("WARNING", "El sistema ya está iniciado.")
            return
        self._running = True
        self._cycle_counter = 0
        self.system_status_changed.emit("INICIANDO")

        if self.config.get("app", {}).get("simulation_enabled", False):
            self._emit_log("INFO", "Inicio del sistema en modo simulación.")
            self._start_simulation_timer()
            return

        try:
            self._manager = CycleManager(
                config=self.config,
                base_dir=self.base_dir,
                emit_status=self.system_status_changed.emit,
                emit_log=self._emit_log,
                emit_scanner_status=self.scanner_status_changed.emit,
                emit_code=self.code_received.emit,
                emit_connection=self.connection_status_changed.emit,
            )
            self._emit_log("INFO", "Inicio del sistema en modo real.")
            self._manager.ensure_connections()
        except Exception:
            logger.exception("Error inicializando CycleManager")
            self._emit_log("ERROR", "Error inicializando sistema real. Revisa logs/trazabilidad.log.")
            self.system_status_changed.emit("ERROR DE CONEXIÓN")

        self._timer = QTimer(self)
        self._timer.setInterval(int(self.config.get("cycle", {}).get("read_poll_interval_ms", 50)))
        self._timer.timeout.connect(self._run_real_cycle)
        self._timer.start()

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
        if self._manager is not None:
            self._manager.close()
            self._manager = None
        self.system_status_changed.emit("DETENIDO")
        self.scanner_status_changed.emit(NestSide.RIGHT.value, "ESPERANDO")
        self.scanner_status_changed.emit(NestSide.LEFT.value, "ESPERANDO")
        self._emit_log("INFO", "Sistema detenido de forma segura.")

    @Slot()
    def reconnect_devices(self) -> None:
        if self.config.get("app", {}).get("simulation_enabled", False):
            self._simulate_connections()
            return
        if self._manager is None:
            self._emit_log("WARNING", "No hay administrador de ciclo activo. Inicia el sistema primero.")
            return
        self.system_status_changed.emit("INICIANDO")
        self._emit_log("INFO", "Reconexión manual de dispositivos solicitada.")
        self._manager.reconnect_all()

    @Slot()
    def simulate_once(self) -> None:
        self._simulate_cycle()

    @Slot()
    def _run_real_cycle(self) -> None:
        if not self._running or self._busy or self._manager is None:
            return
        self._busy = True
        try:
            cycle = self._manager.run_once()
            if cycle is not None:
                self.cycle_result.emit(cycle)
        except Exception:
            logger.exception("Error no controlado en ciclo real")
            self._emit_log("ERROR", "Error no controlado en ciclo real. Revisa logs/trazabilidad.log.")
            self.system_status_changed.emit("ERROR DE CONEXIÓN")
        finally:
            self._busy = False

    def _start_simulation_timer(self) -> None:
        self._simulate_connections()
        interval = int(self.config.get("simulation", {}).get("cycle_interval_ms", 3500))
        self._timer = QTimer(self)
        self._timer.setInterval(interval)
        self._timer.timeout.connect(self._simulate_cycle)
        self._timer.start()
        self.system_status_changed.emit("ESPERANDO LECTURAS")
        self._emit_log("INFO", f"Worker simulado ejecutándose cada {interval} ms.")

    def _simulate_connections(self) -> None:
        right_cfg = self.config["scanners"]["right"]
        left_cfg = self.config["scanners"]["left"]
        plc_cfg = self.config["plc"]
        self.connection_status_changed.emit("Scanner derecho", True, f"{right_cfg['ip']}:{right_cfg['port']}")
        self.connection_status_changed.emit("Scanner izquierdo", True, f"{left_cfg['ip']}:{left_cfg['port']}")
        self.connection_status_changed.emit("PLC", True, f"{plc_cfg['port']} @ {plc_cfg['baudrate']}")
        self.scanner_status_changed.emit(NestSide.RIGHT.value, "ESPERANDO")
        self.scanner_status_changed.emit(NestSide.LEFT.value, "ESPERANDO")

    def _simulate_cycle(self) -> None:
        self._cycle_counter += 1
        now = datetime.now()
        timestamp = now.strftime("%H:%M:%S")
        self.system_status_changed.emit("VALIDANDO")
        valid_code = "A024C393CBLK2615312139"
        long_code = valid_code + valid_code
        pattern = self._cycle_counter % 4
        if pattern == 1:
            right = self._result(NestSide.RIGHT, valid_code, ReadingStatus.NEW, "Lectura simulada válida.")
            left = self._result(NestSide.LEFT, valid_code, ReadingStatus.NEW, "Lectura simulada válida.")
        elif pattern == 2:
            right = self._result(NestSide.RIGHT, valid_code, ReadingStatus.DUPLICATE, "Código ya existe con estado NUEVO.")
            left = self._result(NestSide.LEFT, valid_code, ReadingStatus.NEW, "Lectura simulada válida.")
        elif pattern == 3:
            right = self._result(NestSide.RIGHT, f"ERROR_LONGITUD_{len(long_code)}", ReadingStatus.LENGTH_ERROR, "Lectura empalmada simulada; no se recorta.")
            left = self._result(NestSide.LEFT, valid_code, ReadingStatus.NEW, "Lectura simulada válida.")
        else:
            right = self._result(NestSide.RIGHT, valid_code, ReadingStatus.NEW, "Lectura simulada válida.")
            left = self._result(NestSide.LEFT, "NOREAD", ReadingStatus.SCANNER_ERROR, "Token explícito de error del scanner.")

        for result in (right, left):
            self.code_received.emit(result.side.value, result.code, result.length, timestamp)
            self.scanner_status_changed.emit(result.side.value, result.status.value)
            self._emit_log("INFO", f"{result.side.value.upper()} → {result.status.value}: {result.message}")

        general = GeneralResult.OK if right.status == ReadingStatus.NEW and left.status == ReadingStatus.NEW else GeneralResult.ERROR
        plc_value = self.config["plc"]["d0_values"]["ok" if general == GeneralResult.OK else "error"]
        self.cycle_result.emit(CycleResult(right, left, general, plc_value, now))
        self.system_status_changed.emit("COOLDOWN")
        QTimer.singleShot(int(self.config.get("cycle", {}).get("cooldown_ms", 1000)), lambda: self.system_status_changed.emit("ESPERANDO LECTURAS"))

    @staticmethod
    def _result(side: NestSide, code: str, status: ReadingStatus, message: str) -> ValidationResult:
        return ValidationResult(side=side, code=code, status=status, message=message, length=len(code), is_accepted=status == ReadingStatus.NEW)

    def _emit_log(self, level: str, message: str) -> None:
        level_name = level.upper()
        log_method = getattr(logger, level_name.lower(), logger.info)
        log_method(message)
        self.log_message.emit(level_name, message)
