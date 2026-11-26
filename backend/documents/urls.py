from django.urls import path
from .views import (
    DocumentTypeListCreateAPIView,
    DocumentTypeRetrieveUpdateDestroyAPIView,
    TemplatesByDocumentTypeAPIView,
    DocumentsByDocumentTypeAPIView,
    CompanyDocumentCreateView,
    CompanyDocumentListView,
    CompanyDocumentDetailView,
    CompanyDocumentByReferenceAPIView,
    CompanyDocumentFieldUpdateView,
    CompanyDocumentStatusUpdateView,
    DocumentTemplateListCreateAPIView,
    DocumentTemplateRetrieveUpdateDestroyAPIView,
    PredefinedTemplateListView,
    PredefinedTemplateDetailView,
    PredefinedTemplateImportView,
    VerifyQRAPIView,
    CertificateRenderAPIView,
    HealthCheckAPIView
)


urlpatterns = [
    path('document-types/', DocumentTypeListCreateAPIView.as_view(), name='documenttype-list-create'),
    path('document-types/<int:pk>/', DocumentTypeRetrieveUpdateDestroyAPIView.as_view(), name='documenttype-detail'),
    path('document-types/<int:document_type_id>/templates/', TemplatesByDocumentTypeAPIView.as_view(), name='templates-by-document-type'),
    path('document-types/<int:document_type_id>/documents/', DocumentsByDocumentTypeAPIView.as_view(), name='documents-by-document-type'),
    path('document-template/', DocumentTemplateListCreateAPIView.as_view(), name='documenttemplate-list-create'),
    path('document-template/<int:pk>', DocumentTemplateRetrieveUpdateDestroyAPIView.as_view(), name='documenttemplate-detail'),
    path('predefined-templates/', PredefinedTemplateListView.as_view(), name='predefined-template-list'),
    path('predefined-templates/<slug:slug>/', PredefinedTemplateDetailView.as_view(), name='predefined-template-detail'),
    path('predefined-templates/<slug:slug>/import/', PredefinedTemplateImportView.as_view(), name='predefined-template-import'),
    path("documents/", CompanyDocumentCreateView.as_view(), name="document-create"),
    path("documents/list/", CompanyDocumentListView.as_view(), name="document-list"),
    path("documents/by-reference/<str:reference>/", CompanyDocumentByReferenceAPIView.as_view(), name="document-by-reference"),
    path("documents/<int:pk>/", CompanyDocumentDetailView.as_view(), name="document-detail"),
    path("documents/<int:pk>/update-fields/", CompanyDocumentFieldUpdateView.as_view(), name="document-field-update"),
    path("documents/<int:pk>/status/", CompanyDocumentStatusUpdateView.as_view(), name="document-status-update"),
    path("render/", CertificateRenderAPIView.as_view(), name="document-render"),
    path("verify-qr/<uuid:uuid>/", VerifyQRAPIView.as_view(), name="verify-qr"),
    path("health/", HealthCheckAPIView.as_view(), name="health-check"),
]