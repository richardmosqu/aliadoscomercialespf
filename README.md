# Ali · Evaluador de aliados comerciales · Cumplimiento · PagueloFacil

Herramienta interna para decidir si un comercio puede afiliarse a PagueloFacil **sin quedarse en "¿aplica o no?"**. Se usa como una conversación con **Ali**, una burbuja de PagueloFacil: el analista escribe qué vende el comercio, Ali pregunta una cosa a la vez (las respuestas se tocan como burbujas) y al final muestra el resultado y, sobre todo, **los caminos para poder afiliarlo** cuando no aplica tal como está planteado.

## El problema

El filtro de afiliación es manual y con poca información. Un comercio llena el formulario y, según cómo describe su negocio, el caso queda en duda ("¿rechazamos?", "¿le preguntamos a los jefes?") o se rechaza por una palabra. Caso real: un comercio declaró **"venta de licor"** y se rechazó; después de investigar, vendía **tours por bares**: el cliente pagaba una experiencia, no botellas.

## Cómo se usa

1. Escribe en una frase qué vende el comercio (o toca un ejemplo).
2. Ali muestra lo que detectó ("Bebidas alcohólicas", "Experiencias") y pregunta: "Cuando el cliente paga, ¿qué recibe?". Las respuestas son burbujas: 🍾 Botellas o delivery · 🎟️ Una experiencia o tour · 🍽️ Consumo en su local · 🙅 Nada con alcohol.
3. Cada respuesta tiene su reacción ("👍 El cliente paga por una experiencia: es turismo, no venta de licor") y la burbuja cambia de color según hacia dónde va el caso. ¿No sabes una respuesta? "🤷 No sé, se lo pregunto" la guarda para el comercio. Tocar una respuesta anterior la cambia.
4. Al final: el resultado en grande, las condiciones y los **caminos para afiliar** en burbujas, y cuatro botones: ✉️ Mensaje (listo para copiar al comercio), 📄 Documentos, 🧾 Resumen (para el comité) y 💾 Guardar.

## Cómo lo resuelve

1. **Se evalúa lo que el cliente paga, no las palabras.** "Licor" no rechaza: abre la pregunta "¿qué recibe el cliente cuando paga?". Con "una experiencia o tour", el caso pasa a turismo y aplica con condiciones.
2. **Preguntas que cambian según las respuestas.** Cada respuesta puede descartar una actividad (falso positivo), activar otra (el tour activa "experiencias") o abrir preguntas nuevas (¿quién vende las bebidas?, ¿qué parte del precio son bebidas?).
3. **Resultado con motivos.** Aplica · Aplica con condiciones · Requiere comité · No aplica por ahora. Mientras falten preguntas clave, el resultado dice **"Por aclarar"**: nunca concluye por una palabra. Un "no" confirmado (por ejemplo, vapes) se cierra sin más preguntas.
4. **Siempre busca cómo afiliar.** Todo resultado distinto de "Aplica" trae alternativas: cobrar solo el servicio, afiliar solo la línea permitida, empezar con enlace de pago mientras el comité evalúa, cuenta personal, límites iniciales, reserva, etc. Las alternativas cambian cómo opera el negocio de verdad, nunca solo cómo se describe.
5. **Listo para actuar.** Documentos a pedir, borrador del mensaje para el comercio (sin criterios internos), resumen del expediente para el comité y la decisión final guardada en el historial del equipo.
6. **IA opcional.** Con la clave de la API de Claude, Ali lee cada mensaje con IA: dice lo que entiende ("✨ Lo que entiendo: tours guiados por bares"), marca con ✨ la respuesta que respalda el texto (con la evidencia) y suma preguntas para el comercio. La IA no decide: el analista toca cada respuesta y el resultado lo calcula la política.

## La política es editable

Lo que sabe el evaluador vive en archivos YAML en [`politica/`](politica/README.md): actividades, palabras clave, preguntas, efectos de cada respuesta, alternativas, documentos y mensajes. Cumplimiento la ajusta sin tocar código; la app valida cada cambio y los tests lo prueban contra los [casos de referencia](casos/casos-de-referencia.yaml) (incluido el del tour de bares).

**Estado de la política: propuesta.** La lista de actividades no permitidas sale de lo público de los términos y condiciones (alcohol y tabaco, vapeadores, adultos, apuestas, armas, cripto como giro, tarjetas de juego, países sancionados). El resto (bares, multinivel, réplicas, péptidos, rifas, etc.) es una propuesta basada en prácticas de la industria, marcada como `propuesta` / "por confirmar". Las decisiones pendientes para Cumplimiento están en [`docs/03-preguntas-para-cumplimiento.md`](docs/03-preguntas-para-cumplimiento.md).

## Cómo correrlo

Requiere Python 3.10 o superior.

```bash
cd app
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                      # tests (no llaman a la API)
python -m afilia.web        # http://127.0.0.1:8000
python scripts/demo_web.py  # http://127.0.0.1:8001 con la IA simulada, para conocer la interfaz
```

Para la lectura con IA, crea `app/.env` a partir de `app/.env.example` con `ANTHROPIC_API_KEY`. Sin clave, todo funciona igual sin la IA.

Publicación en Render: [`render.yaml`](render.yaml) deja el servicio listo; las claves (`AFILIA_CLAVE_ACCESO`, `ANTHROPIC_API_KEY`) se escriben en el panel de Render. La app no arranca abierta a la red sin clave de acceso.

## Mapa del repositorio

```
politica/          ← lo que sabe el evaluador (YAML que edita Cumplimiento) + guía
casos/             ← casos de referencia: decisiones que el evaluador debe seguir dando igual
docs/              ← propuesta, cómo decide, preguntas para Cumplimiento
app/afilia/        ← motor de decisión, carga de la política, IA opcional, historial y app web (Ali)
app/tests/         ← tests (política, motor, casos, IA con cliente falso, web)
app/scripts/       ← demo con IA simulada
```

## Datos y seguridad

- Solo correos del dominio de la empresa con la clave de acceso (con `AFILIA_CLAVE_ACCESO`); en local, sin clave y solo en `127.0.0.1`.
- El historial (SQLite en `app/datos/`, fuera de git) guarda los datos del negocio, las respuestas, la recomendación y la decisión final. Retención y acceso: por definir con Legal (Ley 81 de 2019).
- Con la IA activada, lo que el analista escribe del comercio se envía a la API de Claude. No escribir cédulas, datos personales, datos de tarjetas ni contraseñas.

## Relación con otros proyectos

- [CS Ai](https://github.com/richardmosqu/Paguelofacil-customer-ai-agent): copiloto de Customer Service. Su base de conocimiento (afiliación, actividades prohibidas, comité, límites) es la fuente de los datos de PagueloFacil que usa esta política. Mismo stack y misma identidad visual.
