from django.contrib import admin
from .models import CompanyProfile, CompanyVerificationDocument


class VerificationDocInline(admin.TabularInline):
    model = CompanyVerificationDocument
    extra = 0


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("organisation_name", "user", "status", "entity_type", "location", "created_at")
    list_filter = ("status", "entity_type")
    search_fields = ("organisation_name", "user__email", "cin_number")
    inlines = [VerificationDocInline]


@admin.register(CompanyVerificationDocument)
class CompanyVerificationDocumentAdmin(admin.ModelAdmin):
    list_display = ("company", "file", "uploaded_at")