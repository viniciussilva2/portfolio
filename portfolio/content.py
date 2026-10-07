"""Loads and validates the site's text: content/portfolio.yaml (the person) and
content/interface.yaml (menus, buttons, form messages).

The YAML files are the only place the site's text lives. Everything here
exists to turn them into typed objects and to fail loudly, naming the entry
and field, when a file is wrong, so a bad edit is caught by the test suite
instead of reaching production.

The site has three languages. Any text in the files can be written once, when
it is the same everywhere (a name, a technology), or as a translation map:

    role:
      pt: Analista de Sistemas
      en: Systems Analyst
      es: Analista de Sistemas
"""

import datetime as dt
import re
from dataclasses import MISSING, dataclass, fields
from functools import lru_cache
from pathlib import Path

import yaml
from django.conf import settings
from django.utils import translation

LANGUAGES = ("pt", "en", "es")
DEFAULT_LANGUAGE = "pt"
PROJECT_KINDS = ("profissional", "github")
LOGO_GROUNDS = ("light", "dark")
_MONTH_RE = re.compile(r"(\d{4})-(\d{2})")

_MONTHS = {
    "pt": ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"),
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "es": ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
}
_MONTH_AND_YEAR = {"pt": "{month}/{year}", "en": "{month} {year}", "es": "{month} {year}"}
_PRESENT = {"pt": "atual", "en": "present", "es": "actualidad"}
# (one, many) for years and for months, and the word that joins the two.
_DURATION = {
    "pt": (("ano", "anos"), ("mês", "meses"), " e "),
    "en": (("year", "years"), ("month", "months"), " and "),
    "es": (("año", "años"), ("mes", "meses"), " y "),
}


class ContentError(ValueError):
    """A content file is missing something or contains something it should not."""


def current_language() -> str:
    """Language of the page being served: 'pt', 'en' or 'es'."""
    code = (translation.get_language() or "").split("-")[0]
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


def count_months(start: dt.date, end: dt.date) -> int:
    """Months worked, counting both the first and the last month, as LinkedIn does."""
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def format_duration(months: int) -> str:
    year_words, month_words, joiner = _DURATION[current_language()]
    years, rest = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} {year_words[years != 1]}")
    if rest:
        parts.append(f"{rest} {month_words[rest != 1]}")
    return joiner.join(parts)


def _month_label(date: dt.date) -> str:
    language = current_language()
    return _MONTH_AND_YEAR[language].format(month=_MONTHS[language][date.month - 1], year=date.year)


@dataclass(frozen=True)
class Links:
    linkedin: str
    github: str
    email: str = ""
    whatsapp: str = ""


@dataclass(frozen=True)
class Profile:
    name: str
    role: str
    tagline: str
    location: str
    about: tuple[str, ...]
    stack: tuple[str, ...]
    career_start: dt.date
    photo: str
    links: Links

    def years_in_tech_at(self, today: dt.date) -> int:
        return (count_months(self.career_start, today) - 1) // 12

    @property
    def years_in_tech(self) -> int:
        return self.years_in_tech_at(dt.date.today())


@dataclass(frozen=True)
class Experience:
    company: str
    role: str
    start: dt.date
    location: str
    summary: str
    end: dt.date | None = None
    highlights: tuple[str, ...] = ()
    stack: tuple[str, ...] = ()
    logo: str = ""
    logo_ground: str = "light"

    @property
    def is_current(self) -> bool:
        return self.end is None

    @property
    def start_label(self) -> str:
        return _month_label(self.start)

    @property
    def period(self) -> str:
        end = _PRESENT[current_language()] if self.end is None else _month_label(self.end)
        return f"{self.start_label} – {end}"

    def duration_at(self, today: dt.date) -> str:
        return format_duration(count_months(self.start, self.end or today))

    @property
    def duration(self) -> str:
        return self.duration_at(dt.date.today())


