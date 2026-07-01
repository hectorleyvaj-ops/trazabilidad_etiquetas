from __future__ import annotations

from collections.abc import Container

from core.models import NestSide, ReadingStatus, ScannerReading, ValidationResult


class LabelValidator:
    """Valida una lectura individual sin modificarla para hacerla pasar.

    Reglas importantes:
    - Primero se evalúan tokens explícitos de error del scanner.
    - Luego se valida longitud exacta.
    - Nunca se recorta una lectura larga para volverla válida.
    - Los duplicados solo se comparan contra historial con estado NUEVO.
    """

    def __init__(self, expected_length: int, scanner_error_tokens: list[str]) -> None:
        self.expected_length = int(expected_length)
        self.error_tokens = {token.strip().upper() for token in scanner_error_tokens if token.strip()}

    def validate(self, reading: ScannerReading, new_history: Container[str]) -> ValidationResult:
        code = reading.code
        normalized = code.strip().upper()

        if not code.strip():
            return ValidationResult(
                side=reading.side,
                code="ERROR_SCANNER",
                status=ReadingStatus.SCANNER_ERROR,
                message="Lectura vacía recibida desde el scanner.",
                length=0,
                is_accepted=False,
            )

        if normalized in self.error_tokens:
            return ValidationResult(
                side=reading.side,
                code=code,
                status=ReadingStatus.SCANNER_ERROR,
                message=f"Token explícito de error del scanner: {code!r}.",
                length=len(code),
                is_accepted=False,
            )

        if len(code) != self.expected_length:
            display = f"ERROR_LONGITUD_{len(code)}"
            return ValidationResult(
                side=reading.side,
                code=display,
                status=ReadingStatus.LENGTH_ERROR,
                message=(
                    f"Longitud inválida: {len(code)} caracteres; "
                    f"se esperaban {self.expected_length}. No se recortó la lectura."
                ),
                length=len(code),
                is_accepted=False,
            )

        if code in new_history:
            return ValidationResult(
                side=reading.side,
                code=code,
                status=ReadingStatus.DUPLICATE,
                message="El código ya existe en historial con estado NUEVO.",
                length=len(code),
                is_accepted=False,
            )

        return ValidationResult(
            side=reading.side,
            code=code,
            status=ReadingStatus.NEW,
            message="Código válido y nuevo.",
            length=len(code),
            is_accepted=True,
        )
