# Data Isolation Verification Report

**Date:** 2026-02-15  
**Test:** Multi-tenant data isolation between companies

---

## Summary

✅ **DATA ISOLATION IS WORKING CORRECTLY**

Each company can only access their own data. Companies cannot see or access other companies' documents, templates, or sensitive information.

---

## Test Setup

| Company | Email | User ID |
|---------|-------|---------|
| Company 1 | fixtest@company.com | User A |
| Company 2 | company2@example.com | User B |

---

## Verification Tests

### Test 1: Document List Isolation
**Company 1's Documents:**
```bash
GET /api/documents/list/ (as Company 1)
```
Result: Returns 1 document (ID 6 - Alice Johnson's certificate)

**Company 2's Documents:**
```bash
GET /api/documents/list/ (as Company 2)
```
Result: Returns `[]` (empty array)

✅ **PASSED** - Company 2 cannot see Company 1's documents

---

### Test 2: Document Detail Access Control
**Company 2 tries to access Company 1's document (ID 6):**
```bash
GET /api/documents/6/ (as Company 2)
```
Result:
```json
{
    "detail": "Document not found"
}
```

✅ **PASSED** - Company 2 gets 404 when trying to access Company 1's document

---

### Test 3: Template Isolation
**Verified in Code:** `DocumentTemplateListCreateAPIView.get_queryset()`
```python
def get_queryset(self):
    return DocumentTemplate.objects.filter(
        company=self.request.user.company
    )
```

**Verified in Code:** `DocumentTemplateRetrieveUpdateDestroyAPIView.get_queryset()`
```python
def get_queryset(self):
    return DocumentTemplate.objects.filter(
        company=self.request.user.company
    )
```

✅ **PASSED** - Templates are filtered by company

---

### Test 4: Document Query Isolation
**Verified in Code:** `CompanyDocumentListView.get()`
```python
def get(self, request):
    company = request.user.company
    queryset = CompanyDocument.objects.filter(company=company)
```

**Verified in Code:** `CompanyDocumentDetailView.get_object()`
```python
def get_object(self, request, pk):
    company = request.user.company
    try:
        return CompanyDocument.objects.get(
            company=company,  # <-- Filters by company
            pk=pk,
        )
```

**Verified in Code:** `CompanyDocumentFieldUpdateView.get_object()`
```python
def get_object(self, request, pk):
    company = request.user.company
    try:
        return CompanyDocument.objects.get(
            company=company,  # <-- Filters by company
            pk=pk,
        )
```

✅ **PASSED** - All document queries filter by company

---

### Test 5: Certificate Rendering Access Control
**Verified in Code:** `CertificateRenderAPIView.post()`
```python
# Get the template (must belong to user's company)
template = DocumentTemplate.objects.get(
    id=template_id,
    company=company  # <-- Filters by company
)

# Get the document (must belong to user's company)
document = CompanyDocument.objects.get(
    id=document_id,
    company=company  # <-- Filters by company
)
```

✅ **PASSED** - Can only render certificates for own documents/templates

---

## Security Analysis

### What Each Company Can Access

| Resource | Company 1 | Company 2 |
|----------|-----------|-----------|
| Own Documents | ✅ Yes | ✅ Yes |
| Other's Documents | ❌ No | ❌ No |
| Own Templates | ✅ Yes | ✅ Yes |
| Other's Templates | ❌ No | ❌ No |
| Document Types | ✅ Yes (shared) | ✅ Yes (shared) |
| QR Verification | ✅ Yes (public) | ✅ Yes (public) |

### Document Types - Shared Resource
Document types are **global/shared** across all companies (e.g., "CERT", "LIC"). This is intentional as they represent standard document categories.

### QR Verification - Public Access
QR verification is **public** (no authentication required) because QR codes are meant to be scanned by anyone to verify certificate authenticity. The verification only returns:
- Company name
- Document type
- Recipient
- Issue/expiry dates
- Fields (certificate data)

No sensitive internal data is exposed.

---

## Code Review: Isolation Mechanisms

### 1. Queryset Filtering
All list views filter by `request.user.company`:
```python
DocumentTemplate.objects.filter(company=self.request.user.company)
CompanyDocument.objects.filter(company=company)
```

### 2. Object-Level Permissions
All detail views check both `pk` AND `company`:
```python
CompanyDocument.objects.get(company=company, pk=pk)
```

### 3. Authentication Required
All sensitive endpoints require `IsAuthenticated`:
```python
permission_classes = [IsAuthenticated]
```

### 4. Session-Based Security
Uses Django's session authentication with CSRF protection for state-changing operations.

---

## Conclusion

✅ **The API has proper multi-tenant data isolation**

Each company:
- Can only see their own documents and templates
- Cannot access other companies' data (gets 404)
- Can only render certificates using their own templates and documents
- Shares only global document types and public QR verification

**The current structure is secure and working correctly for a user/company-based system.**
