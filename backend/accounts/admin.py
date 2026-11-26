from django.contrib import admin
from .models import CompanyProfile, CompanyVerificationDocument, EmailOTP


class VerificationDocInline(admin.TabularInline):
    model = CompanyVerificationDocument
    extra = 0


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("organisation_name", "short_code", "user", "status", "entity_type", "location", "created_at")
    list_filter = ("status", "entity_type")
    search_fields = ("organisation_name", "user__email", "cin_number", "short_code")
    inlines = [VerificationDocInline]

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        # References already printed on certificates embed this code.
        if obj and obj.documents.exists():
            readonly.append("short_code")
        return readonly


@admin.register(CompanyVerificationDocument)
class CompanyVerificationDocumentAdmin(admin.ModelAdmin):
    list_display = ("company", "file", "uploaded_at")


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "created_at", "expires_at", "attempts", "consumed_at")
    list_filter = ("purpose",)
    search_fields = ("user__email",)
    readonly_fields = ("code_hash", "created_at", "expires_at", "consumed_at")