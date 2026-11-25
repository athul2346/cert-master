"""Project-wide DRF exception handling.

Django's default reaction to an unhandled database error is an HTTP 500 (and,
with ``DEBUG=True``, a full traceback page). API clients get nothing they can
act on and the stack trace is exposed.

This module converts the predictable database failures — duplicate keys and
rows that are still referenced elsewhere — into small, human-readable JSON
responses, while leaving every other exception on DRF's normal path.

Response shape for a conflict::

    {
        "detail": "A template with this name already exists ...",
        "code": "duplicate_entry",
        "errors": {"template_name": ["A template with this name already exists ..."]}
    }

``constraint`` is added only when ``DEBUG`` is on, to keep the diagnostic
useful locally without leaking schema details in production.
"""

import logging
import re

from django.conf import settings
from django.db import IntegrityError
from django.db.models import ProtectedError, RestrictedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

# Constraint name prefix -> (serializer field, human-readable message).
# Postgres truncates identifiers to 63 characters and Django appends a hash
# before "_uniq", so matching on the readable prefix is intentional.
CONSTRAINT_MESSAGES = {
    "documents_documenttempla_company_id_template_name": (
        "template_name",
        "A template with this name already exists for your company. "
        "Open the existing template to edit it, or choose a different name.",
    ),
    "documents_documenttype_company_id_code": (
        "code",
        "A document type with this code already exists for your company.",
    ),
    "documents_documentfield_document_id_key": (
        "key",
        "This field key already exists on the document.",
    ),
    "unique_company_document": (
        "recipient",
        "A document already exists for this recipient and document type.",
    ),
}

_UNIQUE_CONSTRAINT_RE = re.compile(
    r'duplicate key value violates unique constraint "(?P<constraint>[^"]+)"'
)


def api_exception_handler(exc, context):
    """DRF ``EXCEPTION_HANDLER`` entry point (see settings.REST_FRAMEWORK)."""
    if isinstance(exc, IntegrityError):
        return _integrity_error_response(exc, context)

    if isinstance(exc, (ProtectedError, RestrictedError)):
        return _conflict_response(
            "This record is still used by other data and cannot be removed.",
            code="protected_relation",
        )

    return drf_exception_handler(exc, context)


def _integrity_error_response(exc, context):
    text = str(exc)
    match = _UNIQUE_CONSTRAINT_RE.search(text)
    constraint = match.group("constraint") if match else ""
    known = _lookup_constraint(constraint) if constraint else None

    if known:
        # Expected client-side conflict: one concise log line, no traceback.
        logger.info(
            "Duplicate rejected in %s (constraint=%s)",
            _view_name(context),
            constraint,
        )
    else:
        # Unexpected database rejection: keep the traceback for debugging.
        logger.error(
            "IntegrityError answered with 409 in %s",
            _view_name(context),
            exc_info=exc,
        )

    if match:
        field, message = known or (
            None,
            "A record with these details already exists. "
            "Refresh the page and try again.",
        )
        return _conflict_response(
            message,
            code="duplicate_entry",
            field=field,
            constraint=constraint,
        )

    if "violates foreign key constraint" in text:
        message = (
            "This action references data that no longer exists. "
            "Refresh the page and try again."
        )
    else:
        message = (
            "This request conflicts with the current state of the data. "
            "Refresh the page and try again."
        )

    return _conflict_response(message, code="integrity_error")


def _lookup_constraint(constraint):
    for prefix, entry in CONSTRAINT_MESSAGES.items():
        if constraint.startswith(prefix):
            return entry
    return None


def _conflict_response(detail, *, code, field=None, constraint=""):
    body = {"detail": detail, "code": code}
    if field:
        body["errors"] = {field: [detail]}
    if settings.DEBUG and constraint:
        body["constraint"] = constraint
    return Response(body, status=status.HTTP_409_CONFLICT)


def _view_name(context):
    view = (context or {}).get("view")
    return view.__class__.__name__ if view is not None else "unknown view"
