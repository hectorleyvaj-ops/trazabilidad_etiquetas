"""Comunicación serial con PLC Mitsubishi FXCPU.

Siguiente fase:
- send_d0(valor_hex_little_endian),
- send_k0(), send_k1(), send_k2(),
- checksum ASCII del cmd + ETX limitado a 0xFF,
- reconexión automática segura.
"""
