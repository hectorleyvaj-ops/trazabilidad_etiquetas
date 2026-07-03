from __future__ import annotations

import logging
import time

import serial
from serial.tools import list_ports


class PlcFxSerial:
    """Comunicación serial con PLC Mitsubishi FXCPU para escritura en D0.

    La propiedad is_connected solo indica que el objeto Serial está abierto.
    Para detectar desconexión USB física se usa check_connection(), que revisa
    periódicamente si el COM sigue presente en Windows.
    """

    def __init__(self, config: dict, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._serial: serial.Serial | None = None
        self._last_health_check_at = 0.0

    @property
    def port(self) -> str:
        return str(self.config.get("port", "COM3"))

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def connect(self) -> bool:
        self.close()
        if self.config.get("require_port_presence", True) and not self.port_exists():
            self.logger.error("Puerto PLC no disponible: %s", self.port)
            return False

        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=int(self.config.get("baudrate", 9600)),
                bytesize=int(self.config.get("bytesize", serial.SEVENBITS)),
                parity=self.config.get("parity", serial.PARITY_EVEN),
                stopbits=int(self.config.get("stopbits", serial.STOPBITS_ONE)),
                timeout=float(self.config.get("timeout", 1.0)),
                write_timeout=float(self.config.get("write_timeout", 1.0)),
            )
            self._last_health_check_at = 0.0
            self.logger.info("PLC conectado en %s @ %s", self.port, self.config.get("baudrate"))
            return True
        except (serial.SerialException, OSError):
            self.logger.exception("No se pudo conectar el PLC en %s", self.port)
            self.close()
            return False

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except (serial.SerialException, OSError):
                self.logger.exception("Error cerrando puerto serial del PLC")
        self._serial = None

    def reconnect(self) -> bool:
        return self.connect()

    def port_exists(self) -> bool:
        expected = self.port.upper()
        available = {p.device.upper() for p in list_ports.comports()}
        return expected in available

    def check_connection(self, force: bool = False, interval_seconds: float = 1.0) -> bool:
        """Detecta desconexión física del adaptador USB/serial."""
        if not self.is_connected:
            return False

        now = time.monotonic()
        if not force and now - self._last_health_check_at < float(interval_seconds):
            return True
        self._last_health_check_at = now

        try:
            if self.config.get("require_port_presence", True) and not self.port_exists():
                raise serial.SerialException(f"El puerto {self.port} ya no aparece en el sistema.")

            assert self._serial is not None
            # Acceder a in_waiting fuerza a pyserial a consultar el handle del puerto.
            # En Windows suele lanzar excepción cuando el USB fue retirado.
            _ = self._serial.in_waiting
            return True
        except (serial.SerialException, OSError) as exc:
            self.logger.warning("Comunicación con PLC perdida: %s", exc)
            self.close()
            return False

    @staticmethod
    def build_frame(valor_hex_little_endian: str) -> bytes:
        cmd = f"1100002{valor_hex_little_endian}"
        checksum = f"{(sum(ord(c) for c in cmd) + 3) & 0xFF:02X}"
        return b"\x02" + cmd.encode("ascii") + b"\x03" + checksum.encode("ascii")

    def send_d0(self, valor_hex_little_endian: str, description: str = "D0") -> bool:
        if not self.check_connection(force=True):
            if not self.connect():
                return False

        assert self._serial is not None
        frame = self.build_frame(valor_hex_little_endian)
        try:
            self._serial.write(b"\x05")
            self._serial.flush()
            time.sleep(0.1)
            self._serial.write(frame)
            self._serial.flush()
            time.sleep(0.1)
            response = self._serial.read(10)
            self.logger.info("PLC <- %s (%s), respuesta=%s", valor_hex_little_endian, description, response.hex(" "))
            return True
        except (serial.SerialException, OSError):
            self.logger.exception("Comunicación con PLC perdida al enviar %s", description)
            self.close()
            return False

    def send_k0(self) -> bool:
        return self.send_d0(self.config["d0_values"]["reset"], "K0 Reset")

    def send_k1(self) -> bool:
        return self.send_d0(self.config["d0_values"]["ok"], "K1 OK")

    def send_k2(self) -> bool:
        return self.send_d0(self.config["d0_values"]["error"], "K2 Error/Alarma")
