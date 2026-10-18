"""Clasifica cada oferta por departamento, nivel y modalidad a partir del título
(y, si hace falta, de la categoría o el inicio de la descripción).

Las reglas van en orden: la primera que encaja gana. Para afinar la
clasificación basta con añadir palabras a la lista del departamento.
"""
import re
import unicodedata

# (clave, nombre visible, palabras clave). Se comparan sin tildes y en minúsculas.
DEPARTAMENTOS = [
    ("farmacovigilancia", "Farmacovigilancia", [
        "pharmacovigilance", "farmacovigilancia", "drug safety", "patient safety",
        "safety scientist", "safety physician", "case processing", "icsr", "qppv",
        "pv specialist", "pv scientist", "pv associate", "pv manager", "arzneimittelsicherheit",
        "vigilance"]),
    ("regulatorios", "Regulatory affairs", [
        "regulatory", "cmc lifecycle", "license to operate", "regulatorio", "regulatorios", "registro sanitario", "cmc regulatory",
        "labeling", "labelling", "submission", "dossier", "zulassung", "affaires reglementaires"]),
    ("medico", "Departamento médico", [
        "medical science liaison", "msl", "medical affairs", "medical advisor", "medical manager",
        "medical director", "medical sciences liaison", "directeur medical", "medizinischer", "arzt", "arztin", "therapy area specialist", "medical education", "medical healthcare", "medical core", "patient journey", "director medico", "directora medica", "asesor medico", "gerente medico",
        "responsable medico", "medico especialista", "medica especialista", "medical information", "informacion medica",
        "medical lead", "medical scientific", "medizinisch", "medical writer", "medical writing",
        "medical excellence", "field medical"]),
    ("clinica", "Ensayos clínicos", [
        "clinical research", "clinical associate", "clinical coordinator", "clinical delivery", "trial clinical", "study associate", "study site", "site management", "site engagement", "site payment", "site payments", "site data", "start up lead", "startup lead", "central data monitor", "clinical paediatric", "clinical pediatric", "trial lead", "global study", "country approval", "research nurse", "clinical trial", "clinical operations", "clinical study",
        "clinical project", "cra", "monitor clinico", "ensayo", "ensayos clinicos",
        "study manager", "study start", "site manager", "site activation", "trial manager",
        "clinical scientist", "clinical development", "investigacion clinica", "clinical data",
        "ctm", "clinical trial assistant", "feasibility", "klinisch", "etudes cliniques"]),
    ("datos", "Datos y bioestadística", [
        "biostatistic", "data analytics", "analytics manager", "bioestadist", "statistician", "statistical programmer", "estadistic",
        "data scientist", "data science", "real world evidence", "rwe", "epidemiolog",
        "bioinformatic", "computational biology", "machine learning", "data analyst",
        "data management", "business intelligence", "sfe", "sas programmer", "health economics", "heor", "outcomes research"]),
    ("acceso", "Market access", [
        "market access", "acceso al mercado", "pricing", "reimbursement", "health technology",
        "hta", "access manager", "government affairs", "public affairs", "relaciones institucionales",
        "policy"]),
    ("calidad", "Calidad (QA/QC)", [
        "quality", "calidad", "qa ", " qa", "qc ", " qc", "qualified person", "persona cualificada",
        "gmp compliance", "gxp", "validation", "validacion", "auditor", "audit", "deviation",
        "capa", "qualitat", "qualite", "microbiolog", "analytical chemist", "quimico analitico",
        "control de calidad", "batch release", "liberacion de lotes"]),
    ("id", "Investigación y desarrollo (I+D)", [
        "research scientist", "pk analyst", "pharmacokinetic", "bioanalytic", "analytical science", "cell line", "genomics", "pathology", "laborant", "chemikant", "lab analyst", "biobanque", "biobank", "vaccins", "caracterisation", "characterization", "msat", "material expert", "scientist", "cientific", "investigador", "investigacion",
        "non clinical", "nonclinical", "safety assessment", "research associate", "discovery", "preclinical", "preclinica", "laboratory",
        "laboratorio", "lab technician", "tecnico de laboratorio", "biolog", "chemist",
        "quimic", "pharmacolog", "toxicolog", "formulation", "formulacion", "galenic",
        "drug product development", "process development", "analytical development",
        "r&d", "i+d", "postdoc", "post-doc", "phd", "doctorand", "assay", "in vivo", "in vitro",
        "immunolog", "oncology research", "translational", "biomarker", "cell therapy",
        "gene therapy", "forschung", "recherche", "wissenschaftl"]),
    ("produccion", "Producción", [
        "manufacturing", "process technician", "asset lead", "asset excellence", "conducteur d appareil", "pharmacy technician", "production", "produccion", "fabricacion", "operator", "operario",
        "operador", "technician production", "tecnico de produccion", "packaging",
        "acondicionamiento", "fill finish", "aseptic", "esteril", "plant manager",
        "jefe de planta", "shift", "turno", "process engineer", "upstream", "downstream",
        "bioprocess", "produktion", "herstellung", "fabrication", "sterile"]),
    ("it", "IT y digital", [
        "software", "scrum master", "product owner", "observability", "administrator", "collaboration & productivity", "platform services", "informatik", "dashboard", "analytics", "developer", "desarrollador", "it ", " it", "information technology",
        "cloud", "cyber", "ciberseguridad", "devops", "sap ", "erp", "digital transformation", "data engineer",
        "architect", "arquitecto", "infrastructure", "ai ", "artificial intelligence",
        "service desk", "sistemas", "network", "programador", "full stack", "frontend", "backend"]),
    ("ingenieria", "Ingeniería y mantenimiento", [
        "engineer", "elektroniker", "building safety", "hard services", "real estate", "process equipment", "technical application", "commissioning", "qualification manager", "capex", "estimating", "hazard communication", "safety manager", "engineering", "ingenier", "maintenance", "mantenimiento", "automation",
        "automatizacion", "facilities", "instalaciones", "hvac", "metrolog", "calibration",
        "calibracion", "technical services", "utilities", "ehs", "hse", "seguridad industrial",
        "prevencion de riesgos", "environment health"]),
    ("supply", "Logística y supply chain", [
        "supply chain", "supply planner", "planning", "planificacion", "planificador",
        "logistic", "logistica", "warehouse", "almacen", "procurement", "purchasing",
        "compras", "buyer", "sourcing", "distribution", "distribucion", "demand planner",
        "s&op", "import", "export", "customs", "aduanas"]),
    ("marketing", "Marketing", [
        "marketing", "brand manager", "events", "congress", "campaign", "creation digitale", "insights", "corporate affairs", "media manager", "product manager", "jefe de producto", "brand lead",
        "omnichannel", "customer experience", "launch", "lanzamiento", "communications",
        "comunicacion", "digital marketing", "content"]),
    ("ventas", "Comercial y visita médica", [
        "sales", "pharmareferent", "apothekenreferent", "aussendienst", "apothekenaussendienst", "medisch afgevaardigde", "afgevaardigde", "business relationship manager", "contracting and tender", "tender", "negotiation", "customer success", "community development", "customer partnering", "account specialist", "business leader", "ventas", "comercial", "key account", "kam", "account manager",
        "visitador", "delegado", "representative", "rep ", "territory", "business development",
        "desarrollo de negocio", "area manager", "vertrieb", "aussendienst", "ventes",
        "delegue", "customer engagement", "hospital specialist", "specialty manager"]),
    ("legal", "Legal y compliance", [
        "legal", "lawyer", "abogad", "counsel", "compliance", "cumplimiento normativo",
        "privacy counsel", "privacy officer", "data privacy", "data protection",
        "proteccion de datos", "patent", "patente", "intellectual property", "ethics"]),
    ("rrhh", "Recursos humanos y formación", [
        "human resources", "employee lifecycle", "p&c business partner", "people & culture", "benefits", "engagement & capabilities", "recursos humanos", "hr ", " hr", "people partner", "talent",
        "recruit", "seleccion", "reclutamiento", "payroll", "nomina", "learning",
        "formacion", "compensation"]),
    ("proyectos", "Proyectos, estrategia y operaciones", [
        "project manager", "projektmanager", "projekt manager", "program manager", "programme manager",
        "program management", "project management", "project reviews", "pmo", "jefe de proyecto",
        "gestor de proyectos", "project change", "change manager", "transformation", "operational excellence",
        "operations manager", "manager operations", "excelencia operacional", "strategy", "estrategia",
        "transition", "knowledge transfer", "efficiency", "continuous improvement", "amelioration continue",
        "lean", "business excellence", "governance", "team leader", "team lead", "delivery lead",
        "consultant", "consultor", "chief of staff", "regional center", "benchmarking"]),
    ("finanzas", "Finanzas y administración", [
        "finance", "finops", "investor relations", "contract analyst", "contract operations", "contract to pay", "transparency reporting", "customer service", "proposals development", "proposals", "proposal", "droit boursier", "category manager", "contracting & partner", "financ", "accountant", "accounting", "contab", "controller",
        "controlling", "tax", "fiscal", "treasury", "tesoreria", "audit financ",
        "administracion", "administrative", "administrativ", "assistant", "asistente",
        "secretar", "office manager", "fp&a", "credit", "billing", "facturacion"]),
]

