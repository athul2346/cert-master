# Data Isolation Architecture - How It Works

## Overview

The system uses a **multi-tenant architecture** where each user belongs to a company, and all data is filtered by that company. This ensures complete data isolation between different organizations.

---

## The Key Relationship Chain

```
┌─────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    User     │──────▶│  CompanyProfile │──────▶│  Documents &    │
│  (email)    │ 1:1   │  (organisation) │ 1:M   │  Templates      │
└─────────────┘       └─────────────────┘       └─────────────────┘
```

---

## Step 1: User → Company Link

**File:** `backend/accounts/models.py`

```python
class User(AbstractBaseUser):
    email = models.EmailField(unique=True)
    # ... other fields

class CompanyProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="company"  # 🔑 This is the magic key!
    )
    organisation_name = models.CharField(max_length=255)
    cin_number = models.CharField(max_length=50, unique=True)
```

### How to Access:
```python
user = request.user           # Current logged-in user
company = user.company        # Get their company profile
company.id                    # Company ID used for filtering
company.organisation_name     # "API Test Company"
```

**The `related_name="company"`** allows you to go from User → CompanyProfile using `user.company`.

---

## Step 2: Documents Linked to Company

**File:** `backend/documents/models.py`

```python
class CompanyDocument(models.Model):
    # 🔑 ForeignKey links document to a company
    company = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="documents"  # Access via company.documents.all()
    )
    
    document_type = models.ForeignKey(DocumentType, ...)
    template = models.ForeignKey(DocumentTemplate, ...)
    recipient = models.CharField(max_length=255)
    status = models.CharField(max_length=20)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    
    class Meta:
        # 🔑 Unique constraint per company
        constraints = [
            models.UniqueConstraint(
                fields=["company", "document_type", "recipient"],
                name="unique_company_document"
            )
        ]
```

### Database Schema:
```
company_document table:
┌────┬────────────┬─────────────────┬───────────┬────────────┐
│ id │ company_id │ document_type_id│ recipient │ status     │
├────┼────────────┼─────────────────┼───────────┼────────────┤
│  1 │     1      │        1        │ Alice     │ ACTIVE     │
│  2 │     1      │        1        │ Bob       │ PENDING    │
│  3 │     2      │        1        │ Charlie   │ ACTIVE     │  ← Different company
└────┴────────────┴─────────────────┴───────────┴────────────┘
```

---

## Step 3: Templates Linked to Company

**File:** `backend/documents/models.py`

```python
class DocumentTemplate(models.Model):
    # 🔑 ForeignKey links template to a company
    company = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="templates"  # Access via company.templates.all()
    )
    
    template_name = models.CharField(max_length=50)
    template_json = models.JSONField()
    template_html = models.TextField()
```

---

## Step 4: Views Filter by Company

**File:** `backend/documents/views.py`

### Example 1: List Documents (Isolation)
```python
class CompanyDocumentListView(APIView):
    def get(self, request):
        # 🔑 Get current user's company
        company = request.user.company
        
        # 🔑 Filter documents by THIS company only
        queryset = CompanyDocument.objects.filter(
            company=company  # ← Isolation happens here!
        ).prefetch_related('fields')
        
        return Response(serializer.data)
```

**SQL Generated:**
```sql
SELECT * FROM company_document 
WHERE company_id = 1  -- Only current user's company
```

### Example 2: Get Single Document (Isolation)
```python
class CompanyDocumentDetailView(APIView):
    def get_object(self, request, pk):
        company = request.user.company
        
        try:
            return CompanyDocument.objects.get(
                company=company,  # ← Must match company
                pk=pk             # ← And match document ID
            )
        except CompanyDocument.DoesNotExist:
            return None  # 🔑 Returns None if not owned by this company
```

**SQL Generated:**
```sql
SELECT * FROM company_document 
WHERE company_id = 1 AND id = 6
-- If document 6 belongs to company 2, this returns NOTHING
```

### Example 3: Templates (Isolation)
```python
class DocumentTemplateListCreateAPIView(generics.ListCreateAPIView):
    def get_queryset(self):
        # 🔑 Only return templates for current user's company
        return DocumentTemplate.objects.filter(
            company=self.request.user.company
        )
```

---

## Step 5: How Login Enables This

**File:** `backend/accounts/views.py`

```python
class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data, ...)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data["user"]
        
        # 🔑 This creates the session
        login(request, user)
        
        return Response({"message": "Login successful", ...})
```

**What happens:**
1. User submits email/password
2. Django validates credentials
3. `login(request, user)` creates a session
4. Session cookie is stored in browser
5. Subsequent requests include this cookie
6. `request.user` is automatically populated from session

---

## Step 6: The Authentication Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Login     │────▶│   Session   │────▶│  API Call   │
│   POST      │     │   Cookie    │     │   GET       │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │ request.user│
                                       │   = User    │
                                       └─────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │ user.company│
                                       │ = Company 1 │
                                       └─────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │  Filter by  │
                                       │  company_id │
                                       └─────────────┘
```

---

## Visual Example: Data Isolation in Action

### Database State:
```
Companies:
┌────┬──────────────────┐
│ id │ organisation_name│
├────┼──────────────────┤
│  1 │ API Test Company │
│  2 │ Second Company   │
└────┴──────────────────┘

Documents:
┌────┬────────────┬───────────┬────────┐
│ id │ company_id │ recipient│ status │
├────┼────────────┼───────────┼────────┤
│  6 │     1      │ Alice    │ ACTIVE │  ← Company 1's doc
│  7 │     2      │ Bob      │ ACTIVE │  ← Company 2's doc
└────┴────────────┴───────────┴────────┘
```

### When Company 1 Calls `GET /api/documents/list/`:
```python
company = request.user.company  # Company ID = 1
CompanyDocument.objects.filter(company=company)
# Returns: [Document 6] only
```

### When Company 2 Calls `GET /api/documents/6/`:
```python
company = request.user.company  # Company ID = 2
CompanyDocument.objects.get(company=company, pk=6)
# Raises: DoesNotExist (because doc 6 has company_id=1, not 2)
# Returns: {"detail": "Document not found"}
```

---

## Summary: The Isolation Mechanism

| Component | How It Works |
|-----------|--------------|
| **User Model** | `user.company` gives access to CompanyProfile |
| **Foreign Keys** | All data models have `company = ForeignKey(CompanyProfile)` |
| **View Filtering** | Every view uses `.filter(company=request.user.company)` |
| **Object Retrieval** | Every get uses `.get(company=request.user.company, pk=pk)` |
| **Result** | Users can ONLY see data where `company_id` matches their company |

This is a **secure multi-tenant architecture** where the database enforces isolation at the query level!
