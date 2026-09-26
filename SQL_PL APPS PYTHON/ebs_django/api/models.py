"""
EBS R12 Explorer — Database Models v2
=====================================
- 3 roles: ADMIN, CONSULTANT, USER
- Notifications system
- Multi-session support
- Editor preferences per user
"""
import os
import json
import gzip
from pathlib import Path
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings
from django.utils import timezone


# ==================== USER MANAGER ====================
class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra):
        if not username:
            raise ValueError("Username is required")
        user = self.model(username=username.upper(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra):
        extra.setdefault("role", "ADMIN")
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(username, password, **extra)


# ==================== USER ====================
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ("ADMIN", "Administrator"),
        ("CONSULTANT", "Consultant"),
        ("USER", "Standard User"),
    ]

    username = models.CharField(max_length=64, unique=True, db_index=True)
    full_name = models.CharField(max_length=255, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="USER")

    active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # Editor Preferences (per user)
    editor_theme = models.CharField(max_length=30, default="vs-dark")
    editor_case = models.CharField(max_length=20, default="upper")  # upper | lower | asis

    # Setup
    must_change_password = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.username} ({self.role})"

    def save(self, *args, **kwargs):
        self.username = self.username.upper()
        # Auto-sync is_staff/is_superuser with role
        if self.role == "ADMIN":
            self.is_staff = True
            self.is_superuser = True
        else:
            self.is_staff = False
            self.is_superuser = False
        super().save(*args, **kwargs)

    @property
    def can_connect_ebs(self):
        """Only ADMIN and CONSULTANT can connect to EBS."""
        return self.role in ("ADMIN", "CONSULTANT")

    @property
    def can_manage_users(self):
        return self.role == "ADMIN"

    @property
    def can_manage_servers(self):
        return self.role == "ADMIN"


# ==================== DATASET ====================
def dataset_data_path(dataset_id, ext="json.gz"):
    return Path(settings.MEDIA_ROOT) / "data" / f"dataset_{dataset_id}.{ext}"


class Dataset(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True, default="")
    tags = models.CharField(max_length=500, blank=True, default="")

    uploaded_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="datasets",
        to_field="username", db_column="uploaded_by"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    source_filename = models.CharField(max_length=500, blank=True, default="")
    source_format = models.CharField(max_length=20, blank=True, default="")

    row_count = models.IntegerField(default=0)
    column_count = models.IntegerField(default=0)
    columns_json = models.TextField(blank=True, default="[]")

    data_file = models.CharField(max_length=500, blank=True, default="")
    compressed = models.BooleanField(default=True)
    private = models.BooleanField(default=True)
    deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["deleted", "-uploaded_at"]),
            models.Index(fields=["uploaded_by"]),
        ]

    def __str__(self):
        return self.name

    def save_data(self, rows):
        path = dataset_data_path(self.id, "json.gz")
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as f:
            json.dump(rows, f, ensure_ascii=False)
        tmp.replace(path)
        self.data_file = str(path)
        self.compressed = True
        return path

    def load_data(self):
        if not self.data_file:
            return []
        path = Path(self.data_file)
        if not path.exists():
            return []
        try:
            if path.suffix == ".gz":
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    return json.load(f)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            return []

    def delete_data_file(self):
        if self.data_file:
            try:
                p = Path(self.data_file)
                if p.exists():
                    p.unlink()
            except Exception:
                pass

    def get_columns(self):
        try:
            return json.loads(self.columns_json or "[]")
        except Exception:
            return []

    def size_on_disk(self):
        if not self.data_file:
            return 0
        try:
            return Path(self.data_file).stat().st_size
        except Exception:
            return 0


# ==================== DATASET SHARE ====================
class DatasetShare(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="shares")
    shared_with = models.CharField(max_length=64, db_index=True)
    shared_by = models.CharField(max_length=64)
    shared_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("dataset", "shared_with")
        ordering = ["-shared_at"]

    def __str__(self):
        return f"#{self.dataset_id} → {self.shared_with}"


# ==================== ACCESS REQUEST ====================
class AccessRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("revoked", "Revoked"),
    ]

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="access_requests")
    requested_by = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.requested_by} → #{self.dataset_id} ({self.status})"