OTROS = ("otros", "Otros")

NOMBRE_DEPARTAMENTO = {k: n for k, n, _ in DEPARTAMENTOS}
NOMBRE_DEPARTAMENTO[OTROS[0]] = OTROS[1]


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9&+ ]", " ", texto)
    return " " + re.sub(r"\s+", " ", texto).strip() + " "


# Estas palabras solo casan como palabra completa, nunca dentro de otra
# (p. ej. "talent" no debe casar con el alemán "Punktionstalent").
PALABRAS_EXACTAS = {"talent", "intern", "interns", "internship", "internships", "stage", "stages",
                    "placement", "thesis", "apprentice", "apprentices", "trainee", "trainees"}
# ("intern" como palabra completa: "Internal Medical Translator" o "International" ya no cuentan como prácticas)


def _coincide(texto, palabra):
    p = normalizar(palabra).strip()
    if len(p) <= 4 or p in PALABRAS_EXACTAS:  # siglas cortas (qa, msl, cra, it...) deben ir como palabra completa
        return re.search(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", texto) is not None
    return p in texto


def departamento(titulo, categoria="", descripcion=""):
    for fuente in (titulo, categoria, (descripcion or "")[:400]):
        t = normalizar(fuente)
        if not t.strip():
            continue
        for clave, _, palabras in DEPARTAMENTOS:
            if any(_coincide(t, p) for p in palabras):
                return clave
    return OTROS[0]


NIVELES = [
    ("practicas", ["intern", "interns", "internship", "internships", "becari", "beca", "practicas", "trainee",
                    "praktik", "bachelorstage", "masterstage", "stagiaire", "stage", "apprentice", "aprendiz", "ausbildung", "duales studium", "apprentissage", "alternance", "examensarbete", "thesis", "stagiaire", "university student", "student placement", "werkstudent",
                    "working student", "placement", "summer student", "co op", "coop"]),
    ("graduado", ["graduate", "recien graduado", "early career", "junior", "jr ", "entry level",
                   "programa de graduados", "assistant"]),
    ("direccion", ["director", "head of", "vice president", "vp ", "chief", "general manager",
                    "country manager", "directora", "jefe de departamento", "executive director"]),
    ("senior", ["senior", "sr ", "lead", "leader", "principal", "manager", "gerente", "responsable",
                 "jefe", "expert", "experto", "specialist ii", "staff"]),
]

NOMBRE_NIVEL = {
    "practicas": "Prácticas / becas",
    "graduado": "Junior / recién titulado",
    "intermedio": "Con experiencia",
    "senior": "Senior / mánager",
    "direccion": "Dirección",
}


def nivel(titulo):
    t = normalizar(titulo)
    for clave, palabras in NIVELES:
        if any(_coincide(t, p) for p in palabras):
            return clave
    return "intermedio"


def modalidad(remote_type="", titulo="", ubicacion=""):
    t = normalizar(" ".join([remote_type or "", titulo or "", ubicacion or ""]))
    if any(_coincide(t, p) for p in ["hybrid", "hibrido", "hybride", "flexible"]):
        return "hibrido"
    if any(_coincide(t, p) for p in ["remote", "remoto", "teletrabajo", "home based",
                                     "home office", "homeoffice", "field based", "virtual"]):
        return "remoto"
    if remote_type:
        return "presencial"
    return "sin_indicar"


NOMBRE_MODALIDAD = {
    "presencial": "Presencial",
    "hibrido": "Híbrido",
    "remoto": "Remoto / campo",
    "sin_indicar": "Sin indicar",
}
