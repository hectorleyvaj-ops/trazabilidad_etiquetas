from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from core.models import CycleResult, GeneralResult, NestSide, ReadingStatus, ValidationResult
from core.validator import LabelValidator
from devices.plc_fx_serial import PlcFxSerial
from devices.scanner_tcp import ScannerTCP
from storage.excel_repository import ExcelRepository

StatusCallback = Callable[[str], None]
LogCallback = Callable[[str, str], None]
ScannerStatusCallback = Callable[[str, str], None]
CodeCallback = Callable[[str, str, int, str], None]
ConnectionCallback = Callable[[str, bool, str], None]


class CycleManager:
    """Coordina dispositivos, validación, almacenamiento, PLC y cooldown."""

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

    def close(self) -> None:
        self.right_scanner.close()
        self.left_scanner.close()
        self.plc.close()

    def reconnect_all(self) -> None:
        self.close()
        self.ensure_connections()

    def ensure_connections(self) -> bool:
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
        if ok:
            self.emit_status("LISTO")
        return ok

    def run_once(self) -> CycleResult | None:
        if not self.ensure_connections():
            time.sleep(float(self.config["scanners"]["right"].get("reconnect_interval_seconds", 2.0)))
            return None

        self.emit_status("ESPERANDO LECTURAS")
        read_timeout = float(self.config["cycle"].get("read_timeout_ms", 3000)) / 1000.0

        right_read = self._read_scanner(self.right_scanner, read_timeout)
        left_read = self._read_scanner(self.left_scanner, read_timeout)

        if right_read is None or left_read is None:
            return self._handle_connection_or_timeout(right_read, left_read)

        self.emit_status("VALIDANDO")
        history = self.repository.get_new_codes()
        right_result = self.validator.validate(right_read, history)
        local_history = set(history)
        if right_result.status == ReadingStatus.NEW:
            local_history.add(right_result.code)
        left_result = self.validator.validate(left_read, local_history)

        now = datetime.now()
        for result in (right_result, left_result):
            timestamp = result.side.name if False else now.strftime("%H:%M:%S")
            self.emit_code(result.side.value, result.code, result.length, timestamp)
            self.emit_scanner_status(result.side.value, result.status.value)
            self.emit_log("INFO" if result.is_accepted else "WARNING", f"{result.side.value.upper()} → {result.status.value}: {result.message}")

        general = self._general_from_results(right_result, left_result)
        plc_value = self.config["plc"]["d0_values"]["ok" if general == GeneralResult.OK else "error"]

        try:
            self.emit_status("REGISTRANDO")
            self.repository.append_cycle(right_result, left_result, now)
        except PermissionError:
            self.emit_status("ERROR EXCEL")
            self.emit_log("ERROR", "No se pudo escribir el Excel. Cierra el archivo y vuelve a intentar.")
            general = GeneralResult.ERROR
            plc_value = self.config["plc"]["d0_values"]["error"]

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
        self._cooldown()
        return cycle

    def _read_scanner(self, scanner: ScannerTCP, timeout: float):
        try:
            result = scanner.read_first(timeout)
        except ConnectionError as exc:
            self.emit_log("ERROR", str(exc))
            self.emit_connection(scanner.name, False, str(exc))
            self.emit_scanner_status(scanner.side.value, "SIN CONEXIÓN")
            return None

        if result.raw_packet:
            self.emit_log("DEBUG", f"{scanner.name} crudo: {result.raw_packet!r}")
        if result.discarded:
            self.emit_log("WARNING", f"{scanner.name} mandó {1 + len(result.discarded)} lecturas juntas; se usó la primera y se descartó: {result.discarded}")
        if result.reading is None:
            self.emit_log("WARNING", f"{scanner.name}: timeout sin lectura útil.")
            return None
        self.emit_log("INFO", f"{scanner.name}: lectura aceptada para ciclo: {result.reading.code!r}")
        return result.reading

    def _handle_connection_or_timeout(self, right_read, left_read) -> CycleResult:
        now = datetime.now()
        right_result = self._timeout_result(NestSide.RIGHT) if right_read is None else self.validator.validate(right_read, self.repository.get_new_codes())
        left_result = self._timeout_result(NestSide.LEFT) if left_read is None else self.validator.validate(left_read, self.repository.get_new_codes())
        for result in (right_result, left_result):
            self.emit_code(result.side.value, result.code, result.length, now.strftime("%H:%M:%S"))
            self.emit_scanner_status(result.side.value, result.status.value)
        try:
            self.repository.append_cycle(right_result, left_result, now)
        except PermissionError:
            self.emit_status("ERROR EXCEL")
        self.emit_status("ENVIANDO ERROR AL PLC")
        self.plc.send_k2()
        time.sleep(float(self.config["cycle"].get("plc_signal_hold_ms", 2000)) / 1000.0)
        self.emit_status("RESET PLC")
        self.plc.send_k0()
        cycle = CycleResult(right_result, left_result, GeneralResult.READ_ERROR, self.config["plc"]["d0_values"]["error"], now)
        self._cooldown()
        return cycle

    def _cooldown(self) -> None:
        self.emit_status("COOLDOWN")
        self.emit_scanner_status(NestSide.RIGHT.value, "COOLDOWN")
        self.emit_scanner_status(NestSide.LEFT.value, "COOLDOWN")
        discarded = self.right_scanner.clear_buffer() + self.left_scanner.clear_buffer()
        if discarded:
            self.emit_log("WARNING", f"Lecturas tardías descartadas en cooldown: {discarded}")
        time.sleep(float(self.config["cycle"].get("cooldown_ms", 1000)) / 1000.0)
        self.emit_scanner_status(NestSide.RIGHT.value, "ESPERANDO")
        self.emit_scanner_status(NestSide.LEFT.value, "ESPERANDO")
        self.emit_status("ESPERANDO LECTURAS")

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
        return ValidationResult(
            side=side,
            code="ERROR_TIMEOUT",
            status=ReadingStatus.SCANNER_ERROR,
            message="No se recibió lectura dentro del tiempo configurado.",
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
