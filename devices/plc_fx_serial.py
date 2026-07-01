from __future__ import annotations

import logging
import time

import serial


class PlcFxSerial:
    """Comunicación serial con PLC Mitsubishi FXCPU para escritura en D0."""

    def __init__(self, config: dict, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._serial: serial.Serial | None = None

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def connect(self) -> bool:
        self.close()
        try:
            self._serial = serial.Serial(
                port=self.config.get("port", "COM3"),
                baudrate=int(self.config.get("baudrate", 9600)),
                bytesize=int(self.config.get("bytesize", serial.SEVENBITS)),
                parity=self.config.get("parity", serial.PARITY_EVEN),
                stopbits=int(self.config.get("stopbits", serial.STOPBITS_ONE)),
                timeout=float(self.config.get("timeout", 1.0)),
                write_timeout=float(self.config.get("write_timeout", 1.0)),
            )
            self.logger.info("PLC conectado en %s @ %s", self.config.get("port"), self.config.get("baudrate"))
            return True
        except serial.SerialException:
            self.logger.exception("No se pudo conectar el PLC en %s", self.config.get("port"))
            self.close()
            return False

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except serial.SerialException:
                self.logger.exception("Error cerrando puerto serial del PLC")
        self._serial = None

    def reconnect(self) -> bool:
        return self.connect()

    @staticmethod
    def build_frame(valor_hex_little_endian: str) -> bytes:
        cmd = f"1100002{valor_hex_little_endian}"
        checksum = f"{(sum(ord(c) for c in cmd) + 3) & 0xFF:02X}"
        return b"\x02" + cmd.encode("ascii") + b"\x03" + checksum.encode("ascii")

    def send_d0(self, valor_hex_little_endian: str, description: str = "D0") -> bool:
        if not self.is_connected:
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
        except serial.SerialException:
            self.logger.exception("Comunicación con PLC perdida al enviar %s", description)
            self.close()
            return False

    def send_k0(self) -> bool:
        return self.send_d0(self.config["d0_values"]["reset"], "K0 Reset")

    def send_k1(self) -> bool:
        return self.send_d0(self.config["d0_values"]["ok"], "K1 OK")

    def send_k2(self) -> bool:
        return self.send_d0(self.config["d0_values"]["error"], "K2 Error/Alarma")
