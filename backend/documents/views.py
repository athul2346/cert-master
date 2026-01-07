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
    QRGenerateSerializer
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

        document.file.delete(save=False)  # remove file from storage
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

        # ✅ Valid QR
        certificate_url = document.file.url if document.file else None

        return Response(
            {
                "verified": True,
                "certificate_file": certificate_url,
                "company": document.company.organisation_name,
                "document_type": document.document_type.name,
                "recipient": document.recipient,
                "issued_date": document.issued_date,
                "expiry_date": document.expiry_date,
                "payload": qr.payload,
            },
            status=status.HTTP_200_OK
        )