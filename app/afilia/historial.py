"""Evaluaciones guardadas (SQLite): el expediente de cada caso y la decisión final del analista.

El historial es del equipo: todos los analistas ven todas las evaluaciones y cada una registra quién la hizo.
Comparar la recomendación del evaluador con la decisión final sirve para mejorar la política: los casos difíciles
se pasan a casos/casos-de-referencia.yaml.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DECISIONES = {
    "pendiente": "Pendiente",
    "afiliado": "Afiliado",
    "afiliado_condiciones": "Afiliado con condiciones",
    "comite": "Enviado a comité",
    "no_afiliado": "No afiliado",
}

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS evaluaciones (
    id TEXT PRIMARY KEY,
    creada TEXT NOT NULL,
    actualizada TEXT NOT NULL,
    analista TEXT NOT NULL,
    comercio TEXT NOT NULL,
    nivel TEXT NOT NULL,
    estado TEXT NOT NULL,
    decision TEXT NOT NULL,
    notas TEXT NOT NULL,
    entrada TEXT NOT NULL,
    resultado TEXT NOT NULL,
    politica TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS evaluaciones_actualizada ON evaluaciones (actualizada DESC);
"""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Historial:
    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conexion() as con:
            con.executescript(_ESQUEMA)

    def _conexion(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.ruta)
        con.row_factory = sqlite3.Row
        return con

    def guardar(self, analista: str, entrada: dict[str, Any], resultado: dict[str, Any], decision: str,
                notas: str, id: str | None = None) -> str:
        if decision not in DECISIONES:
            raise ValueError(f"Decisión no válida: {decision}")
        ahora = _ahora()
        fila = {
            "actualizada": ahora,
            "analista": analista,
            "comercio": resultado["comercio"]["nombre"] or resultado["comercio"]["razon_social"] or "Sin nombre",
            "nivel": resultado["nivel"],
            "estado": resultado["estado"],
            "decision": decision,
            "notas": notas,
            "entrada": json.dumps(entrada, ensure_ascii=False),
            "resultado": json.dumps(resultado, ensure_ascii=False),
            "politica": resultado["politica"]["version"],
        }
        with self._lock, self._conexion() as con:
            if id and con.execute("SELECT 1 FROM evaluaciones WHERE id = ?", (id,)).fetchone():
                con.execute(
                    "UPDATE evaluaciones SET actualizada=:actualizada, analista=:analista, comercio=:comercio, "
                    "nivel=:nivel, estado=:estado, decision=:decision, notas=:notas, entrada=:entrada, "
                    "resultado=:resultado, politica=:politica WHERE id=:id", {**fila, "id": id})
                return id
            nuevo = uuid.uuid4().hex[:12]
            con.execute(
                "INSERT INTO evaluaciones (id, creada, actualizada, analista, comercio, nivel, estado, decision, "
                "notas, entrada, resultado, politica) VALUES (:id, :creada, :actualizada, :analista, :comercio, "
                ":nivel, :estado, :decision, :notas, :entrada, :resultado, :politica)",
                {**fila, "id": nuevo, "creada": ahora})
            return nuevo

    def listar(self, buscar: str = "", limite: int = 100) -> list[dict[str, Any]]:
        sql = ("SELECT id, creada, actualizada, analista, comercio, nivel, estado, decision FROM evaluaciones "
               "{donde} ORDER BY actualizada DESC LIMIT ?")
        with self._conexion() as con:
            if buscar.strip():
                patron = f"%{buscar.strip()}%"
                filas = con.execute(sql.format(donde="WHERE comercio LIKE ? OR analista LIKE ? OR notas LIKE ?"),
                                    (patron, patron, patron, limite)).fetchall()
            else:
                filas = con.execute(sql.format(donde=""), (limite,)).fetchall()
        return [dict(f) for f in filas]

    def obtener(self, id: str) -> dict[str, Any] | None:
        with self._conexion() as con:
            fila = con.execute("SELECT * FROM evaluaciones WHERE id = ?", (id,)).fetchone()
        if fila is None:
            return None
        datos = dict(fila)
        datos["entrada"] = json.loads(datos["entrada"])
        datos["resultado"] = json.loads(datos["resultado"])
        return datos
