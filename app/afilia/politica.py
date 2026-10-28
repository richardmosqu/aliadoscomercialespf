"""Carga y valida la política de afiliación (los YAML de politica/).

La política es el conocimiento del evaluador: categorías de actividad, preguntas, alternativas, documentos y
mensajes. Cumplimiento la edita sin tocar código; este módulo la valida al cargarla y avisa con un mensaje claro
si algo no cuadra (un id que no existe, un nivel mal escrito), para que un error de edición no llegue a la app.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

NIVELES = ("aplica", "condicionado", "comite", "no_aplica")
RANGO = {nivel: i for i, nivel in enumerate(NIVELES)}
ETIQUETAS = {
    "aplica": "Aplica",
    "condicionado": "Aplica con condiciones",
    "comite": "Requiere comité",
    "no_aplica": "No aplica por ahora",
}
ORIGENES = ("publica", "propuesta")
TIPOS = ("unica", "multiple")
ARCHIVOS = ("categorias.yaml", "preguntas-generales.yaml", "alternativas.yaml", "documentos.yaml", "mensajes.yaml")


class PoliticaError(ValueError):
    """La política tiene un error de edición."""


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes (la ñ queda como n), para comparar palabras clave."""
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def patron_palabra(palabra: str) -> re.Pattern[str]:
    """Expresión que encuentra la palabra clave como palabra completa; un * final acepta cualquier terminación."""
    palabra = normalizar(palabra).strip()
    comodin = palabra.endswith("*")
    partes = palabra.rstrip("*").split()
    cuerpo = r"\s+".join(re.escape(p) for p in partes)
    return re.compile(r"(?<!\w)" + cuerpo + (r"\w*" if comodin else "") + r"(?!\w)")


@dataclass(frozen=True)
class Opcion:
    id: str
    texto: str
    corto: str = ""  # etiqueta de la burbuja en la conversación (si falta, se usa texto)
    nivel: str | None = None
    motivo: str = ""
    tope: str | None = None
    descarta: bool = False
    activa: tuple[str, ...] = ()
    condiciones: tuple[str, ...] = ()
    documentos: tuple[str, ...] = ()
    alternativas: tuple[str, ...] = ()
    servicio_comite: str = ""


@dataclass(frozen=True)
class Pregunta:
    id: str
    texto: str
    opciones: tuple[Opcion, ...]
    corta: str = ""  # cómo la hace la burbuja en la conversación (si falta, se usa texto)
    tipo: str = "unica"
    clave: bool = False
    ayuda: str = ""
    bloque: str = ""
    categoria: str | None = None  # None = pregunta general
    mostrar_si: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def opcion(self, opcion_id: str) -> Opcion | None:
        return next((o for o in self.opciones if o.id == opcion_id), None)


@dataclass(frozen=True)
class Categoria:
    id: str
    nombre: str
    nivel: str
    origen: str
    por_que: str
    palabras_clave: tuple[str, ...]
    preguntas: tuple[str, ...]
    alternativas: tuple[str, ...] = ()
    documentos: tuple[str, ...] = ()
    patrones: tuple[re.Pattern[str], ...] = field(default=(), repr=False, compare=False)


@dataclass(frozen=True)
class Regla:
    id: str
    si: tuple[tuple[str, tuple[str, ...]], ...]
    nivel: str | None = None
    motivo: str = ""
    condiciones: tuple[str, ...] = ()
    documentos: tuple[str, ...] = ()
    alternativas: tuple[str, ...] = ()


@dataclass(frozen=True)
class Politica:
    version: str
    estado: str
    categorias: dict[str, Categoria]
    preguntas: dict[str, Pregunta]
    generales: tuple[str, ...]
    reglas: tuple[Regla, ...]
    alternativas: dict[str, dict[str, Any]]
    documentos: dict[str, dict[str, Any]]
    mensajes: dict[str, Any]
    huella: str

    def detectar(self, texto: str) -> dict[str, list[str]]:
        """Categorías cuyas palabras clave aparecen en el texto, con las palabras encontradas."""
        normal = normalizar(texto)
        encontradas: dict[str, list[str]] = {}
        for cat in self.categorias.values():
            palabras: list[str] = []
            for patron in cat.patrones:
                for m in patron.finditer(normal):
                    if m.group(0) not in palabras:
                        palabras.append(m.group(0))
            if palabras:
                encontradas[cat.id] = palabras
        return encontradas


