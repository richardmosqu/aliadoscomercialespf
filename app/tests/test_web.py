from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from afilia.config import Settings
from afilia.web.server import create_app

from .conftest import POLITICA_DIR
from .fakes import FakeClient
from .test_ia import RESPUESTA

BARES = {"comercio": {"nombre": "Tours", "actividad": "Venta de licor", "descripcion": "tour por bares"}}


def _cliente(tmp_path, **kw) -> TestClient:
    settings = Settings(politica_dir=POLITICA_DIR, datos_dir=tmp_path, **kw)
    return TestClient(create_app(settings, ia_client=FakeClient(datos=RESPUESTA)))


@pytest.fixture
def cliente(tmp_path):
    return _cliente(tmp_path)


def test_estado_local_sin_acceso(cliente):
    r = cliente.get("/api/estado").json()
    assert r["acceso_requerido"] is False and r["ia"] is False
    assert r["politica"]["version"] and r["decisiones"]["pendiente"] == "Pendiente"


def test_pagina_principal(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "Evaluador de aliados" in r.text
    assert cliente.get("/static/app.js").status_code == 200


def test_evaluar(cliente):
    r = cliente.post("/api/evaluar", json={**BARES, "respuestas": {"alcohol_que_paga": "experiencia"}}).json()
    assert r["nivel"] == "condicionado"
    assert {c["id"] for c in r["categorias"]} >= {"alcohol", "experiencias_eventos"}


def test_politica_publica(cliente):
    r = cliente.get("/api/politica").json()
    alcohol = next(c for c in r["categorias"] if c["id"] == "alcohol")
    assert alcohol["preguntas"][0]["opciones"][0]["nivel"] == "no_aplica"
    assert r["generales"][0]["id"] == "g_tipo"


def test_guardar_listar_abrir_y_actualizar(cliente):
    id = cliente.post("/api/evaluaciones", json={**BARES, "decision": "pendiente", "notas": "revisar"}).json()["id"]
    lista = cliente.get("/api/evaluaciones").json()["evaluaciones"]
    assert lista[0]["id"] == id and lista[0]["comercio"] == "Tours" and lista[0]["analista"] == "analista local"
    assert cliente.get("/api/evaluaciones?q=Tours").json()["evaluaciones"]
    assert not cliente.get("/api/evaluaciones?q=zzz").json()["evaluaciones"]

    cuerpo = {**BARES, "respuestas": {"alcohol_que_paga": "experiencia"}, "id": id, "decision": "afiliado_condiciones"}
    assert cliente.post("/api/evaluaciones", json=cuerpo).json()["id"] == id
    e = cliente.get(f"/api/evaluaciones/{id}").json()
    assert e["decision"] == "afiliado_condiciones" and e["nivel"] == "condicionado"
    assert e["entrada"]["respuestas"] == {"alcohol_que_paga": "experiencia"}
    assert len(cliente.get("/api/evaluaciones").json()["evaluaciones"]) == 1


def test_decision_invalida(cliente):
    assert cliente.post("/api/evaluaciones", json={**BARES, "decision": "inventada"}).status_code == 422


def test_evaluacion_que_no_existe(cliente):
    assert cliente.get("/api/evaluaciones/nada").status_code == 404


def test_ia_apagada_responde_503(cliente):
    r = cliente.post("/api/ia/analizar", json=BARES)
    assert r.status_code == 503 and "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_ia_encendida(tmp_path):
    c = _cliente(tmp_path, ia=True)
    assert c.get("/api/estado").json()["ia"] is True
    r = c.post("/api/ia/analizar", json=BARES).json()
    assert r["actividad_real"].startswith("Tours")
    assert c.post("/api/ia/analizar", json={"comercio": {}}).status_code == 422


def test_con_clave_de_acceso(tmp_path):
    c = _cliente(tmp_path, clave_acceso="clave-de-prueba-larga", secreto_sesion="s" * 32)
    assert c.get("/api/estado").json()["acceso_requerido"] is True
    assert c.post("/api/evaluar", json=BARES).status_code == 401
    assert c.get("/api/evaluaciones").status_code == 401
    assert c.post("/api/sesion", json={"correo": "ana@gmail.com", "clave": "clave-de-prueba-larga"}).status_code == 403
    assert c.post("/api/sesion", json={"correo": "ana@paguelofacil.com", "clave": "otra"}).status_code == 403
    r = c.post("/api/sesion", json={"correo": "Ana@PagueloFacil.com", "clave": "clave-de-prueba-larga"})
    assert r.json()["usuario"] == "ana@paguelofacil.com"
    assert c.post("/api/evaluar", json=BARES).status_code == 200
    id = c.post("/api/evaluaciones", json=BARES).json()["id"]
    assert c.get(f"/api/evaluaciones/{id}").json()["analista"] == "ana@paguelofacil.com"
    c.delete("/api/sesion")
    assert c.post("/api/evaluar", json=BARES).status_code == 401


def test_no_arranca_abierta_a_la_red_sin_clave(tmp_path):
    with pytest.raises(ValueError, match="AFILIA_CLAVE_ACCESO"):
        create_app(Settings(host="0.0.0.0", politica_dir=POLITICA_DIR, datos_dir=tmp_path))
    with pytest.raises(ValueError, match="AFILIA_SECRETO_SESION"):
        create_app(Settings(host="0.0.0.0", clave_acceso="x" * 16, politica_dir=POLITICA_DIR, datos_dir=tmp_path))


def test_politica_con_error_sigue_con_la_anterior(tmp_path):
    import shutil
    carpeta = tmp_path / "politica"
    shutil.copytree(POLITICA_DIR, carpeta)
    c = TestClient(create_app(Settings(politica_dir=carpeta, datos_dir=tmp_path)))
    archivo = carpeta / "categorias.yaml"
    archivo.write_text(archivo.read_text(encoding="utf-8").replace("nivel: no_aplica", "nivel: prohibido", 1),
                       encoding="utf-8")
    estado = c.get("/api/estado").json()
    assert "prohibido" in estado["politica"]["error"]
    assert c.post("/api/evaluar", json=BARES).json()["nivel"] == "no_aplica"
