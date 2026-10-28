// Evaluador de aliados comerciales · interfaz (sin dependencias).
// Todo texto que viene del comercio, de la política o de la IA se inserta con textContent (nunca como HTML).
"use strict";

(() => {
  const $ = (sel) => document.querySelector(sel);
  const BORRADOR = "afilia.borrador.v1";
  const CAMPOS = ["nombre", "razon_social", "actividad", "descripcion", "web"];
  const ETIQUETAS = { aplica: "Aplica", condicionado: "Aplica con condiciones", comite: "Requiere comité", no_aplica: "No aplica por ahora" };
  const FUENTES = { detectada: "Detectada en la descripción", agregada: "Agregada por el analista", respuesta: "Activada por una respuesta" };

  const estado = {
    comercio: Object.fromEntries(CAMPOS.map((c) => [c, ""])),
    respuestas: {},
    agregadas: [],
    quitadas: [],
    id: null,
    decision: "pendiente",
    notas: "",
    adicional: "",
    resultado: null,
    politica: null,
    servidor: null,
    sugerencias: null,
  };

  // ───────────── utilidades ─────────────

  function el(tag, attrs = {}, ...hijos) {
    const nodo = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") nodo.className = v;
      else if (k === "text") nodo.textContent = v;
      else if (k.startsWith("on")) nodo.addEventListener(k.slice(2), v);
      else nodo.setAttribute(k, v === true ? "" : v);
    }
    for (const h of hijos.flat()) if (h !== null && h !== undefined && h !== false) nodo.append(h);
    return nodo;
  }

  const chipNivel = (nivel, texto) => el("span", { class: `chip nivel nivel-${nivel || "descartada"}`, text: texto || ETIQUETAS[nivel] || "Descartada" });
  const chipOrigen = (origen) => origen === "publica"
    ? el("span", { class: "chip chip-publica", text: "pública", title: "Está en los términos y condiciones de PagueloFacil" })
    : el("span", { class: "chip chip-propuesta", text: "propuesta", title: "Práctica de la industria por validar con Cumplimiento" });
  const normal = (t) => (t || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();

  function debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  async function api(ruta, opciones = {}) {
    const r = await fetch(ruta, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...opciones });
    if (r.status === 401) { mostrarAcceso(); throw new Error("Inicia sesión para continuar."); }
    const datos = await r.json().catch(() => ({}));
    if (!r.ok) {
      const d = datos.detail;
      throw new Error(typeof d === "string" ? d : `No se pudo completar (error ${r.status}).`);
    }
    return datos;
  }

  function aviso(texto) {
    const nodo = $("#aviso-global");
    nodo.textContent = texto || "";
    nodo.hidden = !texto;
  }

  async function copiar(texto, boton) {
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
    if (boton) {
      const original = boton.textContent;
      boton.textContent = "Copiado ✓";
      boton.classList.add("hecho");
      setTimeout(() => { boton.textContent = original; boton.classList.remove("hecho"); }, 1600);
    }
  }

  function guardarBorrador() {
    const { comercio, respuestas, agregadas, quitadas, id, decision, notas, adicional } = estado;
    try { localStorage.setItem(BORRADOR, JSON.stringify({ comercio, respuestas, agregadas, quitadas, id, decision, notas, adicional })); } catch { /* sin almacenamiento */ }
  }

  function cargarBorrador() {
    try {
      const datos = JSON.parse(localStorage.getItem(BORRADOR) || "null");
      if (datos && typeof datos === "object") cargarEntrada(datos);
    } catch { /* borrador ilegible: se empieza de cero */ }
  }

  function cargarEntrada(datos) {
    estado.comercio = Object.fromEntries(CAMPOS.map((c) => [c, (datos.comercio && datos.comercio[c]) || ""]));
    estado.respuestas = datos.respuestas && typeof datos.respuestas === "object" ? datos.respuestas : {};
    estado.agregadas = Array.isArray(datos.agregadas) ? datos.agregadas : [];
    estado.quitadas = Array.isArray(datos.quitadas) ? datos.quitadas : [];
    estado.id = datos.id || null;
    estado.decision = datos.decision || "pendiente";
    estado.notas = datos.notas || "";
    estado.adicional = datos.adicional || "";
    estado.sugerencias = null;
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

  // ───────────── arranque ─────────────

  async function iniciar() {
    try {
      const st = await api("/api/estado");
      if (st.acceso_requerido && !st.usuario) { mostrarAcceso(); return; }
      await abrirApp(st);
    } catch (e) {
      document.body.prepend(el("p", { class: "aviso-global", text: `No pude conectar con el evaluador: ${e.message}` }));
    }
  }

  async function abrirApp(st) {
    estado.servidor = st;
    $("#acceso").hidden = true;
    $("#app").hidden = false;
    $("#usuario").textContent = st.usuario || "";
    $("#btn-salir").hidden = !st.acceso_requerido;
    $("#bloque-ia").hidden = !st.ia;
    aviso(st.politica.error ? `La política editada tiene un error y se sigue usando la versión anterior: ${st.politica.error}` : "");
    const decision = $("#decision");
    decision.replaceChildren(...Object.entries(st.decisiones).map(([id, texto]) => el("option", { value: id, text: texto })));
    estado.politica = await api("/api/politica");
    cargarBorrador();
    pintarFormulario();
    await evaluar();
  }

  // ───────────── formulario del comercio ─────────────

  const formComercio = $("#form-comercio");
  const evaluarPronto = debounce(() => evaluar(), 350);

  function pintarFormulario() {
    for (const c of CAMPOS) formComercio.elements[c].value = estado.comercio[c] || "";
    $("#ia-adicional").value = estado.adicional;
    $("#decision").value = estado.decision;
    $("#notas").value = estado.notas;
    $("#guardado").textContent = estado.id ? "Editando una evaluación guardada." : "";
    $("#tarjeta-ia").hidden = true;
  }

  formComercio.addEventListener("input", (ev) => {
    if (!CAMPOS.includes(ev.target.name)) return;
    estado.comercio[ev.target.name] = ev.target.value;
    evaluarPronto();
  });
  formComercio.addEventListener("submit", (ev) => ev.preventDefault());
  $("#ia-adicional").addEventListener("input", (ev) => { estado.adicional = ev.target.value; guardarBorrador(); });
  $("#notas").addEventListener("input", (ev) => { estado.notas = ev.target.value; guardarBorrador(); });
  $("#decision").addEventListener("change", (ev) => { estado.decision = ev.target.value; guardarBorrador(); });

  // ───────────── evaluación ─────────────

  let pedido = 0;

  async function evaluar() {
    const n = ++pedido;
    const { comercio, respuestas, agregadas, quitadas } = estado;
    try {
      const r = await api("/api/evaluar", { method: "POST", body: JSON.stringify({ comercio, respuestas, agregadas, quitadas }) });
      if (n !== pedido) return; // llegó una respuesta más nueva
      estado.resultado = r;
      pintar();
      guardarBorrador();
    } catch (e) {
      if (n === pedido) aviso(e.message);
    }
  }

  function pintar() {
    const r = estado.resultado;
    pintarActividades(r);
    pintarPreguntas(r);
    pintarPanel(r);
    if (estado.sugerencias) pintarIA();
  }

  // ───────────── actividades ─────────────

  function pintarActividades(r) {
    const cont = $("#actividades");
    const items = r.categorias.map((c) => el("div", { class: `actividad${c.descartada ? " descartada" : ""}` },
      el("div", { class: "actividad-cuerpo" },
        el("div", { class: "actividad-titulo" },
          el("strong", { text: c.nombre }),
          chipNivel(c.nivel, c.etiqueta),
          chipOrigen(c.origen),
          !c.aclarada && !c.descartada ? el("span", { class: "chip", text: "por aclarar" }) : null),
        el("p", { class: "palabras" },
          FUENTES[c.fuente] || "",
          c.palabras.length ? ": " : "",
          c.palabras.map((p) => el("mark", { text: p }))),
        el("p", { text: c.por_que })),
      el("button", {
        type: "button", class: "accion quitar", text: "Quitar", title: "No corresponde a este comercio",
        onclick: () => {
          estado.quitadas = [...new Set([...estado.quitadas, c.id])];
          estado.agregadas = estado.agregadas.filter((x) => x !== c.id);
          evaluar();
        },
      })));
    const avisos = r.avisos.map((a) => el("p", { class: "vacio", text: a }));
    cont.replaceChildren(...items, ...(items.length ? [] : avisos));

    const activas = new Set(r.categorias.map((c) => c.id));
    const sel = $("#sel-agregar");
    sel.replaceChildren(el("option", { value: "", text: "Agregar actividad…" }),
      ...estado.politica.categorias.filter((c) => !activas.has(c.id))
        .map((c) => el("option", { value: c.id, text: `${c.nombre} (${c.etiqueta.toLowerCase()} si se confirma)` })));

    const quitadas = $("#quitadas");
    const nombres = estado.politica.categorias.filter((c) => estado.quitadas.includes(c.id));
    quitadas.replaceChildren(...(nombres.length ? ["Quitaste: ", ...nombres.flatMap((c, i) => [i ? ", " : "", el("button", {
      type: "button", class: "enlace", text: `${c.nombre} (restaurar)`,
      onclick: () => { estado.quitadas = estado.quitadas.filter((x) => x !== c.id); evaluar(); },
    })])] : []));
  }

  $("#sel-agregar").addEventListener("change", (ev) => {
    const id = ev.target.value;
    if (!id) return;
    estado.agregadas = [...new Set([...estado.agregadas, id])];
    estado.quitadas = estado.quitadas.filter((x) => x !== id);
    evaluar();
  });

  // ───────────── preguntas ─────────────

  function pintarPreguntas(r) {
    const cont = $("#preguntas");
    const activo = document.activeElement;
    const foco = activo && activo.dataset && activo.dataset.clave;
    const nodos = [];
    let seccion = null;
    let grupo = null;
    for (const p of r.preguntas) {
      if (p.seccion !== seccion) { seccion = p.seccion; grupo = null; nodos.push(el("h3", { class: "seccion-preguntas", text: seccion })); }
      if (p.bloque !== grupo) { grupo = p.bloque; nodos.push(el("p", { class: "grupo", text: grupo })); }
      nodos.push(pregunta(p, r));
    }
    if (!nodos.length) nodos.push(el("p", { class: "vacio", text: "No hay preguntas." }));
    cont.replaceChildren(...nodos);
    if (foco) {
      const nuevo = cont.querySelector(`[data-clave="${CSS.escape(foco)}"]`);
      if (nuevo) nuevo.focus({ preventScroll: true });
    }
  }

  function pregunta(p, r) {
    const multiple = p.tipo === "multiple";
    const elegidas = multiple ? (p.respuesta || []) : (p.respuesta ? [p.respuesta] : []);
    const respondida = elegidas.length > 0;
    const opciones = p.opciones.map((o) => {
      const marcada = elegidas.includes(o.id);
      return el("label", { class: `opcion${marcada ? " elegida" : ""}` },
        el("input", {
          type: multiple ? "checkbox" : "radio", name: p.id, value: o.id, checked: marcada,
          "data-clave": `${p.id}:${o.id}`,
          onchange: (ev) => responder(p, o.id, ev.target.checked),
        }),
        el("span", { text: o.texto }));
    });
    return el("fieldset", { class: `pregunta${p.id === r.siguiente ? " siguiente" : ""}${respondida ? " respondida" : ""}`, id: `p-${p.id}` },
      el("legend", {},
        el("span", { text: p.texto }),
        p.clave ? el("span", { class: "chip chip-clave", text: "clave" }) : null,
        p.id === r.siguiente ? el("span", { class: "chip chip-siguiente", text: "siguiente" }) : null),
      p.ayuda ? el("p", { class: "ayuda", text: p.ayuda }) : null,
      el("div", { class: "opciones" }, opciones),
      respondida && !multiple ? el("div", { class: "pregunta-pie" }, el("button", {
        type: "button", class: "enlace", text: "Borrar respuesta",
        onclick: () => { delete estado.respuestas[p.id]; evaluar(); },
      })) : null);
  }

  function responder(p, opcion, marcada) {
    if (p.tipo === "multiple") {
      const actual = new Set(Array.isArray(estado.respuestas[p.id]) ? estado.respuestas[p.id] : []);
      if (marcada) actual.add(opcion); else actual.delete(opcion);
      if (actual.size) estado.respuestas[p.id] = [...actual]; else delete estado.respuestas[p.id];
    } else {
      estado.respuestas[p.id] = opcion;
    }
    evaluar();
  }

  function irASiguiente() {
    const id = estado.resultado && estado.resultado.siguiente;
    const nodo = id && document.getElementById(`p-${id}`);
    if (!nodo) return;
    nodo.scrollIntoView({ behavior: "smooth", block: "center" });
    const input = nodo.querySelector("input");
    if (input) input.focus({ preventScroll: true });
  }
  $("#btn-siguiente").addEventListener("click", irASiguiente);

  // ───────────── panel de recomendación ─────────────

  function pintarPanel(r) {
    const semaforo = $("#semaforo");
    semaforo.dataset.nivel = r.nivel;
    semaforo.classList.toggle("preliminar", r.estado === "preliminar");
    // Sin las preguntas clave no hay conclusión: "Por aclarar" y hacia dónde va, nunca un "No" por una palabra.
    const preliminar = r.estado === "preliminar";
    const faltan = r.pendientes.length;
    $("#semaforo-etiqueta").textContent = preliminar ? "Por aclarar" : r.etiqueta;
    $("#semaforo-estado").textContent = preliminar
      ? `Si se confirma lo detectado: ${r.etiqueta.toLowerCase()} · ${faltan === 1 ? "falta 1 pregunta clave" : `faltan ${faltan} preguntas clave`}`
      : "Completo · preguntas clave respondidas";
    $("#resumen").textContent = r.resumen;
    $("#resumen-movil").dataset.nivel = r.nivel;
    $("#resumen-movil").classList.toggle("preliminar", preliminar);
    $("#movil-etiqueta").textContent = preliminar ? "Por aclarar" : r.etiqueta;
    $("#movil-estado").textContent = preliminar ? `· faltan ${faltan}` : "· completo";
    $("#aviso-mensaje").hidden = !preliminar;

    const claves = r.preguntas.filter((p) => p.clave);
    const respondidas = claves.length - faltan;
    $("#progreso").hidden = !claves.length;
    $("#barra-progreso").style.width = `${claves.length ? Math.round((respondidas / claves.length) * 100) : 0}%`;
    $("#btn-siguiente").hidden = !r.siguiente;
    $("#btn-siguiente").textContent = faltan ? `Ir a la siguiente pregunta clave (${respondidas}/${claves.length})` : "Ir a la siguiente pregunta";

    const bloques = [];
    if (r.motivos.length) {
      bloques.push(el("div", { class: "bloque" }, el("h4", { text: "Por qué" }),
        el("ul", { class: "motivos" }, r.motivos.map((m) => el("li", {},
          el("span", { class: "motivo-origen" }, chipNivel(m.nivel), " ", m.origen),
          el("span", { text: m.texto }),
          m.respuesta ? el("span", { class: "motivo-respuesta", text: `Respuesta: ${m.respuesta}` }) : null)))));
    }
    if (r.servicios_comite.length) {
      bloques.push(el("div", { class: "bloque servicios" }, el("h4", { text: "Servicios que pasan por comité" }),
        el("ul", {}, r.servicios_comite.map((s) => el("li", { text: s }))),
        el("p", { class: "ayuda", text: "No frenan la afiliación: el comercio puede empezar con enlace de pago." })));
    }
    if (r.condiciones.length) {
      bloques.push(el("div", { class: "bloque" }, el("h4", { text: "Condiciones para afiliar" }),
        el("ul", {}, r.condiciones.map((c) => el("li", { text: c })))));
    }
    if (r.alternativas.length) {
      bloques.push(el("div", { class: "bloque" }, el("h4", { text: "Caminos para afiliar" }),
        el("ul", {}, r.alternativas.map((a) => el("li", { class: "alternativa" },
          el("strong", { text: a.titulo }), a.por_confirmar ? el("span", { class: "chip chip-propuesta", text: "por confirmar" }) : null,
          el("span", { text: a.detalle }))))));
    }
    if (r.documentos.length) {
      bloques.push(el("div", { class: "bloque" }, el("h4", { text: "Documentos a pedir" }),
        el("ul", {}, r.documentos.map((d) => el("li", { title: d.detalle || "" },
          d.nombre, d.por_confirmar ? " " : "", d.por_confirmar ? el("span", { class: "chip chip-propuesta", text: "por confirmar" }) : null)))));
    }
    if (r.pasos.length) {
      bloques.push(el("div", { class: "bloque" }, el("h4", { text: "Próximos pasos" }),
        el("ol", {}, r.pasos.map((p) => el("li", { text: p })))));
    }
    $("#detalle").replaceChildren(...bloques);
    $("#mensaje").textContent = r.mensaje_comercio;
  }

  $("#btn-copiar-mensaje").addEventListener("click", (ev) => copiar(estado.resultado ? estado.resultado.mensaje_comercio : "", ev.currentTarget));
  $("#btn-copiar-resumen").addEventListener("click", (ev) => copiar(estado.resultado ? estado.resultado.resumen_comite : "", ev.currentTarget));
  $("#btn-descargar").addEventListener("click", () => {
    if (!estado.resultado) return;
    const nombre = normal(estado.comercio.nombre || estado.comercio.razon_social || "comercio").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "comercio";
    const url = URL.createObjectURL(new Blob([estado.resultado.resumen_comite], { type: "text/markdown;charset=utf-8" }));
    const a = el("a", { href: url, download: `evaluacion-${nombre}.md` });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  $("#form-guardar").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const nota = $("#guardado");
    const { comercio, respuestas, agregadas, quitadas, id, decision, notas } = estado;
    try {
      const r = await api("/api/evaluaciones", { method: "POST", body: JSON.stringify({ comercio, respuestas, agregadas, quitadas, id, decision, notas }) });
      estado.id = r.id;
      guardarBorrador();
      nota.textContent = `Guardada ✓ ${new Date().toLocaleTimeString("es-PA", { hour: "2-digit", minute: "2-digit" })}`;
    } catch (e) {
      nota.textContent = e.message;
    }
  });

  $("#btn-nueva").addEventListener("click", () => {
    const hayDatos = CAMPOS.some((c) => estado.comercio[c]) || Object.keys(estado.respuestas).length;
    if (hayDatos && !estado.id && !confirm("¿Empezar una evaluación nueva? Se borra la que no guardaste.")) return;
    cargarEntrada({});
    try { localStorage.removeItem(BORRADOR); } catch { /* sin almacenamiento */ }
    pintarFormulario();
    mostrarVista("evaluar");
    evaluar();
    window.scrollTo({ top: 0, behavior: "smooth" });
    formComercio.elements.nombre.focus({ preventScroll: true });
  });

  // ───────────── IA ─────────────

  $("#btn-ia").addEventListener("click", async () => {
    const boton = $("#btn-ia");
    const nota = $("#ia-estado");
    boton.disabled = true;
    nota.textContent = "Analizando… puede tardar unos segundos.";
    try {
      estado.sugerencias = await api("/api/ia/analizar", { method: "POST", body: JSON.stringify({ comercio: estado.comercio, adicional: estado.adicional }) });
      nota.textContent = "";
      pintarIA();
      $("#tarjeta-ia").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      nota.textContent = e.message;
    } finally {
      boton.disabled = false;
    }
  });

  function aplicarSugerencia(s) {
    const activas = new Set(estado.resultado.categorias.map((c) => c.id));
    if (s.categoria && !activas.has(s.categoria)) {
      estado.agregadas = [...new Set([...estado.agregadas, s.categoria])];
      estado.quitadas = estado.quitadas.filter((x) => x !== s.categoria);
    }
    if (s.tipo === "multiple") {
      const actual = new Set(Array.isArray(estado.respuestas[s.pregunta]) ? estado.respuestas[s.pregunta] : []);
      actual.add(s.opcion);
      estado.respuestas[s.pregunta] = [...actual];
    } else {
      estado.respuestas[s.pregunta] = s.opcion;
    }
  }

  function pintarIA() {
    const s = estado.sugerencias;
    const r = estado.resultado;
    const activas = new Set(r.categorias.filter((c) => !c.descartada).map((c) => c.id));
    const aplicada = (x) => {
      const actual = estado.respuestas[x.pregunta];
      return Array.isArray(actual) ? actual.includes(x.opcion) : actual === x.opcion;
    };
    const partes = [
      el("p", { class: "ia-actividad", text: s.actividad_real || "Sin conclusión sobre la actividad." }),
      s.explicacion ? el("p", { text: s.explicacion }) : null,
    ];
    if (s.categorias.length) {
      partes.push(el("div", { class: "bloque" }, el("h4", { text: "Actividades que ve la IA" }),
        el("ul", { class: "ia-lista" }, s.categorias.map((c) => el("li", {},
          el("div", {}, el("strong", { text: c.nombre }), " ", el("span", { class: "evidencia", text: c.razon })),
          activas.has(c.id) ? el("span", { class: "chip chip-clave", text: "ya está" }) : el("button", {
            type: "button", class: "accion", text: "Agregar",
            onclick: () => { estado.agregadas = [...new Set([...estado.agregadas, c.id])]; estado.quitadas = estado.quitadas.filter((x) => x !== c.id); evaluar(); },
          }))))));
    }
    if (s.respuestas_sugeridas.length) {
      const pendientes = s.respuestas_sugeridas.filter((x) => !aplicada(x));
      partes.push(el("div", { class: "bloque" },
        el("div", { class: "subtitulo" }, el("h4", { text: "Respuestas que respalda el texto" }),
          pendientes.length > 1 ? el("button", {
            type: "button", class: "accion", text: "Aplicar todas",
            onclick: () => { pendientes.forEach(aplicarSugerencia); evaluar(); },
          }) : null),
        el("ul", { class: "ia-lista" }, s.respuestas_sugeridas.map((x) => el("li", {},
          el("div", {}, el("span", { text: x.pregunta_texto }), " → ", el("strong", { text: x.opcion_texto }),
            x.evidencia ? el("span", { class: "evidencia", text: x.evidencia }) : null),
          aplicada(x) ? el("span", { class: "chip chip-clave", text: "aplicada" }) : el("button", {
            type: "button", class: "accion", text: "Aplicar",
            onclick: () => { aplicarSugerencia(x); evaluar(); },
          }))))));
    }
    if (s.preguntas_para_el_comercio.length) {
      partes.push(el("div", { class: "bloque" },
        el("div", { class: "subtitulo" }, el("h4", { text: "Preguntas para el comercio" }),
          el("button", { type: "button", class: "accion", text: "Copiar", onclick: (ev) => copiar(s.preguntas_para_el_comercio.map((p) => `- ${p}`).join("\n"), ev.currentTarget) })),
        el("ul", {}, s.preguntas_para_el_comercio.map((p) => el("li", { text: p })))));
    }
    if (s.alertas.length) {
      partes.push(el("div", { class: "bloque" }, el("h4", { text: "Alertas" }),
        el("ul", {}, s.alertas.map((a) => el("li", { class: "alerta", text: a })))));
    }
    if (s.alternativas.length) {
      partes.push(el("div", { class: "bloque" }, el("h4", { text: "Caminos que propone" }),
        el("ul", {}, s.alternativas.map((a) => el("li", { class: "alternativa" }, el("strong", { text: a.titulo }), el("span", { text: a.por_que }))))));
    }
    partes.push(el("p", { class: "ayuda", text: `Generado por ${s.modelo}. La IA puede equivocarse: revisa cada sugerencia antes de aplicarla.` }));
    $("#ia-resultado").replaceChildren(...partes);
    $("#tarjeta-ia").hidden = false;
  }

  // ───────────── pestañas ─────────────

  function mostrarVista(vista) {
    for (const b of document.querySelectorAll(".pestana")) {
      const activa = b.dataset.vista === vista;
      b.classList.toggle("activa", activa);
      if (activa) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
    }
    for (const v of ["evaluar", "historial", "politica"]) $(`#vista-${v}`).hidden = v !== vista;
    if (vista === "historial") cargarHistorial();
    if (vista === "politica") pintarPolitica();
  }
  for (const b of document.querySelectorAll(".pestana")) b.addEventListener("click", () => mostrarVista(b.dataset.vista));

  // ───────────── historial ─────────────

  async function cargarHistorial() {
    const cuerpo = $("#lista-historial");
    try {
      const datos = await api(`/api/evaluaciones?q=${encodeURIComponent($("#buscar").value)}`);
      const filas = datos.evaluaciones.map((e) => el("tr", {},
        el("td", { text: new Date(e.actualizada).toLocaleDateString("es-PA", { day: "2-digit", month: "short", year: "numeric" }) }),
        el("td", {}, el("strong", { text: e.comercio })),
        el("td", {}, chipNivel(e.nivel), e.estado === "preliminar" ? el("span", { class: "chip", text: "preliminar" }) : null),
        el("td", { text: datos.decisiones[e.decision] || e.decision }),
        el("td", { text: e.analista }),
        el("td", {}, el("button", { type: "button", class: "accion", text: "Abrir", onclick: () => abrirEvaluacion(e.id) }))));
      cuerpo.replaceChildren(...(filas.length ? filas : [el("tr", {}, el("td", { colspan: "6", class: "vacio", text: "Todavía no hay evaluaciones guardadas." }))]));
    } catch (e) {
      cuerpo.replaceChildren(el("tr", {}, el("td", { colspan: "6", class: "vacio", text: e.message })));
    }
  }
  $("#buscar").addEventListener("input", debounce(cargarHistorial, 300));

  async function abrirEvaluacion(id) {
    try {
      const e = await api(`/api/evaluaciones/${encodeURIComponent(id)}`);
      cargarEntrada({ ...e.entrada, id: e.id, decision: e.decision, notas: e.notas });
      pintarFormulario();
      mostrarVista("evaluar");
      await evaluar();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      aviso(err.message);
    }
  }

  // ───────────── política ─────────────

  function efectos(o) {
    const partes = [];
    if (o.nivel) partes.push(chipNivel(o.nivel));
    if (o.tope) partes.push(el("span", { class: "chip", text: `como máximo: ${ETIQUETAS[o.tope].toLowerCase()}` }));
    if (o.descarta) partes.push(chipNivel(null, "descarta la actividad"));
    if (o.servicio_comite) partes.push(el("span", { class: "chip nivel nivel-comite", text: "servicio por comité" }));
    const detalle = [o.motivo,
      o.activa.length ? `Activa: ${o.activa.join(", ")}.` : "",
      o.condiciones.length ? `Condiciones: ${o.condiciones.join(" ")}` : "",
      o.documentos.length ? `Documentos: ${o.documentos.join(", ")}.` : "",
      o.alternativas.length ? `Alternativas: ${o.alternativas.join(", ")}.` : ""].filter(Boolean).join(" ");
    return [partes.length ? " " : "", ...partes, detalle ? el("span", { class: "pol-efecto", text: detalle }) : null];
  }

  function polPregunta(p) {
    const cond = Object.entries(p.mostrar_si).map(([k, v]) => `${k} = ${v.join(" o ")}`).join(" y ");
    return el("div", { class: "pol-pregunta" },
      el("strong", { text: p.texto }), " ", p.clave ? el("span", { class: "chip chip-clave", text: "clave" }) : null,
      cond ? el("span", { class: "pol-efecto", text: `Aparece si ${cond}.` }) : null,
      el("ul", { class: "pol-opciones" }, p.opciones.map((o) => el("li", {}, o.texto, ...efectos(o)))));
  }

  function pintarPolitica() {
    const pol = estado.politica;
    if (!pol) return;
    const filtro = normal($("#filtro-politica").value.trim());
    $("#politica-version").textContent = `Versión ${pol.version} · estado: ${pol.estado}. ${pol.categorias.length} actividades, ${pol.alternativas.length} alternativas y ${pol.documentos.length} documentos.`;
    const coincide = (c) => !filtro || normal(JSON.stringify(c)).includes(filtro);
    const categorias = pol.categorias.filter(coincide).map((c) => el("details", { class: "pol-categoria", open: Boolean(filtro) },
      el("summary", {}, el("strong", { text: c.nombre }), chipNivel(c.nivel, `${c.etiqueta} si se confirma`), chipOrigen(c.origen)),
      el("p", { text: c.por_que }),
      el("div", { class: "pol-palabras" }, c.palabras_clave.map((p) => el("span", { class: "chip", text: p }))),
      c.preguntas.map(polPregunta)));
    const nodos = [el("h3", { class: "pol-titulo", text: "Actividades" }), ...(categorias.length ? categorias : [el("p", { class: "vacio", text: "Ninguna actividad coincide con el filtro." })])];
    const generales = pol.generales.filter(coincide);
    if (generales.length) nodos.push(el("h3", { class: "pol-titulo", text: "Preguntas para todos los comercios" }), ...generales.map(polPregunta));
    const alternativas = pol.alternativas.filter(coincide);
    if (alternativas.length) {
      nodos.push(el("h3", { class: "pol-titulo", text: "Caminos para afiliar (alternativas)" }),
        el("ul", { class: "pol-catalogo" }, alternativas.map((a) => el("li", { class: "alternativa" },
          el("strong", { text: a.titulo }), " ", el("code", { text: a.id }), a.por_confirmar ? el("span", { class: "chip chip-propuesta", text: "por confirmar" }) : null,
          el("span", { text: a.detalle })))));
    }
    const documentos = pol.documentos.filter(coincide);
    if (documentos.length) {
      nodos.push(el("h3", { class: "pol-titulo", text: "Documentos" }),
        el("ul", { class: "pol-catalogo" }, documentos.map((d) => el("li", { class: "alternativa" },
          el("strong", { text: d.nombre }), " ", el("code", { text: d.id }), d.por_confirmar ? el("span", { class: "chip chip-propuesta", text: "por confirmar" }) : null,
          d.detalle ? el("span", { text: d.detalle }) : null))));
    }
    $("#politica").replaceChildren(...nodos);
  }
  $("#filtro-politica").addEventListener("input", debounce(pintarPolitica, 200));

  iniciar();
})();
