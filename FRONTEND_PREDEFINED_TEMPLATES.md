# Predefined Templates — Frontend Handoff

> Ready-made template bundle: 10 packages (`.html` + `.json`) served by the
> backend. Backend endpoints added this session live in
> `backend/documents/predefined.py`, `backend/documents/views.py`,
> `backend/documents/urls.py`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/predefined-templates/` | Metadata catalog (10 items) |
| `GET` | `/api/predefined-templates/{slug}/` | Full package: metadata + `template_html` + `template_json` |
| `POST` | `/api/predefined-templates/{slug}/import/` | Copy package into the caller's company |

All require authentication (session cookie). The bundle lives on the server at
`backend/documents/predefined_templates/` (read at runtime).

## Recommended flow

1. `GET /api/predefined-templates/` → gallery / editor metadata.
2. `GET /api/predefined-templates/{slug}/` → preview with `template_html`
   (e.g. iframe `srcDoc`) and build the field form from `dynamic_fields`.
3. `POST /api/predefined-templates/{slug}/import/` → returns a normal
   `DocumentTemplate` (`id`, `document_type`, `template_name`, `template_html`,
   `template_json`) or `409 {code: "already_imported", template_id}`.
4. Create the document with the imported template.
5. Render: `POST /api/render/ {template_id, document_id}` → `rendered_html`.

## Shipped bundle (verified)

| `id` | `slug` | `name` | Editor | Pages | Size / Orientation |
|---|---|---|---|---|---|
| `dt-id-card` | `certificate-editor__employee-id-card` | Corporate Employee ID Card | certificate-editor | 1 | ID Badge (Standard), 54×86mm, portrait |
| `dt-1` | `certificate-editor__professional-certificate` | Professional Certificate | certificate-editor | 1 | Certificate (Standard), 297×210mm, landscape |
| `dt-swiss-arch` | `certificate-editor__swiss-architectural-certificate` | Swiss Architectural Credential | certificate-editor | 1 | Certificate (Standard), 297×210mm, landscape |
| `dt-appointment-letter` | `document-editor__appointment-letter` | Appointment Letter (Rules & Privacy Policy) | document-editor | 2 | A4, 210×297mm, portrait |
| `dt-announcement` | `document-editor__company-announcement` | Official Company Announcement | document-editor | 1 | A4, portrait |
| `dt-offer-graphic` | `document-editor__corporate-offer-graphic` | Corporate Offer (Graphic) | document-editor | 1 | A4, portrait |
| `dt-offer-india` | `document-editor__offer-letter-india` | Offer Letter (India — CTC & Privacy) | document-editor | 2 | A4, portrait |
| `dt-official-notice` | `document-editor__official-hr-notice` | Official HR & Statutory Notice | document-editor | 1 | A4, portrait |
| `dt-privacy-policy` | `document-editor__privacy-policy` | Privacy Policy & Data Protection | document-editor | 2 | A4, portrait |
| `dt-relieving-letter` | `document-editor__relieving-experience-letter` | Relieving & Experience Letter | document-editor | 1 | A4, portrait |

Document types used on import (per company): `CERT` (Certificate), `IDCARD` (ID Card),
`OFFER` (Offer Letter), `APPT` (Appointment Letter), `EXP` (Experience Letter),
`POLICY` (Policy), `ANN` (Announcement), `NOTICE` (Notice).

## ⚠️ Critical: field keys

`dynamic_fields[].name` values are **placeholder labels with spaces**, e.g.
`"Recipient Name"`, `"CTC / Salary"`, `"Document ID"`. They must be used
verbatim as document field keys when creating a document — plain snake_case keys
(`recipient_name`) will **not** be substituted by the renderer.

## Example: create document from an imported template

```json
POST /api/documents/
{
    "document_type": 1,
    "template": 1,
    "recipient": "Jane Doe",
    "document_json": {
        "Document ID": "DOC-001",
        "Recipient Name": "Jane Doe",
        "Course Title": "Advanced Distributed Systems",
        "Issue Date": "2026-11-25",
        "Grade": "A+"
    },
    "issued_date": "2026-11-25",
    "expiry_date": "2027-11-25",
    "never_expires": false
}
```

## Example: render

```json
POST /api/render/
{ "template_id": 1, "document_id": 1 }
```
→ `rendered_html` contains substituted values; no `{{...}}` tokens remain.

## Notes

- Multi-page templates embed `<!-- PAGE_BREAK -->` + `<section class="doc-page">`;
  rendered HTML keeps page structure for PDF (WeasyPrint/Puppeteer) pipelines.
- Some templates reference external assets (Google Fonts, Unsplash image for
  `{{Photo}}`) — preview/render needs network access.
- QR slot: certificate templates include a QR area with
  `data-qr-target="https://authensia.com/verify/{{Document ID}}"`; the render
  endpoint injects a QR only when the document status is `ACTIVE`.
