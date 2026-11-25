"""Reader for the predefined template source bundle.

The bundle is a folder of template packages.  Every package is a pair of
files that share a name::

    <editor>/<editor>__<name>.html
    <editor>/<editor>__<name>.json

``<editor>`` is ``certificate-editor`` or ``document-editor``.  The HTML is a
self-contained, print-ready page; the JSON is the editor's document model and
can be re-imported through "Import Template".

Metadata comes from the embedded
``<script id="template-dynamic-values" type="application/json">`` block, which
is written by the template generator and is the source of truth for the
display name, page spec and dynamic fields.  ``<meta>`` tags are used as a
fallback::

    <meta name="template-editor" content="certificate-editor">
    <meta name="template-page-size" content="A4">
    <meta name="template-dimensions-mm" content="210mm x 297mm">
    <meta name="template-orientation" content="portrait">

Dynamic fields are the ``{{Field Name}}`` tokens in the HTML.  The generator
names them with spaces (``{{Recipient Name}}``), so the *names* returned here
are the exact keys a caller must send as ``DocumentField.key`` values for the
renderer to substitute them.

The folder location defaults to ``documents/predefined_templates`` and can be
overridden with the ``PREDEFINED_TEMPLATES_DIR`` setting.
"""

from __future__ import annotations

import json
import logging
import re
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

SLUG_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_DIMENSIONS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*mm\s*[x×]\s*(\d+(?:\.\d+)?)\s*mm",
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(r"\{\{([^{}]+)\}\}")

SUMMARY_FIELDS = (
    "id",
    "slug",
    "name",
    "editor",
    "editor_label",
    "page_size",
    "dimensions_mm",
    "orientation",
    "pages",
    "validity_days",
    "dynamic_fields",
    "document_type",
)

# Fallbacks used when a bundle does not declare its own document type.  The
# first matching slug hint wins, so longer/more specific hints come first.
_DOCUMENT_TYPE_HINTS = (
    ("employee-id-card", ("IDCARD", "ID Card")),
    ("appointment-letter", ("APPT", "Appointment Letter")),
    ("relieving-experience-letter", ("EXP", "Experience Letter")),
    ("offer-letter", ("OFFER", "Offer Letter")),
    ("corporate-offer", ("OFFER", "Offer Letter")),
    ("privacy-policy", ("POLICY", "Policy")),
    ("company-announcement", ("ANN", "Announcement")),
    ("official-hr-notice", ("NOTICE", "Notice")),
    ("certificate", ("CERT", "Certificate")),
)

_EDITOR_DOCUMENT_TYPES = {
    "certificate-editor": ("CERT", "Certificate"),
    "document-editor": ("DOC", "Document"),
}

_DEFAULT_DOCUMENT_TYPE = ("DOC", "Document")

# Parsed packages keyed by file path, invalidated when either file changes.
# The bundle is static, so this keeps the list/detail endpoints cheap.
_CACHE: dict[str, tuple[tuple, dict]] = {}


