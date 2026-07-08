from django.contrib import admin
from django.utils.html import format_html

from .models import (
    ApprovalRoute,
    ApprovalStep,
    ApprovalTask,
    Attachment,
    AuditLog,
    ContractKind,
    CustomFieldDefinition,
    Department,
    Document,
    DocumentApprover,
    DocumentComment,
    DocumentPurpose,
    DocumentType,
    Notification,
    PasswordResetRequest,
    UserProfile,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "manager", "is_active"]
    search_fields = ["name", "code"]
    list_filter = ["is_active"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "patronymic", "department", "position", "phone"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "patronymic", "position"]
    list_filter = ["department"]


@admin.register(ContractKind)
class ContractKindAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active"]
    search_fields = ["name", "code", "description"]
    list_filter = ["is_active"]


@admin.register(DocumentPurpose)
class DocumentPurposeAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active"]
    search_fields = ["name", "code", "description"]
    list_filter = ["is_active"]


class CustomFieldInline(admin.TabularInline):
    model = CustomFieldDefinition
    extra = 0


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "default_due_days", "is_active"]
    search_fields = ["name", "code"]
    list_filter = ["is_active"]
    inlines = [CustomFieldInline]


class ApprovalStepInline(admin.TabularInline):
    model = ApprovalStep
    extra = 0


@admin.register(ApprovalRoute)
class ApprovalRouteAdmin(admin.ModelAdmin):
    list_display = ["name", "document_type", "route_type", "is_default", "is_active"]
    list_filter = ["document_type", "route_type", "is_default", "is_active"]
    search_fields = ["name"]
    inlines = [ApprovalStepInline]


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    readonly_fields = ["original_name", "size", "content_hash", "uploaded_by", "created_at"]


class ApprovalTaskInline(admin.TabularInline):
    model = ApprovalTask
    extra = 0
    readonly_fields = ["completed_at"]


class DocumentApproverInline(admin.TabularInline):
    model = DocumentApprover
    extra = 0


class DocumentCommentInline(admin.TabularInline):
    model = DocumentComment
    extra = 0
    readonly_fields = ["author", "created_at"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["system_number", "title", "document_type", "status", "author", "responsible", "registration_date"]
    list_filter = ["document_type", "status", "registration_date", "is_deleted"]
    search_fields = ["system_number", "internal_number", "title", "counterparty"]
    readonly_fields = ["system_number", "created_at", "updated_at", "archived_at"]
    inlines = [DocumentApproverInline, AttachmentInline, ApprovalTaskInline, DocumentCommentInline]
    fieldsets = [
        ("Регистрация", {"fields": ["document_type", "title", "system_number", "internal_number", "status"]}),
        ("Договор", {"fields": ["contract_kind", "document_purpose"]}),
        ("Ответственные", {"fields": ["author", "responsible", "department", "route"]}),
        ("Сроки и реквизиты", {"fields": ["registration_date", "due_date", "amount", "counterparty"]}),
        ("Содержание", {"fields": ["summary", "custom_data"]}),
        ("Служебное", {"fields": ["is_deleted", "archived_at", "created_at", "updated_at"]}),
    ]


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ["original_name", "document", "size", "uploaded_by", "created_at"]
    search_fields = ["original_name", "document__system_number", "content_hash"]
    readonly_fields = ["content_hash", "size", "created_at", "updated_at"]


@admin.register(DocumentApprover)
class DocumentApproverAdmin(admin.ModelAdmin):
    list_display = ["document", "order", "name", "approver", "due_days"]
    list_filter = ["due_days"]
    search_fields = ["document__system_number", "document__title", "approver__username", "name"]


@admin.register(ApprovalTask)
class ApprovalTaskAdmin(admin.ModelAdmin):
    list_display = ["document", "approver", "status", "due_date", "completed_at", "overdue_badge"]
    list_filter = ["status", "due_date"]
    search_fields = ["document__system_number", "document__title", "approver__username"]

    def overdue_badge(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color:#b00020;font-weight:600;">Просрочено</span>')
        return "Нет"

    overdue_badge.short_description = "Просрочка"


@admin.register(DocumentComment)
class DocumentCommentAdmin(admin.ModelAdmin):
    list_display = ["document", "author", "created_at"]
    search_fields = ["document__system_number", "text", "author__username"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["created_at", "recipient", "notification_type", "title", "is_read"]
    list_filter = ["notification_type", "is_read", "created_at"]
    search_fields = ["recipient__username", "title", "message", "document__system_number"]


@admin.register(PasswordResetRequest)
class PasswordResetRequestAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "code", "status", "expires_at", "used_at"]
    list_filter = ["status", "created_at", "expires_at"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "code"]
    readonly_fields = ["user", "code", "status", "expires_at", "used_at", "created_at", "updated_at"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "document", "action", "ip_address"]
    list_filter = ["action", "created_at"]
    search_fields = ["message", "document__system_number", "user__username"]
    readonly_fields = ["created_at", "updated_at", "user", "document", "action", "message", "ip_address"]
