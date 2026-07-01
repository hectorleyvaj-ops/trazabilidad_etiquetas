from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from utils.logger import setup_logging

def get_base_dir() -> Path:
    """
    Devuelve la carpeta base del programa.

    En modo normal:
    - usa la carpeta donde está main.py.

    En modo ejecutable PyInstaller:
    - usa la carpeta donde está Trazabilidad.exe.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent

BASE_DIR = get_base_dir()
CONFIG_PATH = BASE_DIR / "config.json"

def load_config() -> dict:
    """Carga config.json y devuelve un diccionario normal de Python, desde la carpeta base del programa."""

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"No se encontro config.json en: {CONFIG_PATH}"
        )
    
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> int:
    config = load_config()

    log_file = BASE_DIR / config["logging"]["file_path"]
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    setup_logging(
        log_path=log_file,
        level=config["logging"].get("level", "INFO"),
        max_bytes=int(config["logging"].get("max_bytes", 1_048_576)),
        backup_count=int(config["logging"].get("backup_count", 5)),
    )

    app = QApplication(sys.argv)
    window = MainWindow(config=config, base_dir=BASE_DIR)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
