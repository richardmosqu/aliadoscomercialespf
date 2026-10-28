# Propuesta: evaluador de aliados comerciales para Cumplimiento

## Problema

- El filtro de afiliación es manual y depende de cómo el comercio describe su negocio en el formulario.
- Los casos ambiguos se quedan a medias ("¿aplica o no?", "¿rechazamos?", "¿le preguntamos a los jefes?"), o se rechazan por una palabra.
- Ejemplo real: un comercio declaró "venta de licor" y se rechazó por estar en la lista de actividades no permitidas. Vendía tours por bares: el cliente pagaba la experiencia, y las bebidas las servían los bares.
- Cada rechazo evitable es un comercio que se pierde; cada caso escalado sin información le quita tiempo a la jefatura y al comité.

## Objetivo

Que cada analista de Cumplimiento llegue a una recomendación clara, explicable y consistente, y que **la respuesta por defecto sea buscar cómo afiliar**, no decir que no.

## Cómo funciona

Una conversación con **Ali**, una burbuja de PagueloFacil, pensada para que cualquiera la use sin capacitación:

1. El analista escribe en una frase qué vende el comercio.
2. Ali muestra las actividades que detectó (palabras clave de la política) y aclara con preguntas, una a la vez. Ninguna palabra rechaza por sí sola.
3. Las respuestas son burbujas que se tocan. Cada una puede abrir, cerrar o descartar preguntas, y Ali reacciona explicando lo que cambió. "No sé" guarda la pregunta para el comercio.
4. Resultado en grande: Aplica / Aplica con condiciones / Requiere comité / No aplica por ahora, con las condiciones y los **caminos para afiliar** en burbujas.
5. Cuatro botones: mensaje para el comercio, documentos (con casillas), resumen para el comité y guardar con la decisión final. El historial queda para el equipo.
6. Opcional: la IA lee cada mensaje, dice lo que entiende, marca con ✨ la respuesta que respalda el texto y suma preguntas para el comercio. El analista decide.

## Qué no hace

- No decide: recomienda. La decisión es del analista, la jefatura y el comité.
- No inventa política: todo sale de los YAML de `politica/`. Lo que no está confirmado se ve como "propuesta" o "por confirmar".
- No se conecta todavía a los sistemas de PagueloFacil (panel, core): es una herramienta aparte.

## Fases

| Fase | Qué | Resultado |
| --- | --- | --- |
| 1. Prototipo (esta entrega) | Evaluador con preguntas, política propuesta, casos de referencia, historial, IA opcional | App funcionando en local o en Render |
| 2. Validación con Cumplimiento | Revisar `docs/03-preguntas-para-cumplimiento.md`, ajustar la política, cargar 20 a 30 casos reales anonimizados como casos de referencia, piloto con 2 o 3 analistas | Política `aprobado` y métricas del piloto |
| 3. Integración | Inicio de sesión con Microsoft 365, formulario que el comercio responde directamente, expediente enlazado con el panel o el core, reporte mensual | Flujo de afiliación con menos idas y vueltas |

## Métricas para el piloto

- Tiempo promedio por evaluación (antes y después).
- Porcentaje de casos que se escalan a la jefatura o al comité.
- Porcentaje de rechazos que se revierten después de investigar (como el tour de bares).
- Coincidencia entre la recomendación del evaluador y la decisión final (historial).
- Comercios afiliados gracias a una alternativa.
