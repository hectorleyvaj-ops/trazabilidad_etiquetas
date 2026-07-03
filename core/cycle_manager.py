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
        self.right_scanner = self._build_scanner(
            side=NestSide.RIGHT,
            name="Scanner derecho",
            cfg=scanner_cfg["right"],
        )
        self.left_scanner = self._build_scanner(
            side=NestSide.LEFT,
            name="Scanner izquierdo",
            cfg=scanner_cfg["left"],
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
        self._last_health_check_at = 0.0
        self._connection_lost_since: float | None = None

    def close(self) -> None:
        self.right_scanner.close()
        self.left_scanner.close()
        self.plc.close()

    def reconnect_all(self) -> None:
        self.close()
        self.reset_cycle_state(clear_device_buffers=True)
        self.ensure_connections(force=True)

    def ensure_connections(self, force: bool = False) -> bool:
        """Conecta y monitorea dispositivos sin disparar ciclos de evaluación.

        V9.1 agrega reconexión rápida por fases:
        - Si todos están conectados, solo se hacen health checks ligeros.
        - Si algo cae, se cierra el socket/COM dañado, se cancela el ciclo activo
          y se intenta reconectar rápido durante una ventana corta.
        - Después de esa ventana se reduce la frecuencia para no saturar al scanner.
        """
        self._check_existing_connections(force=force)

        if self._all_devices_connected():
            if self._connection_lost_since is not None:
                self.emit_log("INFO", "Todos los dispositivos fueron reconectados correctamente.")
            self._connection_lost_since = None
            if not self.is_cycle_active and not self.is_in_cooldown:
                self.emit_status("ESPERANDO LECTURAS")
            return True

        now = time.monotonic()
        if self._connection_lost_since is None:
            self._connection_lost_since = now

        reconnect_interval = self._current_reconnect_interval(now)
        if not force and now - self._last_reconnect_attempt_at < reconnect_interval:
            return False

        self._last_reconnect_attempt_at = now
        self.emit_status("RECONECTANDO")

        ok = True
        if not self.plc.is_connected:
            self.emit_status("SIN PLC")
            connected = self.plc.connect()
            self.emit_connection("PLC", connected, f"{self.config['plc']['port']} @ {self.config['plc']['baudrate']}")
            if connected:
                reset_ok = self.plc.send_k0()
                self.emit_log("INFO" if reset_ok else "ERROR", "PLC inicializado con K0." if reset_ok else "PLC conectó, pero falló reset K0.")
            ok &= connected

        ok &= self._ensure_scanner(self.right_scanner, "SIN SCANNER DERECHO")
        ok &= self._ensure_scanner(self.left_scanner, "SIN SCANNER IZQUIERDO")

        if ok:
            self._connection_lost_since = None
            if not self.is_cycle_active and not self.is_in_cooldown:
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
        if not self.plc.check_connection(force=True):
            self.emit_connection("PLC", False, "PLC no disponible antes de enviar resultado")
            self.emit_status("SIN PLC")
            general = GeneralResult.CONNECTION_ERROR

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
        if not reset_ok:
            self.emit_connection("PLC", False, "Fallo al enviar K0 reset")
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

    def _current_reconnect_interval(self, now: float) -> float:
        monitor_cfg = self.config.get("connection_monitor", {})
        fast_window = float(monitor_cfg.get("fast_reconnect_window_seconds", 10.0))
        fast_interval = float(monitor_cfg.get("fast_reconnect_interval_seconds", 0.5))
        slow_interval = float(monitor_cfg.get("slow_reconnect_interval_seconds", 2.0))

        if self._connection_lost_since is None:
            return slow_interval
        elapsed = now - self._connection_lost_since
        return fast_interval if elapsed <= fast_window else slow_interval

    def _ensure_scanner(self, scanner: ScannerTCP, missing_status: str) -> bool:
        if scanner.is_connected:
            return True
        self.emit_status(missing_status)
        connected = scanner.connect()
        self.emit_connection(scanner.name, connected, f"{scanner.ip}:{scanner.port}")
        self.emit_scanner_status(scanner.side.value, "ESPERANDO" if connected else "SIN CONEXIÓN")
        return connected

    def _check_existing_connections(self, force: bool = False) -> None:
        monitor_cfg = self.config.get("connection_monitor", {})
        interval = float(monitor_cfg.get("health_check_interval_seconds", 1.0))
        now = time.monotonic()
        if not force and now - self._last_health_check_at < interval:
            return
        self._last_health_check_at = now

        lost_any = False

        if self.plc.is_connected and not self.plc.check_connection(force=force, interval_seconds=interval):
            lost_any = True
            self.emit_status("SIN PLC")
            self.emit_connection("PLC", False, f"{self.config['plc']['port']} desconectado o no disponible")

        scanner_interval = float(monitor_cfg.get("scanner_health_check_interval_seconds", interval))
        for scanner, status in (
            (self.right_scanner, "SIN SCANNER DERECHO"),
            (self.left_scanner, "SIN SCANNER IZQUIERDO"),
        ):
            if scanner.is_connected and not scanner.check_connection(force=force, interval_seconds=scanner_interval):
                lost_any = True
                self.emit_status(status)
                self.emit_connection(scanner.name, False, f"{scanner.ip}:{scanner.port} sin respuesta")
                self.emit_scanner_status(scanner.side.value, "SIN CONEXIÓN")

        if lost_any:
            # Si se pierde un dispositivo a mitad de una ventana de lectura,
            # se invalida el ciclo para impedir evaluaciones incompletas o falsos OK.
            self.reset_cycle_state(clear_device_buffers=True)
            self.emit_status("ERROR DE CONEXIÓN")
            self.emit_log("ERROR", "Dispositivo desconectado. Ciclo actual cancelado y sistema en reconexión automática.")

    def _all_devices_connected(self) -> bool:
        return self.plc.is_connected and self.right_scanner.is_connected and self.left_scanner.is_connected

    @staticmethod
    def _build_scanner(side: NestSide, name: str, cfg: dict) -> ScannerTCP:
        return ScannerTCP(
            side=side,
            name=name,
            ip=cfg["ip"],
            port=cfg["port"],
            timeout_seconds=cfg.get("timeout_seconds", 0.2),
            tcp_keepalive_enabled=cfg.get("tcp_keepalive_enabled", True),
            tcp_keepalive_idle_ms=cfg.get("tcp_keepalive_idle_ms", 3000),
            tcp_keepalive_interval_ms=cfg.get("tcp_keepalive_interval_ms", 1000),
            tcp_keepalive_count=cfg.get("tcp_keepalive_count", 3),
            active_probe_enabled=cfg.get("active_probe_enabled", False),
            active_probe_interval_seconds=cfg.get("active_probe_interval_seconds", 2.0),
            active_probe_timeout_seconds=cfg.get("active_probe_timeout_seconds", 0.4),
            active_probe_failures_before_disconnect=cfg.get("active_probe_failures_before_disconnect", 2),
        )

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
