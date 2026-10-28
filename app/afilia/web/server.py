"""Servidor de la app web: la página del evaluador y la API que usa.

- /api/evaluar recibe los datos del comercio y las respuestas, y devuelve el veredicto y las preguntas que siguen.
  No guarda nada: la página lo llama en cada cambio.
- /api/evaluaciones guarda el expediente (historial del equipo, SQLite).
- /api/ia/analizar es opcional: solo funciona con la clave de la API de Claude.

Con AFILIA_CLAVE_ACCESO, toda ruta /api/ salvo /api/estado y /api/sesion exige sesión iniciada con un correo del
dominio de la empresa.
"""

from __future__ import annotations

import hmac
import logging
import re
import secrets
import threading
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from ..config import Settings, check_web_settings, get_settings
from ..historial import DECISIONES, Historial
from ..ia import MAX_ADICIONAL, AnalistaIA, IAError
from ..motor import Entrada, evaluar
from ..politica import ETIQUETAS, Politica, PoliticaError, cargar_politica, huella_carpeta

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
SESSION_MAX_AGE_S = 12 * 3600
MAX_CAMPO = 4000
USUARIO_LOCAL = "analista local"

MSG_SESION = "Inicia sesión con tu correo de la empresa."
MSG_IA_APAGADA = ("El análisis con IA no está activado: falta ANTHROPIC_API_KEY en la configuración. "
                  "El evaluador funciona igual con las preguntas.")


class EvaluarIn(BaseModel):
    comercio: dict[str, str] = Field(default_factory=dict)
    respuestas: dict[str, str | list[str]] = Field(default_factory=dict)
    agregadas: list[str] = Field(default_factory=list, max_length=50)
    quitadas: list[str] = Field(default_factory=list, max_length=50)

    def entrada(self) -> Entrada:
        comercio = {k: v[:MAX_CAMPO] for k, v in self.comercio.items()}
        return Entrada(comercio=comercio, respuestas=dict(self.respuestas), agregadas=list(self.agregadas),
                       quitadas=list(self.quitadas))


class GuardarIn(EvaluarIn):
    id: str | None = Field(default=None, max_length=32)
    decision: str = "pendiente"
    notas: str = Field(default="", max_length=4000)


class SesionIn(BaseModel):
    correo: str = Field(min_length=3, max_length=254)
    clave: str = Field(default="", max_length=200)


class IAIn(BaseModel):
    comercio: dict[str, str] = Field(default_factory=dict)
    adicional: str = Field(default="", max_length=MAX_ADICIONAL)


class PoliticaVigente:
    """La política cargada. Si alguien edita los YAML, se recarga; si la edición tiene un error, se sigue usando
    la versión anterior y /api/estado muestra el error."""

    def __init__(self, carpeta: Path):
        self.carpeta = carpeta
        self._lock = threading.Lock()
        self.error = ""
        self._politica = cargar_politica(carpeta)

    def get(self) -> Politica:
        huella = huella_carpeta(self.carpeta)
        with self._lock:
            if huella != self._politica.huella:
                try:
                    self._politica = cargar_politica(self.carpeta)
                    self.error = ""
                except PoliticaError as exc:
                    if self.error != str(exc):
                        log.error("La política editada tiene un error; se sigue usando la anterior: %s", exc)
                    self.error = str(exc)
            return self._politica


def correo_permitido(correo: str, dominio: str) -> str | None:
    correo = (correo or "").strip().lower()
    return correo if re.fullmatch(r"[^@\s]+@" + re.escape(dominio), correo) else None


def politica_publica(pol: Politica) -> dict[str, Any]:
    """La política completa para la pestaña "Política" y para agregar actividades a mano."""

    def pregunta(pid: str) -> dict[str, Any]:
        p = pol.preguntas[pid]
        return {
            "id": p.id, "texto": p.texto, "ayuda": p.ayuda, "tipo": p.tipo, "clave": p.clave,
            "bloque": p.bloque, "mostrar_si": {k: list(v) for k, v in p.mostrar_si},
            "opciones": [{
                "id": o.id, "texto": o.texto, "nivel": o.nivel, "tope": o.tope, "descarta": o.descarta,
                "motivo": o.motivo, "activa": list(o.activa), "condiciones": list(o.condiciones),
                "documentos": list(o.documentos), "alternativas": list(o.alternativas),
                "servicio_comite": o.servicio_comite,
            } for o in p.opciones],
        }

    return {
        "version": pol.version,
        "estado": pol.estado,
        "etiquetas": ETIQUETAS,
        "categorias": [{
            "id": c.id, "nombre": c.nombre, "nivel": c.nivel, "etiqueta": ETIQUETAS[c.nivel], "origen": c.origen,
            "por_que": c.por_que, "palabras_clave": list(c.palabras_clave), "alternativas": list(c.alternativas),
            "preguntas": [pregunta(pid) for pid in c.preguntas],
        } for c in pol.categorias.values()],
        "generales": [pregunta(pid) for pid in pol.generales],
        "reglas": [{"id": r.id, "si": {k: list(v) for k, v in r.si}, "nivel": r.nivel, "motivo": r.motivo,
                    "condiciones": list(r.condiciones)} for r in pol.reglas],
        "alternativas": list(pol.alternativas.values()),
        "documentos": list(pol.documentos.values()),
    }


