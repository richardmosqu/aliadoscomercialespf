from __future__ import annotations

import shutil

import pytest

from afilia.politica import PoliticaError, cargar_politica, normalizar

from .conftest import POLITICA_DIR


def test_la_politica_real_carga(politica):
    assert politica.categorias and politica.preguntas and politica.alternativas and politica.documentos
    assert "alcohol" in politica.categorias
    assert politica.generales[0] == "g_tipo"


def test_cada_categoria_con_preguntas_tiene_una_pregunta_clave(politica):
    for cat in politica.categorias.values():
        if cat.preguntas:
            assert any(politica.preguntas[p].clave for p in cat.preguntas), cat.id


def test_la_primera_pregunta_de_las_categorias_restringidas_siempre_resuelve(politica):
    """Toda opción de la pregunta que aclara qué vende fija un nivel o descarta: así nunca queda a medias."""
    for cat in politica.categorias.values():
        if cat.nivel in ("comite", "no_aplica") and cat.preguntas:
            pregunta = politica.preguntas[cat.preguntas[0]]
            for o in pregunta.opciones:
                assert o.nivel or o.descarta, f"{pregunta.id} › {o.id}"


def test_normalizar_quita_tildes_y_mayusculas():
    assert normalizar("Licorería ÑAME Cócteles") == "licoreria name cocteles"


@pytest.mark.parametrize("texto, categoria", [
    ("Venta de LICORES y cervezas", "alcohol"),
    ("Licorería del barrio", "alcohol"),
    ("Tour por bares", "alcohol"),
    ("vapeadores desechables", "tabaco_vapeo"),
    ("contenido +18 exclusivo", "adultos"),
    ("réplicas 1:1 de relojes", "replicas"),
    ("acompañantes VIP", "adultos"),
    ("Casa de empeño", "servicios_financieros"),
])
def test_detecta_palabras_clave(politica, texto, categoria):
    assert categoria in politica.detectar(texto)


@pytest.mark.parametrize("texto, categoria", [
    ("Barbería y peluquería", "alcohol"),        # "bar" es palabra completa
    ("Zapatos baratos", "alcohol"),
    ("Pago seguro con tarjeta de crédito", "servicios_financieros"),
    ("10 años de experiencia en diseño", "experiencias_eventos"),
    ("Taller mecánico", "experiencias_eventos"),
])
def test_no_detecta_palabras_dentro_de_otras(politica, texto, categoria):
    assert categoria not in politica.detectar(texto)


def test_detectar_devuelve_las_palabras_encontradas(politica):
    assert politica.detectar("venta de licor y tour por bares")["alcohol"] == ["licor", "bares"]


@pytest.fixture
def copia_politica(tmp_path):
    destino = tmp_path / "politica"
    shutil.copytree(POLITICA_DIR, destino)
    return destino


def _reemplazar(ruta, viejo, nuevo):
    texto = ruta.read_text(encoding="utf-8")
    assert viejo in texto
    ruta.write_text(texto.replace(viejo, nuevo, 1), encoding="utf-8")


def test_error_si_se_nombra_una_alternativa_que_no_existe(copia_politica):
    _reemplazar(copia_politica / "categorias.yaml", "alternativas: [cobrar_solo_servicio, afiliar_linea_permitida]",
                "alternativas: [cobrar_solo_servicio, no_existe]")
    with pytest.raises(PoliticaError, match="no_existe"):
        cargar_politica(copia_politica)


def test_error_si_un_nivel_esta_mal_escrito(copia_politica):
    _reemplazar(copia_politica / "categorias.yaml", "nivel: no_aplica", "nivel: prohibido")
    with pytest.raises(PoliticaError, match="prohibido"):
        cargar_politica(copia_politica)


def test_error_claro_si_un_no_queda_sin_comillas(copia_politica):
    _reemplazar(copia_politica / "categorias.yaml", 'id: "no"', "id: no")
    with pytest.raises(PoliticaError, match="comillas"):
        cargar_politica(copia_politica)


def test_error_si_mostrar_si_nombra_una_opcion_que_no_existe(copia_politica):
    _reemplazar(copia_politica / "categorias.yaml", "mostrar_si: {alcohol_que_paga: [venta_directa]}",
                "mostrar_si: {alcohol_que_paga: [botellas]}")
    with pytest.raises(PoliticaError, match="botellas"):
        cargar_politica(copia_politica)


def test_error_si_falta_un_archivo(copia_politica):
    (copia_politica / "mensajes.yaml").unlink()
    with pytest.raises(PoliticaError, match="mensajes.yaml"):
        cargar_politica(copia_politica)


def test_la_huella_cambia_al_editar(copia_politica):
    antes = cargar_politica(copia_politica).huella
    _reemplazar(copia_politica / "alternativas.yaml", "Cobrar con PagueloFacil solo el servicio",
                "Cobrar solo el servicio")
    assert cargar_politica(copia_politica).huella != antes