# ─────────────────────────────── Carga ───────────────────────────────


def _lista(valor: Any, donde: str) -> tuple[str, ...]:
    if valor is None:
        return ()
    if not isinstance(valor, list) or not all(isinstance(v, str) and v.strip() for v in valor):
        raise PoliticaError(f"{donde}: debe ser una lista de textos (revisa comillas en valores como no, sí o +18).")
    return tuple(v.strip() for v in valor)


def _texto(datos: dict, clave: str, donde: str, requerido: bool = True) -> str:
    valor = datos.get(clave)
    if valor is None and not requerido:
        return ""
    if not isinstance(valor, str) or not valor.strip():
        raise PoliticaError(f"{donde}: falta '{clave}' o no es texto (revisa comillas en valores como no, sí o +18).")
    return " ".join(valor.split())


def _nivel(valor: Any, donde: str) -> str | None:
    if valor is None:
        return None
    if valor not in NIVELES:
        raise PoliticaError(f"{donde}: nivel '{valor}' no válido. Opciones: {', '.join(NIVELES)}.")
    return valor


def _condicion(valor: Any, donde: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if valor is None:
        return ()
    if not isinstance(valor, dict) or not valor:
        raise PoliticaError(f"{donde}: debe ser {{pregunta: [opciones]}}.")
    return tuple((str(k), _lista(v, f"{donde}.{k}")) for k, v in valor.items())


def _opcion(datos: Any, donde: str) -> Opcion:
    if not isinstance(datos, dict):
        raise PoliticaError(f"{donde}: cada opción debe tener id y texto.")
    oid = _texto(datos, "id", donde)
    donde = f"{donde} ({oid})"
    nivel = _nivel(datos.get("nivel"), donde)
    tope = _nivel(datos.get("tope"), donde)
    descarta = bool(datos.get("descarta", False))
    motivo = _texto(datos, "motivo", donde, requerido=bool(nivel or tope or descarta))
    return Opcion(
        id=oid,
        texto=_texto(datos, "texto", donde),
        corto=_texto(datos, "corto", donde, requerido=False),
        nivel=nivel,
        motivo=motivo,
        tope=tope,
        descarta=descarta,
        activa=_lista(datos.get("activa"), f"{donde}.activa"),
        condiciones=tuple(" ".join(c.split()) for c in _lista(datos.get("condiciones"), f"{donde}.condiciones")),
        documentos=_lista(datos.get("documentos"), f"{donde}.documentos"),
        alternativas=_lista(datos.get("alternativas"), f"{donde}.alternativas"),
        servicio_comite=_texto(datos, "servicio_comite", donde, requerido=False),
    )


def _pregunta(datos: Any, donde: str, categoria: str | None) -> Pregunta:
    if not isinstance(datos, dict):
        raise PoliticaError(f"{donde}: cada pregunta debe tener id, texto y opciones.")
    pid = _texto(datos, "id", donde)
    donde = f"{donde} ({pid})"
    tipo = datos.get("tipo", "unica")
    if tipo not in TIPOS:
        raise PoliticaError(f"{donde}: tipo '{tipo}' no válido. Opciones: {', '.join(TIPOS)}.")
    opciones_raw = datos.get("opciones")
    if not isinstance(opciones_raw, list) or len(opciones_raw) < 2:
        raise PoliticaError(f"{donde}: necesita al menos dos opciones.")
    opciones = tuple(_opcion(o, f"{donde}.opciones[{i}]") for i, o in enumerate(opciones_raw))
    ids = [o.id for o in opciones]
    if len(set(ids)) != len(ids):
        raise PoliticaError(f"{donde}: hay opciones con el mismo id.")
    return Pregunta(
        id=pid,
        texto=_texto(datos, "texto", donde),
        corta=_texto(datos, "corta", donde, requerido=False),
        opciones=opciones,
        tipo=tipo,
        clave=bool(datos.get("clave", False)),
        ayuda=_texto(datos, "ayuda", donde, requerido=False),
        bloque=_texto(datos, "bloque", donde, requerido=False),
        categoria=categoria,
        mostrar_si=_condicion(datos.get("mostrar_si"), f"{donde}.mostrar_si"),
    )


def _leer(carpeta: Path, nombre: str) -> dict:
    ruta = carpeta / nombre
    if not ruta.is_file():
        raise PoliticaError(f"Falta el archivo de la política: {ruta}")
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PoliticaError(f"{nombre}: el YAML no se puede leer ({exc}).") from exc
    if not isinstance(datos, dict):
        raise PoliticaError(f"{nombre}: el archivo está vacío o no tiene el formato esperado.")
    return datos


def huella_carpeta(carpeta: Path) -> str:
    """Cambia cuando alguien edita un archivo de la política (para recargarla sin reiniciar la app)."""
    h = hashlib.sha256()
    for nombre in ARCHIVOS:
        ruta = carpeta / nombre
        if ruta.is_file():
            h.update(nombre.encode())
            h.update(ruta.read_bytes())
    return h.hexdigest()[:16]


def cargar_politica(carpeta: Path) -> Politica:
    carpeta = Path(carpeta)
    datos_cat = _leer(carpeta, "categorias.yaml")
    datos_gen = _leer(carpeta, "preguntas-generales.yaml")
    datos_alt = _leer(carpeta, "alternativas.yaml")
    datos_doc = _leer(carpeta, "documentos.yaml")
    mensajes = _leer(carpeta, "mensajes.yaml")

    alternativas: dict[str, dict[str, Any]] = {}
    for i, a in enumerate(datos_alt.get("alternativas") or []):
        donde = f"alternativas.yaml[{i}]"
        aid = _texto(a, "id", donde)
        if aid in alternativas:
            raise PoliticaError(f"{donde}: la alternativa '{aid}' está repetida.")
        alternativas[aid] = {"id": aid, "titulo": _texto(a, "titulo", donde), "detalle": _texto(a, "detalle", donde),
                             "por_confirmar": bool(a.get("por_confirmar", True))}

    documentos: dict[str, dict[str, Any]] = {}
    for i, d in enumerate(datos_doc.get("documentos") or []):
        donde = f"documentos.yaml[{i}]"
        did = _texto(d, "id", donde)
        if did in documentos:
            raise PoliticaError(f"{donde}: el documento '{did}' está repetido.")
        documentos[did] = {"id": did, "nombre": _texto(d, "nombre", donde),
                           "detalle": _texto(d, "detalle", donde, requerido=False),
                           "por_confirmar": bool(d.get("por_confirmar", True))}

    preguntas: dict[str, Pregunta] = {}

    def agregar(p: Pregunta, donde: str) -> None:
        if p.id in preguntas:
            raise PoliticaError(f"{donde}: la pregunta '{p.id}' está repetida.")
        preguntas[p.id] = p

    categorias: dict[str, Categoria] = {}
    for i, c in enumerate(datos_cat.get("categorias") or []):
        donde = f"categorias.yaml[{i}]"
        cid = _texto(c, "id", donde)
        donde = f"categorias.yaml ({cid})"
        if cid in categorias:
            raise PoliticaError(f"{donde}: la categoría está repetida.")
        nivel = _nivel(c.get("nivel"), donde)
        if nivel is None:
            raise PoliticaError(f"{donde}: falta 'nivel'.")
        origen = c.get("origen")
        if origen not in ORIGENES:
            raise PoliticaError(f"{donde}: origen '{origen}' no válido. Opciones: {', '.join(ORIGENES)}.")
        palabras = _lista(c.get("palabras_clave"), f"{donde}.palabras_clave")
        ids_preguntas = []
        for j, p in enumerate(c.get("preguntas") or []):
            pregunta = _pregunta(p, f"{donde}.preguntas[{j}]", categoria=cid)
            agregar(pregunta, donde)
            ids_preguntas.append(pregunta.id)
        categorias[cid] = Categoria(
            id=cid,
            nombre=_texto(c, "nombre", donde),
            nivel=nivel,
            origen=origen,
            por_que=_texto(c, "por_que", donde),
            palabras_clave=palabras,
            preguntas=tuple(ids_preguntas),
            alternativas=_lista(c.get("alternativas"), f"{donde}.alternativas"),
            documentos=_lista(c.get("documentos"), f"{donde}.documentos"),
            patrones=tuple(patron_palabra(p) for p in palabras),
        )

    generales = []
    for j, p in enumerate(datos_gen.get("preguntas") or []):
        pregunta = _pregunta(p, f"preguntas-generales.yaml[{j}]", categoria=None)
        agregar(pregunta, "preguntas-generales.yaml")
        generales.append(pregunta.id)

    reglas = []
    for j, r in enumerate(datos_gen.get("reglas") or []):
        donde = f"preguntas-generales.yaml reglas[{j}]"
        rid = _texto(r, "id", donde)
        nivel = _nivel(r.get("nivel"), donde)
        reglas.append(Regla(
            id=rid,
            si=_condicion(r.get("si"), f"{donde}.si"),
            nivel=nivel,
            motivo=_texto(r, "motivo", donde, requerido=nivel is not None),
            condiciones=_lista(r.get("condiciones"), f"{donde}.condiciones"),
            documentos=_lista(r.get("documentos"), f"{donde}.documentos"),
            alternativas=_lista(r.get("alternativas"), f"{donde}.alternativas"),
        ))
        if not reglas[-1].si:
            raise PoliticaError(f"{donde}: falta 'si'.")

    politica = Politica(
        version=str(datos_cat.get("version", "")),
        estado=str(datos_cat.get("estado", "propuesta")),
        categorias=categorias,
        preguntas=preguntas,
        generales=tuple(generales),
        reglas=tuple(reglas),
        alternativas=alternativas,
        documentos=documentos,
        mensajes=mensajes,
        huella=huella_carpeta(carpeta),
    )
    _validar_referencias(politica)
    return politica


def _validar_referencias(pol: Politica) -> None:
    """Todo id que se nombra en la política tiene que existir."""

    def revisar(ids: tuple[str, ...], catalogo: dict, que: str, donde: str) -> None:
        for x in ids:
            if x not in catalogo:
                raise PoliticaError(f"{donde}: {que} '{x}' no existe.")

    def revisar_condicion(cond: tuple[tuple[str, tuple[str, ...]], ...], donde: str) -> None:
        for pid, opciones in cond:
            pregunta = pol.preguntas.get(pid)
            if pregunta is None:
                raise PoliticaError(f"{donde}: la pregunta '{pid}' no existe.")
            for oid in opciones:
                if pregunta.opcion(oid) is None:
                    raise PoliticaError(f"{donde}: la pregunta '{pid}' no tiene la opción '{oid}'.")

    for cat in pol.categorias.values():
        revisar(cat.alternativas, pol.alternativas, "la alternativa", cat.id)
        revisar(cat.documentos, pol.documentos, "el documento", cat.id)
    for p in pol.preguntas.values():
        revisar_condicion(p.mostrar_si, f"{p.id}.mostrar_si")
        for o in p.opciones:
            donde = f"{p.id} › {o.id}"
            revisar(o.alternativas, pol.alternativas, "la alternativa", donde)
            revisar(o.documentos, pol.documentos, "el documento", donde)
            revisar(o.activa, pol.categorias, "la categoría", donde)
            if p.categoria is None and (o.tope or o.descarta):
                raise PoliticaError(f"{donde}: 'tope' y 'descarta' solo sirven en preguntas de una categoría.")
    for r in pol.reglas:
        revisar_condicion(r.si, f"regla {r.id}")
        revisar(r.alternativas, pol.alternativas, "la alternativa", f"regla {r.id}")
        revisar(r.documentos, pol.documentos, "el documento", f"regla {r.id}")
    for clave in ("saludo", "despedida", "por_nivel", "bloques"):
        if clave not in pol.mensajes:
            raise PoliticaError(f"mensajes.yaml: falta '{clave}'.")
    for nivel in NIVELES:
        if not isinstance(pol.mensajes["por_nivel"].get(nivel), str):
            raise PoliticaError(f"mensajes.yaml: falta el mensaje para el nivel '{nivel}'.")
