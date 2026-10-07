import copy
import datetime as dt
import os

import pytest
import yaml
from django.conf import settings

from portfolio.content import (
    ContentError,
    count_months,
    format_duration,
    get_content,
    load_content,
    parse_content,
)

VALID = {
    "profile": {
        "name": "Fulano de Tal",
        "role": "Analista de Sistemas",
        "tagline": "Sistemas corporativos",
        "location": "Salvador, Bahia, Brasil",
        "about": ["Primeiro parágrafo."],
        "stack": [".NET", "Django"],
        "career_start": "2020-02",
        "photo": "portfolio/img/foto.jpg",
        "links": {
            "linkedin": "https://www.linkedin.com/in/fulano",
            "github": "https://github.com/fulano",
        },
    },
    "experiences": [
        {
            "company": "Empresa Atual",
            "role": "Analista de sistemas",
            "start": "2026-05",
            "location": "Salvador, Bahia",
            "summary": "Sustentação de sistemas.",
        },
        {
            "company": "Empresa Antiga",
            "role": "Estagiário",
            "start": "2024-07",
            "end": "2025-12",
            "location": "Salvador, Bahia",
            "summary": "Desenvolvimento web.",
            "highlights": ["Criou API"],
            "stack": ["C#"],
        },
    ],
    "skill_groups": [{"name": "Backend", "skills": [".NET", "C#"]}],
    "projects": [
        {"title": "Sistema X", "kind": "profissional", "description": "Sistema interno."},
        {
            "title": "repo-y",
            "kind": "github",
            "description": "API de exemplo.",
            "url": "https://github.com/fulano/repo-y",
        },
    ],
    "education": [{"institution": "Universidade", "course": "ADS"}],
}


def valid_data():
    return copy.deepcopy(VALID)


def test_count_months_is_inclusive_like_linkedin():
    assert count_months(dt.date(2024, 7, 1), dt.date(2025, 12, 1)) == 18


@pytest.mark.parametrize(
    ("months", "label"),
    [
        (1, "1 mês"),
        (6, "6 meses"),
        (12, "1 ano"),
        (18, "1 ano e 6 meses"),
        (25, "2 anos e 1 mês"),
    ],
)
def test_format_duration_in_portuguese(months, label):
    assert format_duration(months) == label


def test_parse_content_builds_typed_objects():
    content = parse_content(valid_data())

    assert content.profile.name == "Fulano de Tal"
    assert content.profile.links.github == "https://github.com/fulano"
    assert content.experiences[0].start == dt.date(2026, 5, 1)
    assert content.experiences[1].highlights == ("Criou API",)
    assert content.skill_groups[0].skills == (".NET", "C#")
    assert content.education[0].course == "ADS"


def test_current_job_period_ends_with_atual():
    current = parse_content(valid_data()).experiences[0]

    assert current.period == "mai/2026 – atual"


def test_past_job_period_shows_both_months():
    past = parse_content(valid_data()).experiences[1]

    assert past.period == "jul/2024 – dez/2025"


def test_start_label_is_month_and_year():
    current = parse_content(valid_data()).experiences[0]

    assert current.start_label == "mai/2026"


def test_current_job_duration_counts_up_to_today():
    current = parse_content(valid_data()).experiences[0]

    assert current.duration_at(dt.date(2026, 10, 6)) == "6 meses"


def test_past_job_duration_ignores_today():
    past = parse_content(valid_data()).experiences[1]

    assert past.duration_at(dt.date(2030, 1, 1)) == "1 ano e 6 meses"


def test_years_in_tech_counts_full_years_since_career_start():
    profile = parse_content(valid_data()).profile

    assert profile.years_in_tech_at(dt.date(2026, 10, 6)) == 6
    assert profile.years_in_tech_at(dt.date(2026, 1, 15)) == 5


def test_projects_are_split_by_kind():
    content = parse_content(valid_data())

    assert [p.title for p in content.professional_projects] == ["Sistema X"]
    assert [p.title for p in content.github_projects] == ["repo-y"]


def test_company_count_ignores_repeated_companies():
    data = valid_data()
    data["experiences"].append({**data["experiences"][1], "role": "Aprendiz"})

    assert parse_content(data).company_count == 2


AI_USAGE = {
    "summary": "Uso IA para ganhar produtividade.",
    "tools": [
        {"name": "GitHub Copilot", "use": "Sugestões de código no editor."},
        {"name": "Claude", "use": "Análise de código e documentação."},
    ],
}


def test_ai_section_is_optional():
    assert parse_content(valid_data()).ai is None