# ==================== ACTIVITY LOG ====================
class ActivityLog(models.Model):
    username = models.CharField(max_length=64, db_index=True)
    action = models.CharField(max_length=64, db_index=True)
    details = models.TextField(blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["username", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.created_at}] {self.username}: {self.action}"


# ==================== NOTE (Homepage) ====================
class Note(models.Model):
    COLOR_CHOICES = [
        ("blue", "Blue"), ("green", "Green"), ("yellow", "Yellow"),
        ("red", "Red"), ("purple", "Purple"),
    ]
    title = models.CharField(max_length=255)
    content = models.TextField()
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default="blue")
    rank = models.IntegerField(default=0)
    created_by = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["rank", "id"]

    def __str__(self):
        return self.title


# ==================== TOP TABLE ====================
class TopTable(models.Model):
    table_name = models.CharField(max_length=255, db_index=True)
    description = models.CharField(max_length=500, blank=True, default="")
    rank = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["rank", "id"]

    def __str__(self):
        return self.table_name


# ==================== SEARCH LOG ====================
class SearchLog(models.Model):
    username = models.CharField(max_length=64, db_index=True)
    term = models.CharField(max_length=500)
    search_type = models.CharField(max_length=50, default="table")
    dataset_id = models.IntegerField(null=True, blank=True)
    table_hit = models.CharField(max_length=255, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.username}: {self.term}"


# ==================== API KEY ====================
class ApiKey(models.Model):
    key = models.CharField(max_length=128, unique=True, db_index=True)
    label = models.CharField(max_length=255, blank=True, default="")
    created_by = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.label} ({self.key[:12]}...)"


# ==================== SQL TEMPLATE ====================
class SqlTemplate(models.Model):
    CATEGORY_CHOICES = [
        ("general", "General"), ("report", "Report"), ("plsql", "PL/SQL"),
        ("ddl", "DDL"), ("dml", "DML"), ("utility", "Utility"),
    ]
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True, default="")
    content = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default="general")
    tags = models.CharField(max_length=500, blank=True, default="")
    uploaded_by = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    private = models.BooleanField(default=False)
    source_filename = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.name


# ==================== SETTINGS ====================
class AppSetting(models.Model):
    key = models.CharField(max_length=128, unique=True, primary_key=True)
    value = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key

    @classmethod
    def get(cls, key, default=""):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value):
        obj, _ = cls.objects.update_or_create(key=key, defaults={"value": str(value)})
        return obj


