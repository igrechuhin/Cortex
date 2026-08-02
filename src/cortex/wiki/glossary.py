"""Parse the canonical domain glossary at `.cortex/wiki/glossary.md`.

The glossary is a wiki root document, so it loads through the existing wiki read
path — no new MCP tool is introduced for it.
"""

from __future__ import annotations

import re
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.wiki.glossary_models import Glossary, GlossaryEntry, GlossaryParseError
from cortex.wiki.wiki_root_files import WikiRootDocument

_TERMS_HEADING = re.compile(r"^##\s+Terms\s*$", re.MULTILINE)
_ENTRY_HEADING = re.compile(r"^###\s+(?P<term>.+?)\s*$", re.MULTILINE)
_FIELD_LINE = re.compile(r"^-\s+\*\*(?P<label>[^*]+)\*\*:\s*(?P<value>.*?)\s*$")

_DEFINITION_LABEL = "definition"
_ALIASES_LABEL = "aliases"
_CONFUSED_LABEL = "not to be confused with"
_NONE_VALUE = "none"


def glossary_document_path(project_root: Path) -> Path:
    """Return the path to `.cortex/wiki/glossary.md`."""
    return (
        get_cortex_path(project_root, CortexResourceType.WIKI)
        / WikiRootDocument.GLOSSARY.value
    )


def _split_list_value(value: str) -> list[str]:
    """Parse a comma-separated field value; ``none`` means an empty list."""
    if value.strip().lower() == _NONE_VALUE:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_entry_fields(term: str, body: str) -> GlossaryEntry:
    """Build one entry from the bullet block under a ``###`` heading."""
    fields: dict[str, str] = {}
    for line in body.splitlines():
        match = _FIELD_LINE.match(line.strip())
        if match:
            fields[match.group("label").strip().lower()] = match.group("value")
    definition = fields.get(_DEFINITION_LABEL, "").strip()
    if not definition:
        raise GlossaryParseError(f"Glossary entry '{term}' is missing a Definition")
    if _ALIASES_LABEL not in fields or _CONFUSED_LABEL not in fields:
        missing = f"Glossary entry '{term}' must declare both 'Aliases' and"
        raise GlossaryParseError(
            f"{missing} 'Not to be confused with' (use 'none' when empty)"
        )
    return GlossaryEntry(
        term=term,
        definition=definition,
        aliases=_split_list_value(fields[_ALIASES_LABEL]),
        not_to_be_confused_with=_split_list_value(fields[_CONFUSED_LABEL]),
    )


def _terms_section(markdown: str) -> str:
    """Return the text following the ``## Terms`` heading."""
    match = _TERMS_HEADING.search(markdown)
    if match is None:
        raise GlossaryParseError("Glossary is missing a '## Terms' section")
    return markdown[match.end() :]


def parse_glossary(markdown: str) -> Glossary:
    """Parse glossary markdown into typed entries.

    Raises:
        GlossaryParseError: If the ``## Terms`` section is absent, an entry omits a
            required field, or a canonical term is declared twice.
    """
    section = _terms_section(markdown)
    headings = list(_ENTRY_HEADING.finditer(section))
    entries: list[GlossaryEntry] = []
    seen: set[str] = set()
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(section)
        term = heading.group("term").strip()
        key = term.casefold()
        if key in seen:
            raise GlossaryParseError(f"Duplicate glossary term '{term}'")
        seen.add(key)
        entries.append(_parse_entry_fields(term, section[heading.end() : end]))
    return Glossary(entries=entries)


def load_glossary(project_root: Path) -> Glossary | None:
    """Load and parse the project glossary, or return None when it does not exist.

    Raises:
        GlossaryParseError: If the file exists but violates the entry schema.
    """
    path = glossary_document_path(project_root)
    if not path.is_file():
        return None
    return parse_glossary(path.read_text(encoding="utf-8"))