@dataclass(frozen=True)
class SkillGroup:
    name: str
    skills: tuple[str, ...]


@dataclass(frozen=True)
class Project:
    title: str
    kind: str
    description: str
    context: str = ""
    stack: tuple[str, ...] = ()
    url: str = ""


@dataclass(frozen=True)
class Education:
    institution: str
    course: str
    period: str = ""


@dataclass(frozen=True)
class AiTool:
    name: str
    use: str
    logo: str = ""
    logo_ground: str = "light"


@dataclass(frozen=True)
class AiUsage:
    summary: str
    tools: tuple[AiTool, ...]


@dataclass(frozen=True)
class Content:
    profile: Profile
    experiences: tuple[Experience, ...]
    skill_groups: tuple[SkillGroup, ...]
    projects: tuple[Project, ...]
    education: tuple[Education, ...]
    ai: AiUsage | None = None

    @property
    def professional_projects(self) -> tuple[Project, ...]:
        return tuple(p for p in self.projects if p.kind == "profissional")

    @property
    def github_projects(self) -> tuple[Project, ...]:
        return tuple(p for p in self.projects if p.kind == "github")

    @property
    def company_count(self) -> int:
        return len({experience.company for experience in self.experiences})


def _text(value, where: str) -> str:
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise ContentError(f"{where}: esperado um texto, veio {type(value).__name__}.")
    return str(value).strip()


