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
    "cin_number": "CIN123456789"
}
```

**Success Response (201):**
```json
{
    "message": "Company registered successfully",
    "email": "company@example.com"
}
```

**Error Response (400 - CIN exists):**
```json
{
    "cin_number": ["CIN already exists"]
}
```

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
    "is_mandatory": true
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
        "is_mandatory": true
    },
    {
        "id": 2,
        "code": "LIC",
        "name": "License",
        "description": "Business license",
        "is_mandatory": false
    }
]
```

---

### 5. Get Single Document Type

**Endpoint:** `GET /document-types/1/`

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
    "is_mandatory": true
}
```

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

### 9. Get Single Template

**Endpoint:** `GET /document-template/4`

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

**Error Response (404 - Not owned by user):**
```json
{
    "detail": "Not found."
}
```

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

### 11. List Documents

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

### 13. Update Document (Full PUT)

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

### 14. Partial Update Document Fields (PATCH)

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

### 15. Delete Document

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

### 16. Render Certificate

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

### 17. Verify Certificate by UUID

**Endpoint:** `GET /verify/{uuid}/`

**Headers:** None (public endpoint)

**URL Example:** `GET /verify/550e8400-e29b-41d4-a716-446655440000/`

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
| `/auth/login/` | N/A | Public |
| `/document-types/` | By Company | Only see own document types |
| `/document-types/{id}/templates/` | By Company | See templates under a document type |
| `/document-template/` | By Company | Only see own templates (linked to document types) |
| `/documents/` | By Company | Only see own documents |
| `/render/` | By Company | Only render own docs/templates |
| `/verify/{uuid}/` | Public | Anyone can verify certificates |
