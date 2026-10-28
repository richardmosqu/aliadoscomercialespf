// Ali · conversación con una burbuja de PagueloFacil (sin dependencias).
// La conversación se dibuja completa desde el estado en cada cambio; solo lo nuevo entra con animación.
// Todo texto que viene del comercio, de la política o de la IA se inserta con textContent (nunca como HTML).
"use strict";

(() => {
  const $ = (sel) => document.querySelector(sel);
  const BORRADOR = "afilia.conversacion.v1";
  const EMOJI = { aplica: "✅", condicionado: "👍", comite: "🧑‍⚖️", no_aplica: "✋", descartada: "👌" };
  const FRASES = {
    aplica: "¡Listo! Este comercio se puede afiliar. 🎉",
    condicionado: "Se puede afiliar, cumpliendo esto:",
    comite: "Este lo decide el comité. Mientras tanto, hay caminos:",
    no_aplica: "Así como está, no. Pero mira estos caminos:",
  };
  const SIN_CAMINO = "Así como está, no. Para esta actividad no hay un camino con PagueloFacil.";
  const EJEMPLOS = [
    "🍸 Tours por bares con licor incluido",
    "💨 Tienda de vapes y líquidos",
    "🎟️ Rifa benéfica de una fundación",
    "🛍️ Marketplace de artesanos",
  ];

  const nuevoCaso = () => ({
    mensajes: [], nombre: "", extra: { razon_social: "", actividad: "", web: "" },
    respuestas: {}, agregadas: [], quitadas: [], saltadas: [], orden: [],
    id: null, decision: "pendiente", notas: "",
  });
  let caso = nuevoCaso();
  const sesion = {
    resultado: null, politica: null, servidor: null,
    editando: null, seleccion: null, afinar: false, ayuda: null,
    abiertos: new Set(), docsListos: new Set(),
    ia: { estado: "apagada", datos: null, error: "" },
  };
  let vistos = new Set();

  // ───────────── utilidades ─────────────

  function el(tag, attrs = {}, ...hijos) {
    const nodo = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") nodo.className = v;
      else if (k === "text") nodo.textContent = v;
      else if (k === "style") nodo.style.cssText = v;
      else if (k.startsWith("on")) nodo.addEventListener(k.slice(2), v);
      else nodo.setAttribute(k, v === true ? "" : v);
    }
    for (const h of hijos.flat(Infinity)) if (h !== null && h !== undefined && h !== false) nodo.append(h);
    return nodo;
  }
  const icono = (d) => {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    svg.append(path);
    return svg;
  };
  const miniOrbe = () => el("div", { class: "orbe mini-orbe", "aria-hidden": "true" },
    el("span", { class: "nucleo" }), el("span", { class: "brillo" }));
  const normal = (t) => (t || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  // Marca un elemento como nuevo (entra con animación) solo la primera vez que aparece.
  function nuevo(nodo, clave, i = 0) {
    if (!vistos.has(clave)) {
      vistos.add(clave);
      nodo.classList.add("entra", "nueva");
      nodo.style.setProperty("--i", i);
    }
    return nodo;
  }

  async function api(ruta, opciones = {}) {
    const r = await fetch(ruta, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...opciones });
    if (r.status === 401) { mostrarAcceso(); throw new Error("Inicia sesión para continuar."); }
    const datos = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof datos.detail === "string" ? datos.detail : `No se pudo completar (error ${r.status}).`);
    return datos;
  }

  let avisoTimer;
  function aviso(texto, ms = 2200) {
    const nodo = $("#aviso");
    nodo.textContent = texto;
    nodo.hidden = false;
    clearTimeout(avisoTimer);
    avisoTimer = setTimeout(() => { nodo.hidden = true; }, ms);
  }

  async function copiar(texto, mensaje = "Copiado ✓") {
    try {
      await navigator.clipboard.writeText(texto);
    } catch {
      const area = el("textarea", { style: "position:fixed;opacity:0" });
      area.value = texto;
      document.body.append(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    aviso(mensaje);
  }

  function guardarBorrador() {
    try { localStorage.setItem(BORRADOR, JSON.stringify(caso)); } catch { /* sin almacenamiento */ }
  }
  function cargarBorrador() {
    try {
      const datos = JSON.parse(localStorage.getItem(BORRADOR) || "null");
      if (datos && Array.isArray(datos.mensajes)) caso = { ...nuevoCaso(), ...datos };
    } catch { /* se empieza de cero */ }
  }

  // ───────────── acceso ─────────────

  function mostrarAcceso() {
    $("#app").hidden = true;
    $("#acceso").hidden = false;
    $("#correo").focus();
  }

  $("#form-acceso").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const error = $("#acceso-error");
    error.hidden = true;
    try {
      await api("/api/sesion", { method: "POST", body: JSON.stringify({ correo: $("#correo").value, clave: $("#clave-acceso").value }) });
      $("#clave-acceso").value = "";
      await abrirApp(await api("/api/estado"));
    } catch (e) {
      error.textContent = e.message;
      error.hidden = false;
    }
  });

  $("#btn-salir").addEventListener("click", async () => {
    await api("/api/sesion", { method: "DELETE" }).catch(() => {});
    location.reload();
  });

  async function iniciar() {
    try {
      const st = await api("/api/estado");
      if (st.acceso_requerido && !st.usuario) { mostrarAcceso(); return; }
      await abrirApp(st);
    } catch (e) {
      document.body.append(el("p", { class: "aviso", text: `No pude conectar con Ali: ${e.message}` }));
    }
  }

  async function abrirApp(st) {
    sesion.servidor = st;
    $("#acceso").hidden = true;
    $("#app").hidden = false;
    $("#btn-salir").hidden = !st.acceso_requerido;
    if (st.politica.error) aviso(`La política editada tiene un error y se sigue usando la anterior: ${st.politica.error}`, 9000);
    sesion.politica = await api("/api/politica");
    cargarBorrador();
    await evaluar();
    if (!caso.mensajes.length) $("#entrada").focus();
  }

  // ───────────── evaluación ─────────────

  const comercio = () => ({ ...caso.extra, nombre: caso.nombre, descripcion: caso.mensajes.join("\n") });
  let pedido = 0;

  async function evaluar() {
    const n = ++pedido;
    const orbe = $("#orbe");
    orbe.classList.add("pensando");
    try {
      const r = await api("/api/evaluar", {
        method: "POST",
        body: JSON.stringify({ comercio: comercio(), respuestas: caso.respuestas, agregadas: caso.agregadas, quitadas: caso.quitadas }),
      });
      if (n !== pedido) return;
      const antes = sesion.resultado;
      sesion.resultado = r;
      pintar();
      guardarBorrador();
      const listo = r.estado === "completo" && !preguntaActual(r);
      if (listo && (!antes || antes.estado !== "completo" || antes.nivel !== r.nivel) && ["aplica", "condicionado"].includes(r.nivel)) {
        orbe.classList.remove("celebra");
        void orbe.offsetWidth;
        orbe.classList.add("celebra");
      }
    } catch (e) {
      if (n === pedido) aviso(e.message, 5000);
    } finally {
      if (n === pedido) setTimeout(() => orbe.classList.remove("pensando"), 350);
    }
  }

  const respondida = (p) => (p.tipo === "multiple" ? Boolean(p.respuesta && p.respuesta.length) : Boolean(p.respuesta));
  const elegidas = (p) => (p.tipo === "multiple" ? (p.respuesta || []) : (p.respuesta ? [p.respuesta] : []));
  const etiquetaRespuesta = (p) => p.opciones.filter((o) => elegidas(p).includes(o.id)).map((o) => o.corto).join(" · ");

  function preguntaActual(r) {
    if (sesion.editando) return r.preguntas.find((p) => p.id === sesion.editando) || null;
    const pendientes = r.preguntas.filter((p) => !respondida(p) && !caso.saltadas.includes(p.id));
    return pendientes.find((p) => p.clave) || (sesion.afinar ? pendientes[0] : null) || null;
  }

  function ordenVisible(r) {
    const visibles = new Map(r.preguntas.map((p) => [p.id, p]));
    const ids = caso.orden.filter((id) => visibles.has(id) && (respondida(visibles.get(id)) || caso.saltadas.includes(id)));
    for (const p of r.preguntas) if (respondida(p) && !ids.includes(p.id)) ids.push(p.id);
    return ids.filter((id) => id !== sesion.editando);
  }

  const opcionales = (r) => r.preguntas.filter((p) => !p.clave && !respondida(p) && !caso.saltadas.includes(p.id));
  const saltadasClave = (r) => r.preguntas.filter((p) => p.clave && !respondida(p) && caso.saltadas.includes(p.id));

  // ───────────── respuestas ─────────────

  function registrar(id) {
    caso.saltadas = caso.saltadas.filter((x) => x !== id);
    if (!caso.orden.includes(id)) caso.orden.push(id);
  }

  function elegir(p, oid) {
    if (p.tipo === "multiple") {
      const sel = sesion.seleccion;
      if (sel.has(oid)) sel.delete(oid); else sel.add(oid);
      pintar();
      return;
    }
    caso.respuestas[p.id] = oid;
    registrar(p.id);
    sesion.editando = null;
    sesion.ayuda = null;
    evaluar();
  }

  function confirmarMultiple(p) {
    if (!sesion.seleccion.size) return;
    caso.respuestas[p.id] = [...sesion.seleccion];
    registrar(p.id);
    sesion.seleccion = null;
    sesion.editando = null;
    evaluar();
  }

  function saltar(p) {
    delete caso.respuestas[p.id];
    if (!caso.saltadas.includes(p.id)) caso.saltadas.push(p.id);
    if (!caso.orden.includes(p.id)) caso.orden.push(p.id);
    sesion.editando = null;
    sesion.seleccion = null;
    evaluar();
  }

  function editar(id) {
    sesion.editando = id;
    sesion.seleccion = null;
    pintar();
  }

  // ───────────── la conversación ─────────────

  function filaAli(clave, ...contenido) {
    return nuevo(el("div", { class: "fila fila-ali" }, miniOrbe(), el("div", { class: "globo" }, contenido)), clave);
  }

  function filaYo(clave, texto, alEditar) {
    const globo = alEditar
      ? el("button", { type: "button", class: "globo", onclick: alEditar, title: "Cambiar respuesta", "aria-label": `${texto} (cambiar respuesta)` }, texto, el("span", { class: "editar-pista", "aria-hidden": "true", text: "✎" }))
      : el("div", { class: "globo", text: texto });
    return nuevo(el("div", { class: "fila fila-yo" }, globo), clave);
  }

  function pintar() {
    const r = sesion.resultado;
    if (!r) return;
    const enCharla = caso.mensajes.length > 0;
    const actual = enCharla ? preguntaActual(r) : null;
    const completo = enCharla && !actual && r.estado === "completo";
    document.body.dataset.fase = enCharla ? "charla" : "inicio";
    document.body.dataset.nivel = completo ? r.nivel : "reposo";
    $("#entrada").placeholder = enCharla ? "Agrega un detalle del comercio…" : "Escribe qué vende el comercio…";
    pintarPildora(r, enCharla, completo);

    const total = vistos.size;
    const items = [];
    if (!enCharla) {
      items.push(el("p", { class: "saludo" }, "Hola, soy ", el("b", { text: "Ali" }), ". Cuéntame qué vende el comercio y te digo si puede ser aliado."));
      items.push(el("div", { class: "ejemplos" }, EJEMPLOS.map((t, i) => nuevo(el("button", {
        type: "button", class: "opcion", text: t, onclick: () => enviar(t.replace(/^\S+\s/, "")),
      }), `ejemplo-${i}`, i))));
    } else {
      caso.mensajes.forEach((m, i) => {
        items.push(filaYo(`m-${i}`, m));
        items.push(i === 0 ? deteccion(r) : filaAli(`m-${i}-ok`, "Anotado ✍️ Lo sumo al caso."));
      });
      const ia = burbujaIA();
      if (ia) items.push(ia);
      for (const id of ordenVisible(r)) {
        const p = r.preguntas.find((x) => x.id === id);
        const salto = !respondida(p);
        const firma = salto ? "salto" : elegidas(p).join("+");
        items.push(nuevo(el("div", { class: "fila fila-ali" }, el("div", { class: "globo globo-pregunta", text: p.corta })), `q-${id}`));
        items.push(filaYo(`a-${id}-${firma}`, salto ? "🤷 No sé · lo pregunto al comercio" : etiquetaRespuesta(p), () => editar(id)));
        for (const [i, rx] of p.reaccion.entries()) {
          items.push(filaAli(`r-${id}-${firma}-${i}`, `${EMOJI[rx.nivel] || "💬"} ${rx.texto}`));
        }
      }
      items.push(actual ? preguntaViva(actual, r) : resultado(r));
    }
    $("#conversacion").replaceChildren(...items);
    if (vistos.size > total && enCharla) {
      requestAnimationFrame(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" }));
    }
  }

  function pintarPildora(r, enCharla, completo) {
    const pildora = $("#pildora");
    pildora.hidden = !enCharla;
    if (!enCharla) return;
    const claves = r.preguntas.filter((p) => p.clave);
    const hechas = claves.filter(respondida).length;
    pildora.textContent = completo ? r.etiqueta : `Por aclarar · ${hechas}/${claves.length}`;
    pildora.dataset.nivel = completo ? r.nivel : "";
    pildora.classList.toggle("preliminar", !completo);
  }
  $("#pildora").addEventListener("click", () => hojaPorque());

  function deteccion(r) {
    const cats = r.categorias;
    const chips = el("div", { class: "chips" },
      cats.map((c) => el("span", { class: `chip${c.descartada ? " descartada" : ""}`, title: c.por_que },
        el("i", { "data-nivel": c.aclarada || c.descartada ? (c.nivel || "") : "" }),
        c.nombre,
        el("button", {
          type: "button", "aria-label": `Quitar ${c.nombre}`, title: "No corresponde",
          onclick: () => { caso.quitadas = [...new Set([...caso.quitadas, c.id])]; caso.agregadas = caso.agregadas.filter((x) => x !== c.id); evaluar(); },
        }, icono("M6 6l12 12M18 6 6 18")))),
      el("button", { type: "button", class: "chip solo", text: "＋ Agregar", onclick: hojaAgregar }));
    const texto = cats.length
      ? ["Veo señales de esto 👇 Ninguna palabra decide sola: lo aclaramos con unas preguntas rápidas.", chips]
      : ["Nada restringido a la vista 👀 Confirmemos lo básico.", chips];
    return filaAli("deteccion", texto);
  }

  function burbujaIA() {
    const ia = sesion.ia;
    if (ia.estado === "leyendo") {
      return filaAli("ia-leyendo", el("span", { class: "escribiendo", "aria-label": "Leyendo con IA" }, el("span"), el("span"), el("span")), " ✨ Leyendo el caso…");
    }
    if (ia.estado === "error") return filaAli("ia-error", `✨ No pude leer con IA: ${ia.error}`);
    if (ia.estado !== "lista") return null;
    const activas = new Set(sesion.resultado.categorias.map((c) => c.id));
    const nuevas = ia.datos.categorias.filter((c) => !activas.has(c.id) && !caso.quitadas.includes(c.id));
    return filaAli("ia-lista",
      `✨ Lo que entiendo: ${ia.datos.actividad_real}`,
      nuevas.length ? el("div", { class: "chips" }, nuevas.map((c) => el("button", {
        type: "button", class: "chip chip-ia", title: c.razon, text: `＋ ${c.nombre}`,
        onclick: () => { caso.agregadas = [...new Set([...caso.agregadas, c.id])]; evaluar(); },
      }))) : null);
  }

  function preguntaViva(p, r) {
    const multiple = p.tipo === "multiple";
    if (multiple && (!sesion.seleccion || sesion.seleccion.id !== p.id)) {
      sesion.seleccion = new Set(elegidas(p));
      sesion.seleccion.id = p.id;
    }
    const marcadas = multiple ? sesion.seleccion : new Set(elegidas(p));
    const sugerencias = (sesion.ia.estado === "lista" ? sesion.ia.datos.respuestas_sugeridas : []).filter((s) => s.pregunta === p.id);
    const sugeridas = new Set(sugerencias.map((s) => s.opcion));
    const claves = r.preguntas.filter((x) => x.clave);
    const posicion = claves.filter(respondida).length + 1;

    const bloque = el("div", { class: "viva" },
      el("p", { class: "viva-contexto" }, p.bloque, p.clave && !sesion.editando ? el("em", { text: `${Math.min(posicion, claves.length)} de ${claves.length}` }) : null),
      el("h2", { text: p.corta }),
      sesion.ayuda === p.id && p.ayuda ? el("p", { class: "viva-ayuda", text: p.ayuda }) : null,
      sugerencias.length ? el("p", { class: "sugerencia-ia" },
        `✨ La IA sugiere «${p.opciones.find((o) => o.id === sugerencias[0].opcion).corto}»`,
        sugerencias[0].evidencia ? ` porque dice: “${sugerencias[0].evidencia}”` : "") : null,
      el("div", { class: "opciones", role: "group", "aria-label": p.texto },
        p.opciones.map((o, i) => el("button", {
          type: "button", class: `opcion${marcadas.has(o.id) ? " elegida" : ""}${sugeridas.has(o.id) ? " sugerida" : ""}`,
          style: `--i:${i}`, title: o.texto, "aria-pressed": marcadas.has(o.id) ? "true" : "false",
          onclick: () => elegir(p, o.id),
        }, o.corto))),
      multiple ? el("button", {
        type: "button", class: "boton-principal listo", text: "Listo →", disabled: !marcadas.size, onclick: () => confirmarMultiple(p),
      }) : null,
      el("div", { class: "fantasmas" },
        el("button", { type: "button", class: "fantasma", text: "🤷 No sé, se lo pregunto", onclick: () => saltar(p) }),
        p.ayuda && sesion.ayuda !== p.id ? el("button", { type: "button", class: "fantasma", text: "💡 ¿Por qué lo pregunto?", onclick: () => { sesion.ayuda = p.id; pintar(); } }) : null,
        sesion.editando ? el("button", { type: "button", class: "fantasma", text: "Cancelar", onclick: () => { sesion.editando = null; pintar(); } }) : null));
    return nuevo(bloque, `viva-${p.id}-${sesion.editando ? "e" : ""}`);
  }

  function resultado(r) {
    const faltan = saltadasClave(r);
    const preliminar = r.estado !== "completo";
    const partes = [];
    const firma = `${r.nivel}-${r.estado}`;
    partes.push(el("div", { class: "veredicto" },
      el("span", { class: "veredicto-etiqueta", text: preliminar ? "Por aclarar" : r.etiqueta }),
      el("p", { text: preliminar
        ? `Me ${faltan.length === 1 ? "falta 1 dato" : `faltan ${faltan.length} datos`} para decidir. Con lo que sé, va hacia: ${r.etiqueta.toLowerCase()}.`
        : (r.nivel === "no_aplica" && !r.alternativas.length ? SIN_CAMINO : FRASES[r.nivel]) })));

    if (faltan.length) {
      partes.push(el("div", { class: "burbujas" }, faltan.map((p, i) => nuevo(el("button", {
        type: "button", class: "burbuja", onclick: () => editar(p.id), title: "Responder ahora",
      }, `❓ ${p.corta}`), `falta-${p.id}-${firma}`, i))));
    }
    const condiciones = r.condiciones.length ? [
      r.nivel !== "condicionado" || preliminar ? el("p", { class: "grupo-titulo", text: "Condiciones" }) : null,
      el("div", { class: "burbujas" }, r.condiciones.map((c, i) => nuevo(el("div", { class: "burbuja burbuja-condicion", text: c }), `cond-${c}-${firma}`, i))),
    ] : [];
    const caminosLista = r.alternativas.filter((a) => a.id !== "expediente_comite" || r.nivel === "comite");
    const caminos = caminosLista.length ? [
      el("p", { class: "grupo-titulo", text: "Caminos para afiliar" }),
      el("div", { class: "burbujas caminos" }, caminosLista.map((a, i) => {
        const abierto = sesion.abiertos.has(a.id);
        return nuevo(el("button", {
          type: "button", class: `burbuja camino${abierto ? " abierto" : ""}`, "aria-expanded": abierto ? "true" : "false",
          onclick: () => { if (abierto) sesion.abiertos.delete(a.id); else sesion.abiertos.add(a.id); pintar(); },
        }, el("strong", { text: `💡 ${a.titulo}` }),
          abierto ? el("span", { text: a.detalle }) : null,
          abierto && a.por_confirmar ? el("small", { text: "Por confirmar con Cumplimiento" }) : null), `camino-${a.id}`, i);
      })),
    ] : [];
    // Si no aplica o va a comité, primero los caminos; si aplica con condiciones, primero las condiciones.
    if (["comite", "no_aplica"].includes(r.nivel)) partes.push(...caminos, ...condiciones);
    else partes.push(...condiciones, ...caminos);
    if (r.servicios_comite.length) {
      partes.push(el("div", { class: "burbujas" }, r.servicios_comite.map((s, i) => nuevo(el("div", { class: "burbuja burbuja-servicio" },
        `🧑‍⚖️ ${s} pasa por comité · mientras tanto puede cobrar con enlace de pago`), `serv-${s}`, i))));
    }
    const alertas = sesion.ia.estado === "lista" ? sesion.ia.datos.alertas : [];
    if (alertas.length) {
      partes.push(el("div", { class: "burbujas" }, alertas.map((a, i) => nuevo(el("div", { class: "burbuja burbuja-alerta", text: `⚠️ ${a}` }), `alerta-${a}`, i))));
    }

    const preguntasComercio = faltan.length + (sesion.ia.estado === "lista" ? sesion.ia.datos.preguntas_para_el_comercio.length : 0);
    const extra = opcionales(r).length;
    const aFavor = ["aplica", "condicionado"].includes(r.nivel) && !preliminar;
    const acciones = [
      el("button", { type: "button", class: `accion${aFavor ? " principal" : ""}`, text: "✉️ Mensaje", onclick: hojaMensaje }),
      r.documentos.length ? el("button", { type: "button", class: "accion", text: `📄 Documentos · ${r.documentos.length}`, onclick: hojaDocumentos }) : null,
      el("button", { type: "button", class: `accion${r.nivel === "comite" && !preliminar ? " principal" : ""}`, text: "🧾 Resumen", onclick: hojaResumen }),
      el("button", { type: "button", class: "accion", text: caso.id ? "💾 Actualizar" : "💾 Guardar", onclick: hojaGuardar }),
    ].filter(Boolean).map((b, i) => nuevo(b, `accion-${i}-${b.textContent}-${firma}`, i));
    const secundarias = [
      preguntasComercio ? el("button", { type: "button", class: "fantasma", text: `📋 Preguntas para el comercio (${preguntasComercio})`, onclick: hojaPreguntasComercio }) : null,
      el("button", { type: "button", class: "fantasma", text: "🤔 ¿Por qué?", onclick: hojaPorque }),
      extra && r.nivel !== "no_aplica" ? el("button", { type: "button", class: "fantasma", text: `➕ Afinar con ${extra} preguntas más`, onclick: () => { sesion.afinar = true; pintar(); } }) : null,
      el("button", { type: "button", class: "fantasma", text: "✨ Nuevo caso", onclick: pedirNuevo }),
    ];
    partes.push(el("div", { class: "acciones" }, acciones));
    partes.push(el("div", { class: "fantasmas" }, secundarias));
    return nuevo(el("div", { class: "resultado" }, partes), `resultado-${firma}`);
  }

  // ───────────── compositor ─────────────

  const entrada = $("#entrada");
  function ajustarAltura() {
    entrada.style.height = "auto";
    entrada.style.height = `${Math.min(entrada.scrollHeight, 160)}px`;
  }
  entrada.addEventListener("input", ajustarAltura);
  entrada.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); $("#compositor").requestSubmit(); }
  });
  $("#compositor").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const texto = entrada.value.trim();
    if (!texto) return;
    entrada.value = "";
    ajustarAltura();
    enviar(texto);
  });

  async function enviar(texto) {
    caso.mensajes.push(texto);
    await evaluar();
    leerConIA();
  }

  async function leerConIA() {
    if (!sesion.servidor || !sesion.servidor.ia) return;
    sesion.ia = { estado: "leyendo", datos: null, error: "" };
    pintar();
    try {
      const datos = await api("/api/ia/analizar", { method: "POST", body: JSON.stringify({ comercio: comercio(), adicional: "" }) });
      sesion.ia = { estado: "lista", datos, error: "" };
    } catch (e) {
      sesion.ia = { estado: "error", datos: null, error: e.message };
    }
    pintar();
  }

  // ───────────── hojas ─────────────

  let focoAntes = null;
  function abrirHoja(titulo, ...contenido) {
    focoAntes = document.activeElement;
    $("#hoja-titulo").textContent = titulo;
    $("#hoja-cuerpo").replaceChildren(...contenido.flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false));
    $("#hoja").hidden = false;
    $("#hoja-cerrar").focus();
  }
  function cerrarHoja() {
    $("#hoja").hidden = true;
    if (focoAntes && focoAntes.focus) focoAntes.focus();
  }
  $("#hoja-cerrar").addEventListener("click", cerrarHoja);
  $("#hoja").addEventListener("click", (ev) => { if (ev.target.id === "hoja") cerrarHoja(); });
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !$("#hoja").hidden) cerrarHoja(); });

  const CORTAS = { aplica: "Aplica", condicionado: "Con condiciones", comite: "Comité", no_aplica: "No aplica" };
  const etiquetaNivel = (nivel, texto) => el("span", { class: `etiqueta nivel nivel-${nivel || ""}`, text: texto || CORTAS[nivel] || "" });

  function campoNombre(alCambiar) {
    const input = el("input", { value: caso.nombre, maxlength: "200", placeholder: "Ej.: Ruta de Bares PTY" });
    input.addEventListener("input", debounce(async () => { caso.nombre = input.value.trim(); await evaluar(); if (alCambiar) alCambiar(); }, 350));
    return el("label", { class: "campo" }, "Nombre del comercio", input);
  }

  function hojaMensaje() {
    const texto = el("pre", { class: "texto-copiable", text: sesion.resultado.mensaje_comercio });
    abrirHoja("Mensaje al comercio",
      sesion.resultado.estado !== "completo" ? el("p", { class: "ayuda", text: "⚠️ Faltan datos clave: revísalo antes de enviarlo." }) : null,
      el("p", { class: "ayuda", text: "Borrador listo para copiar. No explica criterios internos." }),
      campoNombre(() => { texto.textContent = sesion.resultado.mensaje_comercio; }),
      texto,
      el("button", { type: "button", class: "boton-principal", text: "Copiar mensaje", onclick: () => copiar(sesion.resultado.mensaje_comercio, "Mensaje copiado ✓") }));
  }

  function hojaDocumentos() {
    const docs = sesion.resultado.documentos;
    abrirHoja(`Documentos · ${docs.length}`,
      el("p", { class: "ayuda", text: "Márcalos a medida que llegan." }),
      el("ul", { class: "lista-simple" }, docs.map((d) => {
        const check = el("input", { type: "checkbox", checked: sesion.docsListos.has(d.id) });
        check.addEventListener("change", () => { if (check.checked) sesion.docsListos.add(d.id); else sesion.docsListos.delete(d.id); });
        return el("li", {}, el("label", {}, check, el("span", {}, d.nombre,
          d.por_confirmar ? el("span", { class: "etiqueta etiqueta-propuesta", text: "por confirmar" }) : null,
          d.detalle ? el("small", { text: d.detalle }) : null)));
      })),
      el("button", { type: "button", class: "boton-principal", text: "Copiar lista", onclick: () => copiar(docs.map((d) => `- ${d.nombre}`).join("\n")) }));
  }

  function descargar() {
    const nombre = normal(caso.nombre || "caso").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "caso";
    const url = URL.createObjectURL(new Blob([sesion.resultado.resumen_comite], { type: "text/markdown;charset=utf-8" }));
    const a = el("a", { href: url, download: `aliado-${nombre}.md` });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function hojaResumen() {
    abrirHoja("Resumen para comité",
      el("p", { class: "ayuda", text: "Todo el razonamiento del caso, para el comité o para consultar a la jefatura." }),
      el("pre", { class: "texto-copiable", text: sesion.resultado.resumen_comite }),
      el("div", { class: "acciones" },
        el("button", { type: "button", class: "accion principal", text: "Copiar", onclick: () => copiar(sesion.resultado.resumen_comite, "Resumen copiado ✓") }),
        el("button", { type: "button", class: "accion", text: "Descargar .md", onclick: descargar })));
  }

  function hojaPorque() {
    const r = sesion.resultado;
    if (!r) return;
    const motivos = r.motivos;
    abrirHoja("¿Por qué?",
      motivos.length
        ? el("ul", { class: "lista-simple" }, motivos.map((m) => el("li", {},
          etiquetaNivel(m.nivel),
          ` ${m.origen}`, el("small", { text: m.texto }), m.respuesta ? el("small", { text: `Respuesta: ${m.respuesta}` }) : null)))
        : el("p", { class: "ayuda", text: "Nada lo frena: aplica con el proceso estándar." }),
      r.pasos.length ? [el("p", { class: "grupo-titulo", text: "Próximos pasos" }), el("ol", {}, r.pasos.map((p) => el("li", { text: p })))] : null,
      el("p", { class: "ayuda", text: `Política ${r.politica.version} (${r.politica.estado}). La decisión final es tuya y del comité.` }));
  }

  function hojaPreguntasComercio() {
    const r = sesion.resultado;
    const preguntas = [
      ...saltadasClave(r).map((p) => p.texto),
      ...(sesion.ia.estado === "lista" ? sesion.ia.datos.preguntas_para_el_comercio : []),
    ];
    abrirHoja("Preguntas para el comercio",
      el("p", { class: "ayuda", text: "Cuando responda, vuelve y toca la burbuja para contestar." }),
      el("ul", { class: "lista-simple" }, preguntas.map((t) => el("li", { text: t }))),
      el("button", { type: "button", class: "boton-principal", text: "Copiar preguntas", onclick: () => copiar(preguntas.map((t) => `- ${t}`).join("\n")) }));
  }

  function hojaGuardar() {
    let decision = caso.decision;
    const botones = Object.entries(sesion.servidor.decisiones).map(([id, texto]) => el("button", {
      type: "button", class: `opcion${id === decision ? " elegida" : ""}`, text: texto,
      onclick: (ev) => {
        decision = id;
        for (const b of ev.currentTarget.parentNode.children) b.classList.toggle("elegida", b === ev.currentTarget);
      },
    }));
    const notas = el("textarea", { rows: "3", maxlength: "4000", placeholder: "Qué se decidió y por qué, quién lo aprobó…" });
    notas.value = caso.notas;
    abrirHoja(caso.id ? "Actualizar caso" : "Guardar caso",
      campoNombre(),
      el("div", { class: "campo" }, "Decisión final", el("div", { class: "decisiones" }, botones)),
      el("label", { class: "campo" }, "Notas", notas),
      el("button", {
        type: "button", class: "boton-principal", text: "Guardar",
        onclick: async () => {
          caso.decision = decision;
          caso.notas = notas.value.trim();
          try {
            const r = await api("/api/evaluaciones", { method: "POST", body: JSON.stringify({
              comercio: comercio(), respuestas: caso.respuestas, agregadas: caso.agregadas, quitadas: caso.quitadas,
              id: caso.id, decision: caso.decision, notas: caso.notas,
            }) });
            caso.id = r.id;
            guardarBorrador();
            cerrarHoja();
            pintar();
            aviso("Caso guardado ✓");
          } catch (e) {
            aviso(e.message, 5000);
          }
        },
      }));
  }

  function hojaAgregar() {
    const activas = new Set(sesion.resultado.categorias.map((c) => c.id));
    const disponibles = sesion.politica.categorias.filter((c) => !activas.has(c.id));
    const quitadas = sesion.politica.categorias.filter((c) => caso.quitadas.includes(c.id));
    abrirHoja("Agregar una actividad",
      el("p", { class: "ayuda", text: "Si Ali no la vio en la descripción, agrégala y te hago sus preguntas." }),
      el("div", { class: "decisiones" }, disponibles.map((c) => el("button", {
        type: "button", class: "opcion", text: c.nombre,
        onclick: () => { caso.agregadas = [...new Set([...caso.agregadas, c.id])]; caso.quitadas = caso.quitadas.filter((x) => x !== c.id); cerrarHoja(); evaluar(); },
      }))),
      quitadas.length ? [el("p", { class: "grupo-titulo", text: "Quitaste" }), el("div", { class: "decisiones" }, quitadas.map((c) => el("button", {
        type: "button", class: "opcion", text: `↺ ${c.nombre}`,
        onclick: () => { caso.quitadas = caso.quitadas.filter((x) => x !== c.id); cerrarHoja(); evaluar(); },
      })))] : null);
  }

  function reiniciar() {
    caso = nuevoCaso();
    sesion.editando = null;
    sesion.seleccion = null;
    sesion.afinar = false;
    sesion.ayuda = null;
    sesion.abiertos = new Set();
    sesion.docsListos = new Set();
    sesion.ia = { estado: "apagada", datos: null, error: "" };
    vistos = new Set();
    try { localStorage.removeItem(BORRADOR); } catch { /* sin almacenamiento */ }
    window.scrollTo({ top: 0 });
    evaluar();
    entrada.focus();
  }

  function pedirNuevo() {
    if (!caso.mensajes.length || caso.id) { cerrarHoja(); reiniciar(); return; }
    abrirHoja("¿Empezamos un caso nuevo?",
      el("p", { class: "ayuda", text: "Este caso no está guardado." }),
      el("div", { class: "acciones" },
        el("button", { type: "button", class: "accion principal", text: "Sí, caso nuevo", onclick: () => { cerrarHoja(); reiniciar(); } }),
        el("button", { type: "button", class: "accion", text: "💾 Guardarlo primero", onclick: hojaGuardar }),
        el("button", { type: "button", class: "accion", text: "Seguir aquí", onclick: cerrarHoja })));
  }
  $("#btn-nuevo").addEventListener("click", pedirNuevo);

  async function hojaHistorial() {
    const buscar = el("input", { type: "search", class: "buscar", placeholder: "Buscar por comercio, analista o notas", maxlength: "100" });
    const lista = el("div", { class: "lista-simple" }, el("p", { class: "vacio", text: "Cargando…" }));
    const cargar = async () => {
      try {
        const datos = await api(`/api/evaluaciones?q=${encodeURIComponent(buscar.value)}`);
        lista.replaceChildren(...(datos.evaluaciones.length ? datos.evaluaciones.map((e) => el("button", { type: "button", class: "caso", onclick: () => abrirCaso(e.id) },
          el("span", { class: "punto", "data-nivel": e.nivel }),
          el("div", {}, el("strong", { text: e.comercio }),
            el("small", { text: `${new Date(e.actualizada).toLocaleDateString("es-PA", { day: "2-digit", month: "short" })} · ${datos.etiquetas[e.nivel]} · ${datos.decisiones[e.decision] || e.decision} · ${e.analista}` }))))
          : [el("p", { class: "vacio", text: "Todavía no hay casos guardados." })]));
      } catch (e) {
        lista.replaceChildren(el("p", { class: "vacio", text: e.message }));
      }
    };
    buscar.addEventListener("input", debounce(cargar, 300));
    abrirHoja("Casos guardados", buscar, lista);
    cargar();
  }
  $("#btn-historial").addEventListener("click", hojaHistorial);

  async function abrirCaso(id) {
    try {
      const e = await api(`/api/evaluaciones/${encodeURIComponent(id)}`);
      const c = e.entrada.comercio || {};
      reiniciar();
      caso = {
        ...nuevoCaso(),
        mensajes: [c.actividad, ...(c.descripcion ? c.descripcion.split("\n") : [])].filter(Boolean),
        nombre: c.nombre || "",
        extra: { razon_social: c.razon_social || "", actividad: "", web: c.web || "" },
        respuestas: e.entrada.respuestas || {}, agregadas: e.entrada.agregadas || [], quitadas: e.entrada.quitadas || [],
        id: e.id, decision: e.decision, notas: e.notas,
      };
      cerrarHoja();
      await evaluar();
    } catch (err) {
      aviso(err.message, 5000);
    }
  }

  function hojaPolitica() {
    const pol = sesion.politica;
    const buscar = el("input", { type: "search", class: "buscar", placeholder: "Buscar (ej.: alcohol, rifa, péptidos)", maxlength: "100" });
    const lista = el("div");
    const efecto = (o) => o.nivel ? ({ aplica: "aplica", condicionado: "con condiciones", comite: "comité", no_aplica: "no aplica" })[o.nivel]
      : o.descarta ? "descarta" : o.tope ? "afilia solo lo permitido" : "";
    const pintarLista = () => {
      const f = normal(buscar.value.trim());
      const cats = pol.categorias.filter((c) => !f || normal(JSON.stringify(c)).includes(f));
      lista.replaceChildren(...(cats.length ? cats.map((c) => el("details", { class: "pol", open: Boolean(f) },
        el("summary", {}, c.nombre, " ", etiquetaNivel(c.nivel, c.etiqueta), el("span", { class: `etiqueta etiqueta-${c.origen}`, text: c.origen === "publica" ? "pública" : "propuesta" })),
        el("p", { text: c.por_que }),
        el("p", { class: "pol-palabras", text: `Palabras: ${c.palabras_clave.join(", ")}` }),
        c.preguntas.map((p) => el("div", {}, el("strong", { text: p.corta || p.texto }),
          el("ul", {}, p.opciones.map((o) => el("li", {}, o.corto || o.texto, efecto(o) ? ` → ${efecto(o)}` : "", o.motivo ? el("small", { text: o.motivo }) : null))))))) : [el("p", { class: "vacio", text: "Nada coincide." })]));
    };
    buscar.addEventListener("input", debounce(pintarLista, 200));
    pintarLista();
    abrirHoja("Lo que sabe Ali",
      el("p", { class: "ayuda", text: `Política ${pol.version} (${pol.estado}). "Pública" sale de los términos y condiciones; "propuesta" está por validar con Cumplimiento. Se edita en politica/ del repositorio.` }),
      buscar, lista);
  }
  $("#btn-politica").addEventListener("click", hojaPolitica);

  iniciar();
})();
