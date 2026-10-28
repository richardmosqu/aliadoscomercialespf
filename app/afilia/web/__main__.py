"""Inicia la app web: `python -m afilia.web` (desde app/)."""

from __future__ import annotations

import sys


def main() -> int:
    import uvicorn

    from ..config import get_settings
    from .server import create_app

    try:
        settings = get_settings()
        app = create_app(settings)
    except Exception as exc:  # configuración o política inválida
        print(f"No pude iniciar el evaluador: {exc}", file=sys.stderr)
        return 1
    ia = "con análisis de IA" if settings.ia else "sin IA (falta ANTHROPIC_API_KEY)"
    print(f"Evaluador de aliados comerciales en http://{settings.host}:{settings.port} · {ia}  (Ctrl+C para detener)")
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