# ==================== DB SERVER ====================
class DbServer(models.Model):
    SERVER_TYPE_CHOICES = [
        ("EBS", "Oracle EBS (Direct DB)"),
        ("FUSION", "Oracle Fusion Cloud"),
    ]
    name = models.CharField(max_length=255, db_index=True)
    server_type = models.CharField(max_length=20, choices=SERVER_TYPE_CHOICES, default="EBS")
    description = models.TextField(blank=True, default="")
    host = models.CharField(max_length=255, blank=True, default="")
    port = models.IntegerField(default=1521)
    service_name = models.CharField(max_length=255, blank=True, default="")
    sid = models.CharField(max_length=255, blank=True, default="")
    base_url = models.CharField(max_length=500, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_by = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "DB Server"
        verbose_name_plural = "DB Servers"

    def __str__(self):
        return f"{self.name} ({self.server_type})"

    def to_safe_dict(self):
        return {
            "id": self.id, "name": self.name, "server_type": self.server_type,
            "description": self.description, "host": self.host, "port": self.port,
            "service_name": self.service_name, "sid": self.sid,
            "base_url": self.base_url, "is_active": self.is_active,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ==================== EBS QUERY LOG ====================
class EbsQueryLog(models.Model):
    username = models.CharField(max_length=64, db_index=True)
    server = models.ForeignKey(DbServer, on_delete=models.SET_NULL, null=True, related_name="query_logs")
    sql_hash = models.CharField(max_length=64, db_index=True)
    sql_preview = models.CharField(max_length=300)
    rows_returned = models.IntegerField(default=0)
    duration_ms = models.IntegerField(default=0)
    success = models.BooleanField(default=True)
    error_message = models.CharField(max_length=500, blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["username", "-created_at"]),
            models.Index(fields=["server", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.username} → {self.server} @ {self.created_at}"


# ==================== NOTIFICATION (NEW) ====================
class Notification(models.Model):
    """
    Notifications system.
    - Events are created automatically on key actions.
    - Users see their own notifications + broadcast ones (target_role).
    """
    LEVEL_CHOICES = [
        ("info", "Information"),
        ("success", "Success"),
        ("warning", "Warning"),
        ("danger", "Error"),
    ]
    TARGET_ROLE_CHOICES = [
        ("ALL", "Everyone"),
        ("ADMIN", "Admins only"),
        ("CONSULTANT", "Consultants only"),
        ("USER", "Standard users only"),
    ]

    # Who should see it
    target_user = models.CharField(max_length=64, blank=True, default="", db_index=True,
                                   help_text="Specific user (leave empty for broadcast)")
    target_role = models.CharField(max_length=20, choices=TARGET_ROLE_CHOICES,
                                   default="ALL", db_index=True,
                                   help_text="Broadcast to all users with this role")

    # Content
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True, default="")
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default="info")
    icon = models.CharField(max_length=50, default="fa-bell")

    # Link (optional)
    link = models.CharField(max_length=500, blank=True, default="")
    link_label = models.CharField(max_length=100, blank=True, default="")

    # Metadata
    action_type = models.CharField(max_length=50, blank=True, default="",
                                   help_text="e.g. access_request, ebs_fail, upload")
    action_ref = models.CharField(max_length=255, blank=True, default="",
                                  help_text="Reference to the object (dataset name, etc.)")

    # Read tracking
    read_by = models.TextField(blank=True, default="",
                                help_text="Comma-separated usernames who marked as read")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_user", "-created_at"]),
            models.Index(fields=["target_role", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.level}] {self.title}"

    def is_read_by(self, username):
        if not self.read_by:
            return False
        return username.upper() in [u.strip() for u in self.read_by.split(",")]

    def mark_read_by(self, username):
        username = username.upper()
        existing = set()
        if self.read_by:
            existing = {u.strip() for u in self.read_by.split(",") if u.strip()}
        existing.add(username)
        self.read_by = ",".join(sorted(existing))
        self.save(update_fields=["read_by"])

    @classmethod
    def create_for(cls, target_user=None, target_role="ALL", **kwargs):
        """Helper to create a notification."""
        return cls.objects.create(
            target_user=(target_user or "").upper() if target_user else "",
            target_role=target_role,
            **kwargs
        )

    @classmethod
    def for_user(cls, user, limit=None, unread_only=False):
        """Return notifications visible to a specific user."""
        from django.db.models import Q
        qs = cls.objects.filter(
            Q(target_user=user.username) |
            Q(target_user="", target_role="ALL") |
            Q(target_user="", target_role=user.role)
        )
        if unread_only:
            qs = qs.filter()  # Filter in Python (read_by is CSV)
        qs = qs.order_by("-created_at")
        if limit:
            qs = qs[:limit]
        # Filter unread in Python
        if unread_only:
            qs = [n for n in qs if not n.is_read_by(user.username)]
        return qs


# ==================== EDITOR SESSION (NEW) ====================
class EditorSession(models.Model):
    """
    Persist editor state across sessions until user explicitly closes it.
    Each user can have multiple sessions (multi-session support).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="editor_sessions")
    name = models.CharField(max_length=255, default="Untitled Session")
    session_key = models.CharField(max_length=64, unique=True, db_index=True)

    # Session state (persist across reloads)
    editor_sql = models.TextField(blank=True, default="")
    server_id = models.IntegerField(null=True, blank=True)  # DbServer reference
    db_username = models.CharField(max_length=255, blank=True, default="")

    # Preferences snapshot
    theme = models.CharField(max_length=30, default="vs-dark")
    case_mode = models.CharField(max_length=20, default="upper")

    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    closed = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-last_used"]

    def __str__(self):
        return f"{self.user.username}: {self.name}"