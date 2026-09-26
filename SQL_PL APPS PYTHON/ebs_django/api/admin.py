"""
Django Admin customization for EBS R12 Explorer.
Only ADMIN users (is_staff=True) can access /admin/.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import (
    User, Dataset, DatasetShare, AccessRequest,
    ActivityLog, Note, TopTable, SearchLog,
    ApiKey, SqlTemplate, AppSetting,
    DbServer, EbsQueryLog, Notification, EditorSession,
)


# ==================== USER ADMIN ====================
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("id", "username", "full_name", "role", "active", "is_staff", "last_login", "created_at")
    list_filter = ("role", "active", "is_staff")
    search_fields = ("username", "full_name", "email")
    ordering = ("id",)
    readonly_fields = ("created_at", "last_login")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal Info", {"fields": ("full_name", "email")}),
        ("Role & Permissions", {"fields": ("role", "active", "is_staff", "is_superuser")}),
        ("Editor Preferences", {"fields": ("editor_theme", "editor_case")}),
        ("Timestamps", {"fields": ("created_at", "last_login")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "role", "full_name", "email"),
        }),
    )


# ==================== DATASET ADMIN ====================
@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "uploaded_by", "source_format",
        "row_count", "column_count", "size_display",
        "private_display", "deleted_display", "uploaded_at",
    )
    list_filter = ("private", "deleted", "source_format")
    search_fields = ("name", "description", "tags", "uploaded_by")
    ordering = ("-uploaded_at",)
    readonly_fields = (
        "uploaded_at", "deleted_at", "data_file", "compressed",
        "row_count", "column_count", "columns_json",
    )
    date_hierarchy = "uploaded_at"

    fieldsets = (
        (None, {"fields": ("name", "description", "tags", "uploaded_by")}),
        ("Source", {"fields": ("source_filename", "source_format")}),
        ("Storage", {"fields": ("data_file", "compressed", "row_count", "column_count", "columns_json")}),
        ("Access", {"fields": ("private",)}),
        ("Status", {"fields": ("deleted", "deleted_at")}),
    )

    actions = ["soft_delete_selected", "restore_selected", "permanent_delete_selected"]

    @admin.display(description="Size")
    def size_display(self, obj):
        size = obj.size_on_disk()
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / 1024 / 1024:.2f} MB"

    @admin.display(description="Private")
    def private_display(self, obj):
        if obj.private:
            return format_html('<span style="color:orange;font-weight:bold;">🔒 Private</span>')
        return format_html('<span style="color:green;">🌐 Public</span>')

    @admin.display(description="Status")
    def deleted_display(self, obj):
        if obj.deleted:
            return format_html('<span style="color:red;font-weight:bold;">🗑️ Trash</span>')
        return format_html('<span style="color:green;">✓ Active</span>')

    @admin.action(description="🗑️ Move selected to Trash")
    def soft_delete_selected(self, request, queryset):
        from django.utils import timezone
        queryset.update(deleted=True, deleted_at=timezone.now())
        self.message_user(request, f"{queryset.count()} dataset(s) moved to trash.")

    @admin.action(description="♻️ Restore selected from Trash")
    def restore_selected(self, request, queryset):
        queryset.update(deleted=False, deleted_at=None)
        self.message_user(request, f"{queryset.count()} dataset(s) restored.")

    @admin.action(description="❌ PERMANENTLY delete selected (cannot be undone)")
    def permanent_delete_selected(self, request, queryset):
        count = 0
        for obj in queryset:
            obj.delete_data_file()
            obj.delete()
            count += 1
        self.message_user(request, f"{count} dataset(s) permanently deleted.")


# ==================== INLINES ====================
class DatasetShareInline(admin.TabularInline):
    model = DatasetShare
    extra = 0
    readonly_fields = ("shared_at",)


class AccessRequestInline(admin.TabularInline):
    model = AccessRequest
    extra = 0
    readonly_fields = ("created_at", "resolved_at")
    fields = ("requested_by", "status", "created_at", "resolved_at")


DatasetAdmin.inlines = [DatasetShareInline, AccessRequestInline]


# ==================== DATASET SHARE ADMIN ====================
@admin.register(DatasetShare)
class DatasetShareAdmin(admin.ModelAdmin):
    list_display = ("id", "dataset", "shared_with", "shared_by", "shared_at")
    list_filter = ("shared_at",)
    search_fields = ("shared_with", "shared_by", "dataset__name")
    ordering = ("-shared_at",)


# ==================== ACCESS REQUEST ADMIN ====================
@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "requested_by", "dataset_link", "status_display", "created_at", "resolved_at")
    list_filter = ("status", "created_at")
    search_fields = ("requested_by", "dataset__name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "resolved_at")

    actions = ["approve_selected", "reject_selected", "revoke_selected"]

    @admin.display(description="Dataset")
    def dataset_link(self, obj):
        return format_html('<a href="/admin/api/dataset/{}/change/">{}</a>',
                          obj.dataset.id, obj.dataset.name)

    @admin.display(description="Status")
    def status_display(self, obj):
        colors = {"pending": "orange", "approved": "green", "rejected": "red", "revoked": "purple"}
        color = colors.get(obj.status, "gray")
        return format_html('<span style="color:{};font-weight:bold;">{}</span>',
                          color, obj.status.upper())

    @admin.action(description="✅ Approve selected")
    def approve_selected(self, request, queryset):
        from django.utils import timezone
        queryset.update(status="approved", resolved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} request(s) approved.")

    @admin.action(description="❌ Reject selected")
    def reject_selected(self, request, queryset):
        from django.utils import timezone
        queryset.update(status="rejected", resolved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} request(s) rejected.")

    @admin.action(description="🚫 Revoke selected")
    def revoke_selected(self, request, queryset):
        from django.utils import timezone
        queryset.update(status="revoked", resolved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} request(s) revoked.")


# ==================== ACTIVITY LOG ADMIN ====================
@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "username", "action", "short_details", "ip")
    list_filter = ("action", "username", "created_at")
    search_fields = ("username", "action", "details")
    ordering = ("-created_at",)
    readonly_fields = ("username", "action", "details", "ip", "created_at")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Details")
    def short_details(self, obj):
        return obj.details[:80] + "..." if len(obj.details) > 80 else obj.details


# ==================== NOTE ADMIN ====================
@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "color", "rank", "created_by", "created_at")
    list_filter = ("color", "created_by")
    search_fields = ("title", "content")
    ordering = ("rank", "id")
    list_editable = ("rank", "color")


# ==================== TOP TABLE ADMIN ====================
@admin.register(TopTable)
class TopTableAdmin(admin.ModelAdmin):
    list_display = ("id", "table_name", "description", "rank", "created_at")
    search_fields = ("table_name", "description")
    ordering = ("rank", "id")
    list_editable = ("rank", "description")


# ==================== SEARCH LOG ADMIN ====================
@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "username", "term", "search_type", "table_hit")
    list_filter = ("search_type", "username")
    search_fields = ("term", "table_hit")
    ordering = ("-created_at",)
    readonly_fields = ("username", "term", "search_type", "dataset_id", "table_hit", "created_at")

    def has_add_permission(self, request):
        return False


# ==================== API KEY ADMIN ====================
@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "key_preview", "created_by", "created_at", "last_used", "active")
    list_filter = ("active", "created_by")
    search_fields = ("label", "key")
    ordering = ("-created_at",)
    readonly_fields = ("key", "created_at", "last_used")

    @admin.display(description="Key")
    def key_preview(self, obj):
        return f"{obj.key[:16]}..."


# ==================== SQL TEMPLATE ADMIN ====================
@admin.register(SqlTemplate)
class SqlTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "uploaded_by", "uploaded_at", "private", "content_size")
    list_filter = ("category", "private", "uploaded_by")
    search_fields = ("name", "description", "tags", "content")
    ordering = ("-uploaded_at",)
    readonly_fields = ("uploaded_at", "updated_at")

    @admin.display(description="Size")
    def content_size(self, obj):
        return f"{len(obj.content):,} chars"


# ==================== APP SETTING ADMIN ====================
@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value_preview", "updated_at")
    search_fields = ("key", "value")
    ordering = ("key",)

    @admin.display(description="Value")
    def value_preview(self, obj):
        return obj.value[:80] + "..." if len(obj.value) > 80 else obj.value


# ==================== DB SERVER ADMIN (single registration) ====================
@admin.register(DbServer)
class DbServerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "server_type", "host_display", "connection_info",
                    "is_active", "created_by", "created_at")
    list_filter = ("server_type", "is_active", "created_by")
    search_fields = ("name", "host", "service_name", "sid", "base_url")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Basic Info", {"fields": ("name", "server_type", "description", "is_active")}),
        ("EBS Connection", {"fields": ("host", "port", "service_name", "sid")}),
        ("Fusion Connection", {"fields": ("base_url",)}),
        ("Metadata", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    @admin.display(description="Host")
    def host_display(self, obj):
        if obj.server_type == "EBS":
            return f"{obj.host}:{obj.port}"
        return obj.base_url[:50]

    @admin.display(description="Connection")
    def connection_info(self, obj):
        if obj.server_type == "EBS":
            return obj.service_name or obj.sid or "—"
        return "Cloud API"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user.username
        super().save_model(request, obj, form, change)


# ==================== EBS QUERY LOG ADMIN (single registration) ====================
@admin.register(EbsQueryLog)
class EbsQueryLogAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "username", "server", "rows_returned",
                    "duration_ms", "success_display", "ip")
    list_filter = ("success", "username", "server", "created_at")
    search_fields = ("username", "sql_preview", "sql_hash", "error_message")
    ordering = ("-created_at",)
    readonly_fields = ("username", "server", "sql_hash", "sql_preview",
                       "rows_returned", "duration_ms", "success",
                       "error_message", "ip", "created_at")
    date_hierarchy = "created_at"

    @admin.display(description="Status")
    def success_display(self, obj):
        if obj.success:
            return format_html('<span style="color:green;font-weight:bold;">✓ Success</span>')
        return format_html('<span style="color:red;font-weight:bold;">✗ Failed</span>')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ==================== NOTIFICATION ADMIN ====================
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "title", "level", "target_user", "target_role", "read_count")
    list_filter = ("level", "target_role", "created_at")
    search_fields = ("title", "message", "target_user", "action_ref")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"

    fieldsets = (
        ("Target", {"fields": ("target_user", "target_role")}),
        ("Content", {"fields": ("title", "message", "level", "icon")}),
        ("Link", {"fields": ("link", "link_label")}),
        ("Action", {"fields": ("action_type", "action_ref")}),
        ("Metadata", {"fields": ("read_by", "created_at")}),
    )

    @admin.display(description="Read by")
    def read_count(self, obj):
        if not obj.read_by:
            return "0"
        return str(len(obj.read_by.split(",")))


# ==================== EDITOR SESSION ADMIN ====================
@admin.register(EditorSession)
class EditorSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "server_id", "db_username", "last_used", "closed")
    list_filter = ("closed", "theme", "case_mode")
    search_fields = ("user__username", "name", "editor_sql")
    ordering = ("-last_used",)
    readonly_fields = ("session_key", "created_at", "last_used")