class _PackageParser(HTMLParser):
    """Extracts ``<meta>`` values, the embedded JSON and page markers."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.doc_pages = []
        self._in_dynamic_script = False
        self._dynamic_text = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "meta" and attributes.get("name"):
            self.meta[attributes["name"].strip().lower()] = (
                attributes.get("content") or ""
            ).strip()
        elif tag == "script" and attributes.get("id") == "template-dynamic-values":
            self._in_dynamic_script = True
            self._dynamic_text = []
        elif tag == "section":
            classes = (attributes.get("class") or "").split()
            if "doc-page" in classes:
                self.doc_pages.append(attributes.get("id") or "")

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_dynamic_script = False

    def handle_data(self, data):
        if self._in_dynamic_script:
            self._dynamic_text.append(data)

    @property
    def embedded_json(self) -> dict:
        if not self._dynamic_text:
            return {}
        try:
            value = json.loads("".join(self._dynamic_text))
        except json.JSONDecodeError:
            logger.warning("Could not parse template-dynamic-values JSON")
            return {}
        return value if isinstance(value, dict) else {}


def bundle_root() -> Path:
    """Directory that holds the predefined template packages."""
    configured = getattr(settings, "PREDEFINED_TEMPLATES_DIR", None)
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / "predefined_templates"


def list_packages() -> list[dict]:
    """Load every complete ``.html`` + ``.json`` pair, sorted by slug.

    Incomplete or unreadable packages are skipped with a log message so one
    bad file cannot take the whole endpoint down.
    """
    root = bundle_root()
    if not root.is_dir():
        return []

    packages = []
    for html_path in sorted(root.rglob("*.html")):
        json_path = html_path.with_suffix(".json")
        if not json_path.is_file():
            logger.warning(
                "Predefined template %s has no matching %s; skipping",
                html_path.name,
                json_path.name,
            )
            continue
        try:
            packages.append(_load_package(html_path, json_path))
        except (OSError, ValueError):
            logger.exception("Could not load predefined template %s", html_path)
    return packages


def get_package(slug: str) -> dict | None:
    """Return one package by slug, or ``None`` when it does not exist."""
    if not slug or not SLUG_RE.match(slug):
        return None
    for package in list_packages():
        if package["slug"] == slug:
            return package
    return None


def summary(package: dict) -> dict:
    """Metadata-only view used by the list endpoint."""
    return {field: package[field] for field in SUMMARY_FIELDS}


def detail(package: dict) -> dict:
    """Full package, using the same keys as the template create endpoint."""
    data = summary(package)
    data["template_html"] = package["html"]
    data["template_json"] = package["json"]
    return data


def _load_package(html_path: Path, json_path: Path) -> dict:
    stat_key = (
        html_path.stat().st_mtime_ns,
        html_path.stat().st_size,
        json_path.stat().st_mtime_ns,
        json_path.stat().st_size,
    )
    cache_key = str(html_path)
    cached = _CACHE.get(cache_key)
    if cached is not None and cached[0] == stat_key:
        return cached[1]

    package = _read_package(html_path, json_path)
    _CACHE[cache_key] = (stat_key, package)
    return package


def _read_package(html_path: Path, json_path: Path) -> dict:
    html = html_path.read_text(encoding="utf-8")
    with json_path.open(encoding="utf-8") as handle:
        template_json = json.load(handle)

    parser = _PackageParser()
    parser.feed(html)
    parser.close()

    embedded = parser.embedded_json
    page_spec = embedded.get("pageSpec")
    if not isinstance(page_spec, dict):
        page_spec = {}
    declared_type = _json_document_type(template_json)
    slug = html_path.stem
    editor = (
        embedded.get("editor")
        or parser.meta.get("template-editor")
        or html_path.parent.name
    )

    return {
        "id": embedded.get("documentTypeId") or declared_type.get("id"),
        "slug": slug,
        "name": _display_name(slug, embedded, declared_type),
        "editor": editor,
        "editor_label": embedded.get("editorLabel")
        or parser.meta.get("template-editor-label"),
        "page_size": page_spec.get("sizeName")
        or parser.meta.get("template-page-size")
        or None,
        "dimensions_mm": _dimensions(page_spec, parser.meta),
        "orientation": _orientation(page_spec, parser.meta),
        "pages": _page_count(html, parser, embedded, parser.meta),
        "validity_days": declared_type.get("validityDays"),
        "dynamic_fields": _dynamic_fields(embedded, template_json, html),
        "document_type": _resolve_document_type(slug, editor, template_json),
        "html": html,
        "json": template_json,
    }


def _json_document_type(template_json) -> dict:
    if not isinstance(template_json, dict):
        return {}
    value = template_json.get("documentType")
    return value if isinstance(value, dict) else {}


def _display_name(slug: str, embedded: dict, declared_type: dict) -> str:
    """Prefer the generator's canonical name, else prettify the slug."""
    for candidate in (
        embedded.get("documentTypeName"),
        declared_type.get("name"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    # "certificate-editor__professional-certificate" -> "Professional Certificate"
    name = slug.split("__", 1)[-1]
    return name.replace("-", " ").replace("_", " ").strip().title() or slug


def _dimensions(page_spec: dict, meta: dict) -> dict | None:
    width = page_spec.get("widthMm")
    height = page_spec.get("heightMm")
    if isinstance(width, (int, float)) and isinstance(height, (int, float)):
        return {"width": width, "height": height}

    raw = meta.get("template-dimensions-mm")
    if not raw:
        return None
    match = _DIMENSIONS_RE.search(raw)
    if not match:
        return {"raw": raw}
    width, height = match.groups()
    return {"width": float(width), "height": float(height)}


def _orientation(page_spec: dict, meta: dict) -> str | None:
    value = page_spec.get("orientation") or meta.get("template-orientation")
    return value.strip().lower() if isinstance(value, str) and value.strip() else None


def _page_count(html: str, parser: _PackageParser, embedded: dict, meta: dict) -> int:
    candidates = (
        (embedded.get("pageSpec") or {}).get("totalPages"),
        meta.get("template-total-pages"),
    )
    for value in candidates:
        try:
            pages = int(value)
        except (TypeError, ValueError):
            continue
        if pages > 0:
            return pages

    if parser.doc_pages:
        return len(parser.doc_pages)

    breaks = html.count("PAGE_BREAK")
    return breaks + 1 if breaks else 1


def _dynamic_fields(embedded: dict, template_json, html: str) -> list[dict]:
    """Normalise the dynamic fields into label/type descriptors.

    ``name`` is the exact ``{{token}}`` text (without braces) and is what the
    renderer replaces, so callers must use it as the DocumentField key.
    """
    variables = embedded.get("dynamicVariables")
    if not isinstance(variables, list):
        variables = (
            template_json.get("dynamicVariables")
            if isinstance(template_json, dict)
            else None
        )

    fields = []
    if isinstance(variables, list):
        for item in variables:
            field = _field_descriptor(item)
            if field is not None:
                fields.append(field)

    if fields:
        return fields

    placeholders = embedded.get("placeholders")
    if not isinstance(placeholders, list):
        placeholders = (
            template_json.get("placeholders")
            if isinstance(template_json, dict)
            else None
        )
    if isinstance(placeholders, list):
        for item in placeholders:
            name = _strip_braces(item)
            if name:
                fields.append(_text_field(name))

    if fields:
        return fields

    # Last resort: derive the fields from the tokens actually present in HTML.
    for name in dict.fromkeys(_PLACEHOLDER_RE.findall(html)):
        name = name.strip()
        if name:
            fields.append(_text_field(name))
    return fields


def _field_descriptor(item) -> dict | None:
    if isinstance(item, str):
        name = _strip_braces(item)
        return _text_field(name) if name else None
    if not isinstance(item, dict):
        return None

    name = item.get("fieldName") or _strip_braces(item.get("placeholder"))
    if not isinstance(name, str) or not name.strip():
        return None

    field = _text_field(name)
    field["type"] = str(item.get("type") or "text")
    field["required"] = bool(item.get("required", False))
    if "sampleValue" in item:
        field["sample_value"] = item["sampleValue"]
    return field


def _text_field(name: str) -> dict:
    return {
        "name": name,
        "placeholder": "{{%s}}" % name,
        "type": "text",
        "required": False,
    }


def _strip_braces(value) -> str | None:
    if not isinstance(value, str):
        return None
    return value.replace("{{", "").replace("}}", "").strip() or None


def _resolve_document_type(slug: str, editor: str, template_json) -> dict:
    """Pick the document type the imported template should be attached to.

    Priority: an explicit ``document_type`` code inside the editor JSON, then
    a slug keyword, then the editor default.  The bundle's own
    ``documentType.name`` is the template name, not a document type, so it is
    deliberately not used here.
    """
    declared = _declared_document_type(template_json)
    if declared:
        return declared

    for hint, (code, name) in _DOCUMENT_TYPE_HINTS:
        if hint in slug:
            return {"code": code, "name": name}

    code, name = _EDITOR_DOCUMENT_TYPES.get(editor, _DEFAULT_DOCUMENT_TYPE)
    return {"code": code, "name": name}


def _declared_document_type(template_json) -> dict | None:
    if not isinstance(template_json, dict):
        return None

    for key in ("documentType", "document_type"):
        value = template_json.get(key)
        if isinstance(value, dict):
            code = str(value.get("code") or "").strip()
            if code:
                return {
                    "code": code,
                    "name": str(value.get("name") or code).strip(),
                }
        elif isinstance(value, str) and value.strip():
            code = value.strip()
            return {"code": code, "name": code.replace("_", " ").title()}
    return None
