from __future__ import annotations

# Paleta V8: panel industrial oscuro, minimalista y legible.
# La interfaz usa acentos de color para comunicar estado sin saturar toda la pantalla.
COLOR = {
    "neutral": "rgb(100, 116, 139)",      # gris espera/detenido
    "info": "rgb(14, 165, 164)",         # teal lectura/proceso
    "ok": "rgb(34, 197, 94)",            # verde OK
    "warning": "rgb(245, 158, 11)",      # ámbar duplicado
    "error": "rgb(239, 68, 68)",         # rojo error lectura/código
    "critical": "rgb(153, 27, 27)",      # rojo oscuro desconexión
    "cooldown": "rgb(56, 189, 248)",     # azul limpieza/cooldown
}

BACKGROUND = {
    "neutral": (15, 23, 32),
    "info": (10, 37, 45),
    "ok": (8, 45, 32),
    "warning": (61, 43, 13),
    "error": (67, 20, 25),
    "critical": (42, 8, 13),
    "cooldown": (8, 40, 58),
}

TEXT = "rgb(243, 246, 248)"
TEXT_MUTED = "rgba(226, 232, 240, 0.68)"
SURFACE = "rgba(24, 34, 48, 0.84)"
SURFACE_DEEP = "rgba(10, 16, 25, 0.72)"
BORDER_SOFT = "rgba(148, 163, 184, 0.18)"

STATUS_KIND = {
    "DETENIDO": "neutral",
    "ESPERANDO": "neutral",
    "ESPERANDO LECTURAS": "neutral",
    "LISTO": "neutral",
    "INICIANDO": "info",
    "RECONECTANDO": "warning",
    "ESPERANDO SEGUNDA LECTURA": "info",
    "LECTURA RECIBIDA": "info",
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

APP_STYLESHEET = f"""
QMainWindow {{
    background-color: rgb(15, 23, 32);
}}
QWidget {{
    color: {TEXT};
    font-family: Segoe UI, Arial, sans-serif;
}}
QLabel {{
    color: {TEXT};
    border: none;
    background: transparent;
}}
QPushButton {{
    background-color: rgba(255, 255, 255, 0.075);
    color: {TEXT};
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 10px;
    padding: 8px 13px;
    font-size: 12px;
    font-weight: 750;
}}
QPushButton:hover {{
    background-color: rgba(255, 255, 255, 0.13);
}}
QPushButton:pressed {{
    background-color: rgba(255, 255, 255, 0.055);
}}
QPushButton#primaryButton {{
    background-color: rgba(14, 165, 164, 0.22);
    border: 1px solid rgba(14, 165, 164, 0.55);
}}
QPushButton#dangerButton {{
    background-color: rgba(153, 27, 27, 0.24);
    border: 1px solid rgba(239, 68, 68, 0.48);
}}
QPlainTextEdit {{
    background-color: rgba(2, 6, 23, 0.42);
    color: rgba(226, 232, 240, 0.78);
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: 12px;
    padding: 7px 9px;
    font-family: Consolas, Cascadia Mono, monospace;
    font-size: 10px;
}}
QDialog {{
    background-color: rgb(42, 8, 13);
}}
"""


def kind_for_status(status: str) -> str:
    return STATUS_KIND.get(status, "neutral")


def color_for_status(status: str) -> str:
    return COLOR[kind_for_status(status)]


def app_background_style(status: str) -> str:
    kind = kind_for_status(status)
    r, g, b = BACKGROUND[kind]
    return f"""
    QWidget#appRoot {{
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgb({r}, {g}, {b}),
            stop: 0.50 rgb(15, 23, 32),
            stop: 1 rgb(2, 6, 23)
        );
    }}
    """


def result_panel_style(status: str) -> str:
    kind = kind_for_status(status)
    color = COLOR[kind]
    r, g, b = BACKGROUND[kind]
    return f"""
    QFrame {{
        background-color: rgba({r}, {g}, {b}, 0.58);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-bottom: 4px solid {color};
        border-radius: 22px;
    }}
    """


def card_style(status: str) -> str:
    color = color_for_status(status)
    return f"""
    QFrame {{
        background-color: {SURFACE};
        border: 1px solid {BORDER_SOFT};
        border-top: 6px solid {color};
        border-radius: 28px;
    }}
    """


def indicator_style(status: str) -> str:
    color = color_for_status(status)
    return f"""
    QLabel {{
        background-color: {color};
        border: 8px solid rgba(255, 255, 255, 0.28);
        border-radius: 58px;
        min-width: 116px;
        max-width: 116px;
        min-height: 116px;
        max-height: 116px;
    }}
    """


def result_text_style(status: str) -> str:
    color = color_for_status(status)
    return f"""
    QLabel {{
        color: {color};
        font-family: Cascadia Mono, Consolas, monospace;
        font-size: 24px;
        font-weight: 900;
        letter-spacing: 0.25px;
        line-height: 1.25;
        border: none;
        background: transparent;
        padding: 0px 12px;
    }}
    """


def production_counter_strip_style() -> str:
    return """
    QFrame {
        background-color: rgba(2, 6, 23, 0.24);
        border: none;
        border-radius: 18px;
    }
    """


def stat_chip_style(kind: str) -> str:
    color = COLOR.get(kind, COLOR["neutral"])
    return f"""
    QFrame {{
        background-color: rgba(2, 6, 23, 0.30);
        border: 1px solid rgba(148, 163, 184, 0.08);
        border-bottom: 3px solid {color};
        border-radius: 12px;
    }}
    """


def connection_pill_style(connected: bool) -> str:
    color = COLOR["ok"] if connected else COLOR["critical"]
    return f"""
    QFrame {{
        background-color: rgba(2, 6, 23, 0.30);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 12px;
        border-left: 4px solid {color};
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


def alert_dialog_style() -> str:
    return f"""
    QDialog {{
        background-color: rgb(42, 8, 13);
        border: 2px solid rgba(239, 68, 68, 0.72);
        border-radius: 18px;
    }}
    QLabel {{
        color: white;
        border: none;
        background: transparent;
    }}
    QPushButton {{
        background-color: rgba(255, 255, 255, 0.12);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 10px;
        padding: 9px 18px;
        font-weight: 800;
    QPushButton:hover {{
        background-color: rgba(255, 255, 255, 0.18);
    }}
    """