def _text_list(value, where: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ContentError(f"{where}: esperada uma lista, veio {type(value).__name__}.")
    return tuple(_text(item, f"{where}[{index}]") for index, item in enumerate(value))


def _month(value, where: str) -> dt.date:
    match = _MONTH_RE.fullmatch(str(value))
    if not match or not 1 <= int(match[2]) <= 12:
        raise ContentError(f"{where}: esperado mês no formato AAAA-MM, veio {value!r}.")
    return dt.date(int(match[1]), int(match[2]), 1)


def _list_of(build):
    def convert(value, where: str):
        if not isinstance(value, list):
            raise ContentError(f"{where}: esperada uma lista, veio {type(value).__name__}.")
        return tuple(build(item, f"{where}[{index}]") for index, item in enumerate(value))

    return convert


def _build(cls, raw, where: str, **converters):
    """Build a dataclass from a YAML mapping; fields without a converter are plain text."""
    label = where or "arquivo"
    if not isinstance(raw, dict):
        raise ContentError(f"{label}: esperado um bloco de campos, veio {type(raw).__name__}.")
    known = {field.name: field for field in fields(cls)}
    unknown = sorted(set(raw) - set(known))
    if unknown:
        raise ContentError(
            f"{label}: campo desconhecido {unknown[0]!r}. Campos válidos: {', '.join(known)}."
        )
    prefix = f"{where}." if where else ""
    values = {}
    for name, field in known.items():
        if raw.get(name) is None:
            if field.default is MISSING:
                raise ContentError(f"{label}: campo obrigatório {name!r} ausente.")
            continue
        values[name] = converters.get(name, _text)(raw[name], f"{prefix}{name}")
    return cls(**values)


def _check_logo_ground(item, where: str) -> None:
    """A logo sits on a light plate, or on a dark one when it is drawn in white."""
    if item.logo_ground not in LOGO_GROUNDS:
        raise ContentError(
            f"{where}.logo_ground: valor {item.logo_ground!r} inválido. "
            f"Use: {', '.join(LOGO_GROUNDS)}."
        )


def _links(raw, where: str) -> Links:
    return _build(Links, raw, where)


def _profile(raw, where: str) -> Profile:
    return _build(
        Profile,
        raw,
        where,
        about=_text_list,
        stack=_text_list,
        career_start=_month,
        links=_links,
    )


def _experience(raw, where: str) -> Experience:
    experience = _build(
        Experience,
        raw,
        where,
        start=_month,
        end=_month,
        highlights=_text_list,
        stack=_text_list,
    )
    if experience.end and experience.end < experience.start:
        raise ContentError(f"{where}.end: término anterior ao início.")
    _check_logo_ground(experience, where)
    return experience


def _skill_group(raw, where: str) -> SkillGroup:
    return _build(SkillGroup, raw, where, skills=_text_list)


def _project(raw, where: str) -> Project:
    project = _build(Project, raw, where, stack=_text_list)
    if project.kind not in PROJECT_KINDS:
        raise ContentError(
            f"{where}.kind: valor {project.kind!r} inválido. Use: {', '.join(PROJECT_KINDS)}."
        )
    return project


def _education(raw, where: str) -> Education:
    return _build(Education, raw, where)


def _ai_tool(raw, where: str) -> AiTool:
    tool = _build(AiTool, raw, where)
    _check_logo_ground(tool, where)
    return tool


def _ai_usage(raw, where: str) -> AiUsage:
    return _build(AiUsage, raw, where, tools=_list_of(_ai_tool))


def _localize(node, language: str, where: str):
    """Replace every translation map in the tree by its text in one language."""
    if isinstance(node, list):
        return [_localize(item, language, f"{where}[{index}]") for index, item in enumerate(node)]
    if not isinstance(node, dict):
        return node
    if DEFAULT_LANGUAGE not in node:
        prefix = f"{where}." if where else ""
        return {key: _localize(value, language, f"{prefix}{key}") for key, value in node.items()}
    # A map with "pt" is a translation map: it must have every language and nothing else.
    for code in LANGUAGES:
        if node.get(code) is None:
            raise ContentError(f"{where}: falta a tradução {code!r}.")
    unknown = sorted(set(node) - set(LANGUAGES))
    if unknown:
        raise ContentError(
            f"{where}: idioma {unknown[0]!r} não existe no site. Use: {', '.join(LANGUAGES)}."
        )
    return _localize(node[language], language, where)


def _read_yaml(path: Path):
    try:
        return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ContentError(
            f"{Path(path).name}: não foi possível ler o conteúdo. {error}"
        ) from error


def parse_content(data, language: str = DEFAULT_LANGUAGE) -> Content:
    return _build(
        Content,
        _localize(data, language, ""),
        "",
        profile=_profile,
        experiences=_list_of(_experience),
        skill_groups=_list_of(_skill_group),
        projects=_list_of(_project),
        education=_list_of(_education),
        ai=_ai_usage,
    )


def load_content(path: Path, language: str = DEFAULT_LANGUAGE) -> Content:
    return parse_content(_read_yaml(path), language)


def load_interface(path: Path, language: str = DEFAULT_LANGUAGE) -> dict[str, str]:
    """Texts of menus, buttons and messages, by key, in one language."""
    data = _read_yaml(path)
    if not isinstance(data, dict):
        raise ContentError(f"{Path(path).name}: esperado um bloco de textos.")
    return {key: _text(text, key) for key, text in _localize(data, language, "").items()}


# Parsed files are kept in memory per language. The file's modification time is
# part of the key, so an edit shows up on the next request without a restart.
@lru_cache(maxsize=len(LANGUAGES))
def _content_in(language: str, path: Path, modified: float) -> Content:
    return load_content(path, language)


@lru_cache(maxsize=len(LANGUAGES))
def _interface_in(language: str, path: Path, modified: float) -> dict[str, str]:
    return load_interface(path, language)


def _modified(path: Path) -> float:
    try:
        return Path(path).stat().st_mtime
    except OSError as error:
        raise ContentError(f"{Path(path).name}: arquivo não encontrado.") from error


def get_content() -> Content:
    """The site content in the language of the page being served."""
    path = settings.CONTENT_FILE
    return _content_in(current_language(), path, _modified(path))


def get_interface() -> dict[str, str]:
    """The interface texts in the language of the page being served."""
    path = settings.INTERFACE_FILE
    return _interface_in(current_language(), path, _modified(path))
