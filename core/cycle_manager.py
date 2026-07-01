from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from core.models import CycleResult, GeneralResult, NestSide, ReadingStatus, ScannerReading, ValidationResult
from core.validator import LabelValidator
from devices.plc_fx_serial import PlcFxSerial
from devices.scanner_tcp import ScannerReadResult, ScannerTCP
from storage.excel_repository import ExcelRepository

StatusCallback = Callable[[str], None]
LogCallback = Callable[[str, str], None]
ScannerStatusCallback = Callable[[str, str], None]
CodeCallback = Callable[[str, str, int, str], None]
ConnectionCallback = Callable[[str, bool, str], None]


class CycleManager:
    """Coordina dispositivos, validación, almacenamiento, PLC y cooldown.

    Flujo real V2:
    - El sistema escucha constantemente los dos sockets TCP.
    - NO evalúa al iniciar conexiones.
    - La primera lectura recibida abre una ventana de ciclo.
    - Se espera la lectura del otro scanner dentro de pair_timeout_ms.
    - Cuando existen derecha + izquierda, se valida, registra y responde al PLC.
    - Durante cooldown se descartan lecturas tardías.
    """

    def __init__(
        self,
        config: dict,
        base_dir: Path,
        emit_status: StatusCallback,
        emit_log: LogCallback,
        emit_scanner_status: ScannerStatusCallback,
        emit_code: CodeCallback,
        emit_connection: ConnectionCallback,
    ) -> None:
        self.config = config
        self.base_dir = base_dir
        self.emit_status = emit_status
        self.emit_log = emit_log
        self.emit_scanner_status = emit_scanner_status
        self.emit_code = emit_code
        self.emit_connection = emit_connection
        self.logger = logging.getLogger(__name__)

        scanner_cfg = config["scanners"]
        self.right_scanner = ScannerTCP(
            side=NestSide.RIGHT,
            name="Scanner derecho",
            ip=scanner_cfg["right"]["ip"],
            port=scanner_cfg["right"]["port"],
            timeout_seconds=scanner_cfg["right"].get("timeout_seconds", 0.2),
        )
        self.left_scanner = ScannerTCP(
            side=NestSide.LEFT,
            name="Scanner izquierdo",
            ip=scanner_cfg["left"]["ip"],
            port=scanner_cfg["left"]["port"],
            timeout_seconds=scanner_cfg["left"].get("timeout_seconds", 0.2),
        )
        self.plc = PlcFxSerial(config["plc"])

        validation_cfg = config["validation"]
        self.validator = LabelValidator(
            expected_length=validation_cfg["expected_length"],
            scanner_error_tokens=validation_cfg["scanner_error_tokens"],
        )
        excel_path = self._resolve_path(config["storage"]["excel_path"])
        self.repository = ExcelRepository(excel_path)

        self.pending_right: ScannerReading | None = None
        self.pending_left: ScannerReading | None = None
        self.cycle_started_at: float | None = None
        self.cooldown_until: float | None = None
        self._last_reconnect_attempt_at = 0.0

    def close(self) -> None:
        self.right_scanner.close()
        self.left_scanner.close()
        self.plc.close()

    def reconnect_all(self) -> None:
        self.close()
        self.reset_cycle_state(clear_device_buffers=True)
        self.ensure_connections(force=True)

    def ensure_connections(self, force: bool = False) -> bool:
        """Conecta dispositivos sin disparar ciclos de evaluación."""
        now = time.monotonic()
        reconnect_interval = float(self.config["scanners"]["right"].get("reconnect_interval_seconds", 2.0))
        if not force and now - self._last_reconnect_attempt_at < reconnect_interval:
            return self.plc.is_connected and self.right_scanner.is_connected and self.left_scanner.is_connected
        self._last_reconnect_attempt_at = now

        ok = True
        if not self.plc.is_connected:
            self.emit_status("SIN PLC")
            connected = self.plc.connect()
            self.emit_connection("PLC", connected, f"{self.config['plc']['port']} @ {self.config['plc']['baudrate']}")
            if connected:
                self.plc.send_k0()
            ok &= connected

        ok &= self._ensure_scanner(self.right_scanner, "SIN SCANNER DERECHO")
        ok &= self._ensure_scanner(self.left_scanner, "SIN SCANNER IZQUIERDO")
        if ok and not self.is_cycle_active and not self.is_in_cooldown:
            self.emit_status("ESPERANDO LECTURAS")
        return ok

    @property
    def is_cycle_active(self) -> bool:
        return self.cycle_started_at is not None

    @property
    def is_in_cooldown(self) -> bool:
        return self.cooldown_until is not None and time.monotonic() < self.cooldown_until

    def poll(self) -> CycleResult | None:
        """Tick principal del sistema real.

        Este método NO crea un ciclo por sí solo. Solo escucha sockets TCP y avanza
        la máquina de estados cuando llegan lecturas.
        """
        if not self.ensure_connections():
            return None

        if self.is_in_cooldown:
            self._drain_late_reads_during_cooldown()
            return None

        if self.cooldown_until is not None and time.monotonic() >= self.cooldown_until:
            self.cooldown_until = None
            self.emit_scanner_status(NestSide.RIGHT.value, "ESPERANDO")
            self.emit_scanner_status(NestSide.LEFT.value, "ESPERANDO")
            self.emit_status("ESPERANDO LECTURAS")

        incomplete_idle = float(self.config.get("cycle", {}).get("incomplete_packet_idle_ms", 150)) / 1000.0

        right_result = self._poll_scanner(self.right_scanner, incomplete_idle)
        left_result = self._poll_scanner(self.left_scanner, incomplete_idle)

        if right_result is not None and right_result.reading is not None:
            self._on_scanner_read(right_result)

        if left_result is not None and left_result.reading is not None:
            self._on_scanner_read(left_result)

        if self.pending_right is not None and self.pending_left is not None:
            return self._evaluate_and_finish_cycle()

        if self.is_cycle_active and self._pair_timeout_elapsed():
            return self._handle_pair_timeout()

        return None

    # Compatibilidad con versiones anteriores del worker.
    def run_once(self) -> CycleResult | None:
        return self.poll()

    def reset_cycle_state(self, clear_device_buffers: bool = False) -> None:
        self.pending_right = None
        self.pending_left = None
        self.cycle_started_at = None
        self.cooldown_until = None
        if clear_device_buffers:
            discarded = self.right_scanner.clear_buffer() + self.left_scanner.clear_buffer()
            if discarded:
                self.emit_log("WARNING", f"Lecturas descartadas al reiniciar estado: {discarded}")

    def _poll_scanner(self, scanner: ScannerTCP, incomplete_idle: float) -> ScannerReadResult | None:
        try:
            result = scanner.read_available(incomplete_idle_seconds=incomplete_idle)
        except ConnectionError as exc:
            self.emit_log("ERROR", str(exc))
            self.emit_connection(scanner.name, False, str(exc))
            self.emit_scanner_status(scanner.side.value, "SIN CONEXIÓN")
            return None

        if result is None:
            return None

        if result.raw_packet:
            self.emit_log("DEBUG", f"{scanner.name} crudo: {result.raw_packet!r}")
        if result.discarded:
            self.emit_log(
                "WARNING",
                f"{scanner.name} mandó {1 + len(result.discarded)} lecturas juntas; se usó la primera y se descartó: {result.discarded}",
            )
        return result

    def _on_scanner_read(self, result: ScannerReadResult) -> None:
        reading = result.reading
        if reading is None:
            return

        if not self.is_cycle_active:
            self.cycle_started_at = time.monotonic()
            self.emit_status("ESPERANDO SEGUNDA LECTURA")
            self.emit_log("INFO", f"Inicio de ciclo por llegada de lectura {reading.side.value.upper()}.")

        timestamp = reading.received_at.strftime("%H:%M:%S")
        self.emit_code(reading.side.value, reading.code, reading.length, timestamp)
        self.emit_log("INFO", f"{reading.side.value.upper()} → lectura recibida para ciclo: {reading.code!r}")

        if reading.side == NestSide.RIGHT:
            if self.pending_right is None:
                self.pending_right = reading
                self.emit_scanner_status(NestSide.RIGHT.value, "LECTURA RECIBIDA")
            else:
                self.emit_log("WARNING", f"Lectura extra derecha descartada durante ciclo: {reading.code!r}")
        elif reading.side == NestSide.LEFT:
            if self.pending_left is None:
                self.pending_left = reading
                self.emit_scanner_status(NestSide.LEFT.value, "LECTURA RECIBIDA")
            else:
                self.emit_log("WARNING", f"Lectura extra izquierda descartada durante ciclo: {reading.code!r}")

    def _evaluate_and_finish_cycle(self) -> CycleResult:
        if self.pending_right is None or self.pending_left is None:
            raise RuntimeError("No se puede evaluar sin ambas lecturas.")

        self.emit_status("VALIDANDO")
        history = self.repository.get_new_codes()
        right_result = self.validator.validate(self.pending_right, history)
        left_result = self.validator.validate(self.pending_left, history)
        return self._finish_cycle(right_result, left_result)

    def _handle_pair_timeout(self) -> CycleResult:
        self.emit_status("TIMEOUT LECTURA")
        self.emit_log("ERROR", "Timeout esperando el par de lecturas del ciclo.")
        history = self.repository.get_new_codes()
        if self.pending_right is None:
            right_result = self._timeout_result(NestSide.RIGHT)
        else:
            right_result = self.validator.validate(self.pending_right, history)

        if self.pending_left is None:
            left_result = self._timeout_result(NestSide.LEFT)
        else:
            left_result = self.validator.validate(self.pending_left, history)

        return self._finish_cycle(right_result, left_result, force_general=GeneralResult.READ_ERROR)

    def _finish_cycle(
        self,
        right_result: ValidationResult,
        left_result: ValidationResult,
        force_general: GeneralResult | None = None,
    ) -> CycleResult:
        now = datetime.now()
        for result in (right_result, left_result):
            timestamp = now.strftime("%H:%M:%S")
            self.emit_code(result.side.value, result.code, result.length, timestamp)
            self.emit_scanner_status(result.side.value, result.status.value)
            self.emit_log(
                "INFO" if result.is_accepted else "WARNING",
                f"{result.side.value.upper()} → {result.status.value}: {result.message}",
            )

        general = force_general or self._general_from_results(right_result, left_result)
        plc_value = self.config["plc"]["d0_values"]["ok" if general == GeneralResult.OK else "error"]

        try:
            self.emit_status("REGISTRANDO")
            self.repository.append_cycle(right_result, left_result, now)
        except PermissionError:
            self.emit_status("ERROR EXCEL")
            self.emit_log("ERROR", "No se pudo escribir el Excel. Cierra el archivo y vuelve a intentar.")
            general = GeneralResult.ERROR
            plc_value = self.config["plc"]["d0_values"]["error"]
        except Exception:
            self.logger.exception("Error guardando ciclo en Excel")
            self.emit_status("ERROR EXCEL")
            self.emit_log("ERROR", "Error inesperado escribiendo Excel. Revisa logs/trazabilidad.log.")
            general = GeneralResult.ERROR
            plc_value = self.config["plc"]["d0_values"]["error"]

        sent = False
        if general == GeneralResult.OK:
            self.emit_status("ENVIANDO OK AL PLC")
            sent = self.plc.send_k1()
            self.emit_log("INFO" if sent else "ERROR", f"PLC <- K1 OK ({plc_value})")
        else:
            self.emit_status("ENVIANDO ERROR AL PLC")
            sent = self.plc.send_k2()
            self.emit_log("WARNING" if sent else "ERROR", f"PLC <- K2 ERROR ({plc_value})")

        if not sent:
            self.emit_connection("PLC", False, "Fallo al enviar resultado")
            general = GeneralResult.CONNECTION_ERROR

        hold = float(self.config["cycle"].get("plc_signal_hold_ms", self.config["plc"].get("reset_delay_ms", 500))) / 1000.0
        time.sleep(hold)

        self.emit_status("RESET PLC")
        reset_ok = self.plc.send_k0()
        self.emit_log("INFO" if reset_ok else "ERROR", f"PLC <- K0 RESET ({self.config['plc']['d0_values']['reset']})")

        cycle = CycleResult(right_result, left_result, general, plc_value, now)
        self._enter_cooldown()
        return cycle

    def _enter_cooldown(self) -> None:
        self.pending_right = None
        self.pending_left = None
        self.cycle_started_at = None
        self.emit_status("COOLDOWN")
        self.emit_scanner_status(NestSide.RIGHT.value, "COOLDOWN")
        self.emit_scanner_status(NestSide.LEFT.value, "COOLDOWN")
        discarded = self.right_scanner.clear_buffer() + self.left_scanner.clear_buffer()
        if discarded:
            self.emit_log("WARNING", f"Lecturas tardías descartadas al entrar en cooldown: {discarded}")
        cooldown_seconds = float(self.config["cycle"].get("cooldown_ms", 1000)) / 1000.0
        self.cooldown_until = time.monotonic() + cooldown_seconds

    def _drain_late_reads_during_cooldown(self) -> None:
        discarded = self.right_scanner.clear_buffer() + self.left_scanner.clear_buffer()
        if discarded:
            self.emit_log("WARNING", f"Lecturas tardías descartadas durante cooldown: {discarded}")

    def _pair_timeout_elapsed(self) -> bool:
        if self.cycle_started_at is None:
            return False
        timeout = float(self.config["cycle"].get("pair_timeout_ms", self.config["cycle"].get("read_timeout_ms", 3000))) / 1000.0
        return (time.monotonic() - self.cycle_started_at) >= timeout

    def _ensure_scanner(self, scanner: ScannerTCP, missing_status: str) -> bool:
        if scanner.is_connected:
            return True
        self.emit_status(missing_status)
        connected = scanner.connect()
        self.emit_connection(scanner.name, connected, f"{scanner.ip}:{scanner.port}")
        self.emit_scanner_status(scanner.side.value, "ESPERANDO" if connected else "SIN CONEXIÓN")
        return connected

    @staticmethod
    def _timeout_result(side: NestSide) -> ValidationResult:
        missing_name = "derecha" if side == NestSide.RIGHT else "izquierda"
        return ValidationResult(
            side=side,
            code=f"ERROR_TIMEOUT_{missing_name.upper()}",
            status=ReadingStatus.SCANNER_ERROR,
            message=f"No se recibió lectura {missing_name} dentro del tiempo configurado.",
            length=0,
            is_accepted=False,
        )

    @staticmethod
    def _general_from_results(right: ValidationResult, left: ValidationResult) -> GeneralResult:
        statuses = {right.status, left.status}
        if statuses == {ReadingStatus.NEW}:
            return GeneralResult.OK
        if ReadingStatus.DUPLICATE in statuses:
            return GeneralResult.DUPLICATE
        if ReadingStatus.LENGTH_ERROR in statuses:
            return GeneralResult.LENGTH_ERROR
        if ReadingStatus.SCANNER_ERROR in statuses:
            return GeneralResult.READ_ERROR
        if ReadingStatus.NO_CONNECTION in statuses:
            return GeneralResult.CONNECTION_ERROR
        return GeneralResult.ERROR

    def _resolve_path(self, path_value: str) -> Path:
        path = Path(path_value)
        if not path.is_absolute():
            path = self.base_dir / path
        return path
