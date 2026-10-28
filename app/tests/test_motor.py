from __future__ import annotations

from afilia.motor import Entrada, evaluar

BARES = {"actividad": "Venta de licor", "descripcion": "Tour por bares con licor incluido"}


def _ev(politica, **kw):
    return evaluar(politica, Entrada(**kw))


def test_sin_datos_aplica_y_pide_describir(politica):
    r = _ev(politica)
    assert r["nivel"] == "aplica"
    assert r["categorias"] == []
    assert any("Describe" in a for a in r["avisos"])
    assert r["siguiente"] == "g_tipo"


def test_una_palabra_clave_no_decide_sola_pregunta_primero(politica):
    r = _ev(politica, comercio=BARES)
    assert r["estado"] == "preliminar"
    assert r["siguiente"] == "alcohol_que_paga"
    alcohol = next(c for c in r["categorias"] if c["id"] == "alcohol")
    assert alcohol["palabras"] == ["licor", "bares"] and not alcohol["aclarada"]


def test_una_respuesta_activa_otra_categoria_y_sus_preguntas(politica):
    r = _ev(politica, comercio={"descripcion": "bar"}, respuestas={"alcohol_que_paga": "experiencia"})
    ids = [c["id"] for c in r["categorias"]]
    assert "experiencias_eventos" in ids
    assert next(c for c in r["categorias"] if c["id"] == "experiencias_eventos")["fuente"] == "respuesta"
    assert "eventos_quien_presta" in [p["id"] for p in r["preguntas"]]


def test_las_respuestas_de_preguntas_ocultas_no_cuentan(politica):
    # alcohol_peso solo aparece con experiencia o consumo en el local: con venta directa se ignora.
    r = _ev(politica, comercio=BARES, respuestas={"alcohol_que_paga": "venta_directa", "alcohol_peso": "mas_mitad"})
    assert "alcohol_peso" not in [p["id"] for p in r["preguntas"]]
    assert all(m["texto"] != "alcohol_peso" for m in r["motivos"])
    assert r["nivel"] == "no_aplica"


def test_gana_el_nivel_mas_alto(politica):
    r = _ev(politica, comercio=BARES, respuestas={"alcohol_que_paga": "experiencia", "alcohol_peso": "mas_mitad"})
    assert next(c for c in r["categorias"] if c["id"] == "alcohol")["nivel"] == "comite"
    assert r["nivel"] == "comite"


def test_el_tope_baja_el_nivel_de_la_categoria(politica):
    r = _ev(politica, comercio={"descripcion": "licores y abarrotes"},
            respuestas={"alcohol_que_paga": "venta_directa", "alcohol_excluir": "si_mayoria_permitida"})
    assert next(c for c in r["categorias"] if c["id"] == "alcohol")["nivel"] == "condicionado"


def test_el_analista_puede_quitar_un_falso_positivo(politica):
    r = _ev(politica, comercio=BARES, quitadas=["alcohol"])
    assert "alcohol" not in [c["id"] for c in r["categorias"]]
    assert "alcohol_que_paga" not in [p["id"] for p in r["preguntas"]]


def test_el_analista_puede_agregar_una_actividad(politica):
    r = _ev(politica, comercio={"descripcion": "Tienda"}, agregadas=["cripto", "no_existe"])
    assert [c["id"] for c in r["categorias"]] == ["cripto"]
    assert r["categorias"][0]["fuente"] == "agregada"


def test_respuestas_invalidas_se_ignoran(politica):
    r = _ev(politica, respuestas={"g_tipo": "marciano", "no_existe": "x", "g_canal": ["redes", "redes", "nada"],
                                  "g_entrega": ["inmediata", "futura"]})
    preguntas = {p["id"]: p for p in r["preguntas"]}
    assert preguntas["g_tipo"]["respuesta"] is None
    assert preguntas["g_canal"]["respuesta"] == ["redes"]
    assert preguntas["g_entrega"]["respuesta"] == "inmediata"  # respuesta única: se queda con la primera


def test_servicio_que_pasa_por_comite_no_frena_la_afiliacion(politica):
    r = _ev(politica, respuestas={"g_productos": ["recurrencia"]})
    assert r["nivel"] == "aplica"
    assert r["servicios_comite"]
    assert "evaluacion_debida_diligencia" in [d["id"] for d in r["documentos"]]
    assert "enlace de pago" in r["mensaje_comercio"]


def test_comite_agrega_el_expediente(politica):
    r = _ev(politica, respuestas={"g_historial": "si"})
    assert r["nivel"] == "comite"
    assert "expediente_comite" in [a["id"] for a in r["alternativas"]]
    assert {"formulario_debida_diligencia", "evaluacion_debida_diligencia"} <= {d["id"] for d in r["documentos"]}


def test_regla_de_combinacion(politica):
    r = _ev(politica, respuestas={"g_canal": ["web_propia"], "g_politicas": "ninguno"})
    assert r["nivel"] == "condicionado"
    assert any(m["origen"] == "Combinación de respuestas" for m in r["motivos"])


