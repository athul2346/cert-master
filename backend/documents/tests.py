import json
import tempfile
from pathlib import Path

from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import CompanyProfile, User
from documents.models import (
    CompanyDocument,
    DocumentField,
    DocumentTemplate,
    DocumentType,
)


class DocumentApiMixin:
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com", password="pass12345"
        )
        self.company = CompanyProfile.objects.create(
            user=self.user,
            organisation_name="Acme",
            classification="private",
            country="IN",
            cin_number="CIN-1",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.document_type = DocumentType.objects.create(
            company=self.company, code="CERT", name="Certificate"
        )
        self.template = DocumentTemplate.objects.create(
            company=self.company,
            document_type=self.document_type,
            template_name="cert",
            template_json={},
            template_html="<html></html>",
        )

    def _document(self, recipient, status):
        return CompanyDocument.objects.create(
            company=self.company,
            document_type=self.document_type,
            template=self.template,
            recipient=recipient,
            never_expires=True,
            status=status,
        )


class DocumentTypeDeleteTests(DocumentApiMixin, TestCase):
    def test_delete_preserves_active_and_deletes_inactive_documents(self):
        active = self._document("active", "ACTIVE")
        pending = self._document("pending", "PENDING")
        expired = self._document("expired", "EXPIRED")
        revoked = self._document("revoked", "REVOKED")
        pending_field = DocumentField.objects.create(
            document=pending, key="k", value="v"
        )

        response = self.client.delete(
            f"/api/document-types/{self.document_type.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["documents_preserved"], 1)
        self.assertEqual(response.data["documents_deleted"], 3)
        self.assertEqual(response.data["templates_detached"], 1)

        active.refresh_from_db()
        self.assertIsNone(active.document_type)
        self.assertEqual(active.status, "ACTIVE")
        self.assertEqual(active.template_id, self.template.pk)

        self.assertFalse(
            CompanyDocument.objects.filter(
                pk__in=[pending.pk, expired.pk, revoked.pk]
            ).exists()
        )
        self.assertFalse(DocumentField.objects.filter(pk=pending_field.pk).exists())

        self.template.refresh_from_db()
        self.assertIsNone(self.template.document_type)
        self.assertFalse(
            DocumentType.objects.filter(pk=self.document_type.pk).exists()
        )

    def test_delete_without_documents_or_templates(self):
        self.template.delete()

        response = self.client.delete(
            f"/api/document-types/{self.document_type.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["documents_preserved"], 0)
        self.assertEqual(response.data["documents_deleted"], 0)
        self.assertEqual(response.data["templates_detached"], 0)
        self.assertFalse(
            DocumentType.objects.filter(pk=self.document_type.pk).exists()
        )

    def test_cannot_delete_another_companys_document_type(self):
        other_user = User.objects.create_user(
            email="other@example.com", password="pass12345"
        )
        other_company = CompanyProfile.objects.create(
            user=other_user,
            organisation_name="Other",
            classification="private",
            country="IN",
            cin_number="CIN-2",
        )
        other_type = DocumentType.objects.create(
            company=other_company, code="X", name="Other type"
        )

        response = self.client.delete(f"/api/document-types/{other_type.pk}/")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(DocumentType.objects.filter(pk=other_type.pk).exists())

    def test_document_list_serializes_preserved_document_with_null_type(self):
        self._document("active", "ACTIVE")

        self.client.delete(f"/api/document-types/{self.document_type.pk}/")
        response = self.client.get("/api/documents/list/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertIsNone(response.data[0]["document_type"])

    def test_verify_qr_with_null_document_type(self):
        active = self._document("active", "ACTIVE")

        self.client.delete(f"/api/document-types/{self.document_type.pk}/")
        response = self.client.get(f"/api/verify-qr/{active.uuid}/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["verified"])
        self.assertIsNone(response.data["document_type"])


class ActiveDocumentLockTests(DocumentApiMixin, TestCase):
    def _update_payload(self, recipient="updated"):
        return {
            "document_type": self.document_type.pk,
            "template": self.template.pk,
            "recipient": recipient,
            "never_expires": True,
        }

    def test_put_active_document_is_blocked(self):
        active = self._document("active", "ACTIVE")

        response = self.client.put(
            f"/api/documents/{active.pk}/", self._update_payload()
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"].code, "document_locked")
        active.refresh_from_db()
        self.assertEqual(active.recipient, "active")

    def test_delete_active_document_is_blocked(self):
        active = self._document("active", "ACTIVE")

        response = self.client.delete(f"/api/documents/{active.pk}/")

        self.assertEqual(response.status_code, 409)
        self.assertTrue(CompanyDocument.objects.filter(pk=active.pk).exists())

    def test_field_patch_on_active_document_is_blocked(self):
        active = self._document("active", "ACTIVE")
        field = DocumentField.objects.create(
            document=active, key="existing", value="old"
        )

        response = self.client.patch(
            f"/api/documents/{active.pk}/update-fields/",
            {"to_update": {"existing": "new"}, "to_add": {"extra": "x"}},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        field.refresh_from_db()
        self.assertEqual(field.value, "old")
        self.assertFalse(active.fields.filter(key="extra").exists())

    def test_status_change_on_active_document_is_allowed(self):
        active = self._document("active", "ACTIVE")

        response = self.client.patch(
            f"/api/documents/{active.pk}/status/", {"status": "REVOKED"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "REVOKED")
        active.refresh_from_db()
        self.assertEqual(active.status, "REVOKED")

    def test_put_pending_document_is_allowed(self):
        pending = self._document("pending", "PENDING")

        response = self.client.put(
            f"/api/documents/{pending.pk}/", self._update_payload("edited")
        )

        self.assertEqual(response.status_code, 200)
        pending.refresh_from_db()
        self.assertEqual(pending.recipient, "edited")

    def test_put_can_activate_pending_document_and_rewrite_fields(self):
        pending = self._document("pending", "PENDING")
        DocumentField.objects.create(document=pending, key="k", value="old")

        payload = self._update_payload("activated")
        payload["status"] = "ACTIVE"
        payload["document_json"] = {"k": "new"}

        response = self.client.put(
            f"/api/documents/{pending.pk}/", payload, format="json"
        )

        self.assertEqual(response.status_code, 200)
        pending.refresh_from_db()
        self.assertEqual(pending.status, "ACTIVE")
        self.assertEqual(pending.get_fields_dict(), {"k": "new"})

    def test_delete_template_used_by_active_document_is_blocked(self):
        active = self._document("active", "ACTIVE")

        response = self.client.delete(
            f"/api/document-template/{self.template.pk}"
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(CompanyDocument.objects.filter(pk=active.pk).exists())


class DatabaseLockTests(DocumentApiMixin, TestCase):
    """Exercises the PostgreSQL triggers directly (skipped on other databases)."""

    def setUp(self):
        super().setUp()
        if connection.vendor != "postgresql":
            self.skipTest("The document lock trigger is PostgreSQL only")

    def test_orm_content_update_of_active_document_is_blocked(self):
        active = self._document("active", "ACTIVE")

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CompanyDocument.objects.filter(pk=active.pk).update(
                    recipient="hacked"
                )

        active.refresh_from_db()
        self.assertEqual(active.recipient, "active")

    def test_orm_status_update_of_active_document_is_allowed(self):
        active = self._document("active", "ACTIVE")

        CompanyDocument.objects.filter(pk=active.pk).update(status="REVOKED")

        active.refresh_from_db()
        self.assertEqual(active.status, "REVOKED")

    def test_orm_document_type_detach_of_active_document_is_allowed(self):
        active = self._document("active", "ACTIVE")

        CompanyDocument.objects.filter(pk=active.pk).update(document_type=None)

        active.refresh_from_db()
        self.assertIsNone(active.document_type)

    def test_orm_delete_of_active_document_is_blocked(self):
        active = self._document("active", "ACTIVE")
        active_pk = active.pk

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                active.delete()

        self.assertTrue(CompanyDocument.objects.filter(pk=active_pk).exists())

    def test_orm_field_update_of_active_document_is_blocked(self):
        active = self._document("active", "ACTIVE")
        field = DocumentField.objects.create(
            document=active, key="k", value="old"
        )

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                DocumentField.objects.filter(pk=field.pk).update(value="new")

        field.refresh_from_db()
        self.assertEqual(field.value, "old")

    def test_orm_update_of_pending_document_is_allowed(self):
        pending = self._document("pending", "PENDING")

        CompanyDocument.objects.filter(pk=pending.pk).update(recipient="edited")

        pending.refresh_from_db()
        self.assertEqual(pending.recipient, "edited")


class DocumentTypeTemplatePayloadTests(DocumentApiMixin, TestCase):
    def test_list_includes_templates_with_full_data(self):
        response = self.client.get("/api/document-types/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        templates = response.data[0]["templates"]
        self.assertEqual(len(templates), 1)
        template = templates[0]
        self.assertEqual(template["id"], self.template.pk)
        self.assertEqual(template["template_name"], "cert")
        self.assertEqual(template["template_json"], {})
        self.assertEqual(template["template_html"], "<html></html>")
        self.assertNotIn("document_type", template)

    def test_detail_includes_templates_with_full_data(self):
        response = self.client.get(
            f"/api/document-types/{self.document_type.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["templates"]), 1)
        self.assertEqual(
            response.data["templates"][0]["id"], self.template.pk
        )

    def test_document_type_without_templates_returns_empty_list(self):
        self.template.delete()

        response = self.client.get(
            f"/api/document-types/{self.document_type.pk}/"
        )

        self.assertEqual(response.data["templates"], [])

    def test_multiple_templates_are_all_returned(self):
        second = DocumentTemplate.objects.create(
            company=self.company,
            document_type=self.document_type,
            template_name="second",
            template_json={"a": 1},
            template_html="<p>2</p>",
        )

        response = self.client.get(
            f"/api/document-types/{self.document_type.pk}/"
        )

        ids = [template["id"] for template in response.data["templates"]]
        self.assertEqual(sorted(ids), sorted([self.template.pk, second.pk]))

    def test_other_companys_template_is_not_leaked(self):
        other_user = User.objects.create_user(
            email="other2@example.com", password="pass12345"
        )
        other_company = CompanyProfile.objects.create(
            user=other_user,
            organisation_name="Other",
            classification="private",
            country="IN",
            cin_number="CIN-3",
        )
        DocumentTemplate.objects.create(
            company=other_company,
            document_type=self.document_type,
            template_name="foreign",
            template_json={},
            template_html="",
        )

        response = self.client.get(
            f"/api/document-types/{self.document_type.pk}/"
        )

        names = [template["template_name"] for template in response.data["templates"]]
        self.assertEqual(names, ["cert"])


class TemplateUniquenessTests(DocumentApiMixin, TestCase):
    """Duplicate (company, template_name) must be a 400, never a DB 500."""

    def _payload(self, **overrides):
        payload = {
            "document_type": self.document_type.pk,
            "template_name": "cert",
            "template_json": {},
            "template_html": "<html></html>",
        }
        payload.update(overrides)
        return payload

    def test_duplicate_template_name_is_rejected(self):
        response = self.client.post(
            "/api/document-template/", self._payload(), format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("template_name", response.data)
        self.assertEqual(
            DocumentTemplate.objects.filter(
                company=self.company, template_name="cert"
            ).count(),
            1,
        )

    def test_renaming_template_onto_existing_name_is_rejected(self):
        other = DocumentTemplate.objects.create(
            company=self.company,
            template_name="other",
            template_json={},
            template_html="",
        )

        response = self.client.patch(
            f"/api/document-template/{other.pk}",
            {"template_name": "cert"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        other.refresh_from_db()
        self.assertEqual(other.template_name, "other")

    def test_template_can_keep_its_own_name_on_update(self):
        response = self.client.patch(
            f"/api/document-template/{self.template.pk}",
            {"template_name": "cert", "template_html": "<html>v2</html>"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.template.refresh_from_db()
        self.assertEqual(self.template.template_html, "<html>v2</html>")

    def test_same_name_is_allowed_for_another_company(self):
        other_user = User.objects.create_user(
            email="other3@example.com", password="pass12345"
        )
        CompanyProfile.objects.create(
            user=other_user,
            organisation_name="Other",
            classification="private",
            country="IN",
            cin_number="CIN-4",
        )
        self.client.force_authenticate(user=other_user)

        payload = self._payload()
        payload.pop("document_type")  # belongs to the first company
        response = self.client.post(
            "/api/document-template/", payload, format="json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["template_name"], "cert")


class DocumentTypeUniquenessTests(DocumentApiMixin, TestCase):
    """Duplicate (company, code) must be a 400, never a DB 500."""

    def test_duplicate_code_is_rejected(self):
        response = self.client.post(
            "/api/document-types/",
            {"code": "CERT", "name": "Another certificate"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("code", response.data)
        self.assertEqual(
            DocumentType.objects.filter(company=self.company, code="CERT").count(),
            1,
        )


class ExceptionHandlerTests(SimpleTestCase):
    def test_duplicate_key_becomes_readable_conflict(self):
        from backend.exception_handler import api_exception_handler

        exc = IntegrityError(
            'duplicate key value violates unique constraint '
            '"documents_documenttempla_company_id_template_name_8547b920_uniq"\n'
            "DETAIL:  Key (company_id, template_name)=(1, sample) already exists."
        )

        response = api_exception_handler(exc, {"view": None})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "duplicate_entry")
        self.assertIn("template_name", response.data["errors"])
        self.assertIn("already exists", response.data["detail"])

    def test_unknown_integrity_error_still_returns_clean_json(self):
        from backend.exception_handler import api_exception_handler

        response = api_exception_handler(IntegrityError("boom"), {"view": None})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "integrity_error")


CERTIFICATE_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta name="template-editor" content="certificate-editor">
    <meta name="template-page-size" content="Certificate (Standard)">
    <meta name="template-dimensions-mm" content="297mm x 210mm">
    <meta name="template-orientation" content="landscape">
</head>
<body>
    <div class="canvas-stage"><h1>{{Recipient Name}}</h1></div>
    <script id="template-dynamic-values" type="application/json">
    {
        "templateId": "t-cert",
        "documentTypeId": "dt-cert",
        "documentTypeName": "Professional Certificate",
        "editor": "certificate-editor",
        "editorLabel": "Certificate Editor",
        "pageSpec": {
            "sizeName": "Certificate (Standard)",
            "widthMm": 297,
            "heightMm": 210,
            "orientation": "Landscape",
            "totalPages": 1
        },
        "placeholders": ["{{Recipient Name}}", "{{Course Title}}"],
        "dynamicVariables": [
            {"placeholder": "{{Recipient Name}}", "fieldName": "Recipient Name", "type": "text", "required": true, "sampleValue": "Jane Doe"},
            {"placeholder": "{{Course Title}}", "fieldName": "Course Title", "type": "text", "required": false, "sampleValue": "Intro"}
        ]
    }
    </script>
</body>
</html>
"""

DOCUMENT_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta name="template-editor" content="document-editor">
    <meta name="template-page-size" content="A4">
    <meta name="template-dimensions-mm" content="210mm x 297mm">
    <meta name="template-orientation" content="portrait">
</head>
<body>
    <section class="doc-page" id="page-1"><p>{{Candidate Name}}</p></section>
    <!-- PAGE_BREAK -->
    <section class="doc-page" id="page-2"><p>{{Salary}}</p></section>
    <script id="template-dynamic-values" type="application/json">
    {
        "templateId": "t-offer",
        "documentTypeId": "dt-offer",
        "documentTypeName": "Offer Letter (India)",
        "editor": "document-editor",
        "editorLabel": "Document Editor",
        "pageSpec": {
            "sizeName": "A4",
            "widthMm": 210,
            "heightMm": 297,
            "orientation": "Portrait",
            "totalPages": 2
        },
        "placeholders": ["{{Candidate Name}}", "{{Salary}}"],
        "dynamicVariables": [
            {"placeholder": "{{Candidate Name}}", "fieldName": "Candidate Name", "type": "text", "required": true, "sampleValue": "Jane Doe"},
            {"placeholder": "{{Salary}}", "fieldName": "Salary", "type": "text", "required": true, "sampleValue": "100000"}
        ]
    }
    </script>
</body>
</html>
"""


class PredefinedTemplateApiTests(DocumentApiMixin, TestCase):
    """The predefined bundle is read from disk and served over the API."""

    def setUp(self):
        super().setUp()

        self.bundle = tempfile.TemporaryDirectory()
        self.addCleanup(self.bundle.cleanup)
        root = Path(self.bundle.name)
        (root / "certificate-editor").mkdir()
        (root / "document-editor").mkdir()

        self.cert_slug = "certificate-editor__professional-certificate"
        (root / "certificate-editor" / f"{self.cert_slug}.html").write_text(
            CERTIFICATE_HTML, encoding="utf-8"
        )
        (root / "certificate-editor" / f"{self.cert_slug}.json").write_text(
            json.dumps(
                {
                    "documentType": {
                        "id": "dt-cert",
                        "name": "Professional Certificate",
                        "validityDays": 365,
                    }
                }
            ),
            encoding="utf-8",
        )

        self.doc_slug = "document-editor__offer-letter-india"
        (root / "document-editor" / f"{self.doc_slug}.html").write_text(
            DOCUMENT_HTML, encoding="utf-8"
        )
        (root / "document-editor" / f"{self.doc_slug}.json").write_text(
            json.dumps(
                {
                    "name": "Offer Letter (India)",
                    "document_type": {"code": "OFFER", "name": "Offer Letter"},
                }
            ),
            encoding="utf-8",
        )

        self.override = override_settings(PREDEFINED_TEMPLATES_DIR=root)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_list_returns_metadata_without_full_html(self):
        response = self.client.get("/api/predefined-templates/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["slug"] for item in response.data],
            [self.cert_slug, self.doc_slug],
        )

        certificate = response.data[0]
        self.assertEqual(certificate["id"], "dt-cert")
        self.assertEqual(certificate["name"], "Professional Certificate")
        self.assertEqual(certificate["editor"], "certificate-editor")
        self.assertEqual(certificate["editor_label"], "Certificate Editor")
        self.assertEqual(certificate["page_size"], "Certificate (Standard)")
        self.assertEqual(
            certificate["dimensions_mm"], {"width": 297, "height": 210}
        )
        self.assertEqual(certificate["orientation"], "landscape")
        self.assertEqual(certificate["pages"], 1)
        self.assertEqual(certificate["validity_days"], 365)
        self.assertEqual(
            [
                (field["name"], field["type"], field["required"])
                for field in certificate["dynamic_fields"]
            ],
            [("Recipient Name", "text", True), ("Course Title", "text", False)],
        )
        self.assertEqual(
            certificate["dynamic_fields"][0]["placeholder"], "{{Recipient Name}}"
        )
        self.assertEqual(
            certificate["document_type"], {"code": "CERT", "name": "Certificate"}
        )
        self.assertNotIn("template_html", certificate)

    def test_list_reads_multipage_document_metadata(self):
        response = self.client.get("/api/predefined-templates/")

        document = response.data[1]
        self.assertEqual(document["id"], "dt-offer")
        self.assertEqual(document["name"], "Offer Letter (India)")
        self.assertEqual(document["pages"], 2)
        self.assertEqual(document["orientation"], "portrait")
        self.assertEqual(
            [field["name"] for field in document["dynamic_fields"]],
            ["Candidate Name", "Salary"],
        )
        self.assertEqual(
            document["document_type"], {"code": "OFFER", "name": "Offer Letter"}
        )

    def test_detail_returns_html_and_json(self):
        response = self.client.get(
            f"/api/predefined-templates/{self.doc_slug}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["slug"], self.doc_slug)
        self.assertEqual(response.data["template_html"], DOCUMENT_HTML)
        self.assertEqual(response.data["template_json"]["name"], "Offer Letter (India)")
        self.assertEqual(response.data["pages"], 2)

    def test_unknown_slug_returns_404(self):
        response = self.client.get("/api/predefined-templates/does-not-exist/")

        self.assertEqual(response.status_code, 404)

    def test_import_creates_template_and_document_type(self):
        response = self.client.post(
            f"/api/predefined-templates/{self.doc_slug}/import/"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["template_name"], "Offer Letter (India)")

        template = DocumentTemplate.objects.get(
            company=self.company, template_name="Offer Letter (India)"
        )
        self.assertEqual(template.template_html, DOCUMENT_HTML)
        self.assertEqual(template.template_json["name"], "Offer Letter (India)")

        document_type = template.document_type
        self.assertEqual(document_type.code, "OFFER")
        self.assertEqual(document_type.name, "Offer Letter")
        self.assertEqual(document_type.company, self.company)

    def test_import_infers_certificate_document_type(self):
        response = self.client.post(
            f"/api/predefined-templates/{self.cert_slug}/import/"
        )

        self.assertEqual(response.status_code, 201)
        template = DocumentTemplate.objects.get(
            company=self.company, template_name="Professional Certificate"
        )
        self.assertEqual(template.document_type.code, "CERT")

    def test_import_twice_returns_conflict_without_overwriting(self):
        first = self.client.post(
            f"/api/predefined-templates/{self.cert_slug}/import/"
        )
        self.assertEqual(first.status_code, 201)
        template_id = first.data["id"]

        second = self.client.post(
            f"/api/predefined-templates/{self.cert_slug}/import/"
        )

        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data["code"], "already_imported")
        self.assertEqual(second.data["template_id"], template_id)
        self.assertEqual(
            DocumentTemplate.objects.filter(
                company=self.company, template_name="Professional Certificate"
            ).count(),
            1,
        )

    def test_empty_bundle_directory_returns_empty_list(self):
        empty = tempfile.TemporaryDirectory()
        self.addCleanup(empty.cleanup)
        with override_settings(PREDEFINED_TEMPLATES_DIR=Path(empty.name)):
            response = self.client.get("/api/predefined-templates/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])


class CsrfEnforcementTests(TestCase):
    """Session-authenticated writes must carry a valid CSRF token."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="csrf@example.com", password="pass12345"
        )
        CompanyProfile.objects.create(
            user=self.user,
            organisation_name="CSRF Co",
            classification="private",
            country="IN",
            cin_number="CIN-CSRF-1",
        )
        # enforce_csrf_checks mirrors production behaviour.
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)

    def test_write_without_csrf_token_is_rejected(self):
        response = self.client.post(
            "/api/document-types/",
            {"code": "CSRF1", "name": "CSRF Test"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            DocumentType.objects.filter(code="CSRF1").exists()
        )

    def test_write_with_csrf_token_succeeds(self):
        # Bootstrap the cookie, then echo it back in the header like the SPA.
        csrf_response = self.client.get("/api/auth/csrf/")
        self.assertEqual(csrf_response.status_code, 200)
        token = self.client.cookies["csrftoken"].value

        response = self.client.post(
            "/api/document-types/",
            {"code": "CSRF2", "name": "CSRF Test 2"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(DocumentType.objects.filter(code="CSRF2").exists())

    def test_public_verify_endpoint_needs_no_auth_or_csrf(self):
        self.client.logout()
        response = self.client.get(
            "/api/verify-qr/00000000-0000-0000-0000-000000000000/"
        )
        # Reaches the view (404 = unknown UUID) instead of 401/403.
        self.assertEqual(response.status_code, 404)

    def test_logout_requires_csrf_when_session_present(self):
        response = self.client.post("/api/auth/logout/")
        self.assertEqual(response.status_code, 403)
