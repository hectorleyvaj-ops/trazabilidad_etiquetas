from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class NestSide(str, Enum):
    RIGHT = "right"
    LEFT = "left"


class ReadingStatus(str, Enum):
    WAITING = "ESPERANDO"
    NEW = "NUEVO"
    OK = "OK"
    DUPLICATE = "DUPLICADO"
    LENGTH_ERROR = "ERROR LONGITUD"
    SCANNER_ERROR = "ERROR SCANNER"
    NO_CONNECTION = "SIN CONEXIÓN"
    COOLDOWN = "COOLDOWN"


class SystemStatus(str, Enum):
    STARTING = "INICIANDO"
    READY = "LISTO"
    WAITING_READS = "ESPERANDO LECTURAS"
    VALIDATING = "VALIDANDO"
    REGISTERING = "REGISTRANDO"
    SENDING_OK = "ENVIANDO OK AL PLC"
    SENDING_ERROR = "ENVIANDO ERROR AL PLC"
    RESETTING_PLC = "RESET PLC"
    COOLDOWN = "COOLDOWN"
    STOPPED = "DETENIDO"
    CONNECTION_ERROR = "ERROR DE CONEXIÓN"
    EXCEL_ERROR = "ERROR EXCEL"
    NO_PLC = "SIN PLC"
    NO_RIGHT_SCANNER = "SIN SCANNER DERECHO"
    NO_LEFT_SCANNER = "SIN SCANNER IZQUIERDO"


class GeneralResult(str, Enum):
    WAITING = "ESPERANDO"
    OK = "OK GENERAL"
    ERROR = "ERROR GENERAL"
    DUPLICATE = "DUPLICADO"
    READ_ERROR = "ERROR DE LECTURA"
    LENGTH_ERROR = "ERROR DE LONGITUD"
    CONNECTION_ERROR = "ERROR DE CONEXIÓN"


@dataclass(frozen=True)
class ScannerReading:
    side: NestSide
    raw: str
    code: str
    length: int
    received_at: datetime


@dataclass(frozen=True)
class ValidationResult:
    side: NestSide
    code: str
    status: ReadingStatus
    message: str
    length: int
    is_accepted: bool


@dataclass(frozen=True)
class CycleResult:
    right: Optional[ValidationResult]
    left: Optional[ValidationResult]
    general_result: GeneralResult
    plc_value: str
    finished_at: datetime
