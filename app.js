(() => {
  "use strict";

  const POR_PAGINA = 30;
  const TEST_URL = "https://bertamunoz02.github.io/salidas-cientificas/";
  const $ = (id) => document.getElementById(id);
  // Colores de la marca para los avatares de empresa (cada empresa conserva siempre el suyo)
  const COLORES = ["#131B2E", "#2F5D48", "#B04468", "#B5532F", "#8F3555", "#3A2D5A", "#1E2A4A", "#5A3F48"];

  const estado = {
    deps: new Set(), zona: "", pais: "", empresa: "",
    niveles: new Set(), dias: "", q: "", orden: "fecha",
  };
  let ofertas = [];
  let meta = {};

  // Grupos de departamentos según el mapa del blog de Con B de Biología
  // (orden y nombres de los bloques del post "Trabajar en farma").
  const GRUPOS_DEP = [
    { nombre: "Investigación y desarrollo (I+D)", deps: ["id"] },
    { nombre: "Ensayos clínicos", deps: ["clinica"] },
    { nombre: "Fabricación", deps: ["produccion", "calidad", "ingenieria"] },
    { nombre: "Unidad de negocio", deps: ["medico", "ventas", "marketing"] },
    { nombre: "Áreas transversales", deps: ["acceso", "regulatorios", "legal", "farmacovigilancia", "supply", "rrhh", "finanzas", "proyectos"] },
    { nombre: "Salud digital, datos e IA", deps: ["datos", "it"] },
  ];
  let visibles = POR_PAGINA;

  const normalizar = (t) => (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const fmt = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const nombreDep = (d) => (meta.departamentos || {})[d] || d;
  const contar = (lista, campo) => lista.reduce((m, o) => (m[o[campo]] = (m[o[campo]] || 0) + 1, m), {});
  const ordenar = (cuentas) => Object.entries(cuentas).sort((a, b) => b[1] - a[1]);

  // ---------------------------------------------------------------- carga
  async function cargar() {
    $("anio").textContent = new Date().getFullYear();
    try {
      const r = await fetch("data/jobs.json", { cache: "no-cache" });
      const datos = await r.json();
      meta = datos.meta || {};
      ofertas = (datos.ofertas || []).map((o) => ({
        ...o,
        _texto: normalizar([o.titulo, o.empresa, o.ubicacion, o.otras_ubicaciones, o.descripcion, nombreDep(o.departamento)].join(" ")),
      }));
    } catch (e) {
      ofertas = [];
    }
    leerHash();
    pintarPortada();
    montarControles();
    pintarGraficos();
    pintar();
    pintarPie();
  }

  // ---------------------------------------------------------------- portada
  function pintarPortada() {
    const empresas = new Set(ofertas.map((o) => o.empresa));
    const paises = new Set(ofertas.map((o) => o.pais));
    $("c-ofertas").textContent = fmt(ofertas.length);
    $("c-empresas").textContent = fmt(empresas.size);
    $("c-paises").textContent = fmt(paises.size);
    $("c-espana").textContent = fmt(ofertas.filter((o) => o.pais === "España").length);

    // Franjas con títulos reales de hoy (cortos, sin repetir)
    const titulos = [...new Set(ofertas.map((o) => o.titulo.replace(/\s*\((m\/w\/d|m\/f\/d|f\/m\/d|all genders|h\/f|w\/m\/d)\)\s*/gi, " ").trim()))]
      .filter((t) => t.length > 6 && t.length < 44);
    if (titulos.length < 12) { $("mural").hidden = true; return; }
    const mezcla = titulos.sort(() => Math.random() - .5).slice(0, 60);
    const filas = [0, 1].map((f) => mezcla.filter((_, i) => i % 2 === f));
    $("mural").innerHTML = filas.map((lista, k) => {
      const c = lista.map((n) => `<span>${escapar(n)}</span>`).join("");
      return `<div class="franja ${k % 2 ? "inversa" : ""}" style="--dur:${150 + k * 30}s"><div class="pista">${c}${c}</div></div>`;
    }).join("");
  }

  // ---------------------------------------------------------------- el sector hoy
  function pintarGraficos() {
    const grafico = (id, cuentas, alPulsar, activo, propio, etiqueta = (k) => k, max = 7) => {
      const filas = ordenar(cuentas).slice(0, max);
      const tope = filas.length ? filas[0][1] : 1;
      const ol = $(id);
      ol.innerHTML = "";
      filas.forEach(([k, n]) => {
        const li = document.createElement("li");
        const b = document.createElement("button");
        b.type = "button";
        b.className = "barra-dato" + (propio(k) ? " propia" : "");
        b._activo = () => activo(k);
        b.setAttribute("aria-pressed", activo(k));
        b.title = `${etiqueta(k)}: ${fmt(n)} ofertas`;
        b.innerHTML = `<span class="nombre"></span><span class="riel"><span></span></span><span class="valor">${fmt(n)}</span>`;
        b.querySelector(".nombre").textContent = etiqueta(k);
        b.onclick = () => { alPulsar(k); irAOfertas(); };
        li.append(b);
        ol.append(li);
        requestAnimationFrame(() => requestAnimationFrame(() => {
          b.querySelector(".riel > span").style.width = `${Math.max(3, (n / tope) * 100)}%`;
        }));
      });
    };
    grafico("g-paises", contar(ofertas, "pais"),
      (k) => { estado.pais = estado.pais === k ? "" : k; estado.zona = ""; sincronizarSelects(); cambio(); },
      (k) => estado.pais === k, (k) => k === "España");
    grafico("g-empresas", contar(ofertas, "empresa"),
      (k) => { estado.empresa = estado.empresa === k ? "" : k; sincronizarSelects(); cambio(); },
      (k) => estado.empresa === k, () => false);
    const deps = contar(ofertas.filter((o) => o.departamento !== "otros"), "departamento");
    grafico("g-departamentos", deps,
      (k) => { estado.deps = new Set(estado.deps.has(k) && estado.deps.size === 1 ? [] : [k]); cambio(); },
      (k) => estado.deps.has(k), () => false, nombreDep);
  }

  function irAOfertas() {
    $("ofertas").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }

  // ---------------------------------------------------------------- filtros
  function cumple(o, ignorar) {
    if (ignorar !== "dep" && estado.deps.size && !estado.deps.has(o.departamento)) return false;
    if (estado.zona === "es" && o.pais !== "España") return false;
    if (estado.zona === "eu" && o.pais === "España") return false;
    if (estado.pais && o.pais !== estado.pais) return false;
    if (estado.empresa && o.empresa !== estado.empresa) return false;
    if (ignorar !== "nivel" && estado.niveles.size && !estado.niveles.has(o.nivel)) return false;
    if (estado.dias) {
      if (!o.fecha) return false;
      if (diasDesde(o.fecha) > Number(estado.dias)) return false;
    }
    if (estado.q) {
      const terminos = normalizar(estado.q).split(/\s+/).filter(Boolean);
      if (!terminos.every((t) => o._texto.includes(t))) return false;
    }
    return true;
  }

  function montarControles() {
    const totales = contar(ofertas, "departamento");
    const nombres = meta.departamentos || {};
    const cont = $("departamentos");
    cont.innerHTML = "";
    const todos = chip("Todos", () => { estado.deps.clear(); cambio(); });
    todos.dataset.dep = "";
    cont.append(todos);
    const chipDep = (d) => {
      const b = chip(nombres[d], () => {
        estado.deps.has(d) ? estado.deps.delete(d) : estado.deps.add(d);
        cambio();
      });
      b.dataset.dep = d;
      return b;
    };
    // Los grupos y el orden siguen el mapa de departamentos del blog
    // ("Trabajar en farma: un mapa para entender sus áreas y puestos").
    // La clasificación de cada oferta no cambia: solo cómo se presentan los filtros.
    const asignados = new Set();
    GRUPOS_DEP.forEach((g) => {
      const deps = g.deps.filter((d) => nombres[d]);
      if (!deps.length) return;
      deps.forEach((d) => asignados.add(d));
      cont.append(grupoDep(g.nombre, deps.map(chipDep)));
    });
    const resto = Object.keys(nombres)
      .filter((d) => !asignados.has(d) && d !== "otros")
      .sort((a, b) => (totales[b] || 0) - (totales[a] || 0));
    if (nombres.otros) resto.push("otros");
    if (resto.length) cont.append(grupoDep("Otros", resto.map(chipDep)));

    const paises = [...new Set(ofertas.map((o) => o.pais))].sort((a, b) =>
      (b === "España") - (a === "España") || a.localeCompare(b, "es"));
    llenarSelect($("pais"), paises, "Cualquier país");
    const empresas = [...new Set(ofertas.map((o) => o.empresa))].sort((a, b) => a.localeCompare(b, "es"));
    llenarSelect($("empresa"), empresas, "Todas las empresas");
    sincronizarSelects();

    casillas($("nivel"), meta.niveles || {}, estado.niveles, ["practicas", "graduado", "intermedio", "senior", "direccion"]);

    let espera;
    $("q").oninput = (e) => { clearTimeout(espera); espera = setTimeout(() => { estado.q = e.target.value.trim(); cambio(); }, 200); };
    $("q").onkeydown = (e) => { if (e.key === "Enter") { e.target.blur(); irAOfertas(); } };
    $("pais").onchange = (e) => { estado.pais = e.target.value; if (estado.pais) estado.zona = ""; cambio(); };
    $("empresa").onchange = (e) => { estado.empresa = e.target.value; cambio(); };
    $("dias").onchange = (e) => { estado.dias = e.target.value; cambio(); };
    $("orden").onchange = (e) => { estado.orden = e.target.value; cambio(); };
    document.querySelectorAll("#zona button").forEach((b) => {
      b.onclick = () => { estado.zona = b.dataset.zona; estado.pais = ""; $("pais").value = ""; cambio(); };
    });
    $("atajo-practicas").onclick = () => {
      if (atajoActivo()) { estado.zona = ""; estado.niveles.clear(); }
      else { estado.zona = "es"; estado.pais = ""; estado.niveles = new Set(["practicas"]); }
      document.querySelectorAll(".casillas input").forEach((i) => (i.checked = estado.niveles.has(i.parentNode.dataset.clave)));
      sincronizarSelects();
      cambio();
    };
    $("limpiar").onclick = limpiarFiltros;
    $("mas").onclick = () => { visibles += POR_PAGINA; pintar(false); };
    $("abrir-filtros").onclick = () => hojaFiltros(true);
    $("cerrar-filtros").onclick = () => hojaFiltros(false);
    $("fondo-filtros").onclick = () => hojaFiltros(false);
    $("aplicar").onclick = () => { hojaFiltros(false); irAOfertas(); };
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") hojaFiltros(false); });
  }

  // Atajo: España + Prácticas / becas. Los departamentos y el resto de filtros se pueden sumar encima.
  const atajoActivo = () => estado.zona === "es" && !estado.pais && estado.niveles.size === 1 && estado.niveles.has("practicas");

  function hojaFiltros(abrir) {
    $("panel-filtros").classList.toggle("abierto", abrir);
    $("fondo-filtros").hidden = !abrir;
    document.body.style.overflow = abrir ? "hidden" : "";
    if (abrir) $("cerrar-filtros").focus();
  }

  function limpiarFiltros() {
    Object.assign(estado, { zona: "", pais: "", empresa: "", dias: "", q: "" });
    estado.niveles.clear();
    $("q").value = "";
    document.querySelectorAll(".casillas input").forEach((i) => (i.checked = false));
    sincronizarSelects();
    cambio();
  }

  function sincronizarSelects() {
    $("pais").value = estado.pais; $("empresa").value = estado.empresa;
    $("dias").value = estado.dias; $("orden").value = estado.orden; $("q").value = estado.q;
  }

  function grupoDep(nombre, chips) {
    const g = document.createElement("section");
    g.className = "dep-grupo";
    if (nombre) {
      const h = document.createElement("h3");
      h.className = "dep-grupo-nombre";
      h.textContent = nombre;
      g.append(h);
    }
    const fila = document.createElement("div");
    fila.className = "dep-grupo-chips";
    fila.append(...chips);
    g.append(fila);
    return g;
  }

  function chip(texto, alPulsar) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.innerHTML = `<span></span><span class="cuenta"></span>`;
    b.firstChild.textContent = texto;
    b.onclick = alPulsar;
    return b;
  }

  function llenarSelect(sel, valores, vacio) {
    sel.innerHTML = "";
    sel.append(new Option(vacio, ""));
    valores.forEach((v) => sel.append(new Option(v, v)));
  }

  function casillas(cont, nombres, conjunto, orden) {
    cont.innerHTML = "";
    orden.filter((k) => nombres[k]).forEach((k) => {
      const l = document.createElement("label");
      l.innerHTML = `<input type="checkbox"><span></span><span class="cuenta"></span>`;
      l.children[1].textContent = nombres[k];
      l.dataset.clave = k;
      const input = l.firstChild;
      input.checked = conjunto.has(k);
      input.onchange = () => { input.checked ? conjunto.add(k) : conjunto.delete(k); cambio(); };
      cont.append(l);
    });
  }

  function cambio() {
    visibles = POR_PAGINA;
    escribirHash();
    pintar();
    document.querySelectorAll(".barra-dato").forEach((b) => b.setAttribute("aria-pressed", b._activo()));
  }

  // ---------------------------------------------------------------- resultados
  function pintar(reiniciar = true) {
    const filtradas = ofertas.filter((o) => cumple(o));
    if (estado.orden === "empresa") {
      filtradas.sort((a, b) => a.empresa.localeCompare(b.empresa, "es") || (b.fecha || "").localeCompare(a.fecha || ""));
    }

    const porDep = contar(ofertas.filter((o) => cumple(o, "dep")), "departamento");
    document.querySelectorAll("#departamentos .chip").forEach((b) => {
      const d = b.dataset.dep;
      const n = d ? porDep[d] || 0 : Object.values(porDep).reduce((a, x) => a + x, 0);
      b.querySelector(".cuenta").textContent = fmt(n);
      b.classList.toggle("cero", n === 0);
      b.setAttribute("aria-pressed", d ? estado.deps.has(d) : estado.deps.size === 0);
    });
    $("atajo-practicas").setAttribute("aria-pressed", atajoActivo());
    $("atajo-cuenta").textContent = fmt(ofertas.filter((o) => o.pais === "España" && o.nivel === "practicas").length);
    cuentasCasillas("nivel", contar(ofertas.filter((o) => cumple(o, "nivel")), "nivel"));
    document.querySelectorAll("#zona button").forEach((b) =>
      b.setAttribute("aria-pressed", b.dataset.zona === estado.zona && !estado.pais
        || (b.dataset.zona === "es" && estado.pais === "España")));

    const activos = [estado.zona || estado.pais, estado.empresa, estado.dias].filter(Boolean).length
      + estado.niveles.size;
    $("n-filtros").hidden = !activos;
    $("n-filtros").textContent = activos;

    const n = filtradas.length;
    $("n-res").textContent = ofertas.length ? `${fmt(n)} ${n === 1 ? "oferta" : "ofertas"}` : "Sin datos todavía";
    $("aplicar").textContent = `Ver ${fmt(n)} ${n === 1 ? "oferta" : "ofertas"}`;
    pintarActivos();

    const lista = $("lista");
    if (reiniciar) lista.innerHTML = "";
    const desde = lista.querySelectorAll(".oferta").length;
    const frag = document.createDocumentFragment();
    filtradas.slice(desde, visibles).forEach((o, i) => {
      frag.append(tarjeta(o));
      // tras la 5.ª oferta, si aún no ha elegido departamento, invitamos al test
      if (desde + i === 4 && !estado.deps.size) frag.append(puente());
    });
    lista.append(frag);
    $("mas").hidden = visibles >= n;

    const vacio = $("vacio");
    vacio.hidden = n > 0;
    if (!n) {
      vacio.innerHTML = ofertas.length
        ? `<p>No hay ofertas con estos filtros ahora mismo.</p><button class="boton secundario" type="button" id="vacio-limpiar">Quitar filtros</button>`
        : `<p>Todavía no se han descargado ofertas. Aparecerán aquí tras la primera actualización.</p>`;
      const b = $("vacio-limpiar");
      if (b) b.onclick = () => { estado.deps.clear(); limpiarFiltros(); };
    }
  }

  function pintarActivos() {
    const cont = $("activos");
    cont.innerHTML = "";
    const pastilla = (texto, quitar) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "quitar"; b.textContent = texto;
      b.setAttribute("aria-label", `Quitar filtro ${texto}`);
      b.onclick = () => { quitar(); sincronizarSelects(); document.querySelectorAll(".casillas input").forEach((i) => (i.checked = estado.niveles.has(i.parentNode.dataset.clave))); cambio(); };
      cont.append(b);
    };
    if (estado.q) pastilla(`«${estado.q}»`, () => (estado.q = ""));
    if (estado.zona) pastilla(estado.zona === "es" ? "España" : "Resto de Europa", () => (estado.zona = ""));
    if (estado.pais) pastilla(estado.pais, () => (estado.pais = ""));
    if (estado.empresa) pastilla(estado.empresa, () => (estado.empresa = ""));
    estado.niveles.forEach((k) => pastilla(meta.niveles[k], () => estado.niveles.delete(k)));
    if (estado.dias) pastilla({ 1: "Últimas 24 h", 7: "Última semana", 30: "Último mes" }[estado.dias], () => (estado.dias = ""));
  }

  function cuentasCasillas(id, cuentas) {
    document.querySelectorAll(`#${id} label`).forEach((l) => {
      l.querySelector(".cuenta").textContent = fmt(cuentas[l.dataset.clave] || 0);
    });
  }

  const tpl = $("tpl-oferta");
  function tarjeta(o) {
    const el = tpl.content.firstElementChild.cloneNode(true);
    const a = el.querySelector(".oferta-enlace");
    a.href = o.url;
    const av = el.querySelector(".avatar");
    av.textContent = iniciales(o.empresa);
    av.style.setProperty("--color", colorDe(o.empresa));
    el.querySelector(".empresa").textContent = o.empresa;
    const f = el.querySelector(".fecha");
    const dias = o.fecha ? diasDesde(o.fecha) : null;
    f.textContent = dias === null ? "" : dias <= 2 ? (dias <= 0 ? "Nueva · hoy" : dias === 1 ? "Nueva · ayer" : "Nueva") : haceCuanto(dias);
    f.classList.toggle("nueva", dias !== null && dias <= 2);
    el.querySelector(".titulo").textContent = limpiarTitulo(o.titulo);
    el.querySelector(".lugar").textContent = lugar(o);
    const et = el.querySelector(".etiquetas");
    const etiqueta = (texto, clase = "") => { const s = document.createElement("span"); s.className = "etiqueta " + clase; s.textContent = texto; et.append(s); };
    if (o.departamento !== "otros") etiqueta(nombreDep(o.departamento), "dep");
    if (o.nivel && o.nivel !== "intermedio") etiqueta(meta.niveles[o.nivel], o.nivel === "practicas" ? "practicas" : "");
    if (o.modalidad && o.modalidad !== "sin_indicar" && o.modalidad !== "presencial") etiqueta(meta.modalidades[o.modalidad]);
    return el;
  }

  function puente() {
    const li = document.createElement("li");
    li.innerHTML = `<a class="puente" href="${TEST_URL}">
      <div><p class="puente-titulo">¿No sabes qué departamento <em>encaja contigo</em>?</p>
      <p class="puente-texto">Haz el test de salidas científicas: 20 preguntas y descubres tus áreas con más afinidad.</p></div>
      <span class="boton">Hacer el test</span></a>`;
    return li;
  }

  const iniciales = (e) => {
    const limpio = e.replace(/\(.*?\)/g, "").replace(/&/g, " ").trim();
    const p = limpio.split(/\s+/).filter((x) => /^[A-Za-zÀ-ÿ]/.test(x));
    if (/^[A-Z]{2,5}$/.test(limpio)) return limpio.slice(0, 3);
    return (p.length > 1 ? p[0][0] + p[1][0] : limpio.slice(0, 2)).toUpperCase();
  };
  const colorDe = (e) => { let h = 0; for (const c of e) h = (h * 31 + c.charCodeAt(0)) >>> 0; return COLORES[h % COLORES.length]; };
  const limpiarTitulo = (t) => t.replace(/\s*\((m\/w\/d|m\/f\/d|f\/m\/d|w\/m\/d|all genders|h\/f|f\/h|m\/f|w\/m\/d\/x)\)\s*/gi, " ").trim();

  function lugar(o) {
    const u = (o.ubicacion || "").trim();
    if (!u || /^\d+\s+locat/i.test(u)) return o.pais + (o.otras_ubicaciones ? " · varias ubicaciones" : "");
    return (u.includes(o.pais) || /,|^[A-Z]{2}\s*-/.test(u)) ? u : `${u} (${o.pais})`;
  }

  function diasDesde(fecha) {
    return Math.floor((Date.now() - new Date(fecha + "T12:00:00").getTime()) / 86400000);
  }
  function haceCuanto(dias) {
    if (dias < 30) return `hace ${dias} días`;
    if (dias < 60) return "hace 1 mes";
    return `hace ${Math.floor(dias / 30)} meses`;
  }
  const escapar = (t) => t.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ---------------------------------------------------------------- pie
  function pintarPie() {
    if (meta.actualizado) {
      const f = new Date(meta.actualizado);
      $("actualizado").textContent = `Actualizado el ${f.toLocaleDateString("es-ES", { day: "numeric", month: "long" })} a las ${f.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}.`;
    } else {
      $("actualizado").textContent = "Aún no hay ninguna actualización.";
    }
    fetch("data/status.json", { cache: "no-cache" }).then((r) => r.json()).then((s) => {
      const ul = $("fuentes");
      ul.innerHTML = "";
      (s.fuentes || []).sort((a, b) => a.empresa.localeCompare(b.empresa, "es")).forEach((f) => {
        const li = document.createElement("li");
        li.textContent = f.ok ? `${f.empresa} — ${fmt(f.ofertas)}` : `${f.empresa} — no disponible hoy`;
        if (!f.ok) li.className = "ko";
        ul.append(li);
      });
    }).catch(() => {});
  }

  // ---------------------------------------------------------------- enlace compartible
  function escribirHash() {
    const p = new URLSearchParams();
    if (estado.deps.size) p.set("dep", [...estado.deps].join(","));
    if (estado.zona) p.set("zona", estado.zona);
    if (estado.pais) p.set("pais", estado.pais);
    if (estado.empresa) p.set("empresa", estado.empresa);
    if (estado.niveles.size) p.set("nivel", [...estado.niveles].join(","));
    if (estado.dias) p.set("dias", estado.dias);
    if (estado.q) p.set("q", estado.q);
    if (estado.orden !== "fecha") p.set("orden", estado.orden);
    const h = p.toString();
    history.replaceState(null, "", h ? "#" + h : location.pathname + location.search);
  }

  function leerHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    const lista = (k) => (p.get(k) || "").split(",").filter(Boolean);
    estado.deps = new Set(lista("dep"));
    estado.niveles = new Set(lista("nivel"));
    estado.zona = p.get("zona") || "";
    estado.pais = p.get("pais") || "";
    estado.empresa = p.get("empresa") || "";
    estado.dias = p.get("dias") || "";
    estado.q = p.get("q") || "";
    estado.orden = p.get("orden") || "fecha";
  }

  cargar();
})();
