# Predefined templates

Drop the template source bundle here. Each template is a pair of files with
the same name:

```
predefined_templates/
├── certificate-editor/
│   ├── certificate-editor__professional-certificate.html
│   ├── certificate-editor__professional-certificate.json
│   ├── certificate-editor__swiss-architectural-certificate.html
│   ├── certificate-editor__swiss-architectural-certificate.json
│   ├── certificate-editor__employee-id-card.html
│   └── certificate-editor__employee-id-card.json
└── document-editor/
    ├── document-editor__corporate-offer-graphic.html
    ├── document-editor__corporate-offer-graphic.json
    └── ...
```

The slug is the file name without its extension (for example
`certificate-editor__professional-certificate`). The folder name is only used
as a fallback for the `template-editor` metadata.

## Required metadata in the HTML

```html
<meta name="template-editor" content="certificate-editor">
<meta name="template-page-size" content="A4">
<meta name="template-dimensions-mm" content="210mm x 297mm">
<meta name="template-orientation" content="portrait">

<script id="template-dynamic-values" type="application/json">
  { "recipient_name": "Jane Doe", "course_name": "..." }
</script>
```

- `template-dynamic-values` keys become `dynamic_fields` in the API response.
- Document Editor templates must wrap each page in
  `<section class="doc-page" id="page-N">`; the page count is derived from
  those sections. Certificate Editor templates have a single page.
- The `@page { size: Wmm Hmm; margin: 0; }` rule is kept as-is for print/PDF
  parity.

## Optional: declare the document type

If a package should be imported under a specific document type, add it to the
`.json` file:

```json
{
  "name": "Professional Certificate",
  "document_type": { "code": "CERT", "name": "Certificate" }
}
```

When omitted, the backend infers the type from the slug
(`offer-letter` → `OFFER`, `appointment-letter` → `APPT`, …) and falls back to
the editor default (`CERT` for Certificate Editor, `DOC` for Document Editor).

## API

- `GET /api/predefined-templates/` — metadata catalog
- `GET /api/predefined-templates/{slug}/` — full package (`template_html`,
  `template_json`)
- `POST /api/predefined-templates/{slug}/import/` — copy into the caller's
  company, creating the standard document type if needed

The folder can be moved with the `PREDEFINED_TEMPLATES_DIR` setting.