def test_motivos_ordenados_del_mas_grave_al_menos(politica):
    r = _ev(politica, comercio=BARES, respuestas={"alcohol_que_paga": "experiencia", "g_historial": "si",
                                                  "g_entrega": "futura"})
    rangos = ["aplica", "condicionado", "comite", "no_aplica"]
    niveles = [rangos.index(m["nivel"]) for m in r["motivos"]]
    assert niveles == sorted(niveles, reverse=True)


def test_mensaje_no_aplica_ofrece_alternativas_y_revision(politica):
    r = _ev(politica, comercio={"nombre": "Tabaquería PTY", "descripcion": "puros y habanos"},
            respuestas={"tabaco_que_vende": "tabaco", "tabaco_excluir": "no"})
    assert r["nivel"] == "no_aplica"
    m = r["mensaje_comercio"]
    assert m.startswith("Hola, Tabaquería PTY.")
    assert "se clasificó por error" in m
    assert "Afiliar solo la línea de negocio permitida" in m
    assert "Para avanzar" not in m  # no se piden documentos si hoy no aplica


def test_mensaje_no_revela_criterios_internos(politica):
    r = _ev(politica, comercio=BARES, respuestas={"alcohol_que_paga": "experiencia", "alcohol_peso": "mas_mitad"})
    for m in r["motivos"]:
        assert m["texto"] not in r["mensaje_comercio"]


def test_resumen_comite_marca_lo_preliminar(politica):
    r = _ev(politica, comercio={"nombre": "X", **BARES})
    assert "preliminar" in r["resumen_comite"]
    assert "## Preguntas sin responder" in r["resumen_comite"]
    assert r["resumen_comite"].startswith("# Evaluación de afiliación · X")


def test_determinista(politica):
    kw = dict(comercio=BARES, respuestas={"alcohol_que_paga": "experiencia", "g_canal": ["redes", "presencial"]})
    assert _ev(politica, **kw) == _ev(politica, **kw)


def test_progreso_y_siguiente(politica):
    r = _ev(politica, comercio=BARES, respuestas={"alcohol_que_paga": "experiencia"})
    assert r["progreso"]["respondidas"] == 1
    assert r["siguiente"] == "alcohol_peso"
    assert r["progreso"]["clave_pendientes"] == len(r["pendientes"])


def test_preliminar_no_concluye(politica):
    r = _ev(politica, comercio=BARES)
    assert r["estado"] == "preliminar"
    assert r["resumen"].startswith("Faltan") and "No es una conclusión" in r["resumen"]
    assert r["pasos"][0].startswith("Responder las preguntas clave")


def test_cada_pregunta_trae_su_version_corta_y_la_reaccion(politica):
    r = _ev(politica, comercio=BARES, respuestas={"alcohol_que_paga": "experiencia"})
    p = next(p for p in r["preguntas"] if p["id"] == "alcohol_que_paga")
    assert p["corta"] == "Cuando el cliente paga, ¿qué recibe?"
    assert next(o for o in p["opciones"] if o["id"] == "experiencia")["corto"] == "🎟️ Una experiencia o tour"
    assert p["reaccion"] == [{"nivel": "condicionado", "texto": politica.preguntas["alcohol_que_paga"].opcion(
        "experiencia").motivo}]
    sin = next(p for p in r["preguntas"] if p["id"] == "alcohol_peso")
    assert sin["reaccion"] == []


def test_un_no_confirmado_cierra_el_caso_sin_las_preguntas_generales(politica):
    r = _ev(politica, comercio={"descripcion": "vapes"}, respuestas={"tabaco_que_vende": "vapeadores"})
    assert r["nivel"] == "no_aplica" and r["estado"] == "completo"
    assert not any(p["clave"] for p in r["preguntas"] if p["categoria"] is None)


def test_antes_de_concluir_no_se_ofrece_afiliar_solo_lo_permitido(politica):
    r = _ev(politica, comercio={"descripcion": "licores y abarrotes"}, respuestas={"alcohol_que_paga": "venta_directa"})
    assert r["estado"] == "preliminar" and r["siguiente"] == "alcohol_excluir"


def test_un_no_por_palabra_clave_sin_aclarar_no_cierra_el_caso(politica):
    r = _ev(politica, comercio={"descripcion": "vapes"})
    assert r["estado"] == "preliminar"
    assert any(p["clave"] for p in r["preguntas"] if p["categoria"] is None)


def test_sin_camino_el_mensaje_no_promete_alternativas(politica):
    r = _ev(politica, comercio={"descripcion": "vapes"}, respuestas={"tabaco_que_vende": "vapeadores"})
    assert r["nivel"] == "no_aplica" and r["alternativas"] == []
    assert "forma de trabajar juntos" not in r["mensaje_comercio"]
    assert "se clasificó por error" in r["mensaje_comercio"]
