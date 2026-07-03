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

    Puntos críticos:
    - La separación se hace por CR/LF/CRLF ANTES de limpiar la lectura.
    - Si llegan varias lecturas juntas, solo se conserva la primera lectura útil.
    - El socket se monitorea con keepalive y chequeos periódicos para detectar
      desconexiones físicas que TCP normalmente deja "silenciosas".
    """

    def __init__(
        self,
        side: NestSide,
        name: str,
        ip: str,
        port: int,
        timeout_seconds: float = 0.2,
        tcp_keepalive_enabled: bool = True,
        tcp_keepalive_idle_ms: int = 3000,
        tcp_keepalive_interval_ms: int = 1000,
        tcp_keepalive_count: int = 3,
        active_probe_enabled: bool = False,
        active_probe_interval_seconds: float = 2.0,
        active_probe_timeout_seconds: float = 0.4,
        active_probe_failures_before_disconnect: int = 2,
        logger: logging.Logger | None = None,
    ) -> None:
        self.side = side
        self.name = name
        self.ip = ip
        self.port = int(port)
        self.timeout_seconds = float(timeout_seconds)
        self.tcp_keepalive_enabled = bool(tcp_keepalive_enabled)
        self.tcp_keepalive_idle_ms = int(tcp_keepalive_idle_ms)
        self.tcp_keepalive_interval_ms = int(tcp_keepalive_interval_ms)
        self.tcp_keepalive_count = int(tcp_keepalive_count)
        self.active_probe_enabled = bool(active_probe_enabled)
        self.active_probe_interval_seconds = float(active_probe_interval_seconds)
        self.active_probe_timeout_seconds = float(active_probe_timeout_seconds)
        self.active_probe_failures_before_disconnect = int(active_probe_failures_before_disconnect)
        self.logger = logger or logging.getLogger(__name__)

        self._sock: socket.socket | None = None
        self._buffer = ""
        self._buffer_started_at: float | None = None
        self._last_health_check_at = 0.0
        self._active_probe_failures = 0

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    def connect(self) -> bool:
        self.close()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout_seconds)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._configure_keepalive(sock)
            sock.connect((self.ip, self.port))
            sock.settimeout(self.timeout_seconds)

            self._sock = sock
            self._buffer = ""
            self._buffer_started_at = None
            self._last_health_check_at = 0.0
            self._active_probe_failures = 0
            self.logger.info("%s conectado en %s:%s", self.name, self.ip, self.port)
            return True
        except OSError:
            self.logger.exception("No se pudo conectar %s en %s:%s", self.name, self.ip, self.port)
            self.close()
            return False

    def close(self) -> None:
        """Cierra agresivamente el socket y limpia estado interno.

        En pruebas reales con scanners industriales, un socket medio abierto puede
        quedarse como conexión zombie. shutdown() ayuda a notificar al stack TCP
        local antes de destruir el socket. Si el cable ya está fuera, ignoramos
        el error y seguimos limpiando el objeto para permitir reconexión limpia.
        """
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                self.logger.exception("Error cerrando socket de %s", self.name)
        self._sock = None
        self._buffer = ""
        self._buffer_started_at = None
        self._last_health_check_at = 0.0
        self._active_probe_failures = 0

    def reconnect(self) -> bool:
        return self.connect()

    def check_connection(self, force: bool = False, interval_seconds: float = 1.0) -> bool:
        """Verifica si el socket sigue saludable.

        Importante: en TCP una desconexión física puede tardar en detectarse si no
        hay tráfico. Por eso se combina:
        - TCP keepalive agresivo.
        - SO_ERROR + recv(MSG_PEEK) no destructivo.
        - Probe activo opcional por configuración.
        """
        if self._sock is None:
            return False

        now = time.monotonic()
        if not force and now - self._last_health_check_at < float(interval_seconds):
            return True
        self._last_health_check_at = now

        try:
            err = self._sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if err:
                raise OSError(err, f"SO_ERROR={err}")

            old_timeout = self._sock.gettimeout()
            try:
                self._sock.settimeout(0.0)
                try:
                    data = self._sock.recv(1, socket.MSG_PEEK)
                    if data == b"":
                        raise ConnectionError("socket cerrado por el scanner")
                except (BlockingIOError, socket.timeout):
                    pass
            finally:
                if self._sock is not None:
                    self._sock.settimeout(old_timeout)

            if self.active_probe_enabled:
                if not self._active_connect_probe():
                    self._active_probe_failures += 1
                    if self._active_probe_failures >= self.active_probe_failures_before_disconnect:
                        raise ConnectionError(
                            f"probe TCP falló {self._active_probe_failures} veces consecutivas"
                        )
                else:
                    self._active_probe_failures = 0

            return True
        except Exception as exc:
            self.logger.warning("%s perdió conexión TCP: %s", self.name, exc)
            self.close()
            return False

    def read_available(self, incomplete_idle_seconds: float = 0.15) -> ScannerReadResult | None:
        """Revisa si hay una lectura disponible sin bloquear el ciclo principal."""
        if self._sock is None:
            raise ConnectionError(f"{self.name} no está conectado")

        first, discarded, had_delimiter = self._extract_first_from_buffer()
        if first is not None:
            return self._build_result(first, first, discarded, had_delimiter)

        raw_accumulated = ""
        old_timeout = self._sock.gettimeout()
        try:
            self._sock.settimeout(0.0)
            while True:
                try:
                    data = self._sock.recv(1024)
                except (BlockingIOError, socket.timeout):
                    break
                except OSError as exc:
                    self.close()
                    raise ConnectionError(f"Conexión perdida con {self.name}: {exc}") from exc

                if not data:
                    self.close()
                    raise ConnectionError(f"{self.name} cerró la conexión TCP")

                text = data.decode("utf-8", errors="replace")
                raw_accumulated += text
                if not self._buffer:
                    self._buffer_started_at = time.monotonic()
                self._buffer += text
                self.logger.debug("%s paquete crudo: %r", self.name, text)

                first, discarded, had_delimiter = self._extract_first_from_buffer()
                if first is not None:
                    return self._build_result(first, raw_accumulated, discarded, had_delimiter)
        finally:
            if self._sock is not None:
                self._sock.settimeout(old_timeout)

        if self._buffer.strip() and self._buffer_started_at is not None:
            elapsed = time.monotonic() - self._buffer_started_at
            if elapsed >= float(incomplete_idle_seconds):
                pending = self._buffer.strip()
                self._buffer = ""
                self._buffer_started_at = None
                return self._build_result(pending, raw_accumulated or pending, [], False)

        return None

    def read_first(self, timeout_seconds: float) -> ScannerReadResult:
        if self._sock is None:
            raise ConnectionError(f"{self.name} no está conectado")

        deadline = time.monotonic() + float(timeout_seconds)
        raw_accumulated = ""

        while time.monotonic() < deadline:
            result = self.read_available(incomplete_idle_seconds=0.15)
            if result is not None:
                return result
            time.sleep(0.01)

        pending = self._buffer.strip()
        self._buffer = ""
        self._buffer_started_at = None
        if pending:
            return self._build_result(pending, raw_accumulated or pending, [], False)
        return ScannerReadResult(None, raw_accumulated, [], False)

    def clear_buffer(self) -> list[str]:
        """Drena lecturas tardías después del ciclo/cooldown."""
        discarded: list[str] = []
        if self._buffer.strip():
            parts = [p.strip() for p in _TERMINATOR_RE.split(self._buffer) if p.strip()]
            discarded.extend(parts or [self._buffer.strip()])
        self._buffer = ""
        self._buffer_started_at = None

        if self._sock is None:
            return discarded

        old_timeout = self._sock.gettimeout()
        try:
            self._sock.settimeout(0.01)
            while True:
                try:
                    data = self._sock.recv(1024)
                except (socket.timeout, BlockingIOError):
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

    def _configure_keepalive(self, sock: socket.socket) -> None:
        if not self.tcp_keepalive_enabled:
            return

        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            # Windows: configura tiempo e intervalo en milisegundos.
            if hasattr(socket, "SIO_KEEPALIVE_VALS"):
                sock.ioctl(
                    socket.SIO_KEEPALIVE_VALS,
                    (1, self.tcp_keepalive_idle_ms, self.tcp_keepalive_interval_ms),
                )

            # Linux: configura idle/interval/count si las constantes existen.
            idle_seconds = max(1, int(self.tcp_keepalive_idle_ms / 1000))
            interval_seconds = max(1, int(self.tcp_keepalive_interval_ms / 1000))
            if hasattr(socket, "TCP_KEEPIDLE"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, idle_seconds)
            if hasattr(socket, "TCP_KEEPINTVL"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval_seconds)
            if hasattr(socket, "TCP_KEEPCNT"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, self.tcp_keepalive_count)
        except OSError:
            self.logger.exception("No se pudo configurar TCP keepalive para %s", self.name)

    def _active_connect_probe(self) -> bool:
        """Probe opcional: intenta abrir una conexión corta al endpoint del scanner.

        Si el scanner solo permite un cliente TCP, deja active_probe_enabled=false.
        """
        probe: socket.socket | None = None
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            probe.settimeout(self.active_probe_timeout_seconds)
            probe.connect((self.ip, self.port))
            return True
        except OSError:
            return False
        finally:
            if probe is not None:
                try:
                    probe.close()
                except OSError:
                    pass

    def _extract_first_from_buffer(self) -> tuple[str | None, list[str], bool]:
        match = _TERMINATOR_RE.search(self._buffer)
        if not match:
            return None, [], False

        parts = [p.strip() for p in _TERMINATOR_RE.split(self._buffer) if p.strip()]
        self._buffer = ""
        self._buffer_started_at = None
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
        clean = first.strip()
        reading = ScannerReading(
            side=self.side,
            raw=first,
            code=clean,
            length=len(clean),
            received_at=datetime.now(),
        )
        return ScannerReadResult(reading, raw_packet or first, discarded, had_delimiter)
