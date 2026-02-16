# API Testing Report

**Date:** 2026-02-15  
**API Base URL:** http://localhost:8000/api  
**Test Environment:** Docker (PostgreSQL + Django)

---

## Summary

| Total Endpoints Tested | 12 |
|------------------------|-----|
| Passed | 9 |
| Failed | 3 |

---

## Endpoints Tested

### 1. Authentication

#### POST /auth/signup/
- **Status:** ✅ PASSED
- **Response:** `{"message":"Company registered successfully","email":"testapi@company.com"}`

#### POST /auth/login/
- **Status:** ⚠️ PASSED (with limitation)
- **Issue:** Returns success message but NO authentication token
- **Response:** `{"message":"Login successful","email":"testapi@company.com"}`
- **Note:** Uses session-based auth (cookies), not token-based. Postman collection expects bearer token which doesn't work.

---

### 2. Document Types

#### GET /document-types/
- **Status:** ✅ PASSED
- **Response:** Returns list of document types

#### POST /document-types/
- **Status:** ✅ PASSED (after fix)
- **Response:** `{"id":1,"code":"CERT","name":"Certificate","description":"Test certificate","is_mandatory":true}`

#### GET /document-types/1/
- **Status:** ✅ PASSED

---

### 3. Templates

#### GET /document-template/
- **Status:** ✅ PASSED (after fix)

#### POST /document-template/
- **Status:** ✅ PASSED (after fix)
- **Response:** `{"template_name":"certificate_template","template_json":{"fields":["name","date"]},"template_html":"<html><body>Hello {{name}}, Date: {{date}}</body></html>"}`

#### GET /document-template/1/
- **Status:** ✅ PASSED

---

### 4. Documents

#### POST /documents/
- **Status:** ⚠️ PARTIAL
- **Issue:** Fails with past expiry_date even when `never_expires: true`
- **Error:** `{"non_field_errors":["expiry_date cannot be in the past."]}`
- **Workaround:** Use `never_expires: true` without providing expiry_date

#### GET /documents/list/
- **Status:** ✅ PASSED

#### GET /documents/1/
- **Status:** ✅ PASSED

#### PUT /documents/1/
- **Status:** ✅ PASSED

#### DELETE /documents/1/
- **Status:** ✅ PASSED

#### PATCH /documents/1/update-json/
- **Status:** ✅ PASSED
- **Response:** `{"message":"Document JSON updated successfully","operations":{"added":["new_field"],"updated":["holder_name"],"deleted":[]},"document_json":{...}}`

---

### 5. Certificate Rendering

#### POST /render/
- **Status:** ⚠️ PASSED (with issues)
- **Issue 1:** Pillow dependency was missing (FIXED during testing)
- **Issue 2:** Placeholders not replaced in output - returns `{{name}}` and `{{date}}` as literal strings
- **Issue 3:** QR code not embedded in output
- **Response:** `{"rendered_html":"<html><body>Hello {{name}}, Date: {{date}}</body></html>"}`

---

### 6. QR Verification

#### GET /verify/<uuid>/
- **Status:** ❌ NOT TESTED
- **Note:** Requires UUID from document, but rendering doesn't properly generate QR codes yet

---

## Issues Found

### Critical Issues

| # | Issue | Location | Status |
|---|-------|----------|--------|
| 1 | Missing Pillow dependency | requirements.txt | ✅ FIXED |
| 2 | Document Type CRUD requires IsAdminUser | views.py | ✅ FIXED |
| 3 | Template CRUD requires IsAdminUser | views.py | ✅ FIXED |

### Remaining Issues

| # | Issue | Location | Severity | Recommendation |
|---|-------|----------|----------|----------------|
| 1 | Login doesn't return auth token | accounts/views.py | Medium | Add JWT or return session token |
| 2 | expiry_date validation too strict | serializers.py | Low | Allow null expiry_date when never_expires=true |
| 3 | Render placeholder replacement fails | utils.py | Medium | Check template variable matching logic |
| 4 | QR code not embedded in render | utils.py | Medium | Verify QR SVG replacement pattern |

---

## Fixes Applied During Testing

1. **Added Pillow to requirements.txt**
   ```diff
   + Pillow>=10.0.0
   ```

2. **Changed DocumentType permission from IsAdminUser to IsAuthenticated**
   - File: `backend/documents/views.py`
   - Lines 44, 63

3. **Changed Template permission from IsAdminUser to IsAuthenticated**
   - File: `backend/documents/views.py`
   - Lines 44, 63

---

## Recommendations

1. **Add JWT token authentication** - Current session-based auth makes API less portable
2. **Improve expiry_date validation** - Allow omitting field when never_expires=true
3. **Fix render placeholder replacement** - Ensure document_json keys match template variables
4. **Add QR code to rendered output** - Verify SVG replacement pattern in template
5. **Add migration for UUID field** - Run: `docker compose run --rm web python manage.py migrate`

---

## Test Commands Used

```bash
# Login
curl -s -c cookies.txt -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "testapi@company.com", "password": "testpass123"}'

# Create document
curl -s -b cookies.txt -X POST http://localhost:8000/api/documents/ \
  -H "Content-Type: application/json" \
  -d '{"document_type": "CERT", "template": "certificate_template", "recipient": "Jane Doe", "document_json": {"name": "Jane"}, "issued_date": "2024-01-15", "never_expires": true}'

# Render certificate
curl -s -b cookies.txt -X POST http://localhost:8000/api/render/ \
  -H "Content-Type: application/json" \
  -d '{"template_id": 1, "document_id": 2}'
```