def test_ai_section_lists_each_tool_with_its_use():
    data = valid_data()
    data["ai"] = copy.deepcopy(AI_USAGE)

    ai = parse_content(data).ai

    assert ai.summary == "Uso IA para ganhar produtividade."
    assert [(tool.name, tool.use) for tool in ai.tools] == [
        ("GitHub Copilot", "Sugestões de código no editor."),
        ("Claude", "Análise de código e documentação."),
    ]


def test_ai_tool_without_its_use_is_rejected():
    data = valid_data()
    data["ai"] = copy.deepcopy(AI_USAGE)
    del data["ai"]["tools"][1]["use"]

    with pytest.raises(ContentError, match=r"ai\.tools\[1\].*use"):
        parse_content(data)


def test_logo_is_optional_and_sits_on_a_light_ground_by_default():
    data = valid_data()
    data["experiences"][0]["logo"] = "portfolio/img/logos/empresa.png"

    with_logo, without_logo = parse_content(data).experiences

    assert with_logo.logo == "portfolio/img/logos/empresa.png"
    assert with_logo.logo_ground == "light"
    assert without_logo.logo == ""


def test_logo_drawn_in_white_can_ask_for_a_dark_ground():
    data = valid_data()
    data["experiences"][0].update(logo="portfolio/img/logos/empresa.svg", logo_ground="dark")

    assert parse_content(data).experiences[0].logo_ground == "dark"


def test_unknown_logo_ground_is_rejected():
    data = valid_data()
    data["experiences"][0].update(logo="portfolio/img/logos/empresa.svg", logo_ground="azul")

    with pytest.raises(ContentError, match=r"experiences\[0\]\.logo_ground"):
        parse_content(data)


def test_ai_tool_can_have_a_logo():
    data = valid_data()
    data["ai"] = copy.deepcopy(AI_USAGE)
    data["ai"]["tools"][0]["logo"] = "portfolio/img/logos/copilot.svg"

    assert parse_content(data).ai.tools[0].logo == "portfolio/img/logos/copilot.svg"


def test_missing_field_error_names_entry_and_field():
    data = valid_data()
    del data["experiences"][1]["role"]

    with pytest.raises(ContentError, match=r"experiences\[1\].*role"):
        parse_content(data)


def test_unknown_field_is_rejected_so_typos_do_not_pass_silently():
    data = valid_data()
    data["experiences"][0]["compny"] = "Typo"

    with pytest.raises(ContentError, match="compny"):
        parse_content(data)


def test_invalid_month_is_rejected():
    data = valid_data()
    data["experiences"][0]["start"] = "2026-13"

    with pytest.raises(ContentError, match=r"experiences\[0\].*start"):
        parse_content(data)


def test_end_before_start_is_rejected():
    data = valid_data()
    data["experiences"][1]["end"] = "2023-01"

    with pytest.raises(ContentError, match=r"experiences\[1\].*end"):
        parse_content(data)


def test_unknown_project_kind_is_rejected():
    data = valid_data()
    data["projects"][0]["kind"] = "pessoal"

    with pytest.raises(ContentError, match=r"projects\[0\].*kind"):
        parse_content(data)


def test_text_where_a_list_is_expected_is_rejected():
    data = valid_data()
    data["skill_groups"][0]["skills"] = "C#"

    with pytest.raises(ContentError, match=r"skill_groups\[0\].*skills"):
        parse_content(data)


def test_load_content_reports_broken_yaml_as_content_error(tmp_path):
    broken = tmp_path / "portfolio.yaml"
    broken.write_text("profile: [unclosed", encoding="utf-8")

    with pytest.raises(ContentError):
        load_content(broken)


def test_edit_to_the_content_file_shows_up_without_restarting_the_server(tmp_path, settings):
    content_file = tmp_path / "portfolio.yaml"
    settings.CONTENT_FILE = content_file
    data = valid_data()
    content_file.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert get_content().profile.name == "Fulano de Tal"

    data["profile"]["name"] = "Beltrana"
    content_file.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    later = content_file.stat().st_mtime + 5
    os.utime(content_file, (later, later))

    assert get_content().profile.name == "Beltrana"


def test_published_content_file_is_valid():
    content = load_content(settings.CONTENT_FILE)

    companies = [experience.company for experience in content.experiences]
    assert content.profile.name == "Vinicius Silva"
    assert companies[0] == "Federação das Indústrias do Estado da Bahia (FIEB)"
    assert len(companies) == 6
    assert content.professional_projects
    assert content.github_projects
    assert [tool.name for tool in content.ai.tools] == ["GitHub Copilot", "Claude"]
