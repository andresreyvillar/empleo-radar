"""Extract requirements, benefits and key facts (salary, schedule…) from a job description.

Descriptions keep their line structure (see text.tidy_lines). Short lines that look like
headings ("Requisitos:", "¿Qué ofrecemos?") open a section; the following lines belong to
it until the next heading. When no heading is found, keyword-bearing lines are used instead.
"""
import re

from .text import normalize

REQUIREMENTS = re.compile(
    r"requisitos|requerimientos|que buscamos|que perfil|perfil (buscado|ideal|del candidato|requerido)"
    r"|tu perfil|sobre ti|que necesitas|que esperamos|que aportas|que traes|lo que buscamos|imprescindible"
    r"|se requiere|experiencia (requerida|necesaria|previa)|competencias|habilidades|conocimientos"
    r"|formacion y experiencia|requirements|what we are looking for|about you|your profile"
)
OFFER = re.compile(
    r"ofrecemos|ofrecerte|ofrece la (compania|empresa)|se ofrece|que ofrece|beneficios|condiciones"
    r"|que te damos|ventajas|retribucion|paquete retributivo|que encontraras|te esperamos|what we offer|benefits"
    r"|por que unirte|unete a|que te espera|razones para|por que nosotros"
)
OTHER_HEADING = re.compile(
    r"funciones|responsabilidades|mision|que haras|tareas|dia a dia|que vas a hacer|responsibilities"
    r"|sobre nosotros|quienes somos|la empresa|el puesto|el rol|descripcion|proceso de seleccion|contactanos"
    r"|about us|the role|inscribete|ubicacion|localizacion|etiquetas|tags|palabras clave|contacto"
)
LEADING_JUNK = re.compile(r"^[^\w¿¡(]+", re.UNICODE)

REQ_KEYWORDS = re.compile(r"experiencia|anos|requisit|imprescindible|valorable|competenc|habilidad|conocimient|titulaci|formacion|nivel de|ingles|certificaci")
OFFER_KEYWORDS = re.compile(r"salario|€|euros|brut|horario|jornada|flexib|teletrabajo|remoto|hibrid|beneficio|seguro medico|vacaciones|bonus|plan de carrera|contrato|retribucion|ticket|formacion continua")

SALARY_AMOUNT = re.compile(r"(\d{2}[.,]?\d{3}|\d{2}\s?k)\s?(?:€|eur|euros)?\s?(?:-|a|y|/|hasta)?\s?(\d{2}[.,]?\d{3}|\d{2}\s?k)?\s?(€|eur|euros|brutos|b/a|bruto)")
SALARY_WORDS = re.compile(r"salario|banda salarial|rango salarial|remuneraci|sueldo|retribucion (bruta|anual|fija)")
SCHEDULE = re.compile(r"horario|jornada|intensiva|flexibilidad horaria|horas semanales|\b(35|37|38|40) horas|de lunes a|de \d{1,2}:\d{2} a \d{1,2}|de \d{1,2}h? a \d{1,2}h\b")
MODALITY = re.compile(r"hibrid|\bremot[oa]s?\b|teletrabaj|modalidad|presencialidad|trabajo presencial|puesto presencial|100 ?% presencial")
EXPERIENCE = re.compile(r"(\d+|un|dos|tres|cuatro|cinco|seis)\+?\s?(a|-|o)?\s?(\d+)?\s?anos?[^.]{0,40}experiencia|experiencia[^.]{0,40}\b(\d+|un|dos|tres|cuatro|cinco|seis)\+?\s?(a|-|o)?\s?(\d+)?\s?anos?")
CONTRACT = re.compile(r"contrato|indefinid[oa]|temporal|freelance|autonomos\b|regimen de autonomo")

MAX_ITEMS = 12
MAX_LEN = 220


def _clean(line: str) -> str:
    return LEADING_JUNK.sub("", line).strip()


def _heading_kind(line: str) -> str | None:
    """'req' | 'offer' | 'other' when the line reads like a section heading, else None."""
    n = normalize(line)
    if not n or len(n) > 70:
        return None
    # Headings are questions, end with a colon, or are a few words without a full stop.
    if not (n.endswith((":", "?")) or (len(n.split()) <= 4 and not n.endswith("."))):
        return None
    if OFFER.search(n):
        return "offer"
    if REQUIREMENTS.search(n):
        return "req"
    if OTHER_HEADING.search(n) or n.endswith((":", "?")):
        return "other"
    return None


def extract_details(description: str | None) -> dict:
    lines = [_clean(l) for l in (description or "").split("\n")]
    lines = [l for l in lines if l]
    sections: dict[str, list[str]] = {"req": [], "offer": []}
    current = None
    for line in lines:
        kind = _heading_kind(line)
        if kind:
            current = kind if kind in sections else None
            continue
        if current and len(sections[current]) < MAX_ITEMS:
            item = line[:MAX_LEN]
            if item not in sections[current]:
                sections[current].append(item)

    if not sections["req"]:
        sections["req"] = _keyword_lines(lines, REQ_KEYWORDS)
    if not sections["offer"]:
        sections["offer"] = _keyword_lines(lines, OFFER_KEYWORDS)

    highlights = {
        "salario": _first(lines, SALARY_AMOUNT) or _first(lines, SALARY_WORDS),
        "horario": _first(lines, SCHEDULE),
        "modalidad": _first(lines, MODALITY),
        "experiencia": _first(lines, EXPERIENCE),
        "contrato": _first(lines, CONTRACT),
    }
    claves, used = {}, set()
    for key, value in highlights.items():
        if value and value not in used:       # the same sentence is shown once
            claves[key] = value
            used.add(value)
    return {"requisitos": sections["req"], "ofrecen": sections["offer"], "claves": claves}


def _keyword_lines(lines: list[str], pattern: re.Pattern, limit: int = 6) -> list[str]:
    out = []
    for line in lines:
        if len(line) > 300 or _heading_kind(line):
            continue
        if pattern.search(normalize(line)):
            out.append(line[:MAX_LEN])
        if len(out) >= limit:
            break
    return out


def _first(lines: list[str], pattern: re.Pattern) -> str:
    for line in lines:
        if len(line.split()) < 2 or len(line) > 200 or _heading_kind(line):
            continue
        if pattern.search(normalize(line)):
            return line
    return ""
