"""Coordinador del ciclo de producción.

Siguiente fase:
- leer scanner derecho e izquierdo,
- validar,
- registrar,
- enviar K1/K2 al PLC,
- enviar K0 después del retardo,
- limpiar buffers y entrar a cooldown.
"""

from __future__ import annotations


class CycleManager:
    def __init__(self, config: dict) -> None:
        self.config = config

    def run_once(self) -> None:
        raise NotImplementedError("CycleManager real se integrará en la siguiente fase.")
