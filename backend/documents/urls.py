from django.urls import path
from .views import (
    DocumentTypeListCreateAPIView,
    DocumentTypeRetrieveUpdateDestroyAPIView,
    CompanyDocumentCreateView,
    CompanyDocumentListView,
    CompanyDocumentDetailView,
    DocumentTemplateListCreateAPIView,
    DocumentTemplateRetrieveUpdateDestroyAPIView,
    QRGenerateAPIView,
    VerifyQRAPIView
)


urlpatterns = [
    path('document-types/', DocumentTypeListCreateAPIView.as_view(), name='documenttype-list-create'),
    path('document-types/<int:pk>/', DocumentTypeRetrieveUpdateDestroyAPIView.as_view(), name='documenttype-detail'),
    path('document-template/', DocumentTemplateListCreateAPIView.as_view(), name='documenttemplate-list-create'),
    path('document-template/<int:pk>', DocumentTemplateRetrieveUpdateDestroyAPIView.as_view(), name='documenttemplate-detail'),
    path("documents/", CompanyDocumentCreateView.as_view(), name="document-create"),
    path("generate/", QRGenerateAPIView.as_view(), name="qr-generate"),
    path("verify/<uuid:uuid>/", VerifyQRAPIView.as_view(), name="verify-qr"),


    # LIST
    path("list/", CompanyDocumentListView.as_view(), name="document-list"),

    # GET / UPDATE / DELETE (composite key)
    path(
        "<str:document_type>/<str:recipient>/",
        CompanyDocumentDetailView.as_view(),
        name="document-detail",
    ),
]