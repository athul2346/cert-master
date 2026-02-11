from django.urls import path
from .views import (
    DocumentTypeListCreateAPIView,
    DocumentTypeRetrieveUpdateDestroyAPIView,
    CompanyDocumentCreateView,
    CompanyDocumentListView,
    CompanyDocumentDetailView,
    CompanyDocumentJsonUpdateView,
    DocumentTemplateListCreateAPIView,
    DocumentTemplateRetrieveUpdateDestroyAPIView,
    DocumentTemplateJsonUpdateView,
    QRGenerateAPIView,
    VerifyQRAPIView
)


urlpatterns = [
    path('document-types/', DocumentTypeListCreateAPIView.as_view(), name='documenttype-list-create'),
    path('document-types/<int:pk>/', DocumentTypeRetrieveUpdateDestroyAPIView.as_view(), name='documenttype-detail'),
    path('document-template/', DocumentTemplateListCreateAPIView.as_view(), name='documenttemplate-list-create'),
    path('document-template/<int:pk>', DocumentTemplateRetrieveUpdateDestroyAPIView.as_view(), name='documenttemplate-detail'),
    path('document-template/<int:pk>/update-json/', DocumentTemplateJsonUpdateView.as_view(), name='documenttemplate-json-update'),
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
    
    # Partial JSON Update for documents
    path(
        "<str:document_type>/<str:recipient>/update-json/",
        CompanyDocumentJsonUpdateView.as_view(),
        name="document-json-update",
    ),
]
