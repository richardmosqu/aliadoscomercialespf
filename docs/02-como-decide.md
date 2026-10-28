# Cómo decide el evaluador

El motor (`app/afilia/motor.py`) es determinista: con los mismos datos y respuestas da siempre el mismo resultado, y cada motivo dice qué respuesta lo produjo. La IA, si está activada, solo sugiere; nunca cambia el resultado por su cuenta.

## Principios

1. **Se evalúa lo que el cliente paga, no las palabras.** La pregunta central de cada actividad es "¿qué recibe el cliente cuando paga?".
2. **Una palabra clave nunca rechaza sola.** Solo activa preguntas. El analista puede quitar una actividad mal detectada o agregar una que falte.
3. **Sin preguntas clave no hay conclusión.** Mientras falten, Ali dice "Por aclarar" y muestra hacia dónde va. Un "no aplica" confirmado por las respuestas, con la actividad aclarada, cierra el caso sin preguntas generales (no pueden cambiarlo).
4. **Primero buscar cómo afiliar.** Todo resultado distinto de "Aplica" trae alternativas concretas.
5. **Las alternativas cambian el negocio real, nunca la descripción.** Disfrazar una actividad no permitida es causa de cierre.
6. **Explicable.** Cada motivo cita la respuesta y la política (pública o propuesta).
7. **La decisión final es humana.**

## Paso a paso

1. **Detección.** Se buscan las palabras clave de cada actividad en el nombre, la razón social, la actividad declarada y la descripción (sin tildes ni mayúsculas, palabra completa: "bar" no encuentra "barbería").
2. **Preguntas visibles.** Primero las de las actividades activas, luego las generales. Una pregunta con `mostrar_si` aparece solo si se dio esa respuesta; las respuestas de preguntas ocultas no cuentan.
3. **Activaciones.** Una respuesta puede activar otra actividad (y sus preguntas). Se repite hasta que no cambie nada.
4. **Nivel de cada actividad.** Descartada si alguna respuesta la descarta. Si no, el nivel más alto de sus respuestas; si nadie la aclaró, su nivel base. Un `tope` lo limita.
5. **Nivel de la evaluación.** El más alto entre las actividades, las preguntas generales y las reglas de combinación. Sin nada que lo suba: Aplica.
6. **Lo que hay que hacer.** Se juntan condiciones, documentos (en el orden del catálogo) y alternativas. Si va a comité, se agrega el expediente (formulario en línea y evaluación de debida diligencia). Los servicios que pasan por comité (recurrencia, Wix) no frenan la afiliación.
7. **Mensaje y expediente.** El mensaje para el comercio pide documentos y ofrece alternativas sin explicar criterios internos. El resumen del expediente lleva todo el razonamiento para el comité.

## Ejemplo: el tour de bares

| Paso | Qué pasa |
| --- | --- |
| Descripción: "Venta de licor. Tour por bares con licor incluido" | Se activan **Bebidas alcohólicas** (licor, bares) y **Experiencias** (tour). Ali: Por aclarar (si se confirma: no aplica) |
| ¿Qué recibe el cliente? → una experiencia o tour | Alcohol pasa a "Aplica con condiciones": es turismo, no venta de licor. Aparecen las preguntas de seguimiento |
| ¿Qué parte del precio son bebidas? → menos de la mitad | Sin cambio (con "la mitad o más" iría a comité) |
| ¿Quién vende las bebidas? → los bares aliados con su licencia | Condición: cobrar con PagueloFacil solo el servicio. Documento: acuerdo con los locales |
| ¿Verifica la mayoría de edad? → sí | Sin cambio (con "no", se agrega la verificación como condición) |
| Preguntas generales (persona jurídica, redes, entrega en la semana, listas limpias, enlace de pago) | Documentos del negocio |
| **Resultado** | **Aplica con condiciones**, con el camino "Cobrar solo el servicio" y el mensaje listo para enviar |

Este caso está en `casos/casos-de-referencia.yaml` y se prueba en cada cambio.
