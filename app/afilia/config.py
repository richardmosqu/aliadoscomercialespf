"""Configuración leída de variables de entorno (y de app/.env si existe)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parent

DEFAULT_MODEL = "claude-opus-5-5"
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
# Largo mínimo de la clave de acceso cuando la app se abre a la red.
MIN_ACCESS_KEY_LENGTH = 16


def _load_dotenv(path: Path) -> None:
    """Carga un .env simple (CLAVE=valor) sin dependencias externas; no pisa variables que ya existan."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    politica_dir: Path = PROJECT_ROOT / "politica"
    datos_dir: Path = APP_DIR / "datos"
    # Acceso: correo del dominio + clave compartida. Sin clave, solo se permite en la máquina local.
    clave_acceso: str = ""
    dominio: str = "paguelofacil.com"
    secreto_sesion: str = ""
    url_publica: str = ""
    # Análisis con IA (opcional): sin clave de la API la app funciona igual, sin el botón de IA.
    ia: bool = False
    modelo: str = DEFAULT_MODEL
    esfuerzo: str = "medium"

    @property
    def requiere_acceso(self) -> bool:
        return bool(self.clave_acceso)

    @property
    def es_local(self) -> bool:
        return self.host in LOCAL_HOSTS


def get_settings() -> Settings:
    _load_dotenv(APP_DIR / ".env")
    env = os.environ
    esfuerzo = env.get("AFILIA_ESFUERZO", "medium").strip().lower()
    if esfuerzo not in EFFORT_LEVELS:
        raise ValueError(f"AFILIA_ESFUERZO={esfuerzo!r} no es válido. Opciones: {', '.join(EFFORT_LEVELS)}")
    ia_pedida = env.get("AFILIA_IA", "auto").strip().lower()
    return Settings(
        host=env.get("AFILIA_HOST", "127.0.0.1").strip(),
        port=int(env.get("PORT") or env.get("AFILIA_PORT") or 8000),
        politica_dir=Path(env.get("AFILIA_POLITICA_DIR") or PROJECT_ROOT / "politica"),
        datos_dir=Path(env.get("AFILIA_DATOS_DIR") or APP_DIR / "datos"),
        clave_acceso=env.get("AFILIA_CLAVE_ACCESO", "").strip(),
        dominio=env.get("AFILIA_DOMINIO", "paguelofacil.com").strip().lower(),
        secreto_sesion=env.get("AFILIA_SECRETO_SESION", "").strip(),
        url_publica=env.get("AFILIA_URL_PUBLICA", "").strip(),
        ia=ia_pedida not in ("off", "0", "no", "false") and bool(env.get("ANTHROPIC_API_KEY", "").strip()),
        modelo=env.get("AFILIA_MODELO", DEFAULT_MODEL).strip(),
        esfuerzo=esfuerzo,
    )


def check_web_settings(s: Settings) -> None:
    """La app no se abre a la red sin una clave de acceso larga y un secreto de sesión."""
    if s.es_local:
        return
    if len(s.clave_acceso) < MIN_ACCESS_KEY_LENGTH:
        raise ValueError(
            f"Para abrir la app a la red (AFILIA_HOST={s.host}) define AFILIA_CLAVE_ACCESO con "
            f"{MIN_ACCESS_KEY_LENGTH} caracteres o más."
        )
    if not s.secreto_sesion:
        raise ValueError("Para abrir la app a la red define AFILIA_SECRETO_SESION (un texto largo y aleatorio).")
