# Sistema de trazabilidad con doble scanner y PLC

Proyecto base modular para trazabilidad industrial con dos scanners TCP/IP, interfaz PySide6 y comunicación serial hacia PLC Mitsubishi FXCPU.

## Estado actual

Esta primera versión es un esqueleto funcional con:

- Interfaz PySide6 básica.
- Worker en hilo separado.
- Señales hacia la interfaz.
- Modo simulación.
- Modelos de datos.
- Logger formal a consola y archivo.
- Estructura preparada para scanner TCP, PLC serial, validación, Excel y SQLite.

Aún no conecta a scanners reales ni escribe al PLC. Esa integración entra en la siguiente fase.

## Instalación rápida en Windows

```bash
cd trazabilidad_produccion
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Instalación rápida en Linux / Raspberry Pi

```bash
cd trazabilidad_produccion
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Estructura

```text
trazabilidad_produccion/
├── main.py
├── config.json
├── requirements.txt
├── README.md
├── core/
│   ├── cycle_manager.py
│   ├── validator.py
│   └── models.py
├── devices/
│   ├── scanner_tcp.py
│   └── plc_fx_serial.py
├── storage/
│   ├── excel_repository.py
│   └── sqlite_repository.py
├── ui/
│   ├── main_window.py
│   ├── widgets.py
│   └── styles.py
├── workers/
│   └── traceability_worker.py
├── utils/
│   └── logger.py
├── logs/
│   └── trazabilidad.log
└── data/
    ├── base_datos_produccion.xlsx
    └── trazabilidad.db
```

## Próxima fase sugerida

1. Implementar `scanner_tcp.py` con separación segura por CR/LF/CRLF.
2. Implementar `validator.py`.
3. Implementar `plc_fx_serial.py`.
4. Implementar `excel_repository.py`.
5. Sustituir la simulación del worker por `CycleManager` real.
