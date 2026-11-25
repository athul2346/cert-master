from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from django.db.models import Prefetch
from django.shortcuts import render
from django.utils.timezone import now
from .utils import render_certificate_html
from .models import (
    DocumentType, 
    CompanyDocument, 
    DocumentTemplate,
)
from .serializers import (
    DocumentTypeSerializer, 
    CompanyDocumentSerializer, 
    DocumentTemplateSerializer,
    PatchDocumentFieldSerializer,
    DocumentFieldSerializer,
    CompanyDocumentWithJsonSerializer,
    DocumentStatusUpdateSerializer,
)
from .authentication import CsrfExemptSessionAuthentication
from .exceptions import DocumentLocked
from . import predefined


def ensure_document_editable(document):
    """Reject writes on documents that have already been issued (ACTIVE)."""
    if document.status == "ACTIVE":
        raise DocumentLocked(
            f"Document {document.pk} is ACTIVE and can no longer be modified."
        )


@method_decorator(csrf_exempt, name="dispatch")
class DocumentTypeListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    queryset = DocumentType.objects.all()
    serializer_class = DocumentTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = self.request.user.company
        return DocumentType.objects.filter(company=company).prefetch_related(
            Prefetch(
                "templates",
                queryset=DocumentTemplate.objects.filter(company=company),
            )
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


@method_decorator(csrf_exempt, name="dispatch")
class DocumentTypeRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    queryset = DocumentType.objects.all()
    serializer_class = DocumentTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = self.request.user.company
        return DocumentType.objects.filter(company=company).prefetch_related(
            Prefetch(
                "templates",
                queryset=DocumentTemplate.objects.filter(company=company),
            )
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def destroy(self, request, *args, **kwargs):
        """
        Delete a document type while keeping history that must survive.

        - Documents with status ACTIVE are preserved and detached from the
          document type (document_type = NULL).
        - Documents in any other status (PENDING, EXPIRED, REVOKED) are deleted.
        - Templates are preserved and detached from the document type so that
          preserved documents can still be rendered with them.
        """
        from django.db import transaction

        instance = self.get_object()
        document_type_id = instance.pk
        document_type_code = instance.code
        document_type_name = instance.name

        documents = CompanyDocument.objects.filter(document_type=instance)
        active_documents = documents.filter(status="ACTIVE")
        inactive_documents = documents.exclude(status="ACTIVE")
        templates = DocumentTemplate.objects.filter(document_type=instance)

        with transaction.atomic():
            documents_preserved = active_documents.count()
            documents_deleted = inactive_documents.count()
            templates_detached = templates.count()

            # Detach preserved documents before the type is removed. The FK is
            # PROTECT, so this must happen before instance.delete().
            active_documents.update(document_type=None)

            # Non-active documents are discarded along with their fields.
            inactive_documents.delete()

            # Keep templates usable by the preserved documents.
            templates.update(document_type=None)

            instance.delete()

        return Response(
            {
                "message": "Document type deleted successfully",
                "document_type": {
                    "id": document_type_id,
                    "code": document_type_code,
                    "name": document_type_name,
                },
                "documents_preserved": documents_preserved,
                "documents_deleted": documents_deleted,
                "templates_detached": templates_detached,
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class DocumentTemplateListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentTemplateSerializer

    def get_queryset(self):
        return DocumentTemplate.objects.filter(
            company=self.request.user.company
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context



@method_decorator(csrf_exempt, name="dispatch")
class DocumentTemplateRetrieveUpdateDestroyAPIView(
    generics.RetrieveUpdateDestroyAPIView
):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentTemplateSerializer

    def get_queryset(self):
        return DocumentTemplate.objects.filter(
            company=self.request.user.company
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # Templates cascade into CompanyDocument; deleting one that is used
        # by ACTIVE documents would remove issued certificates.
        if instance.template_documents.filter(status="ACTIVE").exists():
            raise DocumentLocked(
                "This template is used by ACTIVE documents and cannot be deleted."
            )

        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name="dispatch")
class TemplatesByDocumentTypeAPIView(APIView):
    """
    API to get all templates under a specific document type.
    
    GET /document-types/{document_type_id}/templates/
    
    Returns all templates that belong to the specified document type.
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentTemplateSerializer

    def get(self, request, document_type_id):
        company = request.user.company
        
        # Verify the document type exists and belongs to the company
        try:
            document_type = DocumentType.objects.get(
                id=document_type_id,
                company=company
            )
        except DocumentType.DoesNotExist:
            return Response(
                {"detail": "Document type not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all templates under this document type
        templates = DocumentTemplate.objects.filter(
            company=company,
            document_type=document_type
        )
        
        serializer = DocumentTemplateSerializer(
            templates,
            many=True,
            context={"request": request}
        )
        
        return Response({
            "document_type": {
                "id": document_type.id,
                "code": document_type.code,
                "name": document_type.name
            },
            "templates": serializer.data
        })


@method_decorator(csrf_exempt, name="dispatch")
class DocumentsByDocumentTypeAPIView(APIView):
    """
    Get all documents that belong to a specific document type.
    
    GET /document-types/{document_type_id}/documents/
    
    Returns all documents that belong to the specified document type
    for the logged-in user's company.
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = CompanyDocumentSerializer

    def get(self, request, document_type_id):
        company = request.user.company

        # Verify the document type exists and belongs to the company
        try:
            document_type = DocumentType.objects.get(
                id=document_type_id,
                company=company
            )
        except DocumentType.DoesNotExist:
            return Response(
                {"detail": "Document type not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get all documents under this document type
        documents = CompanyDocument.objects.filter(
            company=company,
            document_type=document_type
        ).prefetch_related('fields')

        serializer = CompanyDocumentSerializer(
            documents,
            many=True,
            context={"request": request}
        )

        return Response({
            "document_type": {
                "id": document_type.id,
                "code": document_type.code,
                "name": document_type.name
            },
            "documents": serializer.data
        })


@method_decorator(csrf_exempt, name="dispatch")
class CompanyDocumentCreateView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CompanyDocumentWithJsonSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        document = serializer.save()

        return Response(
            CompanyDocumentSerializer(document).data,
            status=status.HTTP_201_CREATED
        )


@method_decorator(csrf_exempt, name="dispatch")
class CompanyDocumentListView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = request.user.company

        queryset = CompanyDocument.objects.filter(company=company).prefetch_related('fields')

        serializer = CompanyDocumentSerializer(
            queryset,
            many=True,
            context={"request": request}
        )
        return Response(serializer.data)


@method_decorator(csrf_exempt, name="dispatch")
class CompanyDocumentDetailView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        company = request.user.company

        try:
            return CompanyDocument.objects.prefetch_related('fields').get(
                company=company,
                pk=pk,
            )
        except CompanyDocument.DoesNotExist:
            return None

    def get(self, request, pk):
        document = self.get_object(request, pk)

        if not document:
            return Response(
                {"detail": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CompanyDocumentSerializer(document)
        return Response(serializer.data)
    

    def put(self, request, pk):
        document = self.get_object(request, pk)

        if not document:
            return Response(
                {"detail": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        ensure_document_editable(document)

        serializer = CompanyDocumentWithJsonSerializer(
            document,
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(CompanyDocumentSerializer(document).data)


    def delete(self, request, pk):
        document = self.get_object(request, pk)

        if not document:
            return Response(
                {"detail": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        ensure_document_editable(document)

        document.delete()

        return Response(
            {"message": "Document deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )


class VerifyQRAPIView(APIView):
    """
    API to verify a QR code and return certificate info.
    """

    def get(self, request, uuid):
        # Look up the Document directly
        try:
            document = CompanyDocument.objects.prefetch_related('fields').get(uuid=uuid)
        except CompanyDocument.DoesNotExist:
            return Response(
                {"verified": False, "reason": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check expiry
        if not document.never_expires and document.expiry_date:
            if document.expiry_date < now().date():
                return Response(
                    {"verified": False, "reason": "Document has expired"},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Check status (handles revoked/expired)
        if document.status != "ACTIVE":
            return Response(
                {"verified": False, "reason": f"Document status: {document.status}"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get fields as dictionary
        fields_dict = {f.key: f.value for f in document.fields.all()}

        return Response(
            {
                "verified": True,
                "company": document.company.organisation_name,
                "document_type": (
                    document.document_type.name if document.document_type else None
                ),
                "recipient": document.recipient,
                "issued_date": document.issued_date,
                "expiry_date": document.expiry_date,
                "fields": fields_dict,
            },
            status=status.HTTP_200_OK
        )


@method_decorator(csrf_exempt, name="dispatch")
class CompanyDocumentFieldUpdateView(APIView):
    """
    API to partially update DocumentField entries without full document replacement.
    
    Supports three operations:
    - to_add: Add new key-value pairs
    - to_update: Update existing keys
    - to_delete: Remove keys
    
    All operations are atomic - they all succeed or fail together.
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        company = request.user.company
        try:
            return CompanyDocument.objects.prefetch_related('fields').get(
                company=company,
                pk=pk,
            )
        except CompanyDocument.DoesNotExist:
            return None

    def patch(self, request, pk):
        """
        Partial update DocumentField
        
        Request body:
        {
            "to_add": {
                "new_key": "value"
            },
            "to_update": {
                "existing_key": "new_value"
            },
            "to_delete": ["key_to_remove"]
        }
        """
        document = self.get_object(request, pk)
        
        if not document:
            return Response(
                {"detail": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        ensure_document_editable(document)
        
        serializer = PatchDocumentFieldSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        validated_data = serializer.validated_data
        to_add = validated_data.get('to_add', {})
        to_update = validated_data.get('to_update', {})
        to_delete = validated_data.get('to_delete', [])
        
        # Atomic update
        from django.db import transaction
        with transaction.atomic():
            # Delete keys first
            if to_delete:
                document.fields.filter(key__in=to_delete).delete()
            
            # Update existing keys
            if to_update:
                for key, value in to_update.items():
                    document.fields.update_or_create(
                        key=key,
                        defaults={'value': str(value)}
                    )
            
            # Add new keys
            if to_add:
                for key, value in to_add.items():
                    document.fields.update_or_create(
                        key=key,
                        defaults={'value': str(value)}
                    )
        
        # Refresh and return updated fields
        document.fields.all()
        
        return Response({
            "message": "Document fields updated successfully",
            "operations": {
                "added": list(to_add.keys()) if to_add else [],
                "updated": list(to_update.keys()) if to_update else [],
                "deleted": to_delete if to_delete else []
            },
            "fields": DocumentFieldSerializer(document.fields.all(), many=True).data
        })


@method_decorator(csrf_exempt, name="dispatch")
class CompanyDocumentStatusUpdateView(APIView):
    """
    API to update only the status of a CompanyDocument.

    PATCH /documents/{pk}/status/

    Request body:
    {
        "status": "ACTIVE"   # one of: PENDING, ACTIVE, EXPIRED, REVOKED
    }
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        company = request.user.company
        try:
            return CompanyDocument.objects.prefetch_related('fields').get(
                company=company,
                pk=pk,
            )
        except CompanyDocument.DoesNotExist:
            return None

    def patch(self, request, pk):
        document = self.get_object(request, pk)

        if not document:
            return Response(
                {"detail": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = DocumentStatusUpdateSerializer(
            document,
            data=request.data,
            partial=True,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            CompanyDocumentSerializer(document, context={"request": request}).data,
            status=status.HTTP_200_OK
        )


@method_decorator(csrf_exempt, name="dispatch")
class CertificateRenderAPIView(APIView):
    """
    API to render certificate HTML by replacing placeholders and adding QR code.

    The real QR code (encoding the verify URL) is only injected when the
    document status is ACTIVE. For any other status the dummy QR provided
    in the template is returned as-is.

    Request body:
    {
        "template_id": 1,
        "document_id": 1
    }

    Response:
    {
        "rendered_html": "<html>...</html>"
    }
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        template_id = request.data.get("template_id")
        document_id = request.data.get("document_id")

        if not template_id or not document_id:
            return Response(
                {"detail": "Both template_id and document_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get the template (must belong to user's company)
        company = request.user.company
        try:
            template = DocumentTemplate.objects.get(
                id=template_id,
                company=company
            )
        except DocumentTemplate.DoesNotExist:
            return Response(
                {"detail": "Template not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get the document (must belong to user's company)
        try:
            document = CompanyDocument.objects.prefetch_related('fields').get(
                id=document_id,
                company=company
            )
        except CompanyDocument.DoesNotExist:
            return Response(
                {"detail": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get document fields as dictionary
        document_json = {f.key: f.value for f in document.fields.all()}

        # Only inject the real QR when the document is ACTIVE.
        # For any other status (PENDING / EXPIRED / REVOKED) we pass None
        # so the dummy QR from the template is returned untouched.
        qr_verify_url = None
        if document.status == "ACTIVE":
            qr_verify_url = (
                f"{settings.CERT_FRONTEND_URL}/verify-qr/{document.uuid}"
            )

        # Render the certificate HTML
        rendered_html = render_certificate_html(
            template_html=template.template_html,
            document_json=document_json,
            qr_verify_url=qr_verify_url
        )

        return Response(
            {"rendered_html": rendered_html},
            status=status.HTTP_200_OK
        )


@method_decorator(csrf_exempt, name="dispatch")
class PredefinedTemplateListView(APIView):
    """
    GET /predefined-templates/

    Catalog of the predefined template bundle shipped with the backend.
    Returns metadata only; fetch a single package for its HTML and JSON.
    """

    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        packages = predefined.list_packages()
        return Response([predefined.summary(package) for package in packages])


@method_decorator(csrf_exempt, name="dispatch")
class PredefinedTemplateDetailView(APIView):
    """
    GET /predefined-templates/{slug}/

    Full package (``template_html`` + ``template_json``) plus its metadata.
    The payload can be posted as-is to /document-template/.
    """

    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        package = predefined.get_package(slug)
        if package is None:
            return Response(
                {"detail": "Predefined template not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(predefined.detail(package))


@method_decorator(csrf_exempt, name="dispatch")
class PredefinedTemplateImportView(APIView):
    """
    POST /predefined-templates/{slug}/import/

    Copies a predefined package into the caller's company as a regular
    DocumentTemplate. The matching standard DocumentType is created for the
    company if it does not exist yet. Importing the same package twice is
    reported as a 409 instead of overwriting user edits.
    """

    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        package = predefined.get_package(slug)
        if package is None:
            return Response(
                {"detail": "Predefined template not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        company = request.user.company
        document_type_hint = package["document_type"]
        max_length = DocumentTemplate._meta.get_field("template_name").max_length
        template_name = package["name"][:max_length]

        existing = DocumentTemplate.objects.filter(
            company=company,
            template_name=template_name,
        ).first()
        if existing is not None:
            return Response(
                {
                    "detail": (
                        "This template has already been imported for your "
                        "company."
                    ),
                    "code": "already_imported",
                    "template_id": existing.pk,
                },
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            document_type, _ = DocumentType.objects.get_or_create(
                company=company,
                code=document_type_hint["code"],
                defaults={"name": document_type_hint["name"]},
            )
            template = DocumentTemplate.objects.create(
                company=company,
                document_type=document_type,
                template_name=template_name,
                template_json=package["json"],
                template_html=package["html"],
            )

        serializer = DocumentTemplateSerializer(
            template,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class HealthCheckAPIView(APIView):
    """
    Public health check endpoint to verify that the application
    and its database connection are active and healthy.
    """
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        from django.db import connections
        from django.db.utils import OperationalError
        
        try:
            db_conn = connections['default']
            db_conn.cursor()
        except OperationalError:
            return Response(
                {"status": "unhealthy", "database": "disconnected"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        return Response(
            {"status": "healthy", "database": "connected"},
            status=status.HTTP_200_OK
        )