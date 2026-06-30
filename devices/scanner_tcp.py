"""Cliente TCP para scanner.

Siguiente fase crítica:
Separar primero por CR/LF/CRLF y solo después limpiar caracteres.
No recortar lecturas largas para volverlas válidas.
Aceptar únicamente la primera lectura útil por ciclo.
"""
