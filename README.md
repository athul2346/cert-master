# cert-master

## Quick Start (Local)

```bash
cp .env.example .env
# Edit .env for local: DEBUG=true, POSTGRES_* match docker-compose.yml
docker compose up --build
```

API docs: See `API_REFERENCE_GUIDE.md` and `postman-collection.json`

## Deploy to Render (Production)

### 1. Push to GitHub
```
git add .
git commit -m "Deploy ready: Render config"
git push origin main
```

### 2. Render.com Dashboard
- Sign up/login: https://render.com
- New → Web Service → Connect your GitHub repo
- Plan: Free (or Starter for custom domain)
- **Runtime: Docker**
- **Root Directory: `./`**
- **Dockerfile: `./Dockerfile`**
- Auto-deploy: yes (on main)

Environment Variables (from `.env.example`):
```
SECRET_KEY=generate new @ https://djecrety.ir/
DEBUG=false
ALLOWED_HOSTS=yourapp.onrender.com,.onrender.com
DATABASE_URL=from Render Postgres below
# PUBLIC_BASE_URL=https://yourapp.onrender.com  (set after first deploy if needed)
```

### 3. Create PostgreSQL Database
- New → PostgreSQL
- Name: cert-master-db
- Plan: Free
- Copy **External Database URL** to Web Service DATABASE_URL env var
- Region same as web service

### 4. Deploy
- Deploy → watch build/logs
- Render auto-runs migrate via `python manage.py migrate` detect? If not, use Shell/CLI: `manage.py migrate`

### 5. Post-Deploy
- Admin: https://yourapp.onrender.com/admin/ (create superuser via shell if needed)
- Test endpoints: `/api/documents/` etc.
- Verify: `/api/verify/{uuid}/`

## Endpoints Summary
See `API_REFERENCE_GUIDE.md`

**Troubleshooting:**
- Build fail: Check logs, ensure git has all files.
- Static: Whitenoise serves.
- Media uploads: POST /api/documents/

## Local Prod Test
```bash
cp .env.example .env
# Set DEBUG=false, generate SECRET_KEY, use docker postgres vars
# PUBLIC_BASE_URL optional (auto http://hostname:8000 if unset)
docker compose up --build
curl -X POST $PUBLIC_BASE_URL/api/render/ ...
```
