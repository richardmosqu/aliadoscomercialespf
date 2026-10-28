"""Los casos de referencia (casos/casos-de-referencia.yaml) deben dar la decisión que tomó el equipo."""

from __future__ import annotations

import pytest
import yaml

from afilia.motor import Entrada, evaluar

from .conftest import CASOS

_CASOS = yaml.safe_load(CASOS.read_text(encoding="utf-8"))["casos"]


def test_los_casos_tienen_ids_unicos():
    ids = [c["id"] for c in _CASOS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("caso", _CASOS, ids=[c["id"] for c in _CASOS])
def test_caso_de_referencia(politica, caso):
    r = evaluar(politica, Entrada(comercio=caso.get("comercio") or {}, respuestas=caso.get("respuestas") or {}))
    esperado = caso["esperado"]
    detalle = f"{r['etiqueta']} ({r['estado']}); motivos: {[m['texto'] for m in r['motivos']]}"

    assert r["nivel"] == esperado["nivel"], detalle
    if "estado" in esperado:
        assert r["estado"] == esperado["estado"], f"pendientes: {r['pendientes']}"
    activas = {c["id"] for c in r["categorias"] if not c["descartada"]}
    descartadas = {c["id"] for c in r["categorias"] if c["descartada"]}
    assert set(esperado.get("activas", [])) <= activas, activas
    assert set(esperado.get("descartadas", [])) <= descartadas, descartadas
    assert set(esperado.get("alternativas", [])) <= {a["id"] for a in r["alternativas"]}
    assert set(esperado.get("documentos", [])) <= {d["id"] for d in r["documentos"]}
    if "servicios_comite" in esperado:
        assert bool(r["servicios_comite"]) == esperado["servicios_comite"]
    # Las respuestas del caso deben ser válidas: si una pregunta cambia de id, el caso tiene que actualizarse.
    for pid in caso.get("respuestas") or {}:
        assert pid in politica.preguntas, f"La pregunta '{pid}' ya no existe en la política"
