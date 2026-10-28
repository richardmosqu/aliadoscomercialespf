"""App web con el análisis de IA SIMULADO (sin clave de la API), para conocer la interfaz.

    python scripts/demo_web.py        # http://127.0.0.1:8001

La "IA" de la demostración no es un modelo: arma sus sugerencias con las palabras clave de la política. Sirve para
ver cómo se presentan las sugerencias, no para evaluar comercios. Las evaluaciones se guardan en una carpeta
temporal que se borra al cerrar.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from afilia.config import PROJECT_ROOT, Settings  # noqa: E402
from afilia.politica import cargar_politica  # noqa: E402

PUERTO = 8001


class _MensajesDemo:
    def __init__(self) -> None:
        self.politica = cargar_politica(PROJECT_ROOT / "politica")

    def create(self, **params: Any) -> SimpleNamespace:
        texto = params["messages"][0]["content"]
        descripcion = re.search(r"Descripción: (.*)", texto)
        descripcion = descripcion.group(1) if descripcion else ""
        detectadas = self.politica.detectar(texto.split("</comercio>")[0] + texto.split("<informacion_adicional>")[-1])
        datos: dict[str, Any] = {
            "actividad_real": "Demostración: respuesta simulada con las palabras clave de la política (no es la IA).",
            "explicacion": "Con la clave de la API, aquí aparece la lectura del caso: qué vende de verdad el comercio "
                           "y por qué.",
            "categorias": [{"id": c, "razon": f"Menciona: {', '.join(p)}."} for c, p in detectadas.items()],
            "respuestas_sugeridas": [],
            "preguntas_para_el_comercio": [self.politica.preguntas[self.politica.categorias[c].preguntas[0]].texto
                                           for c in detectadas if self.politica.categorias[c].preguntas],
            "alertas": [],
            "alternativas": [],
        }
        if "alcohol" in detectadas and "experiencias_eventos" in detectadas:
            datos["respuestas_sugeridas"].append({"pregunta": "alcohol_que_paga", "opcion": "experiencia",
                                                  "evidencia": descripcion})
            datos["alertas"].append("Lo declarado y lo descrito no coinciden: confirmar qué recibe el cliente al pagar.")
            datos["alternativas"].append({"id": "cobrar_solo_servicio",
                                          "por_que": "Si los bares venden las bebidas, el comercio cobra solo el tour."})
        return SimpleNamespace(model="demostración (sin IA)", stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=json.dumps(datos, ensure_ascii=False))])


class ClienteDemo:
    def __init__(self) -> None:
        self.beta = SimpleNamespace(messages=_MensajesDemo())


def main() -> int:
    import uvicorn

    from afilia.web.server import create_app

    with tempfile.TemporaryDirectory() as datos:
        settings = Settings(port=PUERTO, datos_dir=Path(datos), ia=True)
        app = create_app(settings, ia_client=ClienteDemo())
        print(f"Demostración del evaluador en http://127.0.0.1:{PUERTO} (IA simulada; Ctrl+C para detener)")
        uvicorn.run(app, host="127.0.0.1", port=PUERTO, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
