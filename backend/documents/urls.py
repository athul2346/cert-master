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
    VerifyQRAPIView,
    CertificateRenderAPIView
)


urlpatterns = [
    path('document-types/', DocumentTypeListCreateAPIView.as_view(), name='documenttype-list-create'),
    path('document-types/<int:pk>/', DocumentTypeRetrieveUpdateDestroyAPIView.as_view(), name='documenttype-detail'),
    path('document-template/', DocumentTemplateListCreateAPIView.as_view(), name='documenttemplate-list-create'),
    path('document-template/<int:pk>/', DocumentTemplateRetrieveUpdateDestroyAPIView.as_view(), name='documenttemplate-detail'),
    path("documents/", CompanyDocumentCreateView.as_view(), name="document-create"),
    path("documents/list/", CompanyDocumentListView.as_view(), name="document-list"),
    path("documents/<int:pk>/", CompanyDocumentDetailView.as_view(), name="document-detail"),
    path("documents/<int:pk>/update-json/", CompanyDocumentJsonUpdateView.as_view(), name="document-json-update"),
    path("render/", CertificateRenderAPIView.as_view(), name="document-render"),
    path("verify/<uuid:uuid>/", VerifyQRAPIView.as_view(), name="verify-qr"),
]
