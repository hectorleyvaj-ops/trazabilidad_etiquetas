from __future__ import annotations


APP_STYLESHEET = """
QMainWindow {
    background-color: rgb(18, 24, 38);
}
QLabel {
    color: rgb(235, 239, 245);
}
QPushButton {
    background-color: rgb(36, 52, 78);
    color: rgb(245, 247, 250);
    border: 1px solid rgb(73, 91, 122);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: rgb(48, 68, 101);
}
QPushButton:pressed {
    background-color: rgb(28, 42, 66);
}
QPlainTextEdit {
    background-color: rgb(10, 15, 25);
    color: rgb(220, 225, 235);
    border: 1px solid rgb(50, 65, 90);
    border-radius: 8px;
    padding: 8px;
    font-family: Consolas, monospace;
    font-size: 12px;
}
"""

STATUS_COLORS = {
    "ESPERANDO": "rgb(120, 130, 145)",
    "LECTURA OK": "rgb(38, 166, 91)",
    "LECTURA RECIBIDA": "rgb(43, 120, 220)",
    "ESPERANDO SEGUNDA LECTURA": "rgb(43, 120, 220)",
    "TIMEOUT LECTURA": "rgb(210, 63, 63)",
    "NUEVO": "rgb(38, 166, 91)",
    "OK": "rgb(38, 166, 91)",
    "OK GENERAL": "rgb(38, 166, 91)",
    "DUPLICADO": "rgb(240, 171, 0)",
    "ERROR LONGITUD": "rgb(210, 63, 63)",
    "ERROR DE LONGITUD": "rgb(210, 63, 63)",
    "ERROR SCANNER": "rgb(210, 63, 63)",
    "ERROR DE LECTURA": "rgb(210, 63, 63)",
    "ERROR GENERAL": "rgb(210, 63, 63)",
    "SIN CONEXIÓN": "rgb(120, 25, 35)",
    "ERROR DE CONEXIÓN": "rgb(120, 25, 35)",
    "COOLDOWN": "rgb(43, 120, 220)",
    "LISTO": "rgb(43, 120, 220)",
    "DETENIDO": "rgb(120, 130, 145)",
}


def color_for_status(status: str) -> str:
    return STATUS_COLORS.get(status, "rgb(120, 130, 145)")


def indicator_style(status: str) -> str:
    color = color_for_status(status)
    return f"""
    QLabel {{
        background-color: {color};
        border: 2px solid rgba(255, 255, 255, 0.35);
        border-radius: 20px;
        min-width: 40px;
        max-width: 40px;
        min-height: 40px;
        max-height: 40px;
    }}
    """


def card_style(status: str) -> str:
    color = color_for_status(status)
    return f"""
    QFrame {{
        background-color: rgb(25, 34, 52);
        border: 2px solid {color};
        border-radius: 14px;
    }}
    """


def badge_style(status: str) -> str:
    color = color_for_status(status)
    return f"""
    QLabel {{
        background-color: {color};
        color: white;
        border-radius: 10px;
        padding: 6px 12px;
        font-weight: bold;
    }}
    """
