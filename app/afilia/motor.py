"""Motor de decisión del evaluador.

Con los datos del comercio y las respuestas del analista decide qué preguntar y qué recomendar. Es determinista
(las mismas entradas dan siempre el mismo resultado) y no guarda estado: la interfaz le manda todo en cada cambio.

Principios (docs/02-como-decide.md):
1. Se evalúa lo que el cliente paga, no las palabras con que el comercio describe su negocio.
2. Una palabra clave nunca rechaza por sí sola: activa preguntas para aclarar.
3. Todo resultado distinto de "aplica" trae alternativas para poder afiliar.
4. Cada motivo dice qué respuesta lo produjo; la decisión final es del analista y del comité.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .politica import ETIQUETAS, NIVELES, RANGO, Opcion, Politica, Pregunta

CAMPOS_COMERCIO = ("nombre", "razon_social", "actividad", "descripcion", "web")
# La web no se usa para detectar palabras clave: un dominio no describe lo que se vende.
CAMPOS_DETECCION = ("nombre", "razon_social", "actividad", "descripcion")
MAX_CAMPO = 4000

# Documentos y alternativa que siempre van cuando el caso pasa por comité (expediente).
DOCUMENTOS_COMITE = ("formulario_debida_diligencia", "evaluacion_debida_diligencia")
ALTERNATIVA_COMITE = "expediente_comite"

BLOQUE_ACTIVIDAD = "Aclarar la actividad"

RESUMENES = {
    "aplica": "El comercio aplica: se afilia con el proceso estándar.",
    "condicionado": "Aplica con condiciones: se afilia cuando cumpla las condiciones y entregue los documentos.",
    "comite": "Requiere comité: armar el expediente y, mientras tanto, ofrecer las alternativas.",
    "no_aplica": "No aplica tal como está planteado: revisar las alternativas para afiliarlo de otra forma.",
}


@dataclass
class Entrada:
    comercio: dict[str, str] = field(default_factory=dict)
    respuestas: dict[str, Any] = field(default_factory=dict)
    agregadas: list[str] = field(default_factory=list)
    quitadas: list[str] = field(default_factory=list)


Respuestas = dict[str, tuple[str, ...]]


def limpiar_comercio(comercio: dict[str, Any] | None) -> dict[str, str]:
    comercio = comercio or {}
    return {c: " ".join(str(comercio.get(c) or "").split())[:MAX_CAMPO] for c in CAMPOS_COMERCIO}


def limpiar_respuestas(pol: Politica, respuestas: dict[str, Any] | None) -> Respuestas:
    """Solo preguntas que existen y opciones válidas; una respuesta única se queda con una opción."""
    limpias: Respuestas = {}
    for pid, valor in (respuestas or {}).items():
        pregunta = pol.preguntas.get(pid)
        if pregunta is None:
            continue
        valores = [valor] if isinstance(valor, str) else valor if isinstance(valor, list) else []
        elegidas = tuple(dict.fromkeys(v for v in valores if isinstance(v, str) and pregunta.opcion(v)))
        if pregunta.tipo == "unica":
            elegidas = elegidas[:1]
        if elegidas:
            limpias[pid] = elegidas
    return limpias


def _cumple(condicion: Iterable[tuple[str, tuple[str, ...]]], respuestas: Respuestas) -> bool:
    return all(any(o in respuestas.get(pid, ()) for o in opciones) for pid, opciones in condicion)


def _elegidas(pregunta: Pregunta, respuestas: Respuestas) -> list[Opcion]:
    return [o for oid in respuestas.get(pregunta.id, ()) if (o := pregunta.opcion(oid))]


def _orden_preguntas(pol: Politica, activas: dict[str, str]) -> list[str]:
    """Primero las preguntas de las actividades detectadas (lo que hay que aclarar), luego las generales."""
    ids = [pid for cid in pol.categorias if cid in activas for pid in pol.categorias[cid].preguntas]
    return ids + list(pol.generales)


def _visibles(pol: Politica, activas: dict[str, str], respuestas: Respuestas) -> tuple[list[str], Respuestas]:
    """Preguntas que se muestran y las respuestas que cuentan (las de preguntas ocultas se ignoran)."""
    visibles: list[str] = []
    cuentan: Respuestas = {}
    for pid in _orden_preguntas(pol, activas):
        if _cumple(pol.preguntas[pid].mostrar_si, cuentan):
            visibles.append(pid)
            if pid in respuestas:
                cuentan[pid] = respuestas[pid]
    return visibles, cuentan


def _agregar(destino: list, valores: Iterable) -> None:
    for v in valores:
        if v and v not in destino:
            destino.append(v)


def _maximo(niveles: Iterable[str], defecto: str) -> str:
    niveles = list(niveles)
    return max(niveles, key=RANGO.__getitem__) if niveles else defecto


def evaluar(pol: Politica, entrada: Entrada) -> dict[str, Any]:
    comercio = limpiar_comercio(entrada.comercio)
    respuestas = limpiar_respuestas(pol, entrada.respuestas)
    quitadas = {c for c in entrada.quitadas if c in pol.categorias}
    texto = " ".join(comercio[c] for c in CAMPOS_DETECCION)
    detectadas = pol.detectar(texto)

    # Categorías activas y por qué: detectada (palabras clave), agregada (analista) o respuesta (otra respuesta la activó).
    activas: dict[str, str] = {}
    for cid in detectadas:
        activas[cid] = "detectada"
    for cid in entrada.agregadas:
        if cid in pol.categorias:
            activas.setdefault(cid, "agregada")
    for cid in quitadas:
        activas.pop(cid, None)

    # Una respuesta puede activar otra categoría (el tour de bares activa "experiencias"), cuyas preguntas
    # aparecen y pueden activar otras: se repite hasta que no cambie nada.
    for _ in range(len(pol.categorias) + 1):
        visibles, cuentan = _visibles(pol, activas, respuestas)
        nuevas = [cid for pid in visibles for o in _elegidas(pol.preguntas[pid], cuentan) for cid in o.activa
                  if cid not in activas and cid not in quitadas]
        if not nuevas:
            break
        for cid in nuevas:
            activas.setdefault(cid, "respuesta")
    activas = {cid: activas[cid] for cid in pol.categorias if cid in activas}

    motivos: list[dict[str, Any]] = []
    condiciones: list[str] = []
    documentos: list[str] = []
    alternativas: list[str] = []
    servicios: list[str] = []
    niveles: list[str] = []
    categorias_out: list[dict[str, Any]] = []

    def registrar(o: Opcion) -> None:
        _agregar(condiciones, o.condiciones)
        _agregar(documentos, o.documentos)
        _agregar(alternativas, o.alternativas)
        _agregar(servicios, [o.servicio_comite])

    for cid, fuente in activas.items():
        cat = pol.categorias[cid]
        elegidas = [(pol.preguntas[pid], o) for pid in cat.preguntas if pid in cuentan
                    for o in _elegidas(pol.preguntas[pid], cuentan)]
        descartada = any(o.descarta for _, o in elegidas)
        niveles_cat = [o.nivel for _, o in elegidas if o.nivel]
        topes = [o.tope for _, o in elegidas if o.tope]
        pendientes_cat = [pid for pid in cat.preguntas if pid in visibles and pol.preguntas[pid].clave
                          and pid not in cuentan]
        nivel = None
        if not descartada:
            nivel = _maximo(niveles_cat, cat.nivel)
            if topes:
                tope = min(topes, key=RANGO.__getitem__)
                if RANGO[nivel] > RANGO[tope]:
                    nivel = tope
        motivos_cat = []
        if not descartada and not niveles_cat:
            motivos_cat.append({"nivel": cat.nivel, "texto": cat.por_que, "pregunta": None, "respuesta": None,
                                "base": True})
        for p, o in elegidas:
            if o.motivo:
                motivos_cat.append({"nivel": o.nivel or o.tope or ("descartada" if o.descarta else None),
                                    "texto": o.motivo, "pregunta": p.texto, "respuesta": o.texto, "base": False})
            registrar(o)
        if nivel is not None:
            niveles.append(nivel)
            _agregar(documentos, cat.documentos)
            # Las alternativas generales de la categoría son para buscar cómo afiliar lo que no aplica directo.
            if RANGO[nivel] >= RANGO["comite"]:
                _agregar(alternativas, cat.alternativas)
            for m in motivos_cat:
                if m["nivel"] in NIVELES and not (m["base"] and m["nivel"] == "aplica"):
                    motivos.append({**m, "origen": cat.nombre})
        categorias_out.append({
            "id": cid,
            "nombre": cat.nombre,
            "fuente": fuente,
            "palabras": detectadas.get(cid, []),
            "nivel_base": cat.nivel,
            "nivel": nivel,
            "etiqueta": ETIQUETAS[nivel] if nivel else "Descartada",
            "origen": cat.origen,
            "por_que": cat.por_que,
            "descartada": descartada,
            "aclarada": not pendientes_cat,
            "motivos": motivos_cat,
        })

    for pid in pol.generales:
        if pid not in cuentan:
            continue
        pregunta = pol.preguntas[pid]
        for o in _elegidas(pregunta, cuentan):
            if o.nivel:
                niveles.append(o.nivel)
                motivos.append({"nivel": o.nivel, "texto": o.motivo, "pregunta": pregunta.texto,
                                "respuesta": o.texto, "base": False, "origen": pregunta.bloque or "General"})
            registrar(o)

    for regla in pol.reglas:
        if not _cumple(regla.si, cuentan):
            continue
        if regla.nivel:
            niveles.append(regla.nivel)
            motivos.append({"nivel": regla.nivel, "texto": regla.motivo, "pregunta": None, "respuesta": None,
                            "base": False, "origen": "Combinación de respuestas"})
        _agregar(condiciones, regla.condiciones)
        _agregar(documentos, regla.documentos)
        _agregar(alternativas, regla.alternativas)

    nivel_global = _maximo(niveles, "aplica")
    if nivel_global == "comite" or servicios:
        _agregar(documentos, DOCUMENTOS_COMITE)
    if nivel_global == "comite":
        _agregar(alternativas, [ALTERNATIVA_COMITE])
    motivos.sort(key=lambda m: -RANGO[m["nivel"]])

    preguntas_out = []
    for pid in visibles:
        p = pol.preguntas[pid]
        respuesta = list(cuentan.get(pid, ()))
        preguntas_out.append({
            "id": p.id,
            "texto": p.texto,
            "ayuda": p.ayuda,
            "tipo": p.tipo,
            "clave": p.clave,
            "categoria": p.categoria,
            "bloque": pol.categorias[p.categoria].nombre if p.categoria else (p.bloque or "General"),
            "seccion": BLOQUE_ACTIVIDAD if p.categoria else "Perfil y riesgo",
            "opciones": [{"id": o.id, "texto": o.texto} for o in p.opciones],
            "respuesta": respuesta if p.tipo == "multiple" else (respuesta[0] if respuesta else None),
        })
    pendientes = [p["id"] for p in preguntas_out if p["clave"] and not p["respuesta"]]
    sin_responder = [p["id"] for p in preguntas_out if not p["respuesta"]]
    siguiente = pendientes[0] if pendientes else (sin_responder[0] if sin_responder else None)

    # Los documentos salen en el orden del catálogo (primero los básicos de identidad y del negocio).
    docs = [d for did, d in pol.documentos.items() if did in documentos]
    alts = [pol.alternativas[a] for a in alternativas]
    avisos = []
    if not texto.strip():
        avisos.append("Describe qué vende el comercio para que el evaluador detecte la actividad.")
    elif not detectadas:
        avisos.append("No se detectaron actividades restringidas en la descripción. Si algo no cuadra, agrega la "
                      "actividad a mano.")

    resumen = RESUMENES[nivel_global]
    pasos = list(pol.mensajes.get("pasos", {}).get(nivel_global, []))
    if pendientes:
        # Mientras falten preguntas clave no hay conclusión: se muestra hacia dónde va, sin cerrar el caso.
        faltan = "Falta 1 pregunta clave" if len(pendientes) == 1 else f"Faltan {len(pendientes)} preguntas clave"
        resumen = (f"{faltan}. Con lo que se sabe hasta ahora: {ETIQUETAS[nivel_global].lower()}. "
                   "No es una conclusión: responde las preguntas clave antes de decidir.")
        pasos.insert(0, "Responder las preguntas clave pendientes; si no sabes una respuesta, pregúntasela al comercio.")

    resultado = {
        "nivel": nivel_global,
        "etiqueta": ETIQUETAS[nivel_global],
        "estado": "preliminar" if pendientes else "completo",
        "resumen": resumen,
        "comercio": comercio,
        "categorias": categorias_out,
        "motivos": motivos,
        "condiciones": condiciones,
        "documentos": docs,
        "alternativas": alts,
        "servicios_comite": servicios,
        "preguntas": preguntas_out,
        "pendientes": pendientes,
        "siguiente": siguiente,
        "progreso": {"respondidas": len(preguntas_out) - len(sin_responder), "visibles": len(preguntas_out),
                     "clave_pendientes": len(pendientes)},
        "pasos": pasos,
        "avisos": avisos,
        "politica": {"version": pol.version, "estado": pol.estado, "huella": pol.huella},
    }
    resultado["mensaje_comercio"] = mensaje_comercio(pol, resultado)
    resultado["resumen_comite"] = resumen_comite(resultado)
    return resultado


def mensaje_comercio(pol: Politica, r: dict[str, Any]) -> str:
    """Borrador para el comercio: qué sigue y qué necesita, sin explicar criterios internos de riesgo."""
    m = pol.mensajes
    nombre = r["comercio"]["nombre"] or "[nombre del comercio]"
    nivel = r["nivel"]
    partes = [m["saludo"].format(nombre=nombre), " ".join(m["por_nivel"][nivel].split())]
    if r["documentos"] and nivel != "no_aplica":
        partes.append(m["bloques"]["documentos"] + "\n" + "\n".join(f"- {d['nombre']}" for d in r["documentos"]))
    if r["servicios_comite"]:
        partes.append(m["bloques"]["servicios"] + "\n" + "\n".join(f"- {s}" for s in r["servicios_comite"]))
    if r["alternativas"] and nivel in ("comite", "no_aplica"):
        visibles = [a for a in r["alternativas"] if a["id"] != ALTERNATIVA_COMITE]
        if visibles:
            partes.append(m["bloques"]["alternativas"] + "\n" + "\n".join(f"- {a['titulo']}" for a in visibles))
    if nivel == "no_aplica":
        partes.append(m["bloques"]["revision"])
    partes.append(m["despedida"])
    return "\n\n".join(partes)


def resumen_comite(r: dict[str, Any]) -> str:
    """Resumen en Markdown para el expediente o para consultar al comité."""
    c = r["comercio"]
    lineas = [f"# Evaluación de afiliación · {c['nombre'] or 'Comercio sin nombre'}", ""]
    estado = " (preliminar: faltan preguntas clave)" if r["estado"] == "preliminar" else ""
    lineas += [f"**Recomendación del evaluador:** {r['etiqueta']}{estado}", "", r["resumen"], "", "## Comercio"]
    for etiqueta, campo in (("Nombre comercial", "nombre"), ("Razón social", "razon_social"),
                            ("Actividad declarada", "actividad"), ("Descripción", "descripcion"),
                            ("Sitio web o redes", "web")):
        if c[campo]:
            lineas.append(f"- {etiqueta}: {c[campo]}")
    if r["categorias"]:
        lineas += ["", "## Actividad identificada"]
        for cat in r["categorias"]:
            palabras = f" (palabras: {', '.join(cat['palabras'])})" if cat["palabras"] else ""
            lineas.append(f"- {cat['nombre']}: {cat['etiqueta']}{palabras}")
    respondidas = [p for p in r["preguntas"] if p["respuesta"]]
    if respondidas:
        lineas += ["", "## Respuestas"]
        for p in respondidas:
            ids = p["respuesta"] if isinstance(p["respuesta"], list) else [p["respuesta"]]
            textos = [o["texto"] for o in p["opciones"] if o["id"] in ids]
            lineas.append(f"- {p['texto']} → {'; '.join(textos)}")
    secciones = (
        ("Motivos", [f"[{_etiqueta(m['nivel'])}] {m['origen']}: {m['texto']}" for m in r["motivos"]]),
        ("Condiciones para afiliar", r["condiciones"]),
        ("Servicios que pasan por comité", r["servicios_comite"]),
        ("Documentos", [d["nombre"] for d in r["documentos"]]),
        ("Alternativas", [f"{a['titulo']}: {a['detalle']}" for a in r["alternativas"]]),
        ("Preguntas sin responder", [p["texto"] for p in r["preguntas"] if p["id"] in r["pendientes"]]),
    )
    for titulo, items in secciones:
        if items:
            lineas += ["", f"## {titulo}"] + [f"- {i}" for i in items]
    pol = r["politica"]
    lineas += ["", f"_Evaluador de aliados comerciales · política {pol['version']} ({pol['estado']})._"]
    return "\n".join(lineas)


def _etiqueta(nivel: str) -> str:
    return ETIQUETAS.get(nivel, nivel)
