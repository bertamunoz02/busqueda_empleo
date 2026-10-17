(() => {
  "use strict";

  const POR_PAGINA = 30;
  const $ = (id) => document.getElementById(id);

  const estado = {
    deps: new Set(), zona: "", pais: "", empresa: "",
    niveles: new Set(), modalidades: new Set(), dias: "", q: "", orden: "fecha",
  };
  let ofertas = [];
  let meta = {};
  let visibles = POR_PAGINA;

  const normalizar = (t) => (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const fmtNum = (n) => n.toLocaleString("es-ES");

  // ---------- Carga
  async function cargar() {
    try {
      const r = await fetch("data/jobs.json", { cache: "no-cache" });
      const datos = await r.json();
      meta = datos.meta || {};
      ofertas = (datos.ofertas || []).map((o) => ({
        ...o,
        _texto: normalizar([o.titulo, o.empresa, o.ubicacion, o.otras_ubicaciones, o.descripcion].join(" ")),
      }));
    } catch (e) {
      ofertas = [];
    }
    leerHash();
    montarControles();
    pintar();
    pintarPie();
  }

  // ---------- Filtros
  function cumple(o, ignorar) {
    if (ignorar !== "dep" && estado.deps.size && !estado.deps.has(o.departamento)) return false;
    if (estado.zona === "es" && o.pais !== "España") return false;
    if (estado.zona === "eu" && o.pais === "España") return false;
    if (estado.pais && o.pais !== estado.pais) return false;
    if (estado.empresa && o.empresa !== estado.empresa) return false;
    if (ignorar !== "nivel" && estado.niveles.size && !estado.niveles.has(o.nivel)) return false;
    if (ignorar !== "modalidad" && estado.modalidades.size && !estado.modalidades.has(o.modalidad)) return false;
    if (estado.dias) {
      if (!o.fecha) return false;
      const limite = Date.now() - Number(estado.dias) * 86400000 - 86400000;
      if (new Date(o.fecha).getTime() < limite) return false;
    }
    if (estado.q) {
      const terminos = normalizar(estado.q).split(/\s+/).filter(Boolean);
      if (!terminos.every((t) => o._texto.includes(t))) return false;
    }
    return true;
  }

  const contar = (lista, campo) => lista.reduce((m, o) => (m[o[campo]] = (m[o[campo]] || 0) + 1, m), {});

  // ---------- Controles
  function montarControles() {
    // Departamentos, ordenados por número de ofertas
    const totales = contar(ofertas, "departamento");
    const deps = Object.keys(meta.departamentos || {})
      .sort((a, b) => (a === "otros") - (b === "otros") || (totales[b] || 0) - (totales[a] || 0));
    $("departamentos").innerHTML = "";
    const todos = boton("Todos", "", () => { estado.deps.clear(); cambio(); });
    todos.dataset.dep = "";
    $("departamentos").append(todos);
    deps.forEach((d) => {
      const b = boton(meta.departamentos[d], d, () => {
        estado.deps.has(d) ? estado.deps.delete(d) : estado.deps.add(d);
        cambio();
      });
      b.dataset.dep = d;
      $("departamentos").append(b);
    });

    // Países y empresas
    const paises = [...new Set(ofertas.map((o) => o.pais))].sort((a, b) =>
      (b === "España") - (a === "España") || a.localeCompare(b, "es"));
    llenarSelect($("pais"), paises, "Cualquier país", estado.pais);
    const empresas = [...new Set(ofertas.map((o) => o.empresa))].sort((a, b) => a.localeCompare(b, "es"));
    llenarSelect($("empresa"), empresas, "Todas las empresas", estado.empresa);

    casillas($("nivel"), meta.niveles || {}, estado.niveles, "nivel",
      ["practicas", "graduado", "intermedio", "senior", "direccion"]);
    casillas($("modalidad"), meta.modalidades || {}, estado.modalidades, "modalidad",
      ["presencial", "hibrido", "remoto", "sin_indicar"]);

    $("q").value = estado.q;
    $("dias").value = estado.dias;
    $("orden").value = estado.orden;

    let temporizador;
    $("q").oninput = (e) => { clearTimeout(temporizador); temporizador = setTimeout(() => { estado.q = e.target.value.trim(); cambio(); }, 200); };
    $("pais").onchange = (e) => { estado.pais = e.target.value; if (estado.pais) estado.zona = ""; cambio(); };
    $("empresa").onchange = (e) => { estado.empresa = e.target.value; cambio(); };
    $("dias").onchange = (e) => { estado.dias = e.target.value; cambio(); };
    $("orden").onchange = (e) => { estado.orden = e.target.value; cambio(); };
    document.querySelectorAll("#zona button").forEach((b) => {
      b.onclick = () => { estado.zona = b.dataset.zona; estado.pais = ""; $("pais").value = ""; cambio(); };
    });
    $("limpiar").onclick = () => {
      Object.assign(estado, { zona: "", pais: "", empresa: "", dias: "", q: "" });
      estado.niveles.clear(); estado.modalidades.clear();
      $("q").value = ""; $("pais").value = ""; $("empresa").value = ""; $("dias").value = "";
      document.querySelectorAll(".casillas input").forEach((i) => (i.checked = false));
      cambio();
    };
    $("mas").onclick = () => { visibles += POR_PAGINA; pintar(false); };
    document.querySelector(".abrir-filtros").onclick = (e) => {
      const panel = $("panel-filtros");
      const abierto = panel.classList.toggle("abierto");
      e.currentTarget.setAttribute("aria-expanded", abierto);
    };
  }

  function boton(texto, clave, alPulsar) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.innerHTML = `<span></span><span class="cuenta"></span>`;
    b.firstChild.textContent = texto;
    b.onclick = alPulsar;
    return b;
  }

  function llenarSelect(sel, valores, vacio, actual) {
    sel.innerHTML = "";
    sel.append(new Option(vacio, ""));
    valores.forEach((v) => sel.append(new Option(v, v)));
    sel.value = valores.includes(actual) ? actual : "";
  }

  function casillas(cont, nombres, conjunto, campo, orden) {
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
  }

  // ---------- Pintado
  function pintar(reiniciar = true) {
    const filtradas = ofertas.filter((o) => cumple(o));
    if (estado.orden === "empresa") {
      filtradas.sort((a, b) => a.empresa.localeCompare(b.empresa, "es") || (b.fecha || "").localeCompare(a.fecha || ""));
    }

    // Recuentos en chips y casillas (teniendo en cuenta el resto de filtros)
    const porDep = contar(ofertas.filter((o) => cumple(o, "dep")), "departamento");
    document.querySelectorAll("#departamentos .chip").forEach((b) => {
      const d = b.dataset.dep;
      const n = d ? porDep[d] || 0 : Object.values(porDep).reduce((a, x) => a + x, 0);
      b.querySelector(".cuenta").textContent = fmtNum(n);
      b.classList.toggle("cero", n === 0);
      b.setAttribute("aria-pressed", d ? estado.deps.has(d) : estado.deps.size === 0);
    });
    actualizarCuentas("nivel", contar(ofertas.filter((o) => cumple(o, "nivel")), "nivel"));
    actualizarCuentas("modalidad", contar(ofertas.filter((o) => cumple(o, "modalidad")), "modalidad"));
    document.querySelectorAll("#zona button").forEach((b) =>
      b.setAttribute("aria-pressed", b.dataset.zona === estado.zona && !estado.pais));

    // Contador de filtros activos (móvil)
    const activos = [estado.zona || estado.pais, estado.empresa, estado.dias, estado.q].filter(Boolean).length
      + estado.niveles.size + estado.modalidades.size;
    $("n-filtros").hidden = !activos;
    $("n-filtros").textContent = activos;

    // Lista
    const n = filtradas.length;
    $("n-res").textContent = ofertas.length
      ? `${fmtNum(n)} ${n === 1 ? "oferta abierta" : "ofertas abiertas"}`
      : "Sin datos todavía";
    const lista = $("lista");
    if (reiniciar) lista.innerHTML = "";
    const desde = lista.children.length;
    const frag = document.createDocumentFragment();
    filtradas.slice(desde, visibles).forEach((o) => frag.append(tarjeta(o)));
    lista.append(frag);
    $("mas").hidden = visibles >= n;

    const vacio = $("vacio");
    vacio.hidden = n > 0;
    if (!n) {
      vacio.textContent = ofertas.length
        ? "No hay ofertas con estos filtros ahora mismo. Prueba a quitar alguno o a ampliar a toda Europa."
        : "Todavía no se han descargado ofertas. En cuanto se ejecute la primera actualización aparecerán aquí.";
    }
  }

  function actualizarCuentas(id, cuentas) {
    document.querySelectorAll(`#${id} label`).forEach((l) => {
      l.querySelector(".cuenta").textContent = fmtNum(cuentas[l.dataset.clave] || 0);
    });
  }

  const tpl = $("tpl-oferta");
  function tarjeta(o) {
    const el = tpl.content.firstElementChild.cloneNode(true);
    el.querySelector(".dep").textContent = (meta.departamentos || {})[o.departamento] || o.departamento;
    const t = el.querySelector(".fecha");
    t.textContent = haceCuanto(o.fecha);
    if (o.fecha) t.dateTime = o.fecha;
    const a = el.querySelector(".titulo");
    a.textContent = o.titulo;
    a.href = o.url;
    el.querySelector(".empresa").textContent = o.empresa;
    el.querySelector(".lugar").textContent = lugar(o);
    const extra = [
      (meta.niveles || {})[o.nivel],
      o.modalidad !== "sin_indicar" ? (meta.modalidades || {})[o.modalidad] : "",
      traducirJornada(o.jornada),
    ].filter(Boolean);
    const p = el.querySelector(".extra");
    extra.forEach((x) => { const s = document.createElement("span"); s.textContent = x; p.append(s); });
    return el;
  }

  function lugar(o) {
    const u = (o.ubicacion || "").trim();
    if (!u || /^\d+\s+locat/i.test(u)) return o.pais + (o.otras_ubicaciones ? " · varias ubicaciones" : "");
    return (u.includes(o.pais) || /,|^[A-Z]{2}\s*-/.test(u)) ? u : `${u} (${o.pais})`;
  }

  function traducirJornada(j) {
    const t = normalizar(j);
    if (!t) return "";
    if (t.includes("full")) return "Jornada completa";
    if (t.includes("part")) return "Jornada parcial";
    if (t.includes("temp") || t.includes("fixed")) return "Temporal";
    return j;
  }

  function haceCuanto(fecha) {
    if (!fecha) return "";
    const dias = Math.floor((Date.now() - new Date(fecha + "T12:00:00").getTime()) / 86400000);
    if (dias <= 0) return "hoy";
    if (dias === 1) return "ayer";
    if (dias < 30) return `hace ${dias} días`;
    if (dias < 60) return "hace 1 mes";
    return `hace ${Math.floor(dias / 30)} meses`;
  }

  function pintarPie() {
    if (meta.actualizado) {
      const f = new Date(meta.actualizado);
      $("actualizado").textContent = `Última actualización: ${f.toLocaleDateString("es-ES", { day: "numeric", month: "long", year: "numeric" })}, ${f.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })} · ${fmtNum(meta.total || 0)} ofertas.`;
    } else {
      $("actualizado").textContent = "Aún no hay ninguna actualización.";
    }
    fetch("data/status.json", { cache: "no-cache" }).then((r) => r.json()).then((s) => {
      const ul = $("fuentes");
      ul.innerHTML = "";
      (s.fuentes || []).sort((a, b) => a.empresa.localeCompare(b.empresa, "es")).forEach((f) => {
        const li = document.createElement("li");
        li.textContent = f.ok ? `${f.empresa} — ${fmtNum(f.ofertas)} ofertas` : `${f.empresa} — no disponible hoy`;
        if (!f.ok) li.className = "ko";
        ul.append(li);
      });
    }).catch(() => {});
  }

  // ---------- Enlace compartible (los filtros viajan en la URL)
  function escribirHash() {
    const p = new URLSearchParams();
    if (estado.deps.size) p.set("dep", [...estado.deps].join(","));
    if (estado.zona) p.set("zona", estado.zona);
    if (estado.pais) p.set("pais", estado.pais);
    if (estado.empresa) p.set("empresa", estado.empresa);
    if (estado.niveles.size) p.set("nivel", [...estado.niveles].join(","));
    if (estado.modalidades.size) p.set("modalidad", [...estado.modalidades].join(","));
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
    estado.modalidades = new Set(lista("modalidad"));
    estado.zona = p.get("zona") || "";
    estado.pais = p.get("pais") || "";
    estado.empresa = p.get("empresa") || "";
    estado.dias = p.get("dias") || "";
    estado.q = p.get("q") || "";
    estado.orden = p.get("orden") || "fecha";
  }

  cargar();
})();
