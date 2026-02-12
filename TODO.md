# Certificate Render Feature Implementation

## Tasks Completed

### Step 1: Add UUID to CompanyDocument Model
- [x] Add `uuid` field to CompanyDocument model
- [x] Generate migration
- [ ] Run migration (when Docker is available)

### Step 2: Add PUBLIC_BASE_URL to settings.py
- [x] Add `PUBLIC_BASE_URL` from environment variable

### Step 3: Create Render Utility Function
- [x] Create `render_certificate_html()` in utils.py
- [x] Handle placeholder replacement ({{key}})
- [x] Handle QR code generation as base64
- [x] Replace QR SVG placeholder with base64 img

### Step 4: Add Render Endpoint
- [x] Add URL pattern for `/api/documents/render/`

### Step 5: Add Render View
- [x] Create CertificateRenderAPIView class
- [x] Handle POST request with template_id and document_id
- [x] Return rendered HTML

### Step 6: Update Document URLs to Use ID
- [x] Changed `/<document_type>/<recipient>/` to `/<int:pk>/`
- [x] Changed `/<document_type>/<recipient>/update-json/` to `/<int:pk>/update-json/`
- [x] Updated CompanyDocumentDetailView to use pk
- [x] Updated CompanyDocumentJsonUpdateView to use pk

### Step 7: Remove QRGenerate API
- [x] Removed QRGenerateAPIView class
- [x] Removed generate/ endpoint
- [x] Removed generate_qr_image function from utils.py
- [x] Removed QRGenerateSerializer import

## Current API Endpoints

| URL | Method | Description |
|-----|--------|-------------|
| `/api/auth/login/` | POST | User login |
| `/api/auth/signup/` | POST | Company registration |
| `/api/document-types/` | GET/POST | List/create document types |
| `/api/document-types/<pk>/` | GET/PUT/DELETE | Manage document type |
| `/api/document-template/` | GET/POST | List/create templates |
| `/api/document-template/<pk>/` | GET/PUT/DELETE | Manage template |
| `/api/documents/` | POST | Create document |
| `/api/documents/list/` | GET | List company documents |
| `/api/documents/<pk>/` | GET/PUT/DELETE | Get/Update/Delete by ID |
| `/api/documents/<pk>/update-json/` | PATCH | Partial update JSON |
| `/api/render/` | POST | Render certificate HTML |
| `/api/verify/<uuid>/` | GET | Verify certificate |

## Next Steps
- [ ] Run migration: `docker compose run --rm web python manage.py migrate`
- [ ] Set PUBLIC_BASE_URL in .env file
- [ ] Test the render API endpoint

