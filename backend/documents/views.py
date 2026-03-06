from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from django.shortcuts import render
from django.utils.timezone import now
from .utils import render_certificate_html
from .models import (
    DocumentType, 
    CompanyDocument, 
    DocumentTemplate,
    QRRecord,
    DocumentField
)
from .serializers import (
    DocumentTypeSerializer, 
    CompanyDocumentSerializer, 
    DocumentTemplateSerializer,
    PatchDocumentFieldSerializer,
    DocumentFieldSerializer,
    CompanyDocumentWithJsonSerializer
)
from .authentication import CsrfExemptSessionAuthentication


@method_decorator(csrf_exempt, name="dispatch")
class DocumentTypeListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    queryset = DocumentType.objects.all()
    serializer_class = DocumentTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DocumentType.objects.filter(
            company=self.request.user.company
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
        return DocumentType.objects.filter(
            company=self.request.user.company
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


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
        try:
            qr = QRRecord.objects.select_related("document").get(id=uuid)
        except QRRecord.DoesNotExist:
            return Response(
                {"verified": False, "reason": "QR code not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if not qr.is_active:
            return Response(
                {"verified": False, "reason": "QR code has been revoked"},
                status=status.HTTP_403_FORBIDDEN
            )

        document = getattr(qr, "document", None)

        if not document:
            return Response(
                {"verified": False, "reason": "No document linked to this QR"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check expiry
        if not document.never_expires and document.expiry_date:
            if document.expiry_date < now().date():
                return Response(
                    {"verified": False, "reason": "Document has expired"},
                    status=status.HTTP_403_FORBIDDEN
                )

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
                "document_type": document.document_type.name,
                "recipient": document.recipient,
                "issued_date": document.issued_date,
                "expiry_date": document.expiry_date,
                "fields": fields_dict,
                "payload": qr.payload,
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
class CertificateRenderAPIView(APIView):
    """
    API to render certificate HTML by replacing placeholders and adding QR code.
    
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

        # Generate verification URL using document's UUID
        qr_verify_url = f"{settings.PUBLIC_BASE_URL}/verify/{document.uuid}/"

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
