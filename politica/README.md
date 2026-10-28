# Política del evaluador: guía para editarla

Estos archivos son todo lo que sabe el evaluador. Se editan sin tocar código: al guardar, la app valida el cambio (si hay un error, sigue usando la versión anterior y lo muestra arriba en la pantalla) y los tests lo prueban contra los casos de referencia.

| Archivo | Qué contiene |
| --- | --- |
| `categorias.yaml` | Actividades (alcohol, rifas, multinivel…): nivel, por qué, palabras clave y preguntas de aclaración |
| `preguntas-generales.yaml` | Preguntas para todo comercio (perfil, canal, entrega, listas, montos, servicios) y reglas de combinación |
| `alternativas.yaml` | Caminos para poder afiliar |
| `documentos.yaml` | Documentos que se pueden pedir |
| `mensajes.yaml` | Borrador del mensaje al comercio y próximos pasos del analista |

## Niveles

| Nivel | Se muestra como | Significa |
| --- | --- | --- |
| `aplica` | Aplica | Se afilia con el proceso estándar |
| `condicionado` | Aplica con condiciones | Se afilia si cumple condiciones o entrega documentos |
| `comite` | Requiere comité | Lo decide el comité, con el expediente completo |
| `no_aplica` | No aplica por ahora | Tal como está planteado no se procesa; se ofrecen alternativas |

El resultado de la evaluación es el nivel **más alto** de todo lo que se respondió. Mientras falten preguntas `clave`, se muestra "Por aclarar".

## Cómo decide una actividad

1. Una **palabra clave** en la descripción activa la actividad. No decide nada: solo hace aparecer sus preguntas.
2. La primera pregunta `clave` aclara **qué recibe el cliente cuando paga**. Cada opción fija el nivel (`nivel` + `motivo`) o descarta la actividad (`descarta: true`, para los falsos positivos como "alcohol en gel").
3. Las siguientes preguntas afinan (`mostrar_si` las muestra solo con ciertas respuestas). El nivel de la actividad es el más alto de sus respuestas.
4. `tope` baja el nivel de la actividad: sirve para "afiliar solo la línea permitida" (un minisúper que también vende licor).
5. `activa` suma otra actividad: el tour de bares activa "Experiencias, tours y eventos" y aparecen sus preguntas.
6. Si nadie aclara la actividad, queda con el `nivel` de la categoría.

Ejemplo (resumido de `categorias.yaml`):

```yaml
- id: alcohol
  nombre: Bebidas alcohólicas
  nivel: no_aplica            # si se confirma y no se aclara
  origen: publica             # está en los términos y condiciones
  palabras_clave: [licor*, cerveza*, bar, bares]   # licor* = licor, licores, licorería
  preguntas:
    - id: alcohol_que_paga
      clave: true
      texto: Cuando el cliente paga con PagueloFacil, ¿qué recibe exactamente?
      opciones:
        - id: venta_directa
          texto: Bebidas alcohólicas para llevar o a domicilio
          nivel: no_aplica
          motivo: La venta directa de bebidas alcohólicas está en la lista de actividades no permitidas.
        - id: experiencia
          texto: Una experiencia o servicio (tour, cata guiada, clase de coctelería) que incluye bebidas
          nivel: condicionado
          motivo: El cliente paga por una experiencia; la actividad es turismo, no venta de licor.
          activa: [experiencias_eventos]
        - id: sin_alcohol
          texto: Nada con alcohol (alcohol en gel, cristalería…)
          descarta: true
          motivo: No vende bebidas alcohólicas; la palabra clave era un falso positivo.
```

## Campos de una pregunta

| Campo | Efecto |
| --- | --- |
| `texto` | La pregunta completa (va al resumen del comité) |
| `corta` | Cómo la hace Ali en la conversación, si `texto` es largo (máx. 70 caracteres) |
| `clave: true` | Define el resultado: mientras falte, el caso queda "Por aclarar" |
| `ayuda` | Lo que se muestra con "💡 ¿Por qué lo pregunto?" |
| `tipo: multiple` | Se pueden elegir varias respuestas |
| `mostrar_si` | La pregunta aparece solo con ciertas respuestas |

## Campos de una opción

| Campo | Efecto |
| --- | --- |
| `texto` | La respuesta completa (va al resumen del comité) |
| `corto` | La etiqueta de la burbuja, con emoji si ayuda (obligatoria, máx. 40 caracteres) |
| `nivel` + `motivo` | Nivel de la actividad con esa respuesta (en preguntas generales: de toda la evaluación) |
| `tope` + `motivo` | Nivel máximo de la actividad |
| `descarta: true` + `motivo` | La actividad no aplica (falso positivo) |
| `activa: [ids]` | Suma otras actividades |
| `condiciones: [textos]` | Condiciones para afiliar (para el analista; no van al comercio) |
| `documentos: [ids]` | Documentos a pedir (de `documentos.yaml`) |
| `alternativas: [ids]` | Caminos para afiliar (de `alternativas.yaml`) |
| `servicio_comite: texto` | Un servicio de PagueloFacil que pasa por comité sin frenar la afiliación (recurrencia, Wix) |

## Reglas para editar

- **Una palabra clave nunca rechaza sola.** Toda actividad restringida necesita su pregunta `clave` de "¿qué vende?" y una opción para el falso positivo.
- **No inventar datos de PagueloFacil** (comisiones, plazos, límites, requisitos). Lo que no esté confirmado se marca `origen: propuesta` o `por_confirmar: true`, y se anota en `docs/03-preguntas-para-cumplimiento.md`.
- **Las alternativas cambian el negocio real, no la descripción.** Nunca proponer disfrazar una actividad (transaction laundering).
- **Comillas en valores dudosos.** YAML lee `no`, `sí`, `+18` o `1:1` como otra cosa: escribir `"no"`, `"+18"`, `"1:1"`. La app avisa si falta.
- **"Afiliar solo lo permitido" antes del "no".** Las actividades no permitidas tienen una pregunta `*_excluir` con `clave: true`: Ali la hace antes de concluir.
- Los `id` no se cambian una vez en uso: el historial y los casos de referencia los nombran. Para retirar una opción, se borra y se actualizan los casos.
- Al cambiar algo, actualizar `version` en `categorias.yaml`. Cuando Cumplimiento apruebe la política completa, `estado: aprobado`.

## Probar un cambio

```bash
cd app && source .venv/bin/activate && pytest
```

Si un caso de referencia deja de dar la decisión esperada, el test lo dice. Cuando el equipo resuelva un caso difícil, se agrega a `casos/casos-de-referencia.yaml` (anonimizado) para que el evaluador lo recuerde.
