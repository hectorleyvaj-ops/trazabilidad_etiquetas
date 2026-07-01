from __future__ import annotations

import logging
import re
import socket
import time
from dataclasses import dataclass
from datetime import datetime

from core.models import NestSide, ScannerReading

_TERMINATOR_RE = re.compile(r"\r\n|\r|\n")


@dataclass(frozen=True)
class ScannerReadResult:
    reading: ScannerReading | None
    raw_packet: str
    discarded: list[str]
    had_delimiter: bool


class ScannerTCP:
    """Cliente TCP para scanner industrial.

    Punto crítico:
    La separación se hace por CR/LF/CRLF ANTES de limpiar la lectura. Así evitamos
    empalmar dos códigos como `ABC\rABC\r\n` y convertirlos en una cadena falsa.
    """

    def __init__(
        self,
        side: NestSide,
        name: str,
        ip: str,
        port: int,
        timeout_seconds: float = 0.2,
        logger: logging.Logger | None = None,
    ) -> None:
        self.side = side
        self.name = name
        self.ip = ip
        self.port = int(port)
        self.timeout_seconds = float(timeout_seconds)
        self.logger = logger or logging.getLogger(__name__)
        self._sock: socket.socket | None = None
        self._buffer = ""

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    def connect(self) -> bool:
        self.close()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout_seconds)
            sock.connect((self.ip, self.port))
            sock.settimeout(self.timeout_seconds)
            self._sock = sock
            self._buffer = ""
            self.logger.info("%s conectado en %s:%s", self.name, self.ip, self.port)
            return True
        except OSError:
            self.logger.exception("No se pudo conectar %s en %s:%s", self.name, self.ip, self.port)
            self.close()
            return False

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                self.logger.exception("Error cerrando socket de %s", self.name)
        self._sock = None

    def reconnect(self) -> bool:
        return self.connect()

    def read_first(self, timeout_seconds: float) -> ScannerReadResult:
        """Lee hasta obtener la primera lectura útil o agotar timeout.

        Si llegan múltiples lecturas en el mismo paquete, se conserva la primera no vacía
        y se reportan las demás como descartadas. Si llega una cadena sin delimitadores,
        se devuelve al vencer el timeout y el validador decidirá por longitud/token.
        """
        if self._sock is None:
            raise ConnectionError(f"{self.name} no está conectado")

        deadline = time.monotonic() + float(timeout_seconds)
        raw_accumulated = ""

        while time.monotonic() < deadline:
            first, discarded, had_delimiter = self._extract_first_from_buffer()
            if first is not None:
                return self._build_result(first, raw_accumulated, discarded, had_delimiter)

            try:
                data = self._sock.recv(1024)
            except socket.timeout:
                continue
            except OSError as exc:
                self.close()
                raise ConnectionError(f"Conexión perdida con {self.name}: {exc}") from exc

            if not data:
                self.close()
                raise ConnectionError(f"{self.name} cerró la conexión TCP")

            text = data.decode("utf-8", errors="replace")
            raw_accumulated += text
            self._buffer += text
            self.logger.debug("%s paquete crudo: %r", self.name, text)

        # Si no hubo terminador, no inventamos cortes. Se entrega tal cual para validar.
        pending = self._buffer.strip()
        self._buffer = ""
        if pending:
            reading = ScannerReading(
                side=self.side,
                raw=pending,
                code=pending,
                length=len(pending),
                received_at=datetime.now(),
            )
            return ScannerReadResult(reading, raw_accumulated or pending, [], False)
        return ScannerReadResult(None, raw_accumulated, [], False)

    def clear_buffer(self) -> list[str]:
        """Drena lecturas tardías después del ciclo/cooldown."""
        discarded: list[str] = []
        self._buffer = ""
        if self._sock is None:
            return discarded

        old_timeout = self._sock.gettimeout()
        try:
            self._sock.settimeout(0.01)
            while True:
                try:
                    data = self._sock.recv(1024)
                except socket.timeout:
                    break
                if not data:
                    self.close()
                    break
                text = data.decode("utf-8", errors="replace")
                parts = [p.strip() for p in _TERMINATOR_RE.split(text) if p.strip()]
                discarded.extend(parts or [text.strip()])
        except OSError:
            self.logger.exception("Error limpiando buffer de %s", self.name)
            self.close()
        finally:
            if self._sock is not None:
                self._sock.settimeout(old_timeout)
        return discarded

    def _extract_first_from_buffer(self) -> tuple[str | None, list[str], bool]:
        match = _TERMINATOR_RE.search(self._buffer)
        if not match:
            return None, [], False

        parts = [p.strip() for p in _TERMINATOR_RE.split(self._buffer) if p.strip()]
        self._buffer = ""
        if not parts:
            return None, [], True
        return parts[0], parts[1:], True

    def _build_result(
        self,
        first: str,
        raw_packet: str,
        discarded: list[str],
        had_delimiter: bool,
    ) -> ScannerReadResult:
        reading = ScannerReading(
            side=self.side,
            raw=first,
            code=first.strip(),
            length=len(first.strip()),
            received_at=datetime.now(),
        )
        return ScannerReadResult(reading, raw_packet or first, discarded, had_delimiter)
