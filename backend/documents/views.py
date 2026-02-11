from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from django.shortcuts import render
from django.utils.timezone import now
from .utils import generate_qr_image
from .models import (
    DocumentType, 
    CompanyDocument, 
    DocumentTemplate,
    QRRecord
)
from .serializers import (
    DocumentTypeSerializer, 
    CompanyDocumentSerializer, 
    DocumentTemplateSerializer,
    QRGenerateSerializer,
    PatchDocumentJsonSerializer,
    PatchTemplateJsonSerializer
)
from .authentication import CsrfExemptSessionAuthentication


@method_decorator(csrf_exempt, name="dispatch")
class DocumentTypeListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    queryset = DocumentType.objects.all()
    serializer_class = DocumentTypeSerializer
    permission_classes = [IsAdminUser]


@method_decorator(csrf_exempt, name="dispatch")
class DocumentTypeRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    queryset = DocumentType.objects.all()
    serializer_class = DocumentTypeSerializer
    permission_classes = [IsAdminUser]


@method_decorator(csrf_exempt, name="dispatch")
class DocumentTemplateListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAdminUser]
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
    permission_classes = [IsAdminUser]
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
class CompanyDocumentCreateView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CompanyDocumentSerializer(
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

        queryset = CompanyDocument.objects.filter(company=company)

        # serializer = CompanyDocumentSerializer(queryset, many=True)
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

    def get_object(self, request, document_type, recipient):
        company = request.user.company

        try:
            return CompanyDocument.objects.get(
                company=company,
                document_type__code=document_type,
                recipient=recipient,
            )
        except CompanyDocument.DoesNotExist:
            return None


    def get(self, request, document_type, recipient):
        document = self.get_object(request, document_type, recipient)

        if not document:
            return Response(
                {"detail": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CompanyDocumentSerializer(document)
        return Response(serializer.data)
    

    def put(self, request, document_type, recipient):
        document = self.get_object(request, document_type, recipient)

        if not document:
            return Response(
                {"detail": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CompanyDocumentSerializer(
            document,
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)


    def delete(self, request, document_type, recipient):
        document = self.get_object(request, document_type, recipient)

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


class QRGenerateAPIView(APIView):
    """
    Generates a QR code and stores payload
    """

    def post(self, request):
        serializer = QRGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        qr_record = serializer.save()

        verify_url = f"{settings.PUBLIC_BASE_URL}/verify/{qr_record.id}/"

        qr_image = generate_qr_image(verify_url)

        return Response(
            {
                "qr_id": str(qr_record.id),
                "verify_url": verify_url,
                "qr_image_base64": qr_image.read().decode("latin1"),
            },
            status=status.HTTP_201_CREATED
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



        return Response(
            {
                "verified": True,
                "company": document.company.organisation_name,
                "document_type": document.document_type.name,
                "recipient": document.recipient,
                "issued_date": document.issued_date,
                "expiry_date": document.expiry_date,
                "payload": qr.payload,
            },
            status=status.HTTP_200_OK
        )


@method_decator(csrf_exempt, name="dispatch")
class CompanyDocumentJsonUpdateView(APIView):
    """
    API to partially update document_json field without full document replacement.
    
    Supports three operations:
    - to_add: Add new keys to the JSON document
    - to_update: Update existing keys in the JSON document
    - to_delete: Remove keys from the JSON document
    
    All operations are atomic - they all succeed or fail together.
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self, request, document_type, recipient):
        company = request.user.company
        try:
            return CompanyDocument.objects.get(
                company=company,
                document_type__code=document_type,
                recipient=recipient,
            )
        except CompanyDocument.DoesNotExist:
            return None

    def patch(self, request, document_type, recipient):
        """
        Partial update document_json field
        
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
        document = self.get_object(request, document_type, recipient)
        
        if not document:
            return Response(
                {"detail": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PatchDocumentJsonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        validated_data = serializer.validated_data
        to_add = validated_data.get('to_add', {})
        to_update = validated_data.get('to_update', {})
        to_delete = validated_data.get('to_delete', [])
        
        # Get current JSON with atomic update
        from django.db import transaction
        with transaction.atomic():
            # Lock the document row to prevent race conditions
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT document_json FROM documents_companydocument WHERE id = %s FOR UPDATE",
                    [document.id]
                )
            
            current_json = document.document_json or {}
            updated_json = current_json.copy()
            
            # Delete keys first
            if to_delete:
                for key in to_delete:
                    updated_json.pop(key, None)  # Safe delete - ignore if key doesn't exist
            
            # Update existing keys
            if to_update:
                updated_json.update(to_update)
            
            # Add new keys
            if to_add:
                updated_json.update(to_add)
            
            # Save the updated JSON
            document.document_json = updated_json
            document.save(update_fields=['document_json', 'updated_at'])
        
        return Response({
            "message": "Document JSON updated successfully",
            "operations": {
                "added": list(to_add.keys()) if to_add else [],
                "updated": list(to_update.keys()) if to_update else [],
                "deleted": to_delete if to_delete else []
            },
            "document_json": document.document_json
        })


@method_decator(csrf_exempt, name="dispatch")
class DocumentTemplateJsonUpdateView(APIView):
    """
    API to partially update template_json field.
    
    Supports three operations:
    - to_add: Add new keys to the template JSON
    - to_update: Update existing keys in the template JSON
    - to_delete: Remove keys from the template JSON
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAdminUser]

    def get_object(self, request, template_id):
        try:
            return DocumentTemplate.objects.get(
                id=template_id,
                company=request.user.company
            )
        except DocumentTemplate.DoesNotExist:
            return None

    def patch(self, request, template_id):
        """
        Partial update template_json field
        
        Request body:
        {
            "to_add": {
                "new_field": "value"
            },
            "to_update": {
                "existing_field": "new_value"
            },
            "to_delete": ["field_to_remove"]
        }
        """
        template = self.get_object(request, template_id)
        
        if not template:
            return Response(
                {"detail": "Template not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PatchTemplateJsonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        validated_data = serializer.validated_data
        to_add = validated_data.get('to_add', {})
        to_update = validated_data.get('to_update', {})
        to_delete = validated_data.get('to_delete', [])
        
        # Get current JSON with atomic update
        from django.db import transaction
        with transaction.atomic():
            current_json = template.template_json or {}
            updated_json = current_json.copy()
            
            # Delete keys first
            if to_delete:
                for key in to_delete:
                    updated_json.pop(key, None)
            
            # Update existing keys
            if to_update:
                updated_json.update(to_update)
            
            # Add new keys
            if to_add:
                updated_json.update(to_add)
            
            # Save the updated JSON
            template.template_json = updated_json
            template.save(update_fields=['template_json'])
        
        return Response({
            "message": "Template JSON updated successfully",
            "operations": {
                "added": list(to_add.keys()) if to_add else [],
                "updated": list(to_update.keys()) if to_update else [],
                "deleted": to_delete if to_delete else []
            },
            "template_json": template.template_json
        })
