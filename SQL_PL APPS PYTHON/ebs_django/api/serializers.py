"""DRF Serializers."""
from rest_framework import serializers
from .models import (
    User, Dataset, DatasetShare, AccessRequest,
    ActivityLog, Note, TopTable, SearchLog,
    ApiKey, SqlTemplate, AppSetting,
    DbServer, EbsQueryLog, Notification, EditorSession,
)


# ==================== USER ====================
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "full_name", "email", "role", "active",
                  "editor_theme", "editor_case", "created_at", "last_login")
        read_only_fields = ("id", "created_at", "last_login")


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ("id", "username", "password", "full_name", "email", "role")

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("full_name", "email", "role", "active", "password")

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


# ==================== DATASET ====================
class DatasetSummarySerializer(serializers.ModelSerializer):
    is_owner = serializers.SerializerMethodField()
    accessible = serializers.SerializerMethodField()
    pending_request = serializers.SerializerMethodField()
    size_bytes = serializers.SerializerMethodField()

    class Meta:
        model = Dataset
        fields = ("id", "name", "description", "tags", "uploaded_by",
                  "uploaded_at", "source_filename", "source_format",
                  "row_count", "column_count", "private",
                  "is_owner", "accessible", "pending_request", "size_bytes")

    def get_is_owner(self, obj):
        user = self.context.get("user")
        return user and obj.uploaded_by_id == user.username

    def get_accessible(self, obj):
        user = self.context.get("user")
        if not user:
            return False
        if user.role == "ADMIN":
            return True
        if obj.uploaded_by_id == user.username:
            return True
        if not obj.private:
            return True
        if DatasetShare.objects.filter(dataset=obj, shared_with=user.username).exists():
            return True
        if AccessRequest.objects.filter(dataset=obj, requested_by=user.username, status="approved").exists():
            return True
        return False

    def get_pending_request(self, obj):
        user = self.context.get("user")
        if not user:
            return False
        return AccessRequest.objects.filter(
            dataset=obj, requested_by=user.username, status="pending"
        ).exists()

    def get_size_bytes(self, obj):
        return obj.size_on_disk()


class DatasetDetailSerializer(DatasetSummarySerializer):
    data = serializers.SerializerMethodField()
    columns = serializers.SerializerMethodField()

    class Meta(DatasetSummarySerializer.Meta):
        fields = DatasetSummarySerializer.Meta.fields + ("data", "columns")

    def get_data(self, obj):
        return obj.load_data()

    def get_columns(self, obj):
        return obj.get_columns()


# ==================== SHARE ====================
class DatasetShareSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = DatasetShare
        fields = ("id", "shared_with", "shared_by", "shared_at", "full_name")

    def get_full_name(self, obj):
        try:
            return User.objects.get(username=obj.shared_with).full_name
        except User.DoesNotExist:
            return ""


# ==================== ACCESS REQUEST ====================
class AccessRequestSerializer(serializers.ModelSerializer):
    dataset_name = serializers.SerializerMethodField()
    dataset_owner = serializers.SerializerMethodField()

    class Meta:
        model = AccessRequest
        fields = ("id", "dataset_id", "requested_by", "status",
                  "created_at", "resolved_at", "dataset_name", "dataset_owner")

    def get_dataset_name(self, obj):
        return obj.dataset.name if obj.dataset else ""

    def get_dataset_owner(self, obj):
        return obj.dataset.uploaded_by_id if obj.dataset else ""


# ==================== ACTIVITY ====================
class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ("id", "username", "action", "details", "ip", "created_at")


# ==================== NOTE ====================
class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ("id", "title", "content", "color", "rank",
                  "created_by", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


# ==================== TOP TABLE ====================
class TopTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopTable
        fields = ("id", "table_name", "description", "rank", "created_at")
        read_only_fields = ("id", "created_at")


# ==================== API KEY ====================
class ApiKeySerializer(serializers.ModelSerializer):
    preview = serializers.SerializerMethodField()

    class Meta:
        model = ApiKey
        fields = ("id", "label", "created_by", "created_at",
                  "last_used", "active", "preview")

    def get_preview(self, obj):
        return f"{obj.key[:12]}..."


# ==================== SQL TEMPLATE ====================
class SqlTemplateSummarySerializer(serializers.ModelSerializer):
    content_length = serializers.SerializerMethodField()

    class Meta:
        model = SqlTemplate
        fields = ("id", "name", "description", "category", "tags",
                  "uploaded_by", "uploaded_at", "updated_at",
                  "private", "source_filename", "content_length")

    def get_content_length(self, obj):
        return len(obj.content)


class SqlTemplateDetailSerializer(SqlTemplateSummarySerializer):
    class Meta(SqlTemplateSummarySerializer.Meta):
        fields = SqlTemplateSummarySerializer.Meta.fields + ("content",)


# ==================== SETTING ====================
class AppSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppSetting
        fields = ("key", "value", "updated_at")


# ==================== DB SERVER ====================
class DbServerSerializer(serializers.ModelSerializer):
    class Meta:
        model = DbServer
        fields = (
            "id", "name", "server_type", "description",
            "host", "port", "service_name", "sid", "base_url",
            "is_active", "created_by", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")


class DbServerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DbServer
        fields = (
            "name", "server_type", "description",
            "host", "port", "service_name", "sid", "base_url",
            "is_active",
        )

    def validate(self, data):
        st = data.get("server_type", "EBS")
        if st == "EBS":
            if not data.get("host"):
                raise serializers.ValidationError("Host is required for EBS servers")
            if not data.get("service_name") and not data.get("sid"):
                raise serializers.ValidationError("Either service_name or sid is required")
        elif st == "FUSION":
            if not data.get("base_url"):
                raise serializers.ValidationError("base_url is required for Fusion servers")
        return data


# ==================== EBS QUERY LOG ====================
class EbsQueryLogSerializer(serializers.ModelSerializer):
    server_name = serializers.SerializerMethodField()

    class Meta:
        model = EbsQueryLog
        fields = (
            "id", "username", "server_name", "sql_hash", "sql_preview",
            "rows_returned", "duration_ms", "success", "error_message",
            "ip", "created_at",
        )

    def get_server_name(self, obj):
        return obj.server.name if obj.server else "—"


# ==================== NOTIFICATION ====================
class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id", "target_user", "target_role",
            "title", "message", "level", "icon",
            "link", "link_label",
            "action_type", "action_ref",
            "created_at", "is_read",
        )

    def get_is_read(self, obj):
        user = self.context.get("user")
        if not user:
            return False
        return obj.is_read_by(user.username)


# ==================== EDITOR SESSION ====================
class EditorSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EditorSession
        fields = (
            "id", "name", "session_key", "editor_sql",
            "server_id", "db_username", "theme", "case_mode",
            "created_at", "last_used", "closed",
        )
        read_only_fields = ("id", "session_key", "created_at", "last_used")