def create_app(settings: Settings | None = None, ia_client: Any | None = None) -> FastAPI:
    settings = settings or get_settings()
    check_web_settings(settings)
    politica = PoliticaVigente(settings.politica_dir)
    historial = Historial(settings.datos_dir / "evaluaciones.db")
    analista_ia = AnalistaIA(settings, client=ia_client) if settings.ia else None

    app = FastAPI(title="Evaluador de aliados comerciales · PagueloFacil", docs_url=None, redoc_url=None)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secreto_sesion or secrets.token_hex(32),
        session_cookie="afilia_sesion",
        max_age=SESSION_MAX_AGE_S,
        same_site="lax",
        https_only=settings.url_publica.startswith("https://"),
    )

    def usuario_actual(request: Request) -> str:
        usuario = request.session.get("usuario")
        if usuario:
            return usuario
        if settings.requiere_acceso:
            raise HTTPException(status_code=401, detail=MSG_SESION)
        return USUARIO_LOCAL

    @app.get("/api/estado")
    def estado(request: Request) -> dict[str, Any]:
        pol = politica.get()
        return {
            "ok": True,
            "acceso_requerido": settings.requiere_acceso,
            "usuario": request.session.get("usuario"),
            "ia": analista_ia is not None,
            "dominio": settings.dominio,
            "decisiones": DECISIONES,
            "politica": {"version": pol.version, "estado": pol.estado, "error": politica.error},
        }

    @app.post("/api/sesion")
    def iniciar_sesion(datos: SesionIn, request: Request) -> dict[str, str]:
        correo = correo_permitido(datos.correo, settings.dominio)
        if correo is None:
            raise HTTPException(status_code=403, detail=f"Solo pueden entrar correos @{settings.dominio}.")
        if settings.requiere_acceso and not hmac.compare_digest(datos.clave.encode(), settings.clave_acceso.encode()):
            raise HTTPException(status_code=403, detail="La clave de acceso no es correcta.")
        request.session["usuario"] = correo
        return {"usuario": correo}

    @app.delete("/api/sesion")
    def cerrar_sesion(request: Request) -> dict[str, bool]:
        request.session.clear()
        return {"ok": True}

    @app.get("/api/politica")
    def ver_politica(_: str = Depends(usuario_actual)) -> dict[str, Any]:
        return politica_publica(politica.get())

    @app.post("/api/evaluar")
    def evaluar_comercio(datos: EvaluarIn, _: str = Depends(usuario_actual)) -> dict[str, Any]:
        return evaluar(politica.get(), datos.entrada())

    @app.post("/api/evaluaciones")
    def guardar(datos: GuardarIn, usuario: str = Depends(usuario_actual)) -> dict[str, str]:
        if datos.decision not in DECISIONES:
            raise HTTPException(status_code=422, detail="Decisión no válida.")
        entrada = datos.entrada()
        resultado = evaluar(politica.get(), entrada)
        entrada_json = {"comercio": resultado["comercio"], "respuestas": entrada.respuestas,
                        "agregadas": entrada.agregadas, "quitadas": entrada.quitadas}
        id = historial.guardar(usuario, entrada_json, resultado, datos.decision, datos.notas.strip(), id=datos.id)
        return {"id": id}

    @app.get("/api/evaluaciones")
    def listar(q: str = "", _: str = Depends(usuario_actual)) -> dict[str, Any]:
        return {"evaluaciones": historial.listar(q[:100]), "decisiones": DECISIONES, "etiquetas": ETIQUETAS}

    @app.get("/api/evaluaciones/{id}")
    def obtener(id: str, _: str = Depends(usuario_actual)) -> dict[str, Any]:
        evaluacion = historial.obtener(id)
        if evaluacion is None:
            raise HTTPException(status_code=404, detail="Esa evaluación no existe.")
        return evaluacion

    @app.post("/api/ia/analizar")
    def analizar_con_ia(datos: IAIn, _: str = Depends(usuario_actual)) -> dict[str, Any]:
        if analista_ia is None:
            raise HTTPException(status_code=503, detail=MSG_IA_APAGADA)
        if not any(v.strip() for v in datos.comercio.values()) and not datos.adicional.strip():
            raise HTTPException(status_code=422, detail="Escribe qué vende el comercio antes de analizar.")
        try:
            return analista_ia.analizar(politica.get(), datos.comercio, datos.adicional)
        except IAError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def inicio() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})

    return app
