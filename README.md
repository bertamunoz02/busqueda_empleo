# Vacantes Farma

Web gratuita que reúne las ofertas de empleo abiertas en la industria farmacéutica (España y resto de Europa) y permite filtrarlas por departamento, país, empresa, nivel, modalidad, fecha y palabras clave.

## Cómo funciona

- **Cada día**, una tarea automática de GitHub (`.github/workflows/actualizar-ofertas.yml`) ejecuta `scraper/fetch_jobs.py`.
- Ese script lee los portales de empleo de los laboratorios listados en `scraper/sources.json`, se queda con las ofertas europeas, las clasifica por departamento (`scraper/classify.py`) y guarda el resultado en `data/jobs.json`.
- La web (`index.html`, `styles.css`, `app.js`) es estática: lee ese archivo y filtra en el navegador. No hay servidor ni nada de pago.
- Si un portal falla un día, se conservan sus ofertas del último día bueno y aparece marcado en «Fuentes consultadas», al pie de la web.

## Puesta en marcha (una sola vez)

1. **Settings → Pages**: en *Source* elige «Deploy from a branch», rama `main`, carpeta `/ (root)`. Guarda.
2. **Settings → Actions → General**: en *Workflow permissions* marca «Read and write permissions». Guarda.
3. **Actions → Actualizar ofertas → Run workflow** para lanzar la primera descarga (tarda unos minutos).
4. La web queda en `https://bertamunoz02.github.io/<nombre-del-repo>/`.

## Añadir o corregir empresas

Edita `scraper/sources.json`:

- **Workday** (la mayoría de grandes farmas). Si la web de empleo es `https://pfizer.wd1.myworkdayjobs.com/PfizerCareers`, los datos son `host: pfizer.wd1.myworkdayjobs.com`, `tenant: pfizer`, `site: PfizerCareers`.
- Los sitios con protección anti-bot (error 403 / Incapsula) no se pueden leer desde GitHub: por eso no están J&J, Bayer ni Boehringer.
- **Sitemap + JSON-LD** (portales Phenom y otros cuya búsqueda va con JavaScript): `sitemap` es la dirección del sitemap; si hay varios numerados, usa `{n}` (`https://careers.ejemplo.com/sitemap{n}.xml`). `patron_oferta` es un trozo que solo aparece en las URLs de ofertas (normalmente `/job/`). La primera vez tarda más porque abre cada oferta; después solo abre las nuevas (se guardan en `data/cache/`).
- **Listado HTML** (TalentBrew, Jobvite, webs propias): `url` es la página del buscador con `{n}` en el número de página (`?p={n}`), `primera_pagina` si empieza en 0, y `patron_oferta` un trozo que solo tienen los enlaces a ofertas. Si en el listado no aparece el país, se abre cada oferta para buscarlo. `formato_fecha: "mdy"` para webs con fechas estadounidenses (mes/día/año).
- **API JSON propia** (como Medpace): `url` del JSON; los campos se adivinan por su nombre, y `url_oferta` construye el enlace con `{id}` si el JSON no lo trae.
- **Greenhouse**: `token` es lo que va tras `boards.greenhouse.io/`.
- **Lever**: `empresa_id` es lo que va tras `jobs.lever.co/`.
- **SmartRecruiters**: `empresa_id` es lo que va tras `jobs.smartrecruiters.com/`.

Tras guardar, lanza «Run workflow» y mira en el registro qué fuentes dicen OK o FALLO.

## Afinar los departamentos

En `scraper/classify.py` cada departamento tiene una lista de palabras clave (en español, inglés y algo de alemán y francés). La primera que coincide con el título gana. Si ves ofertas mal clasificadas, añade la palabra que falta al departamento correcto.
