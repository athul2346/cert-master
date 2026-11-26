# API Reference Guide - Sample Inputs & Outputs

**Base URL:** `http://localhost:8000/api`

---

## Authentication

All protected endpoints require session-based authentication. Login first to get a session cookie.

### 1. Signup (Create Company)

**Endpoint:** `POST /auth/signup/`

**Headers:**
```http
Content-Type: application/json
```

**Request Body:**
```json
{
    "email": "company@example.com",
    "password": "SecurePass123!",
    "organisation_name": "My Company",
    "classification": "private",
    "country": "USA",
    "cin_number": "CIN123456789",
    "company_url": "https://company.com"
}
```

**Success Response (201):**
```json
{
    "message": "Company registered successfully. Please verify the OTP sent to your email; your organisation will then await verification.",
    "email": "company@example.com",
    "status": "PENDING",
    "docs_attached": 0,
    "email_verified": false,
    "otp_sent": true
}
```

An OTP (6 digits by default) is emailed to the signup address. The account
cannot log in until the OTP is verified **and** an admin approves the
organisation. If the email could not be sent, the response still returns
`201` with `"otp_sent": false` and a `warning`; call the resend endpoint.

**Error Response (400 - CIN exists):**
```json
{
    "cin_number": ["CIN already exists"]
}
```

---

### 1.1 Verify Signup OTP

**Endpoint:** `POST /auth/otp/verify/`

**Headers:**
```http
Content-Type: application/json
```

**Request Body:**
```json
{
    "email": "company@example.com",
    "otp": "123456"
}
```

**Success Response (200):**
```json
{
    "message": "Email verified successfully. Your organisation is now awaiting admin verification.",
    "email": "company@example.com",
    "email_verified": true,
    "can_login": false,
    "company_status": "PENDING"
}
```

`can_login` becomes `true` once the organisation has been approved by an admin.

**Error Response (400 - wrong/expired code or already verified):**
```json
{
    "detail": "Invalid or expired verification code."
}
```

**Error Response (429 - too many wrong attempts):**
```json
{
    "detail": "Too many incorrect attempts. Request a new verification code."
}
```

---

### 1.2 Resend Signup OTP

**Endpoint:** `POST /auth/otp/resend/`

**Headers:**
```http
Content-Type: application/json
```

**Request Body:**
```json
{
    "email": "company@example.com"
}
```

**Success Response (200):**
```json
{
    "message": "A new verification code has been sent.",
    "email": "company@example.com",
    "expires_in": 600
}
```

**Error Response (429 - resend cooldown still active):**
```json
{
    "detail": "Please wait 42 seconds before requesting a new code.",
    "retry_after": 42
}
```

**Notes:**
- A new code invalidates any previous unused code.
- Unknown email addresses return `200` with a generic message so the endpoint
  cannot be used to enumerate registered accounts.
- Email can be sent through **SMTP** (default) or the **Resend API**. Select
  with `EMAIL_PROVIDER=smtp|resend|console`. For Resend, set `RESEND_API_KEY`
  (API token) and a verified `DEFAULT_FROM_EMAIL`; the SMTP values are then
  ignored. An explicit `EMAIL_BACKEND` always overrides the provider setting.
- If neither provider nor SMTP host is configured, Django prints the email to
  the server console instead (development fallback).

---

### 2. Login

**Endpoint:** `POST /auth/login/`

**Headers:**
```http
Content-Type: application/json
X-CSRFToken: {csrf_token}
```

**Request Body:**
```json
{
    "email": "company@example.com",
    "password": "SecurePass123!"
}
```

**Success Response (200):**
```json
{
    "message": "Login successful",
    "email": "company@example.com"
}
```

**Error Response (400):**
```json
{
    "non_field_errors": ["Invalid credentials"]
}
```

**Note:** Save the session cookie for subsequent requests.

---

## Document Types (Company-Specific)

**Note:** Document Types are now company-specific. Each company can only see and manage their own document types.

### 3. Create Document Type

**Endpoint:** `POST /document-types/`

**Headers:**
```http
Content-Type: application/json
X-CSRFToken: {csrf_token}
Cookie: sessionid={session_id}
```

**Request Body:**
```json
{
    "code": "CERT",
    "name": "Certificate",
    "description": "Official certificate document",
    "is_mandatory": true
}
```

