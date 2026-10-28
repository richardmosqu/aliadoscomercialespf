# Preguntas para Cumplimiento (y Legal) antes del piloto

La política del evaluador está en estado **propuesta**. Lo que sale de los términos y condiciones públicos está marcado `pública`; todo lo demás es una propuesta basada en prácticas de la industria. Estas son las decisiones que hacen falta para pasarla a `aprobado`. Al responder cada una, se ajusta el YAML indicado y se agrega un caso de referencia si aplica.

## Lista de actividades

| # | Pregunta | Propuesta actual | Dónde se cambia |
| --- | --- | --- | --- |
| 1 | ¿Cuál es la lista completa y vigente de actividades no permitidas? (la pública es parcial) | Alcohol y tabaco, vapeadores, adultos, apuestas, armas, cripto como giro, tarjetas de juego, países sancionados por OFAC | `categorias.yaml` |
| 2 | ¿La restricción de alcohol cubre a bares y discotecas (consumo en el local) o solo la venta para llevar o en línea? | Consumo en el local: aplica con condiciones; si las bebidas son la mitad o más de lo que se cobra, comité | `alcohol_que_paga`, `alcohol_peso` |
| 3 | Experiencias con alcohol (tours, catas): ¿el umbral de "la mitad o más del precio" para ir a comité es razonable? | Sí | `alcohol_peso` |
| 4 | ¿Se acepta afiliar solo la línea permitida de un comercio mixto, con carta compromiso de exclusión? ¿Para qué actividades? | Sí, con tope "aplica con condiciones" si lo permitido es lo principal y "comité" si no | preguntas `*_excluir` |
| 5 | Productos de bienestar sexual (sex shop) y entretenimiento adulto en un local | Comité | `adultos_que_vende` |
| 6 | Armas blancas o de defensa personal, polígonos de tiro, pirotecnia, paintball y airsoft | Comité; paintball y airsoft como actividad recreativa: con condiciones | `armas_que_vende` |
| 7 | Recargas de telefonía y venta de cuentas o ítems de juegos | Comité | `tarjetas_que_vende` |
| 8 | Réplicas y falsificaciones, reventa de cuentas de streaming, multinivel de reclutamiento | No aplica (propuesta) | `replicas`, `multinivel` |
| 9 | Esoterismo, sitios de citas, reventa de boletos, colectas para personas, donaciones políticas | Comité | varias |
| 10 | Productos de salud sin registro sanitario (péptidos, hormonas, productos para bajar de peso), cannabis y CBD | Comité; sustancias controladas sin receta: no aplica | `salud_que_vende` |
| 11 | Joyería, metales preciosos, bienes raíces y vehículos (sujetos obligados no financieros) | Con condiciones y debida diligencia reforzada; compra de oro como inversión: comité | `alto_valor` |
| 12 | Marketplaces y cobros a nombre de terceros | Comité; lo ideal es que cada vendedor tenga su cuenta | `facilitador_terceros` |

## Requisitos y documentos

| # | Pregunta | Dónde se cambia |
| --- | --- | --- |
| 13 | Lista oficial de documentos por tipo de persona (natural, natural con Aviso de Operación, jurídica) | `g_tipo` en `preguntas-generales.yaml` |
| 14 | Nombre exacto de cada permiso y la entidad que lo emite (licencia de licor, registro de turismo, farmacia, Junta de Control de Juegos, reguladores financieros) | `documentos.yaml` (`por_confirmar`) |
| 15 | ¿Cuándo se aplica la reserva de 5 a 10% a un comercio nuevo? ¿Se puede ofrecer como alternativa para entregas futuras o historial de contracargos? | `alternativas.yaml` (`reserva_riesgo`) |
| 16 | Entregas a más de 30 días (preventas, eventos, viajes): ¿con condiciones o comité? ¿A partir de qué monto? | `g_entrega` |
| 17 | Montos: ¿a partir de qué ticket o volumen el caso necesita debida diligencia reforzada o comité? | `g_ticket`, `g_volumen` |
| 18 | ¿Qué herramienta de verificación en listas (OFAC, ONU, PEP) se usa y quién la corre? | `g_listas` |

## Referencias legales a validar con Legal

- Vapeadores y cigarrillos electrónicos: Ley 315 de 2022.
- Cannabis medicinal: Ley 242 de 2021.
- Prevención de blanqueo de capitales (sujetos obligados no financieros): Ley 23 de 2015.
- Protección de datos personales (historial de evaluaciones, uso de la IA): Ley 81 de 2019.

## Operación

| # | Pregunta |
| --- | --- |
| 19 | ¿Quién aprueba los cambios a la política y quién los edita? (propuesta: Cumplimiento aprueba; un responsable edita los YAML y corre los tests) |
| 20 | ¿Cuánto tiempo se guardan las evaluaciones y quién puede verlas? (hoy: todo el equipo ve todo el historial) |
| 21 | ¿Se activa el análisis con IA? Envía a la API de Claude la descripción del negocio y el texto que pegue el analista (sin datos personales ni de tarjetas). Legal debe revisar el proveedor, como en CS Ai |
| 22 | ¿Dónde se publica la app? (Render como CS Ai, o un servidor interno) e inicio de sesión con Microsoft 365 |
