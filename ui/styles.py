from __future__ import annotations


APP_STYLESHEET = """
QMainWindow {
    background-color: rgb(12, 18, 30);
}
QWidget {
    color: rgb(238, 242, 248);
    font-family: Segoe UI, Arial, sans-serif;
}
QLabel {
    color: rgb(238, 242, 248);
}
QPushButton {
    background-color: rgba(255, 255, 255, 0.09);
    color: rgb(245, 247, 250);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: rgba(255, 255, 255, 0.15);
}
QPushButton:pressed {
    background-color: rgba(255, 255, 255, 0.06);
}
QPushButton#primaryButton {
    background-color: rgb(46, 196, 182);
    color: rgb(6, 20, 34);
    border: none;
}
QPushButton#dangerButton {
    background-color: rgba(255, 82, 82, 0.20);
    border: 1px solid rgba(255, 82, 82, 0.45);
}
QPlainTextEdit {
    background-color: rgba(0, 0, 0, 0.22);
    color: rgb(219, 226, 237);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    padding: 8px;
    font-family: Consolas, monospace;
    font-size: 11px;
}
"""

COLOR = {
    "neutral": "rgb(126, 137, 153)",
    "info": "rgb(43, 120, 220)",
    "ok": "rgb(46, 196, 116)",
    "warning": "rgb(244, 171, 0)",
    "error": "rgb(226, 70, 70)",
    "critical": "rgb(122, 24, 36)",
    "cooldown": "rgb(62, 142, 230)",
}

BACKGROUND = {
    "neutral": (12, 18, 30),
    "info": (10, 30, 58),
    "ok": (8, 48, 38),
    "warning": (70, 47, 8),
    "error": (68, 16, 24),
    "critical": (42, 9, 16),
    "cooldown": (8, 34, 68),
}

STATUS_KIND = {
    "DETENIDO": "neutral",
    "ESPERANDO": "neutral",
    "ESPERANDO LECTURAS": "info",
    "ESPERANDO SEGUNDA LECTURA": "info",
    "LECTURA RECIBIDA": "info",
    "LISTO": "info",
    "INICIANDO": "info",
    "VALIDANDO": "info",
    "REGISTRANDO": "info",
    "RESET PLC": "info",
    "COOLDOWN": "cooldown",
    "NUEVO": "ok",
    "OK": "ok",
    "LECTURA OK": "ok",
    "OK GENERAL": "ok",
    "ENVIANDO OK AL PLC": "ok",
    "DUPLICADO": "warning",
    "ERROR LONGITUD": "error",
    "ERROR DE LONGITUD": "error",
    "ERROR SCANNER": "error",
    "ERROR DE LECTURA": "error",
    "ERROR GENERAL": "error",
    "TIMEOUT LECTURA": "error",
    "ENVIANDO ERROR AL PLC": "error",
    "ERROR EXCEL": "error",
    "SIN CONEXIÓN": "critical",
    "ERROR DE CONEXIÓN": "critical",
    "SIN PLC": "critical",
    "SIN SCANNER DERECHO": "critical",
    "SIN SCANNER IZQUIERDO": "critical",
}


def kind_for_status(status: str) -> str:
    return STATUS_KIND.get(status, "neutral")


def color_for_status(status: str) -> str:
    return COLOR[kind_for_status(status)]


def app_background_style(status: str) -> str:
    kind = kind_for_status(status)
    r, g, b = BACKGROUND[kind]
    return f"""
    QWidget#appRoot {{
        background-color: rgb({r}, {g}, {b});
    }}
    """


def glass_panel_style(status: str = "ESPERANDO") -> str:
    color = color_for_status(status)
    return f"""
    QFrame {{
        background-color: rgba(255, 255, 255, 0.075);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-left: 6px solid {color};
        border-radius: 18px;
    }}
    """


def card_style(status: str) -> str:
    color = color_for_status(status)
    return f"""
    QFrame {{
        background-color: rgba(255, 255, 255, 0.095);
        border: 3px solid {color};
        border-radius: 22px;
    }}
    """


def indicator_style(status: str) -> str:
    color = color_for_status(status)
    return f"""
    QLabel {{
        background-color: {color};
        border: 5px solid rgba(255, 255, 255, 0.42);
        border-radius: 44px;
        min-width: 88px;
        max-width: 88px;
        min-height: 88px;
        max-height: 88px;
    }}
    """


def badge_style(status: str) -> str:
    color = color_for_status(status)
    return f"""
    QLabel {{
        background-color: {color};
        color: white;
        border-radius: 16px;
        padding: 10px 18px;
        font-size: 18px;
        font-weight: 800;
    }}
    """


def result_panel_style(status: str) -> str:
    color = color_for_status(status)
    return f"""
    QFrame {{
        background-color: rgba(255, 255, 255, 0.105);
        border: 2px solid {color};
        border-radius: 22px;
    }}
    """


def connection_pill_style(connected: bool) -> str:
    color = COLOR["ok"] if connected else COLOR["critical"]
    background = "rgba(46, 196, 116, 0.16)" if connected else "rgba(226, 70, 70, 0.20)"
    return f"""
    QFrame {{
        background-color: {background};
        border: 1px solid {color};
        border-radius: 14px;
    }}
    """


def small_dot_style(connected: bool) -> str:
    color = COLOR["ok"] if connected else COLOR["critical"]
    return f"""
    QLabel {{
        background-color: {color};
        border-radius: 7px;
        min-width: 14px;
        max-width: 14px;
        min-height: 14px;
        max-height: 14px;
    }}
    """


def counter_card_style(kind: str) -> str:
    color = COLOR.get(kind, COLOR["neutral"])
    return f"""
    QFrame {{
        background-color: rgba(255, 255, 255, 0.085);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-bottom: 5px solid {color};
        border-radius: 16px;
    }}
    """


def alert_banner_style(level: str = "error") -> str:
    color = COLOR["critical"] if level == "critical" else COLOR.get(level, COLOR["error"])
    return f"""
    QFrame {{
        background-color: rgba(0, 0, 0, 0.30);
        border: 2px solid {color};
        border-radius: 16px;
    }}
    """
