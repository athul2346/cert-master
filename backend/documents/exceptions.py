from rest_framework import status
from rest_framework.exceptions import APIException


class DocumentLocked(APIException):
    """Raised when a write is attempted on an ACTIVE (issued) document."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "This document is ACTIVE and can no longer be modified."
    default_code = "document_locked"