**Success Response (201):**
```json
{
    "id": 1,
    "code": "CERT",
    "name": "Certificate",
    "description": "Official certificate document",
    "document_canvas": "",
    "is_mandatory": true,
    "templates": []
}
```

---

### 4. List All Document Types

**Endpoint:** `GET /document-types/`

**Headers:**
```http
Cookie: sessionid={session_id}
```

**Success Response (200):**
```json
[
    {
        "id": 1,
        "code": "CERT",
        "name": "Certificate",
        "description": "Official certificate document",
        "document_canvas": "",
        "is_mandatory": true,
        "templates": [
            {
                "id": 4,
                "template_name": "certificate_template",
                "template_json": {
                    "fields": ["recipient_name", "course_name", "issue_date", "certificate_number"]
                },
                "template_html": "<html><body><h1>Certificate of Completion</h1>..."
            }
        ]
    },
    {
        "id": 2,
        "code": "LIC",
        "name": "License",
        "description": "Business license",
        "document_canvas": "",
        "is_mandatory": false,
        "templates": []
    }
]
```

---

### 5. Get/Update/Delete Document Type

**GET /document-types/{pk}/** (Retrieve)
**Headers:**
```http
Cookie: sessionid={session_id}
```
**Success Response (200):**
```json
{
    "id": 1,
    "code": "CERT",
    "name": "Certificate",
    "description": "Official certificate document",
    "document_canvas": "",
    "is_mandatory": true,
    "templates": [
        {
            "id": 4,
            "template_name": "certificate_template",
            "template_json": {
                "fields": ["recipient_name", "course_name", "issue_date", "certificate_number"]
            },
            "template_html": "<html><body><h1>Certificate of Completion</h1>..."
        }
    ]
}
```

**Note:** `templates` contains every template linked to this document type for the logged-in user's company. It is `[]` when none are linked.

**PUT /document-types/{pk}/** (Full Update)
**Headers:**
```http
Content-Type: application/json
X-CSRFToken: {csrf_token}
Cookie: sessionid={session_id}
```
**Request Body:**
```json
{
    "code": "CERT-UPDATED",
    "name": "Updated Certificate",
    "description": "Updated description",
    "is_mandatory": false
}
```
**Success Response (200):** Same as GET.

**PATCH /document-types/{pk}/** (Partial Update)
**Request Body:**
```json
{
    "name": "Partially Updated Certificate"
}
```

**DELETE /document-types/{pk}/**
**Success Response (200):**
```json
{
    "message": "Document type deleted successfully",
    "document_type": {
        "id": 1,
        "code": "CERT",
        "name": "Certificate"
    },
    "documents_preserved": 2,
    "documents_deleted": 5,
    "templates_detached": 1
}
```

ACTIVE documents are preserved with `document_type = null`; non-ACTIVE documents are deleted; templates are preserved and detached from the type.

**Error Response (404):**
```json
{
    "detail": "Not found."
}
```

---

### 6. Get Templates by Document Type

**Endpoint:** `GET /document-types/1/templates/`

**Headers:**
```http
Cookie: sessionid={session_id}
```

**Success Response (200):**
```json
{
    "document_type": {
        "id": 1,
        "code": "CERT",
        "name": "Certificate"
    },
    "templates": [
        {
            "id": 4,
            "document_type": 1,
            "template_name": "certificate_template",
            "template_json": {
                "fields": ["recipient_name", "course_name", "issue_date", "certificate_number"]
            },
            "template_html": "<html><body><h1>Certificate of Completion</h1>..."
        }
    ]
}
```

**Error Response (404):**
```json
{
    "detail": "Document type not found"
}
```

**Note:** Only returns templates belonging to the logged-in user's company.

---

## Templates (Company-Specific)

**Note:** Templates are now linked to a specific Document Type. Each template must specify which document type it belongs to.

### 7. Create Template

**Endpoint:** `POST /document-template/`

**Headers:**
```http
Content-Type: application/json
X-CSRFToken: {csrf_token}
Cookie: sessionid={session_id}
```

**Request Body:**
```json
{
    "document_type": 1,
    "template_name": "certificate_template",
    "template_json": {
        "fields": ["recipient_name", "course_name", "issue_date", "certificate_number"]
    },
    "template_html": "<html><body><h1>Certificate of Completion</h1><p>This certifies that <strong>{{recipient_name}}</strong> has completed <strong>{{course_name}}</strong> on {{issue_date}}.</p><p>Certificate #: {{certificate_number}}</p><div class='qr-code'>{{QR_CODE}}</div></body></html>"
}
```

**Success Response (201):**
```json
{
    "id": 4,
    "document_type": 1,
    "template_name": "certificate_template",
    "template_json": {
        "fields": ["recipient_name", "course_name", "issue_date", "certificate_number"]
    },
    "template_html": "<html><body><h1>Certificate of Completion</h1>..."
}
```

**Error Response (400) — template name already used by this company:**
```json
{
    "template_name": [
        "A template with this name already exists for your company. Open the existing template to edit it, or choose a different name."
    ]
}
```

**Error Response (409) — database conflict (e.g. two concurrent creates):**
```json
{
    "detail": "A template with this name already exists for your company. Open the existing template to edit it, or choose a different name.",
    "code": "duplicate_entry",
    "errors": {
        "template_name": ["A template with this name already exists for your company. Open the existing template to edit it, or choose a different name."]
    }
}
```

**Note:** `POST` always creates a new template. To save changes to an existing one, use `PATCH /document-template/{pk}` (or `PUT`); re-posting an existing `template_name` is rejected.

---

### 8. List Templates

**Endpoint:** `GET /document-template/`

**Headers:**
```http
Cookie: sessionid={session_id}
```

**Success Response (200):**
```json
[
    {
        "id": 4,
        "document_type": 1,
        "template_name": "certificate_template",
        "template_json": {
            "fields": ["recipient_name", "course_name", "issue_date", "certificate_number"]
        },
        "template_html": "<html><body><h1>Certificate of Completion</h1>..."
    }
]
```

**Note:** Only returns templates belonging to the logged-in user's company.

---

### 9. Get/Update/Delete Template

**GET /document-template/{pk}**
**Headers:**
```http
Cookie: sessionid={session_id}
```
**Success Response (200):**
```json
{
    "id": 4,
    "document_type": 1,
    "template_name": "certificate_template",
    "template_json": {
        "fields": ["recipient_name", "course_name", "issue_date", "certificate_number"]
    },
    "template_html": "<html><body><h1>Certificate of Completion</h1>..."
}
```

**PUT /document-template/{pk}** (Full Update)
**Headers:**
```http
Content-Type: application/json
X-CSRFToken: {csrf_token}
Cookie: sessionid={session_id}
```
**Request Body:**
```json
{
    "document_type": 1,
    "template_name": "updated_template",
    "template_json": {...},
    "template_html": "<html>updated</html>"
}
```

**PATCH /document-template/{pk}** (Partial)
**Request Body:**
```json
{
    "template_name": "partially_updated"
}
```

**DELETE /document-template/{pk}/**
**Success Response (204):** No content.

**Error Response (404):**
```json
{
    "detail": "Not found."
}
```

---

## Predefined Templates (Source Bundle)

Ready-made templates ship with the backend as `.html` + `.json` packages under
`backend/documents/predefined_templates/` (see the README there for the exact
layout). These endpoints expose them to the frontend; nothing is created until
`/import/` is called.

### 9a. List Predefined Templates

**Endpoint:** `GET /predefined-templates/`

**Success Response (200):**
```json
[
    {
        "id": "dt-1",
        "slug": "certificate-editor__professional-certificate",
        "name": "Professional Certificate",
        "editor": "certificate-editor",
        "editor_label": "Certificate Editor (Canvas)",
        "page_size": "Certificate (Standard)",
        "dimensions_mm": {"width": 297, "height": 210},
        "orientation": "landscape",
        "pages": 1,
        "validity_days": 365,
        "dynamic_fields": [
            {
                "name": "Document ID",
                "placeholder": "{{Document ID}}",
                "type": "text",
                "required": true,
                "sample_value": "VERIFIED-474705"
            }
        ],
        "document_type": {"code": "CERT", "name": "Certificate"}
    }
]
```

- `id` is the bundle's stable identifier (`dt-1`, `dt-offer-india`, …); `slug`
  is the file-based identifier used in URLs.
- `dynamic_fields[].name` is the **exact placeholder text** (including spaces,
  e.g. `Recipient Name`). Use it as the `DocumentField.key` / `document_json`
  key when creating a document, otherwise `{{...}}` tokens will not be
  replaced.
- `document_type` is the standard type that `/import/` will create (or reuse)
  for the caller's company. It comes from the package JSON when declared,
  otherwise it is inferred from the slug and editor.
- `validity_days` is the template's suggested validity (may be `null`).

---

### 9b. Get a Predefined Template

**Endpoint:** `GET /predefined-templates/{slug}/`

**Success Response (200):** the same object as the list item, plus:
```json
{
    "id": "dt-1",
    "slug": "certificate-editor__professional-certificate",
    "name": "Professional Certificate",
    "template_html": "<!DOCTYPE html>...",
    "template_json": {
        "schemaVersion": "1.0",
        "documentType": {"id": "dt-1", "name": "Professional Certificate"},
        "placeholders": ["{{Document ID}}", "{{Recipient Name}}"],
        "dynamicVariables": [
            {
                "placeholder": "{{Recipient Name}}",
                "fieldName": "Recipient Name",
                "type": "text",
                "required": true,
                "sampleValue": "Ananya Sharma"
            }
        ],
        "sampleData": {"Recipient Name": "Ananya Sharma"}
    }
}
```

The `template_html` / `template_json` keys match the create-template payload,
so the response can be posted to `/document-template/` unchanged.

**Error Response (404):**
```json
{"detail": "Predefined template not found"}
```

---

### 9c. Import a Predefined Template

**Endpoint:** `POST /predefined-templates/{slug}/import/`

Creates the standard `DocumentType` for the caller's company if missing, then
copies the package into a normal `DocumentTemplate`. No request body needed.

**Success Response (201):** the created template, same shape as
`POST /document-template/`.

**Error Response (409) — already imported:**
```json
{
    "detail": "This template has already been imported for your company.",
    "code": "already_imported",
    "template_id": 12
}
```

Importing never overwrites user edits; use `PATCH /document-template/{id}` to
change an imported template.

---

## Documents (Company-Specific)

**Note:** When creating a document, the `document_type` must match the `document_type` linked to the selected `template`. If there's a mismatch, you'll receive an error indicating which document type the template is linked to.

### 10. Create Document

**Endpoint:** `POST /documents/`

**Headers:**
```http
Content-Type: application/json
X-CSRFToken: {csrf_token}
Cookie: sessionid={session_id}
```

**Request Body (with document_json):**
```json
{
    "document_type": 1,
    "template": 1,
    "recipient": "Alice Johnson",
    "document_json": {
        "recipient_name": "Alice Johnson",
        "course_name": "Advanced Python Programming",
        "issue_date": "2024-01-15",
        "certificate_number": "CERT-2024-001"
    },
    "issued_date": "2024-01-15",
    "expiry_date": "2025-01-15",
    "never_expires": false
}
```

**Success Response (201):**
```json
{
    "id": 6,
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "document_type": 1,
    "template": 1,
    "recipient": "Alice Johnson",
    "fields": [
        {"key": "recipient_name", "value": "Alice Johnson"},
        {"key": "course_name", "value": "Advanced Python Programming"},
        {"key": "issue_date", "value": "2024-01-15"},
        {"key": "certificate_number", "value": "CERT-2024-001"}
    ],
    "issued_date": "2024-01-15",
    "expiry_date": "2025-01-15",
    "never_expires": false,
    "status": "ACTIVE"
}
```

**Error Response (400 - Validation Error):**
```json
{
    "non_field_errors": ["If never_expires is true, expiry_date must be empty."]
}
```

---

### 11. Get Documents by Document Type

**Endpoint:** `GET /document-types/{document_type_id}/documents/`

**Headers:**
```http
Cookie: sessionid={session_id}
```

**Success Response (200):**
```json
{
    "document_type": {
        "id": 1,
        "code": "CERT",
        "name": "Certificate"
    },
    "documents": [
        {
            "id": 6,
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
            "document_type": 1,
            "template": 1,
            "recipient": "Alice Johnson",
            "fields": [
                {"key": "recipient_name", "value": "Alice Johnson"},
                {"key": "course_name", "value": "Advanced Python Programming"},
                {"key": "issue_date", "value": "2024-01-15"},
                {"key": "certificate_number", "value": "CERT-2024-001"}
            ],
            "issued_date": "2024-01-15",
            "expiry_date": "2025-01-15",
            "never_expires": false,
            "status": "ACTIVE"
        }
    ]
}
```

**Error Response (404):**
```json
{
    "detail": "Document type not found"
}
```

**Note:** Only returns documents belonging to the logged-in user's company for the specified document type.

---

### 12. List Documents

**Endpoint:** `GET /documents/list/`

**Headers:**
```http
Cookie: sessionid={session_id}
```

**Success Response (200):**
```json
[
    {
        "id": 6,
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "document_type": 1,
        "template": 1,
        "recipient": "Alice Johnson",
        "fields": [
            {"key": "recipient_name", "value": "Alice Johnson"},
            {"key": "course_name", "value": "Advanced Python Programming"},
            {"key": "issue_date", "value": "2024-01-15"},
            {"key": "certificate_number", "value": "CERT-2024-001"}
        ],
        "issued_date": "2024-01-15",
        "expiry_date": "2025-01-15",
        "never_expires": false,
        "status": "ACTIVE"
    }
]
```

**Note:** Only returns documents belonging to the logged-in user's company.

---

### 12. Get Single Document

**Endpoint:** `GET /documents/6/`

**Headers:**
```http
Cookie: sessionid={session_id}
```

**Success Response (200):**
```json
{
    "id": 6,
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "document_type": 1,
    "template": 1,
    "recipient": "Alice Johnson",
    "fields": [
        {"key": "recipient_name", "value": "Alice Johnson"},
        {"key": "course_name", "value": "Advanced Python Programming"},
        {"key": "issue_date", "value": "2024-01-15"},
        {"key": "certificate_number", "value": "CERT-2024-001"}
    ],
    "issued_date": "2024-01-15",
    "expiry_date": "2025-01-15",
    "never_expires": false,
    "status": "ACTIVE"
}
```

**Error Response (404 - Not owned by user):**
```json
{
    "detail": "Document not found"
}
```

---

### 14. Update Document (Full PUT)

**Endpoint:** `PUT /documents/6/`

**Headers:**
```http
Content-Type: application/json
X-CSRFToken: {csrf_token}
Cookie: sessionid={session_id}
```

**Request Body:**
```json
{
    "document_type": 1,
    "template": 1,
    "recipient": "Alice Johnson Updated",
    "document_json": {
        "recipient_name": "Alice Johnson Updated",
        "course_name": "Advanced Python Programming",
        "issue_date": "2024-01-15",
        "certificate_number": "CERT-2024-001-UPDATED"
    },
    "issued_date": "2024-01-15",
    "expiry_date": "2026-01-15",
    "never_expires": false,
    "status": "ACTIVE"
}
```

**Success Response (200):**
```json
{
    "id": 6,
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "document_type": 1,
    "template": 1,
    "recipient": "Alice Johnson Updated",
    "fields": [
        {"key": "recipient_name", "value": "Alice Johnson Updated"},
        {"key": "course_name", "value": "Advanced Python Programming"},
        {"key": "issue_date", "value": "2024-01-15"},
        {"key": "certificate_number", "value": "CERT-2024-001-UPDATED"}
    ],
    "issued_date": "2024-01-15",
    "expiry_date": "2026-01-15",
    "never_expires": false,
    "status": "ACTIVE"
}
```

---

### 15. Partial Update Document Fields (PATCH)

**Endpoint:** `PATCH /documents/6/update-fields/`

**Headers:**
```http
Content-Type: application/json
X-CSRFToken: {csrf_token}
Cookie: sessionid={session_id}
```

**Request Body:**
```json
{
    "to_add": {
        "new_field": "new_value"
    },
    "to_update": {
        "recipient_name": "Updated Name"
    },
    "to_delete": ["old_field"]
}
```

**Success Response (200):**
```json
{
    "message": "Document fields updated successfully",
    "operations": {
        "added": ["new_field"],
        "updated": ["recipient_name"],
        "deleted": ["old_field"]
    },
    "fields": [
        {"key": "recipient_name", "value": "Updated Name"},
        {"key": "course_name", "value": "Advanced Python Programming"},
        {"key": "new_field", "value": "new_value"}
    ]
}
```

---

### 16. Delete Document

**Endpoint:** `DELETE /documents/6/`

**Headers:**
```http
X-CSRFToken: {csrf_token}
Cookie: sessionid={session_id}
```

**Success Response (204):**
```json
{
    "message": "Document deleted successfully"
}
```

**Error Response (404):**
```json
{
    "detail": "Document not found"
}
```

---

## Certificate Rendering

### 17. Render Certificate

**Endpoint:** `POST /render/`

**Headers:**
```http
Content-Type: application/json
X-CSRFToken: {csrf_token}
Cookie: sessionid={session_id}
```

**Request Body:**
```json
{
    "template_id": 4,
    "document_id": 6
}
```

**Success Response (200):**
```json
{
    "rendered_html": "<html><body><h1>Certificate of Completion</h1><p>This certifies that <strong>Alice Johnson</strong> has completed <strong>Advanced Python Programming</strong> on 2024-01-15.</p><p>Certificate #: CERT-2024-001</p><img src=\"data:image/png;base64,iVBORw0KGgoAAAANS...\" alt=\"QR Code\" style=\"width: 100%; height: 100%;\"></body></html>"
}
```

**Note:** The response contains fully rendered HTML with:
- All placeholders ({{key}}) replaced with actual values
- QR code embedded as base64 image

**Error Response (404 - Template not found):**
```json
{
    "detail": "Template not found"
}
```

**Error Response (404 - Document not found):**
```json
{
    "detail": "Document not found"
}
```

---

## QR Verification (Public)

### 18. Verify Certificate by UUID

**Endpoint:** `GET /verify-qr/{uuid}/`

**Headers:** None (public endpoint)

**URL Example:** `GET /verify-qr/550e8400-e29b-41d4-a716-446655440000/`

**Success Response (200):**
```json
{
    "verified": true,
    "company": "API Test Company",
    "document_type": "Certificate",
    "recipient": "Alice Johnson",
    "issued_date": "2024-01-15",
    "expiry_date": "2025-01-15",
    "fields": {
        "recipient_name": "Alice Johnson",
        "course_name": "Advanced Python Programming",
        "issue_date": "2024-01-15",
        "certificate_number": "CERT-2024-001"
    },
    "payload": {}
}
```

**Error Response (404 - QR not found):**
```json
{
    "verified": false,
    "reason": "QR code not found"
}
```

**Error Response (403 - Expired):**
```json
{
    "verified": false,
    "reason": "Document has expired"
}
```

**Error Response (403 - Revoked):**
```json
{
    "verified": false,
    "reason": "QR code has been revoked"
}
```

**Error Response (403 - Not Active):**
```json
{
    "verified": false,
    "reason": "Document status: PENDING"
}
```

---

## Quick Reference: curl Commands

### Save session after login:
```bash
curl -s -c cookies.txt -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "company@example.com", "password": "SecurePass123!"}'
```

### Use saved session:
```bash
curl -s -b cookies.txt -X GET http://localhost:8000/api/documents/list/ \
  -H "X-CSRFToken: your-csrf-token"
```

### Create document:
```bash
curl -s -b cookies.txt -X POST http://localhost:8000/api/documents/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: your-csrf-token" \
  -d '{"document_type": 1, "template": 1, "recipient": "Test User", "document_json": {"name": "Test"}, "never_expires": true}'
```

---

## HTTP Status Codes Reference

| Code | Meaning | When It Occurs |
|------|---------|----------------|
| 200 | OK | Successful GET, PUT, PATCH |
| 201 | Created | Successful POST (new resource) |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Validation errors, invalid data |
| 403 | Forbidden | Expired document, revoked QR |
| 404 | Not Found | Resource doesn't exist or not owned |
| 405 | Method Not Allowed | Wrong HTTP method for endpoint |

---

## Data Isolation Summary

| Endpoint | Isolation | Notes |
|----------|-----------|-------|
| `/auth/signup/` | N/A | Public |
| `/auth/otp/verify/` | N/A | Public |
| `/auth/otp/resend/` | N/A | Public |
| `/auth/login/` | N/A | Public |
| `/document-types/` | By Company | Only see own document types |
| `/document-types/{id}/templates/` | By Company | See templates under a document type |
| `/document-types/{id}/documents/` | By Company | See documents under a document type |
| `/document-template/` | By Company | Only see own templates (linked to document types) |
| `/documents/` | By Company | Only see own documents |
| `/render/` | By Company | Only render own docs/templates |
| `/verify/{uuid}/` | Public | Anyone can verify certificates |
