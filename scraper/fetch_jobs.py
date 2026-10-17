"""Lee los portales de empleo de sources.json, se queda con las ofertas de
España y del resto de Europa, las clasifica y escribe data/jobs.json y
data/status.json. Solo usa la librería estándar de Python.

Uso:  python scraper/fetch_jobs.py
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import classify  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data"
UA = "Mozilla/5.0 (compatible; EmpleoFarmaBot/1.0; +https://github.com)"
MAX_POR_EMPRESA = 1500
HILOS_DETALLE = 6

# Nombre en español -> variantes con las que suelen aparecer en los portales.
PAISES = {
    "España": ["spain", "espana", "españa", "spanien", "espagne", "spagna", "es"],
    "Portugal": ["portugal", "pt"],
    "Francia": ["france", "francia", "frankreich", "fr"],
    "Italia": ["italy", "italia", "italien", "italie", "it"],
    "Alemania": ["germany", "alemania", "deutschland", "allemagne", "de"],
    "Suiza": ["switzerland", "suiza", "schweiz", "suisse", "svizzera", "ch"],
    "Austria": ["austria", "osterreich", "österreich", "autriche", "at"],
    "Bélgica": ["belgium", "belgica", "bélgica", "belgien", "belgique", "be"],
    "Países Bajos": ["netherlands", "paises bajos", "países bajos", "holland", "niederlande", "pays-bas", "nl"],
    "Luxemburgo": ["luxembourg", "luxemburgo", "lu"],
    "Irlanda": ["ireland", "irlanda", "irland", "irlande", "ie"],
    "Reino Unido": ["united kingdom", "reino unido", "uk", "gb", "great britain", "england", "scotland", "wales", "northern ireland"],
    "Dinamarca": ["denmark", "dinamarca", "dänemark", "danemark", "dk"],
    "Suecia": ["sweden", "suecia", "schweden", "suède", "se"],
    "Noruega": ["norway", "noruega", "norwegen", "no"],
    "Finlandia": ["finland", "finlandia", "finnland", "fi"],
    "Polonia": ["poland", "polonia", "polen", "pologne", "pl"],
    "Chequia": ["czech republic", "czechia", "chequia", "república checa", "tschechien", "cz"],
    "Eslovaquia": ["slovakia", "eslovaquia", "sk"],
    "Hungría": ["hungary", "hungria", "hungría", "ungarn", "hu"],
    "Rumanía": ["romania", "rumania", "rumanía", "rumänien", "ro"],
    "Bulgaria": ["bulgaria", "bg"],
    "Grecia": ["greece", "grecia", "griechenland", "gr"],
    "Croacia": ["croatia", "croacia", "hr"],
    "Eslovenia": ["slovenia", "eslovenia", "si"],
    "Serbia": ["serbia", "rs"],
    "Lituania": ["lithuania", "lituania", "lt"],
    "Letonia": ["latvia", "letonia", "lv"],
    "Estonia": ["estonia", "ee"],
    "Islandia": ["iceland", "islandia", "is"],
    "Malta": ["malta", "mt"],
    "Chipre": ["cyprus", "chipre", "cy"],
}

# Ciudades frecuentes en farma, por si el portal solo da la ciudad.
CIUDADES = {
    "España": ["madrid", "barcelona", "sant cugat", "alcobendas", "san sebastian de los reyes",
               "tres cantos", "alcala de henares", "getafe", "leganes", "valencia", "sevilla",
               "granada", "bilbao", "zaragoza", "parets del valles", "sant joan despi",
               "el prat", "l'hospitalet", "cornella", "aranjuez", "toledo", "guadalajara",
               "san agustin de guadalix", "pozuelo"],
    "Suiza": ["basel", "basilea", "zurich", "geneva", "ginebra", "zug", "lausanne", "bern"],
    "Alemania": ["berlin", "munich", "münchen", "frankfurt", "mainz", "darmstadt", "leverkusen",
                 "hamburg", "ingelheim", "biberach", "marburg", "wuppertal", "cologne", "köln"],
    "Francia": ["paris", "lyon", "gentilly", "marcy-l'etoile", "rueil-malmaison", "courbevoie"],
    "Bélgica": ["brussels", "bruselas", "bruxelles", "wavre", "beerse", "rixensart"],
    "Irlanda": ["dublin", "cork", "limerick", "carlow"],
    "Reino Unido": ["london", "londres", "cambridge", "macclesfield", "stevenage", "brentford",
                    "oxford", "edinburgh", "glasgow", "manchester", "ware", "slough"],
    "Italia": ["milan", "milano", "rome", "roma", "siena", "verona", "latina"],
    "Países Bajos": ["amsterdam", "leiden", "utrecht", "rotterdam", "oss", "breda"],
    "Portugal": ["lisbon", "lisboa", "porto", "oporto"],
    "Dinamarca": ["copenhagen", "copenhague", "bagsværd", "kalundborg"],
    "Suecia": ["stockholm", "gothenburg", "göteborg", "södertälje", "uppsala"],
    "Polonia": ["warsaw", "varsovia", "warszawa", "krakow", "cracovia", "poznan", "lodz"],
}

# Para no confundir Cambridge (MA), Valencia (Venezuela), Guadalajara (México)...
NO_EUROPA = re.compile(r"\b(united states|usa|u\.s\.|estados unidos|canada|mexico|méxico|brazil|brasil|"
                       r"argentina|colombia|chile|peru|perú|venezuela|nicaragua|china|japan|india|"
                       r"singapore|australia|korea|philippines|filipinas|south africa|puerto rico|"
                       r"massachusetts|new jersey|california|pennsylvania|north carolina|texas|illinois)\b")

_alias = []
for pais, variantes in list(PAISES.items()) + list(CIUDADES.items()):
    for v in variantes:
        _alias.append((pais, v.lower(), len(v) <= 2))


def pais_de(texto):
    """Devuelve el país europeo que aparece en el texto, o None."""
    if not texto:
        return None
    if ";" in texto:  # varias ubicaciones: nos vale la primera europea
        for parte in texto.split(";"):
            p = pais_de(parte)
            if p:
                return p
        return None
    t = texto.lower()
    if NO_EUROPA.search(t) or re.search(r",\s*[A-Z]{2}\s*,\s*(US|USA)\b", texto):
        return None
    # Primero nombres largos (más fiables), luego códigos de 2 letras en formato "ES-Madrid" o ", ES"
    for pais, v, corto in _alias:
        if not corto and re.search(r"(?<![a-zà-ÿ])" + re.escape(v) + r"(?![a-zà-ÿ])", t):
            return pais
    # Códigos de 2 letras solo en mayúsculas y en posiciones típicas: "ES-Madrid", "Madrid, ES", "(ES)"
    for pais, v, corto in _alias:
        if corto:
            c = v.upper()
            if re.search(r"(^" + c + r"\s*[-–:]|[,(]\s*" + c + r"\s*\)?\s*$|\(" + c + r"\))", texto.strip()):
                return pais
    return None


def http(url, datos=None, intentos=3):
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    cabeceras = {"User-Agent": UA, "Accept": "application/json",
                 "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"}
    if cuerpo is not None:
        cabeceras["Content-Type"] = "application/json"
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, data=cuerpo, headers=cabeceras)
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404, 422) or i == intentos - 1:
                raise
        except Exception:
            if i == intentos - 1:
                raise
        time.sleep(2 * (i + 1))


def http_texto(url, intentos=3):
    cabeceras = {"User-Agent": UA, "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8",
                 "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"}
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers=cabeceras)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404, 410) or i == intentos - 1:
                raise
        except Exception:
            if i == intentos - 1:
                raise
        time.sleep(2 * (i + 1))


def limpiar_html(html, n=600):
    texto = re.sub(r"<[^>]+>", " ", html or "")
    texto = re.sub(r"&nbsp;|&#160;", " ", texto)
    texto = re.sub(r"&amp;", "&", texto)
    texto = re.sub(r"&[a-z#0-9]+;", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()[:n]


def fecha_relativa(posted_on, hoy):
    """Workday da 'Posted Today', 'Posted 3 Days Ago', 'Posted 30+ Days Ago'."""
    t = (posted_on or "").lower()
    if "today" in t or "hoy" in t:
        return hoy.date().isoformat()
    if "yesterday" in t or "ayer" in t:
        return (hoy - timedelta(days=1)).date().isoformat()
    m = re.search(r"(\d+)\+?\s*(day|día|dia)", t)
    if m:
        return (hoy - timedelta(days=int(m.group(1)))).date().isoformat()
    return None


# ---------------------------------------------------------------- Workday

def _facetas_europa(facetas):
    """Busca en las facetas de Workday los valores de país/ubicación europeos."""
    elegidas = {}

    def recorrer(lista, parametro):
        for f in lista or []:
            param = f.get("facetParameter") or parametro
            if f.get("values"):
                recorrer(f["values"], param)
            elif f.get("id") and f.get("descriptor"):
                if param and re.search(r"countr|locationmain|location_country", param, re.I):
                    if pais_de(f["descriptor"]):
                        elegidas.setdefault(param, []).append(f["id"])

    recorrer(facetas, None)
    # Preferimos la faceta de país si existe
    for clave in sorted(elegidas, key=lambda k: 0 if "ountr" in k else 1):
        return {clave: elegidas[clave]}
    return {}


def workday(fuente, hoy):
    base = f"https://{fuente['host']}/wday/cxs/{fuente['tenant']}/{fuente['site']}"
    web = f"https://{fuente['host']}/{fuente['site']}"
    primera = http(base + "/jobs", {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""})
    facetas = _facetas_europa(primera.get("facets"))
    filtrado_por_faceta = bool(facetas)

    resumenes, offset, total, limite = [], 0, None, 100
    while True:
        try:
            pag = http(base + "/jobs", {"appliedFacets": facetas, "limit": limite,
                                         "offset": offset, "searchText": ""})
        except urllib.error.HTTPError as e:
            if e.code == 400 and limite > 20:  # algunos portales solo aceptan 20 por página
                limite = 20
                continue
            raise
        if total is None:
            total = pag.get("total", 0)
        items = pag.get("jobPostings") or []
        if not items:
            break
        resumenes.extend(items)
        offset += len(items)
        if offset >= min(total, MAX_POR_EMPRESA):
            break
        time.sleep(0.3)

    # Sin faceta de país: descartamos lo que claramente no es europeo antes de pedir detalles
    if not filtrado_por_faceta:
        resumenes = [r for r in resumenes
                     if pais_de(r.get("locationsText")) or re.search(r"\d+\s+locat", r.get("locationsText", ""), re.I)]

    def detalle(r):
        try:
            d = http(base + r["externalPath"]).get("jobPostingInfo", {})
        except Exception:
            d = {}
        ubic = d.get("location") or r.get("locationsText") or ""
        extra = " ".join(d.get("additionalLocations") or [])
        pais = (pais_de(d.get("country", {}).get("descriptor") if isinstance(d.get("country"), dict) else "")
                or pais_de(ubic) or pais_de(extra))
        if not pais:
            return None
        desc = limpiar_html(d.get("jobDescription", ""))
        return {
            "titulo": r.get("title") or d.get("title", ""),
            "empresa": fuente["empresa"],
            "ubicacion": ubic,
            "otras_ubicaciones": extra,
            "pais": pais,
            "fecha": d.get("startDate") or fecha_relativa(r.get("postedOn"), hoy),
            "url": d.get("externalUrl") or (web + r["externalPath"]),
            "jornada": d.get("timeType", ""),
            "remoto": d.get("remoteType", ""),
            "descripcion": desc,
        }

    with ThreadPoolExecutor(HILOS_DETALLE) as ex:
        return [o for o in ex.map(detalle, resumenes) if o]


# ---------------------------------------------------------------- Greenhouse

def greenhouse(fuente, hoy):
    datos = http(f"https://boards-api.greenhouse.io/v1/boards/{fuente['token']}/jobs?content=true")
    ofertas = []
    for j in datos.get("jobs", []):
        ubic = (j.get("location") or {}).get("name", "")
        pais = pais_de(ubic)
        if not pais:
            continue
        ofertas.append({
            "titulo": j.get("title", ""), "empresa": fuente["empresa"], "ubicacion": ubic,
            "otras_ubicaciones": "", "pais": pais,
            "fecha": (j.get("updated_at") or "")[:10] or None,
            "url": j.get("absolute_url", ""), "jornada": "", "remoto": "",
            "categoria": ", ".join(d.get("name", "") for d in j.get("departments", [])),
            "descripcion": limpiar_html(j.get("content", "")),
        })
    return ofertas


# ---------------------------------------------------------------- Lever

def lever(fuente, hoy):
    datos = http(f"https://api.lever.co/v0/postings/{fuente['empresa_id']}?mode=json")
    ofertas = []
    for j in datos:
        cat = j.get("categories") or {}
        ubic = cat.get("location", "")
        pais = pais_de(ubic) or pais_de(j.get("country", ""))
        if not pais:
            continue
        creado = j.get("createdAt")
        ofertas.append({
            "titulo": j.get("text", ""), "empresa": fuente["empresa"], "ubicacion": ubic,
            "otras_ubicaciones": "", "pais": pais,
            "fecha": datetime.fromtimestamp(creado / 1000, timezone.utc).date().isoformat() if creado else None,
            "url": j.get("hostedUrl", ""), "jornada": cat.get("commitment", ""),
            "remoto": j.get("workplaceType", ""), "categoria": cat.get("team", ""),
            "descripcion": limpiar_html(j.get("descriptionPlain", "")),
        })
    return ofertas


# ---------------------------------------------------------------- SmartRecruiters

def smartrecruiters(fuente, hoy):
    ofertas, offset = [], 0
    while True:
        datos = http(f"https://api.smartrecruiters.com/v1/companies/{fuente['empresa_id']}/postings"
                     f"?limit=100&offset={offset}")
        items = datos.get("content", [])
        for j in items:
            loc = j.get("location") or {}
            ubic = ", ".join(x for x in [loc.get("city"), loc.get("country")] if x)
            pais = pais_de(loc.get("country", "")) or pais_de(ubic)
            if not pais:
                continue
            ofertas.append({
                "titulo": j.get("name", ""), "empresa": fuente["empresa"], "ubicacion": ubic,
                "otras_ubicaciones": "", "pais": pais,
                "fecha": (j.get("releasedDate") or "")[:10] or None,
                "url": f"https://jobs.smartrecruiters.com/{fuente['empresa_id']}/{j.get('id')}",
                "jornada": (j.get("typeOfEmployment") or {}).get("label", ""),
                "remoto": "remote" if loc.get("remote") else "",
                "categoria": (j.get("function") or {}).get("label", ""),
                "descripcion": "",
            })
        offset += len(items)
        if not items or offset >= datos.get("totalFound", 0):
            break
    return ofertas



# ---------------------------------------------------------------- Sitemap + JSON-LD (Phenom y similares)
#
# Para portales cuya búsqueda funciona con JavaScript: el sitemap lista todas las
# ofertas y cada página de oferta lleva un bloque JSON-LD (JobPosting) con la
# ubicación. Como pedir miles de páginas cada día es lento, se guarda una caché
# en data/cache/ y solo se descargan las ofertas nuevas.

CACHE = DATOS / "cache"
MAX_NUEVAS_POR_EMPRESA = 3000


def _urls_sitemap(url, vistos=None):
    vistos = vistos if vistos is not None else set()
    if url in vistos:
        return []
    vistos.add(url)
    xml = http_texto(url)
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
    if "<sitemapindex" in xml:
        urls = []
        for hijo in locs:
            urls.extend(_urls_sitemap(hijo.replace("&amp;", "&"), vistos))
        return urls
    return [u.replace("&amp;", "&") for u in locs]


def _sitemaps(fuente):
    """'sitemap' puede ser una URL o un patrón con {n} (sitemap1.xml, sitemap2.xml...)."""
    patron = fuente["sitemap"]
    if "{n}" not in patron:
        return _urls_sitemap(patron)
    urls = []
    for n in range(1, 101):
        try:
            nuevas = _urls_sitemap(patron.format(n=n))
        except urllib.error.HTTPError:
            break
        if not nuevas:
            break
        urls.extend(nuevas)
    return urls


def _jobposting(html):
    for bloque in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            datos = json.loads(bloque.strip())
        except Exception:
            continue
        pila = [datos]
        while pila:
            d = pila.pop()
            if isinstance(d, list):
                pila.extend(d)
            elif isinstance(d, dict):
                tipo = d.get("@type")
                if tipo == "JobPosting" or (isinstance(tipo, list) and "JobPosting" in tipo):
                    return d
                pila.extend(v for k, v in d.items() if k == "@graph")
    return None


def _ubicaciones_jsonld(jp):
    locs = jp.get("jobLocation") or []
    if isinstance(locs, dict):
        locs = [locs]
    textos = []
    for l in locs:
        a = (l or {}).get("address") or {}
        if isinstance(a, str):
            textos.append(a)
            continue
        pais = a.get("addressCountry")
        if isinstance(pais, dict):
            pais = pais.get("name")
        partes = [a.get("addressLocality"), a.get("addressRegion"), pais]
        textos.append(", ".join(p for p in partes if p))
    return [t for t in textos if t]


def sitemap(fuente, hoy):
    patron = re.compile(fuente.get("patron_oferta", r"/job/"))
    urls = sorted({u for u in _sitemaps(fuente) if patron.search(u)})
    if not urls:
        raise RuntimeError("el sitemap no contiene URLs de ofertas")

    CACHE.mkdir(parents=True, exist_ok=True)
    archivo = CACHE / (re.sub(r"[^a-z0-9]+", "-", fuente["empresa"].lower()).strip("-") + ".json")
    try:
        cache = json.loads(archivo.read_text(encoding="utf-8"))
    except Exception:
        cache = {}

    nuevas = [u for u in urls if u not in cache][:MAX_NUEVAS_POR_EMPRESA]

    def leer(u):
        try:
            jp = _jobposting(http_texto(u))
        except Exception:
            return u, None  # se reintentará mañana
        if not jp:
            return u, {"fuera": True}
        ubics = _ubicaciones_jsonld(jp)
        pais = next((p for p in map(pais_de, ubics) if p), None)
        if not pais:
            return u, {"fuera": True}
        remoto = "remote" if str(jp.get("jobLocationType", "")).upper() == "TELECOMMUTE" else ""
        empleo = jp.get("employmentType") or ""
        return u, {
            "titulo": limpiar_html(jp.get("title", ""), 200),
            "empresa": fuente["empresa"],
            "ubicacion": ubics[0],
            "otras_ubicaciones": "; ".join(ubics[1:])[:200],
            "pais": pais,
            "fecha": (jp.get("datePosted") or "")[:10] or None,
            "url": u,
            "jornada": ", ".join(empleo) if isinstance(empleo, list) else empleo,
            "remoto": remoto,
            "categoria": jp.get("occupationalCategory") or jp.get("industry") or "",
            "descripcion": limpiar_html(jp.get("description", "")),
        }

    with ThreadPoolExecutor(HILOS_DETALLE) as ex:
        for u, dato in ex.map(leer, nuevas):
            if dato is not None:
                cache[u] = dato

    vigentes = set(urls)
    cache = {u: d for u, d in cache.items() if u in vigentes}  # olvidar ofertas cerradas
    archivo.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return [dict(d) for d in cache.values() if not d.get("fuera")]


# ---------------------------------------------------------------- Listados HTML (TalentBrew, Jobvite, webs propias)
#
# Recorre las páginas del buscador (plantilla de URL con {n}), localiza los
# enlaces a ofertas con 'patron_oferta' y lee el texto de la fila que los
# contiene (li, tr o div). Si en esa fila no aparece el país, abre la oferta y
# lo busca en su JSON-LD o en su texto (con caché, como en los sitemaps).

from html import unescape as _unescape
from urllib.parse import urljoin as _urljoin

MAX_PAGINAS = 300
MESES = {"jan": 1, "ene": 1, "feb": 2, "mar": 3, "apr": 4, "abr": 4, "may": 5, "jun": 6,
         "jul": 7, "aug": 8, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12, "dic": 12}


def _texto(html):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>|</(p|div|span|td|li|h\d)>", " | ", t, flags=re.I)
    t = _unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s*(\|\s*)+", " | ", re.sub(r"[ \t\r\n]+", " ", t)).strip(" |")


def _fecha_en_texto(t, mdy=False):
    m = re.search(r"\b(20\d\d)-(\d\d)-(\d\d)\b", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](20\d\d)\b", t)
    if m:
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if mdy or mth > 12:  # formato estadounidense (mes/día/año)
            d, mth = mth, d
        if 1 <= mth <= 12 and 1 <= d <= 31:
            return f"{y}-{mth:02d}-{d:02d}"
    m = re.search(r"\b([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(20\d\d)\b", t) or None
    if m and m.group(1).lower() in MESES:
        return f"{m.group(3)}-{MESES[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+(20\d\d)\b", t)
    if m and m.group(2).lower() in MESES:
        return f"{m.group(3)}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return None


def _filas(html, url_pagina, patron):
    """Devuelve [(url, titulo, texto_de_la_fila)] para cada enlace a oferta."""
    vistos, filas = set(), []
    for m in re.finditer(r'<a\b[^>]*?href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S | re.I):
        href = _unescape(m.group(1))
        if not patron.search(href):
            continue
        url = _urljoin(url_pagina, href).split("#")[0]
        titulo = _texto(m.group(2)).split(" | ")[0].strip()
        if url in vistos or len(titulo) < 3 or titulo.lower() in ("apply", "apply now", "ver oferta", "more", "view job"):
            continue
        vistos.add(url)
        ini = max(html.rfind(t, 0, m.start()) for t in ("<li", "<tr", "<article"))
        if ini < 0 or m.start() - ini > 4000:
            ini = max(0, m.start() - 1500)
        fins = [i for i in (html.find(t, m.end()) for t in ("</li>", "</tr>", "</article>")) if i != -1]
        fin = min(fins) if fins and min(fins) - m.end() < 4000 else m.end() + 1500
        fila = _texto(html[ini:fin])
        filas.append((url, titulo, fila))
    return filas


def _paginas(fuente):
    plantilla, inicio = fuente["url"], int(fuente.get("primera_pagina", 1))
    if "{n}" not in plantilla:
        yield plantilla
        return
    for n in range(inicio, inicio + MAX_PAGINAS):
        yield plantilla.format(n=n)


def _cargar_cache(fuente):
    CACHE.mkdir(parents=True, exist_ok=True)
    archivo = CACHE / (re.sub(r"[^a-z0-9]+", "-", fuente["empresa"].lower()).strip("-") + ".json")
    try:
        return archivo, json.loads(archivo.read_text(encoding="utf-8"))
    except Exception:
        return archivo, {}


def listado_html(fuente, hoy):
    patron = re.compile(fuente.get("patron_oferta", r"/job/"))
    encontradas, orden = {}, []
    for url_pag in _paginas(fuente):
        try:
            html = http_texto(url_pag)
        except urllib.error.HTTPError as e:
            if orden and e.code in (404, 410):
                break
            raise
        nuevas = [f for f in _filas(html, url_pag, patron) if f[0] not in encontradas]
        if not nuevas:
            break
        for url, titulo, fila in nuevas:
            encontradas[url] = (titulo, fila)
            orden.append(url)
        time.sleep(0.4)
    if not encontradas:
        raise RuntimeError("no se han encontrado enlaces a ofertas en el listado")

    archivo, cache = _cargar_cache(fuente)
    mdy = fuente.get("formato_fecha") == "mdy"

    def oferta(url, titulo, ubic, pais, fecha, extra=None):
        o = {"titulo": titulo, "empresa": fuente["empresa"], "ubicacion": ubic,
             "otras_ubicaciones": "", "pais": pais, "fecha": fecha, "url": url,
             "jornada": "", "remoto": "", "descripcion": ""}
        o.update(extra or {})
        return o

    def ubicacion_en_fila(titulo, fila):
        partes = [p.strip() for p in fila.split(" | ") if p.strip() and p.strip() != titulo]
        for p in partes:
            if len(p) < 80 and pais_de(p):
                return p, pais_de(p)
        return None, pais_de(fila.replace(titulo, " "))

    pendientes = []
    for url, (titulo, fila) in encontradas.items():
        ubic, pais = ubicacion_en_fila(titulo, fila)
        if pais:
            cache[url] = oferta(url, titulo, ubic or pais, pais, _fecha_en_texto(fila, mdy),
                                {"remoto": fila if re.search(r"remote|remoto|hybrid|h[ií]brido", fila, re.I) else ""})
        elif url not in cache:
            pendientes.append(url)
    pendientes = pendientes[:MAX_NUEVAS_POR_EMPRESA]

    def detalle(url):
        titulo, fila = encontradas[url]
        try:
            html = http_texto(url)
        except Exception:
            return url, None
        jp = _jobposting(html)
        if jp:
            ubics = _ubicaciones_jsonld(jp)
            pais = next((p for p in map(pais_de, ubics) if p), None)
            if not pais:
                return url, {"fuera": True}
            return url, oferta(url, limpiar_html(jp.get("title") or titulo, 200), ubics[0], pais,
                               (jp.get("datePosted") or "")[:10] or _fecha_en_texto(fila, mdy),
                               {"descripcion": limpiar_html(jp.get("description", "")),
                                "categoria": jp.get("occupationalCategory") or ""})
        texto = _texto(html)[:8000]
        # Sin JSON-LD solo damos por buena la oferta si el país aparece junto a "location/ubicación"
        # (el texto completo de la página no sirve: los menús y pies suelen listar países).
        for m in re.finditer(r"(location|locations|ubicaci[oó]n|localizaci[oó]n|city|country|pa[ií]s)\s*[:|]\s*([^|]{2,80})", texto, re.I):
            if pais_de(m.group(2)):
                return url, oferta(url, titulo, m.group(2).strip(), pais_de(m.group(2)), _fecha_en_texto(fila, mdy))
        return url, {"fuera": True}

    with ThreadPoolExecutor(HILOS_DETALLE) as ex:
        for url, dato in ex.map(detalle, pendientes):
            if dato is not None:
                cache[url] = dato

    cache = {u: d for u, d in cache.items() if u in encontradas}
    archivo.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return [dict(d) for d in cache.values() if not d.get("fuera")]


# ---------------------------------------------------------------- API JSON propia (Medpace y similares)
#
# Lee una URL que devuelve JSON con una lista de ofertas y adivina los campos
# por su nombre. Se pueden fijar a mano con "campos": {"titulo": "...", ...}.

CANDIDATOS = {
    "titulo": ["title", "job_title", "jobTitle", "name", "position", "titulo"],
    "ubicacion": ["location", "locations", "job_location", "city_state_country", "full_location",
                  "locationName", "location_name", "office", "city"],
    "pais": ["country", "country_name", "countryName", "country_code"],
    "fecha": ["posted_date", "datePosted", "date_posted", "postedDate", "created_at", "publish_date",
              "updated_at", "date"],
    "url": ["url", "apply_url", "job_url", "absolute_url", "hostedUrl", "link", "applyUrl", "detail_url"],
    "id": ["req_id", "requisition_id", "id", "job_id", "jobId", "reqId"],
    "descripcion": ["description", "job_description", "summary", "descriptionPlain"],
    "categoria": ["category", "department", "job_category", "function", "team"],
    "jornada": ["employment_type", "type", "schedule", "commitment"],
}


def _lista_de_ofertas(datos):
    if isinstance(datos, list):
        return datos
    if isinstance(datos, dict):
        for k in ("jobs", "results", "data", "items", "postings", "content", "requisitions"):
            if isinstance(datos.get(k), list):
                return datos[k]
        for v in datos.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
            if isinstance(v, dict):
                r = _lista_de_ofertas(v)
                if r:
                    return r
    return []


def _campo(item, nombre, fijos):
    claves = [fijos[nombre]] if nombre in fijos else CANDIDATOS[nombre]
    for k in claves:
        v = item
        for parte in k.split("."):
            v = v.get(parte) if isinstance(v, dict) else None
        if isinstance(v, list):
            v = ", ".join(str(x.get("name", x) if isinstance(x, dict) else x) for x in v)
        if isinstance(v, dict):
            v = v.get("name") or v.get("label") or ", ".join(str(x) for x in v.values() if isinstance(x, str))
        if v not in (None, ""):
            return str(v)
    return ""


def api_json(fuente, hoy):
    fijos = fuente.get("campos", {})
    items = _lista_de_ofertas(http(fuente["url"]))
    if not items:
        raise RuntimeError("la respuesta no contiene una lista de ofertas")
    ofertas = []
    for it in items:
        titulo = _campo(it, "titulo", fijos)
        ubic = _campo(it, "ubicacion", fijos)
        pais_txt = _campo(it, "pais", fijos)
        desc = limpiar_html(_campo(it, "descripcion", fijos), 2000)
        pais = pais_de(pais_txt) or pais_de(ubic)
        if not pais and not ubic and not pais_txt:
            pais = pais_de(desc[:600])  # último recurso: país mencionado al inicio de la descripción
        if not pais:
            continue
        url = _campo(it, "url", fijos)
        if not url and fuente.get("url_oferta"):
            url = fuente["url_oferta"].format(id=_campo(it, "id", fijos))
        ofertas.append({
            "titulo": titulo, "empresa": fuente["empresa"],
            "ubicacion": ubic or pais_txt or pais, "otras_ubicaciones": "", "pais": pais,
            "fecha": (_campo(it, "fecha", fijos) or "")[:10] or None,
            "url": url or fuente.get("web", fuente["url"]),
            "jornada": _campo(it, "jornada", fijos), "remoto": "",
            "categoria": _campo(it, "categoria", fijos), "descripcion": desc[:600],
        })
    return ofertas

LECTORES = {"workday": workday, "sitemap": sitemap, "html": listado_html, "api_json": api_json, "greenhouse": greenhouse, "lever": lever,
            "smartrecruiters": smartrecruiters}


def enriquecer(o):
    o["departamento"] = classify.departamento(o["titulo"], o.get("categoria", ""), o.get("descripcion", ""))
    o["nivel"] = classify.nivel(o["titulo"])
    o["modalidad"] = classify.modalidad(o.get("remoto", ""), o["titulo"], o.get("ubicacion", ""))
    o.pop("remoto", None)
    o.pop("categoria", None)
    o["descripcion"] = o.get("descripcion", "")[:280]
    return o


def main():
    hoy = datetime.now(timezone.utc)
    fuentes = json.loads((RAIZ / "scraper" / "sources.json").read_text(encoding="utf-8"))
    todas, estado = [], []
    for tipo, lector in LECTORES.items():
        for fuente in fuentes.get(tipo, []):
            inicio = time.time()
            try:
                ofertas = lector(fuente, hoy)
                todas.extend(enriquecer(o) for o in ofertas)
                estado.append({"empresa": fuente["empresa"], "tipo": tipo, "ok": True,
                               "ofertas": len(ofertas)})
                print(f"OK    {fuente['empresa']:<25} {len(ofertas):>5} ofertas ({time.time()-inicio:.0f}s)")
            except Exception as e:
                estado.append({"empresa": fuente["empresa"], "tipo": tipo, "ok": False,
                               "error": f"{type(e).__name__}: {e}"[:200]})
                print(f"FALLO {fuente['empresa']:<25} {type(e).__name__}: {e}")

    if not any(e["ok"] for e in estado):
        print("Ninguna fuente ha funcionado; se conservan los datos anteriores.")
        sys.exit(1)

    # Para las fuentes que hoy han fallado, conservamos sus ofertas del último día bueno
    fallidas = {e["empresa"] for e in estado if not e["ok"]}
    previo = DATOS / "jobs.json"
    if fallidas and previo.exists():
        try:
            anteriores = json.loads(previo.read_text(encoding="utf-8")).get("ofertas", [])
            conservadas = [o for o in anteriores if o.get("empresa") in fallidas]
            todas.extend(conservadas)
            for e in estado:
                if not e["ok"]:
                    e["conservadas"] = sum(1 for o in conservadas if o["empresa"] == e["empresa"])
        except Exception:
            pass

    # Quitar duplicados (misma oferta publicada en varias ubicaciones)
    vistas, unicas = set(), []
    for o in todas:
        clave = (o["empresa"], o["url"])
        if clave not in vistas:
            vistas.add(clave)
            unicas.append(o)
    unicas.sort(key=lambda o: o.get("fecha") or "", reverse=True)
    for i, o in enumerate(unicas):
        o["id"] = i

    DATOS.mkdir(exist_ok=True)
    meta = {
        "actualizado": hoy.isoformat(timespec="minutes"),
        "total": len(unicas),
        "departamentos": classify.NOMBRE_DEPARTAMENTO,
        "niveles": classify.NOMBRE_NIVEL,
        "modalidades": classify.NOMBRE_MODALIDAD,
    }
    (DATOS / "jobs.json").write_text(json.dumps({"meta": meta, "ofertas": unicas},
                                                ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (DATOS / "status.json").write_text(json.dumps({"actualizado": meta["actualizado"], "fuentes": estado},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for e in estado if e["ok"])
    print(f"\n{len(unicas)} ofertas de {ok}/{len(estado)} fuentes")


if __name__ == "__main__":
    main()
