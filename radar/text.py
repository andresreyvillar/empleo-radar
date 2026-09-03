"""Text helpers: normalisation, HTML stripping and a tiny language heuristic."""
import html
import re
import unicodedata

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SPACES_RE = re.compile(r"[ \t\xa0]+")
_BLANKS_RE = re.compile(r"\n{3,}")
_WORD_RE = re.compile(r"[a-z]+")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str | None) -> str:
    """Lowercase, accent-free, single-spaced text used for every pattern match."""
    if not text:
        return ""
    return _WS_RE.sub(" ", strip_accents(text).lower()).strip()


_COMPANY_NOISE = re.compile(
    r"\b(espana|spain|iberia|iberica|group|grupo|company|holding|s\.?l\.?u?\.?|s\.?a\.?u?\.?|sl|sa|slu|sau|ltd|inc|gmbh|"
    r"consulting|consultores|consultoria|people first|talent|recruitment|hr)\b"
)


def company_key(company: str | None) -> str:
    """Company name reduced to its distinctive tokens, for cross-source deduplication."""
    key = re.sub(r"[|–—\-·,()]+", " ", normalize(company))
    key = _COMPANY_NOISE.sub(" ", key)
    return _WS_RE.sub(" ", key).strip()


def tidy_lines(text: str) -> str:
    """Collapse spaces inside lines and runs of blank lines, keeping the line structure."""
    lines = [_SPACES_RE.sub(" ", line).strip() for line in text.replace("\r", "").split("\n")]
    return _BLANKS_RE.sub("\n\n", "\n".join(lines)).strip()


def html_to_text(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"<br\s*/?>|</p>|</li>|</div>|</h\d>|</tr>", "\n", raw, flags=re.I)
    text = _TAG_RE.sub(" ", text)
    return tidy_lines(html.unescape(text))


def markdown_to_text(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|])", r"\1", raw)   # 25\.000 \- 30\.000 -> 25.000 - 30.000
    text = re.sub(r"[*_`#>]+", " ", text)
    text = re.sub(r"^\s*[-+]\s+", "", text, flags=re.M)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return tidy_lines(text)


# Function words that are frequent in one language and rare in the other
# (accent-free, because they are matched on normalised text).
_ES = {
    "de", "la", "el", "en", "los", "las", "para", "con", "una", "que", "del", "por", "se",
    "como", "nuestro", "nuestra", "nuestros", "equipo", "experiencia", "gestion", "proyectos",
    "buscamos", "ofrecemos", "requisitos", "funciones", "empresa", "puesto", "incorporacion",
    "anos", "conocimientos", "desarrollo", "ser", "mas", "sobre", "entre", "tambien", "muy",
    "este", "esta", "sus", "nos", "cliente", "clientes", "trabajo",
}
_EN = {
    "the", "and", "with", "for", "you", "we", "our", "will", "of", "to", "in", "is", "are",
    "experience", "team", "this", "that", "as", "be", "your", "have", "on", "from", "or", "by",
    "at", "an", "it", "skills", "role", "work", "working", "who", "their", "about", "must",
    "should", "company", "job", "years",
}


# Catalan function/content words that do not occur in Spanish (accent-free).
_CA = {
    "amb", "els", "dels", "aquest", "aquesta", "aquests", "aquestes", "projecte", "projectes", "tambe", "fins",
    "seva", "nostre", "nostra", "desenvolupament", "gestio", "coneixements", "coneixement", "treball", "hores",
    "empreses", "persones", "funcions", "requisits", "oferim", "busquem", "cerquem", "tasques", "equip", "any",
    "anys", "sou", "lloc", "feina", "sense", "molt", "altres", "totes", "tots", "nivell", "habilitats",
    "capacitat", "responsabilitats", "titulacio", "formacio", "contracte", "salari", "horari", "flexibilitat",
    "incorporacio", "candidat", "candidats", "valorara", "necessari", "necessaria", "millora", "seguiment",
}


def is_catalan(text: str | None) -> bool:
    """True when the text is written in Catalan (shares many function words with Spanish)."""
    words = _WORD_RE.findall(normalize(text))
    ca = sum(1 for w in words if w in _CA)
    es = sum(1 for w in words if w in _ES)
    return ca >= 4 and ca / max(1, ca + es) >= 0.2


def spanish_ratio(text: str | None) -> float | None:
    """Share of Spanish function words among Spanish+English ones. None if too short."""
    words = _WORD_RE.findall(normalize(text))
    es = sum(1 for w in words if w in _ES)
    en = sum(1 for w in words if w in _EN)
    total = es + en
    if total < 8:
        return None
    return es / total
