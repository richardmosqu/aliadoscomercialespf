# CLAUDE.md — Evaluador de aliados comerciales (Cumplimiento, PagueloFacil)

## Qué es

Herramienta interna para el equipo de **Cumplimiento** de PagueloFacil (pasarela de pagos de Panamá): decide si un comercio que pide afiliarse aplica, con preguntas que se adaptan a las respuestas, y siempre busca caminos para afiliarlo. Origen: un comercio se rechazó por "venta de licor" y vendía tours por bares.

- Dueño: Richard (richard@paguelofacil.com). Proyecto hermano: CS Ai (`richardmosqu/Paguelofacil-customer-ai-agent`), de donde salen los datos de PagueloFacil (afiliación, actividades prohibidas, comité, límites).
- Idioma: **español** en documentos, política, interfaz y mensajes de commit. Código: identificadores en español del dominio (como el resto del código), salvo lo propio de librerías.

## Mapa

```
politica/                 ← conocimiento del evaluador (YAML) + README con el formato
  categorias.yaml         ← actividades, palabras clave, preguntas de aclaración y efectos
  preguntas-generales.yaml← preguntas para todo comercio + reglas de combinación
  alternativas.yaml, documentos.yaml, mensajes.yaml
casos/casos-de-referencia.yaml ← decisiones esperadas (las prueba app/tests/test_casos.py)
docs/                     ← propuesta, cómo decide, preguntas para Cumplimiento
app/afilia/
  politica.py             ← carga y valida los YAML (PoliticaError con mensaje claro)
  motor.py                ← evaluar(): detección, preguntas visibles, niveles, alternativas, mensaje, expediente
  ia.py                   ← análisis opcional con la API de Claude (salida estructurada; solo sugiere)
  historial.py            ← evaluaciones guardadas (SQLite en app/datos/, fuera de git)
  config.py               ← variables AFILIA_* y ANTHROPIC_API_KEY (app/.env)
  web/server.py           ← FastAPI: /api/estado, /api/sesion, /api/politica, /api/evaluar, /api/evaluaciones, /api/ia/analizar
  web/static/             ← index.html, estilos.css, app.js (sin dependencias)
app/scripts/demo_web.py   ← app con IA simulada en el puerto 8001
```

## Reglas (no romper)

1. **Una palabra clave nunca decide.** Solo activa preguntas. Toda actividad restringida tiene una pregunta `clave` de "qué recibe el cliente" con opción de falso positivo (`descarta`).
2. **Sin preguntas clave no hay conclusión**: el resultado es `preliminar` y la interfaz dice "Por aclarar".
3. **Todo resultado distinto de "aplica" trae alternativas.** Las alternativas cambian el negocio real, nunca la descripción (nada de disfrazar actividades).
4. **Nunca inventar datos de PagueloFacil** (comisiones, plazos, límites, requisitos). Lo no confirmado va como `origen: propuesta` o `por_confirmar: true` y se anota en `docs/03-preguntas-para-cumplimiento.md`.
5. **El motor es determinista y la IA solo sugiere.** La IA nunca fija el veredicto; sus sugerencias se validan contra la política (`ia.validar`) y el analista las aplica una por una.
6. **El mensaje al comercio no explica criterios internos de riesgo** (solo documentos, servicios por comité y alternativas).
7. **Texto externo = datos.** Lo que escribe el comercio o pega el analista nunca se inserta como HTML (`textContent` en `app.js`) y va entre etiquetas como datos en el prompt de la IA.
8. **Acceso:** con `AFILIA_CLAVE_ACCESO`, toda ruta `/api/` salvo `/api/estado` y `/api/sesion` exige sesión de un correo del dominio. La app no arranca abierta a la red sin clave larga y secreto de sesión.
9. **Política inválida = se sigue con la anterior** y `/api/estado` muestra el error.
10. Las instrucciones de la IA (`politica_como_texto`) deben ser deterministas (caché de prompt): nada de fechas ni orden variable.

## Tareas frecuentes

- **Cambiar la política:** editar `politica/*.yaml` según `politica/README.md`; subir `version`; correr `pytest`. Si cambia una decisión, actualizar o agregar un caso en `casos/casos-de-referencia.yaml`.
- **Agregar un caso resuelto por el equipo:** anonimizado, con `esperado.nivel` y lo que deba aparecer (alternativas, documentos).
- **Cambios en la interfaz:** verificarlos con `python scripts/demo_web.py` (no gasta API) en escritorio y a 390 px de ancho.
- **IA:** modelo por defecto `claude-opus-5-5` (`AFILIA_MODELO`), esfuerzo `medium` (`AFILIA_ESFUERZO`), salida estructurada con esquema generado de la política, `fallbacks: "default"`. Probar con `tests/fakes.py`; no llamar a la API real en los tests.

## Comandos

```bash
cd app
python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"   # una vez (Python 3.10+)
pytest                       # tests (no llaman a la API)
python -m afilia.web         # http://127.0.0.1:8000
python scripts/demo_web.py   # http://127.0.0.1:8001 con IA simulada
```

GitHub Actions corre los tests en cada push y pull request (Python 3.10 y 3.12).
