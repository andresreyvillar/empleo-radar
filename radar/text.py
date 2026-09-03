"""Text helpers: normalisation, HTML stripping and a tiny language heuristic."""
import html
import re
import unicodedata

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[a-z]+")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str | None) -> str:
    """Lowercase, accent-free, single-spaced text used for every pattern match."""
    if not text:
        return ""
    return _WS_RE.sub(" ", strip_accents(text).lower()).strip()


def html_to_text(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", raw, flags=re.I)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def markdown_to_text(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"[*_`#>]+", " ", raw)
    text = re.sub(r"^\s*[-+]\s+", "", text, flags=re.M)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return _WS_RE.sub(" ", text).strip()


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


def spanish_ratio(text: str | None) -> float | None:
    """Share of Spanish function words among Spanish+English ones. None if too short."""
    words = _WORD_RE.findall(normalize(text))
    es = sum(1 for w in words if w in _ES)
    en = sum(1 for w in words if w in _EN)
    total = es + en
    if total < 8:
        return None
    return es / total
