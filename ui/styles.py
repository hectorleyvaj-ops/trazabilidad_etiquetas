from __future__ import annotations

# Paleta V5: oscuro industrial, alto contraste y acentos sobrios.
# Mantiene colores de producción claros sin saturar toda la pantalla.
COLOR = {
    "neutral": "rgb(113, 124, 139)",      # gris técnico
    "info": "rgb(54, 132, 245)",         # azul proceso/listo
    "ok": "rgb(34, 197, 94)",            # verde OK
    "warning": "rgb(245, 158, 11)",      # ámbar duplicado/warning
    "error": "rgb(239, 68, 68)",         # rojo error de lectura/código
    "critical": "rgb(185, 28, 28)",      # rojo oscuro desconexión
    "cooldown": "rgb(20, 184, 166)",     # teal limpieza/cooldown
}

BACKGROUND = {
    "neutral": (13, 18, 28),
    "info": (10, 30, 58),
    "ok": (7, 45, 32),
    "warning": (61, 41, 9),
    "error": (67, 20, 25),
    "critical": (42, 8, 13),
    "cooldown": (8, 45, 53),
}

SURFACE = "rgba(15, 23, 42, 0.78)"
SURFACE_SOFT = "rgba(255, 255, 255, 0.075)"
TEXT = "rgb(241, 245, 249)"
TEXT_MUTED = "rgba(226, 232, 240, 0.72)"

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

APP_STYLESHEET = f"""
QMainWindow {{
    background-color: rgb(13, 18, 28);
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
    background-color: rgba(255, 255, 255, 0.08);
    color: {TEXT};
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 11px;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 700;
}}
QPushButton:hover {{
    background-color: rgba(255, 255, 255, 0.14);
}}
QPushButton:pressed {{
    background-color: rgba(255, 255, 255, 0.06);
}}
QPushButton#primaryButton {{
    background-color: rgb(54, 132, 245);
    color: white;
    border: none;
}}
QPushButton#dangerButton {{
    background-color: rgba(239, 68, 68, 0.20);
    border: 1px solid rgba(239, 68, 68, 0.52);
}}
QPlainTextEdit {{
    background-color: rgba(2, 6, 23, 0.52);
    color: rgba(226, 232, 240, 0.84);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
    padding: 8px;
    font-family: Consolas, monospace;
    font-size: 10px;
}}
QMessageBox {{
    background-color: rgb(15, 23, 42);
}}
QMessageBox QLabel {{
    color: {TEXT};
    font-size: 14px;
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
            stop: 0.62 rgb(13, 18, 28),
            stop: 1 rgb(2, 6, 23)
        );
    }}
    """


def result_panel_style(status: str) -> str:
    # Panel superior sin borde: solo informa el resultado y los contadores.
    return """
    QFrame {
        background-color: rgba(15, 23, 42, 0.58);
        border: none;
        border-radius: 24px;
    }
    """


def card_style(status: str) -> str:
    color = color_for_status(status)
    return f"""
    QFrame {{
        background-color: rgba(15, 23, 42, 0.78);
        border: 3px solid {color};
        border-radius: 28px;
    }}
    """


def indicator_style(status: str) -> str:
    color = color_for_status(status)
    return f"""
    QLabel {{
        background-color: {color};
        border: 8px solid rgba(255, 255, 255, 0.34);
        border-radius: 62px;
        min-width: 124px;
        max-width: 124px;
        min-height: 124px;
        max-height: 124px;
    }}
    """


def result_text_style(status: str) -> str:
    color = color_for_status(status)
    return f"""
    QLabel {{
        color: {color};
        font-size: 24px;
        font-weight: 950;
        letter-spacing: 0.8px;
        border: none;
        background: transparent;
    }}
    """


def counter_card_style(kind: str) -> str:
    color = COLOR.get(kind, COLOR["neutral"])
    return f"""
    QFrame {{
        background-color: rgba(255, 255, 255, 0.078);
        border: 1px solid rgba(255, 255, 255, 0.13);
        border-bottom: 5px solid {color};
        border-radius: 18px;
    }}
    """




def sensor_counter_strip_style() -> str:
    return """
    QFrame {
        background-color: rgba(255, 255, 255, 0.055);
        border: none;
        border-radius: 18px;
    }
    """


def stat_chip_style(kind: str) -> str:
    color = COLOR.get(kind, COLOR["neutral"])
    return f"""
    QFrame {{
        background-color: rgba(2, 6, 23, 0.42);
        border: none;
        border-bottom: 4px solid {color};
        border-radius: 14px;
    }}
    """


def connection_pill_style(connected: bool) -> str:
    color = COLOR["ok"] if connected else COLOR["critical"]
    background = "rgba(34, 197, 94, 0.14)" if connected else "rgba(185, 28, 28, 0.18)"
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
