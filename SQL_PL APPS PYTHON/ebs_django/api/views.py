"""
EBS R12 Explorer — API Views v2
================================
- 3 roles (ADMIN, CONSULTANT, USER)
- Notifications
- Multi-session EBS
- Setup wizard
"""
import json
import time
from pathlib import Path
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    User, Dataset, DatasetShare, AccessRequest,
    ActivityLog, Note, TopTable, SearchLog,
    ApiKey, SqlTemplate, AppSetting,
    DbServer, EbsQueryLog, Notification, EditorSession,
)
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    DatasetSummarySerializer, DatasetDetailSerializer,
    DatasetShareSerializer, AccessRequestSerializer,
    ActivityLogSerializer, NoteSerializer, TopTableSerializer,
    ApiKeySerializer, SqlTemplateSummarySerializer, SqlTemplateDetailSerializer,
    DbServerSerializer, DbServerCreateSerializer, EbsQueryLogSerializer,
    NotificationSerializer, EditorSessionSerializer,
)
from .ebs_connector import (
    session_store, validate_sql, execute_query, log_ebs_query,
    get_oracle_connection, hash_sql, HAS_ORACLEDB, clean_sql,
)
from .utils import log_activity, client_ip, load_datasets_to_sqlite, sanitize_table_name
from .notifications import (
    notify_access_request, notify_access_resolved,
    notify_dataset_uploaded, notify_ebs_failure, notify_template_added,
    notify_announcement, notify_user_created,
)


# ==================== HELPERS ====================
def is_admin(user):
    return user.is_authenticated and user.role == "ADMIN"


def is_consultant_or_above(user):
    return user.is_authenticated and user.role in ("ADMIN", "CONSULTANT")


def error(msg, code=400):
    return Response({"error": msg}, status=code)


# ==================== SETUP WIZARD ====================
@api_view(["GET"])
@permission_classes([AllowAny])
def setup_status(request):
    """Check if initial setup is needed."""
    admin_exists = User.objects.filter(username="ADMIN").exists()
    has_password = False
    if admin_exists:
        admin = User.objects.get(username="ADMIN")
        has_password = admin.has_usable_password()
    return Response({
        "setup_complete": admin_exists and has_password,
        "admin_exists": admin_exists,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def setup_create_admin(request):
    """Create the initial ADMIN user. Only works if no ADMIN exists yet."""
    if User.objects.filter(username="ADMIN").exists():
        return error("Setup already complete. ADMIN user exists.", 400)

    username = (request.data.get("username") or "ADMIN").strip().upper()
    password = request.data.get("password") or ""
    password2 = request.data.get("password2") or ""
    full_name = (request.data.get("full_name") or "").strip()
    email = (request.data.get("email") or "").strip()

    if not password or len(password) < 8:
        return error("Password must be at least 8 characters")
    if password != password2:
        return error("Passwords do not match")

    user = User.objects.create_superuser(
        username=username,
        password=password,
        role="ADMIN",
        full_name=full_name or "System Administrator",
        email=email,
    )
    log_activity(username, "SETUP_ADMIN", "Initial ADMIN created", client_ip(request))
    return Response({"message": "Admin created successfully", "username": user.username})


# ==================== PUBLIC SETTINGS ====================
@api_view(["GET"])
@permission_classes([AllowAny])
def public_settings(request):
    keys = ["site_name", "site_tagline", "announcement", "brand_color"]
    return Response({k: AppSetting.get(k, "") for k in keys})


# ==================== AUTH ====================
@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = (request.data.get("username") or "").strip().upper()
    password = request.data.get("password") or ""

    if not username or not password:
        return error("Username and password required")

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return error("Invalid credentials", 401)

    if not user.check_password(password):
        return error("Invalid credentials", 401)

    if not user.active:
        return error("Account disabled", 403)

    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])

    refresh = RefreshToken.for_user(user)
    log_activity(username, "LOGIN", "Successful login", client_ip(request))

    return Response({
        "token": str(refresh.access_token),
        "refresh": str(refresh),
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name,
            "editor_theme": user.editor_theme,
            "editor_case": user.editor_case,
        }
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_token_view(request):
    from rest_framework_simplejwt.tokens import RefreshToken as RT
    from rest_framework_simplejwt.exceptions import TokenError
    refresh_str = request.data.get("refresh") or ""
    if not refresh_str:
        return error("Refresh token required")
    try:
        refresh = RT(refresh_str)
        return Response({"token": str(refresh.access_token)})
    except TokenError as e:
        return error(f"Invalid refresh token: {e}", 401)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    u = request.user
    return Response({
        "id": u.id,
        "username": u.username,
        "role": u.role,
        "full_name": u.full_name,
        "email": u.email,
        "last_login": u.last_login,
        "editor_theme": u.editor_theme,
        "editor_case": u.editor_case,
        "can_connect_ebs": u.can_connect_ebs,
        "can_manage_users": u.can_manage_users,
    })


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_my_preferences(request):
    """Update the current user's editor preferences."""
    u = request.user
    theme = request.data.get("editor_theme")
    case_mode = request.data.get("editor_case")
    if theme:
        u.editor_theme = theme
    if case_mode in ("upper", "lower", "asis"):
        u.editor_case = case_mode
    u.save(update_fields=["editor_theme", "editor_case"])
    return Response({"message": "Preferences updated"})


# ==================== DATASETS ====================
def _dataset_summary(row, db, username, user_role):
    d = dict(row)
    is_owner = d["uploaded_by"] == username
    is_shared = db.execute("SELECT 1 FROM dataset_shares WHERE dataset_id=? AND shared_with=?",
                           (d["id"], username)).fetchone() is not None
    is_public = d["private"] == 0
    is_approved = db.execute(
        "SELECT 1 FROM access_requests WHERE dataset_id=? AND requested_by=? AND status='approved'",
        (d["id"], username)).fetchone() is not None
    d["is_owner"] = is_owner
    d["accessible"] = is_owner or is_shared or is_public or is_approved
    return d


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_datasets(request):
    qs = Dataset.objects.filter(uploaded_by=request.user.username, deleted=False)
    return Response(DatasetSummarySerializer(qs, many=True, context={"user": request.user}).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def all_datasets(request):
    user = request.user

    if user.role == "ADMIN":
        qs = Dataset.objects.filter(deleted=False)
        return Response(DatasetSummarySerializer(qs, many=True, context={"user": user}).data)

    accessible_qs = Dataset.objects.filter(
        Q(deleted=False) & (
            Q(uploaded_by=user.username)
            | Q(private=False)
            | Q(shares__shared_with=user.username)
            | Q(access_requests__requested_by=user.username, access_requests__status="approved")
        )
    ).distinct()

    out = DatasetSummarySerializer(accessible_qs, many=True, context={"user": user}).data

    locked_qs = Dataset.objects.filter(
        deleted=False, private=True
    ).exclude(
        uploaded_by=user.username
    ).exclude(
        shares__shared_with=user.username
    ).exclude(
        access_requests__requested_by=user.username, access_requests__status="approved"
    ).distinct()

    for ds in locked_qs:
        d = DatasetSummarySerializer(ds, context={"user": user}).data
        d["is_owner"] = False
        d["accessible"] = False
        d["pending_request"] = AccessRequest.objects.filter(
            dataset=ds, requested_by=user.username, status="pending"
        ).exists()
        out.append(d)

    return Response(out)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_dataset(request, ds_id):
    try:
        ds = Dataset.objects.get(id=ds_id, deleted=False)
    except Dataset.DoesNotExist:
        return error("Dataset not found", 404)

    user = request.user
    if user.role != "ADMIN":
        allowed = (
            ds.uploaded_by_id == user.username
            or not ds.private
            or DatasetShare.objects.filter(dataset=ds, shared_with=user.username).exists()
            or AccessRequest.objects.filter(dataset=ds, requested_by=user.username, status="approved").exists()
        )
        if not allowed:
            return error("Access denied", 403)

    return Response(DatasetDetailSerializer(ds, context={"user": user}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_dataset(request):
    """All roles can upload. Only CONSULTANT/ADMIN can mark public."""
    user = request.user
    if "file" not in request.FILES:
        return error("No file provided")

    file = request.FILES["file"]
    name = (request.data.get("name") or "").strip()
    description = (request.data.get("description") or "").strip()
    tags = (request.data.get("tags") or "").strip()
    is_private = str(request.data.get("private", "true")).lower() == "true"

    # USER role: force private
    if user.role == "USER":
        is_private = True

    if not file.name:
        return error("Empty filename")

    ext = Path(file.name).suffix.lower()
    file_bytes = file.read()

    warnings = []
    try:
        if ext == ".zip":
            from .parsers import process_zip
            rows, cols, warnings = process_zip(file_bytes)
            source_format = "zip"
        else:
            from .parsers import parse_any_file
            rows, cols = parse_any_file(file.name, file_bytes)
            if not rows:
                return error("No data rows extracted")
            source_format = ext.lstrip(".")

        if not name:
            name = Path(file.name).stem

        ds = Dataset.objects.create(
            name=name,
            description=description,
            tags=tags,
            uploaded_by_id=user.username,
            source_filename=file.name,
            source_format=source_format,
            row_count=len(rows),
            column_count=len(cols),
            columns_json=json.dumps(cols),
            private=is_private,
        )
        ds.save_data(rows)
        ds.save(update_fields=["data_file", "compressed"])

        log_activity(user.username, "UPLOAD_DATASET",
                     f"'{name}' ({len(rows)} rows, {source_format})", client_ip(request))

        # Notify if public
        if not is_private:
            notify_dataset_uploaded(ds, user.username)

        return Response({
            "id": ds.id,
            "name": name,
            "row_count": len(rows),
            "column_count": len(cols),
            "source_format": source_format,
            "warnings": warnings if warnings else None,
            "message": "Uploaded successfully"
        })
    except Exception as e:
        return error(f"Upload failed: {str(e)}")


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_dataset(request, ds_id):
    try:
        ds = Dataset.objects.get(id=ds_id)
    except Dataset.DoesNotExist:
        return error("Not found", 404)

    if request.user.role != "ADMIN" and ds.uploaded_by_id != request.user.username:
        return error("Only owner or admin can edit", 403)

    data = request.data
    changed = False
    for k in ("name", "description", "tags"):
        if k in data:
            setattr(ds, k, data[k])
            changed = True
    if "private" in data and request.user.role in ("ADMIN", "CONSULTANT"):
        ds.private = bool(data["private"])
        changed = True

    if changed:
        ds.save()
        log_activity(request.user.username, "UPDATE_DATASET", f"#{ds_id}", client_ip(request))

    return Response({"message": "Updated"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_dataset(request, ds_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    try:
        ds = Dataset.objects.get(id=ds_id)
    except Dataset.DoesNotExist:
        return error("Not found", 404)
    ds.deleted = True
    ds.deleted_at = timezone.now()
    ds.save()
    log_activity(request.user.username, "DELETE_DATASET", f"Moved to trash: '{ds.name}'", client_ip(request))
    return Response({"message": "Moved to trash"})


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def restore_dataset(request, ds_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    try:
        ds = Dataset.objects.get(id=ds_id)
    except Dataset.DoesNotExist:
        return error("Not found", 404)
    ds.deleted = False
    ds.deleted_at = None
    ds.save()
    log_activity(request.user.username, "RESTORE_DATASET", f"#{ds_id}", client_ip(request))
    return Response({"message": "Restored"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def permanent_delete(request, ds_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    try:
        ds = Dataset.objects.get(id=ds_id)
    except Dataset.DoesNotExist:
        return error("Not found", 404)
    ds.delete_data_file()
    ds.delete()
    log_activity(request.user.username, "PERMANENT_DELETE", f"#{ds_id}", client_ip(request))
    return Response({"message": "Permanently deleted"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def trash_list(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    cutoff = timezone.now() - timezone.timedelta(days=30)
    for ds in Dataset.objects.filter(deleted=True, deleted_at__lt=cutoff):
        ds.delete_data_file()
        ds.delete()
    qs = Dataset.objects.filter(deleted=True).order_by("-deleted_at")
    data = [{
        "id": d.id, "name": d.name, "description": d.description,
        "uploaded_by": d.uploaded_by_id, "deleted_at": d.deleted_at,
        "row_count": d.row_count, "column_count": d.column_count,
        "source_format": d.source_format,
    } for d in qs]
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_delete(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    mode = request.data.get("mode", "selected")
    ids = request.data.get("ids", [])
    if mode == "all":
        count = Dataset.objects.filter(deleted=False).update(deleted=True, deleted_at=timezone.now())
        log_activity(request.user.username, "BULK_DELETE", f"All datasets ({count})", client_ip(request))
        return Response({"message": f"All {count} datasets moved to trash"})
    elif mode == "selected" and ids:
        count = Dataset.objects.filter(id__in=ids, deleted=False).update(deleted=True, deleted_at=timezone.now())
        log_activity(request.user.username, "BULK_DELETE", f"{count} dataset(s)", client_ip(request))
        return Response({"message": f"{count} dataset(s) moved to trash"})
    return error("Invalid mode or empty ids")


# ==================== SHARES ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_shares(request, ds_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    shares = DatasetShare.objects.filter(dataset_id=ds_id)
    return Response(DatasetShareSerializer(shares, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_share(request, ds_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    username = (request.data.get("username") or "").strip().upper()
    if not username:
        return error("Username required")
    if not User.objects.filter(username=username).exists():
        return error("User not found", 404)
    try:
        DatasetShare.objects.create(dataset_id=ds_id, shared_with=username, shared_by=request.user.username)
        log_activity(request.user.username, "SHARE_DATASET", f"#{ds_id} with {username}", client_ip(request))
        return Response({"message": "Shared"})
    except Exception:
        return error("Already shared")


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_share(request, ds_id, username):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    DatasetShare.objects.filter(dataset_id=ds_id, shared_with=username.upper()).delete()
    log_activity(request.user.username, "UNSHARE_DATASET", f"#{ds_id} from {username}", client_ip(request))
    return Response({"message": "Removed"})


# ==================== ACCESS REQUESTS ====================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def request_access(request):
    ds_id = request.data.get("dataset_id")
    if not ds_id:
        return error("dataset_id required")
    try:
        ds = Dataset.objects.get(id=ds_id)
    except Dataset.DoesNotExist:
        return error("Dataset not found", 404)

    existing = AccessRequest.objects.filter(dataset=ds, requested_by=request.user.username).first()
    if existing:
        if existing.status == "revoked":
            existing.status = "pending"
            existing.created_at = timezone.now()
            existing.resolved_at = None
            existing.save()
            notify_access_request(ds, request.user.username)
            log_activity(request.user.username, "RE_REQUEST_ACCESS", f"'{ds.name}'", client_ip(request))
            return Response({"message": "Request submitted"})
        return error(f"Request already {existing.status}")

    AccessRequest.objects.create(dataset=ds, requested_by=request.user.username)
    notify_access_request(ds, request.user.username)
    log_activity(request.user.username, "REQUEST_ACCESS", f"Requested access to '{ds.name}'", client_ip(request))
    return Response({"message": "Request submitted"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_access_requests(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    qs = AccessRequest.objects.filter(status="pending").select_related("dataset")
    return Response(AccessRequestSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_approved_requests(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    qs = AccessRequest.objects.filter(status="approved").select_related("dataset").order_by("-resolved_at")
    return Response(AccessRequestSerializer(qs, many=True).data)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def resolve_request(request, req_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    try:
        req = AccessRequest.objects.get(id=req_id)
    except AccessRequest.DoesNotExist:
        return error("Request not found", 404)

    new_status = request.data.get("status")
    if new_status not in ("approved", "rejected"):
        return error("Invalid status")

    req.status = new_status
    req.resolved_at = timezone.now()
    req.save()

    notify_access_resolved(req.dataset, req.requested_by, new_status)
    log_activity(request.user.username, "RESOLVE_ACCESS", f"#{req_id} → {new_status}", client_ip(request))
    return Response({"message": f"Request {new_status}"})


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def revoke_access(request, req_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    try:
        req = AccessRequest.objects.get(id=req_id)
    except AccessRequest.DoesNotExist:
        return error("Request not found", 404)
    if req.status != "approved":
        return error("Only approved requests can be revoked")
    req.status = "revoked"
    req.resolved_at = timezone.now()
    req.save()

    notify_access_resolved(req.dataset, req.requested_by, "revoked")
    log_activity(request.user.username, "REVOKE_ACCESS",
                 f"Revoked access for {req.requested_by} on dataset #{req.dataset_id}", client_ip(request))
    return Response({"message": "Access revoked"})


# ==================== USERS (Admin only) ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_users(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    qs = User.objects.all().order_by("id")
    return Response(UserSerializer(qs, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_user(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    s = UserCreateSerializer(data=request.data)
    if not s.is_valid():
        return error(str(s.errors))
    username = s.validated_data["username"].upper()
    if User.objects.filter(username=username).exists():
        return error("Username exists")
    s.validated_data["username"] = username
    user = s.save()
    notify_user_created(user.username, user.role, request.user.username)
    log_activity(request.user.username, "CREATE_USER", f"{user.username} ({user.role})", client_ip(request))
    return Response({"id": user.id, "message": "Created"})


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_user(request, user_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return error("Not found", 404)
    if user.username == "ADMIN" and request.data.get("role") and request.data["role"] != "ADMIN":
        return error("Cannot change ADMIN role")
    s = UserUpdateSerializer(user, data=request.data, partial=True)
    if not s.is_valid():
        return error(str(s.errors))
    s.save()
    log_activity(request.user.username, "UPDATE_USER", f"#{user_id}", client_ip(request))
    return Response({"message": "Updated"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_user(request, user_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return error("Not found", 404)
    if user.username == "ADMIN":
        return error("Cannot delete ADMIN")
    username = user.username
    user.delete()
    log_activity(request.user.username, "DELETE_USER", username, client_ip(request))
    return Response({"message": "Deleted"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_activity(request, username):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    qs = ActivityLog.objects.filter(username=username.upper()).order_by("-created_at")[:200]
    return Response(ActivityLogSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_stats(request, username):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    u = username.upper()
    return Response({
        "username": u,
        "uploads": Dataset.objects.filter(uploaded_by=u).count(),
        "logins": ActivityLog.objects.filter(username=u, action="LOGIN").count(),
        "queries": ActivityLog.objects.filter(username=u, action="RUN_QUERY").count(),
        "access_requests": AccessRequest.objects.filter(requested_by=u).count(),
    })


# ==================== ACTIVITY ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_activity(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    limit = min(int(request.query_params.get("limit", 200)), 1000)
    qs = ActivityLog.objects.all().order_by("-created_at")[:limit]
    return Response(ActivityLogSerializer(qs, many=True).data)


# ==================== SETTINGS ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_settings(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    return Response({s.key: s.value for s in AppSetting.objects.all()})


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_settings(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    for k, v in request.data.items():
        AppSetting.set(k, str(v))
    log_activity(request.user.username, "UPDATE_SETTINGS", f"Keys: {list(request.data.keys())}", client_ip(request))
    return Response({"message": "Settings updated"})


# ==================== NOTES ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_notes(request):
    qs = Note.objects.all().order_by("rank", "id")
    return Response(NoteSerializer(qs, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_note(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    s = NoteSerializer(data=request.data)
    if not s.is_valid():
        return error(str(s.errors))
    note = s.save(created_by=request.user.username)
    log_activity(request.user.username, "CREATE_NOTE", note.title, client_ip(request))
    return Response({"id": note.id, "message": "Note created"})


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_note(request, note_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    try:
        note = Note.objects.get(id=note_id)
    except Note.DoesNotExist:
        return error("Not found", 404)
    s = NoteSerializer(note, data=request.data, partial=True)
    if not s.is_valid():
        return error(str(s.errors))
    s.save(updated_at=timezone.now())
    log_activity(request.user.username, "UPDATE_NOTE", f"#{note_id}", client_ip(request))
    return Response({"message": "Updated"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_note(request, note_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    Note.objects.filter(id=note_id).delete()
    log_activity(request.user.username, "DELETE_NOTE", f"#{note_id}", client_ip(request))
    return Response({"message": "Deleted"})


# ==================== TOP TABLES ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_top_tables(request):
    qs = TopTable.objects.all().order_by("rank", "id")
    return Response(TopTableSerializer(qs, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_top_table(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    s = TopTableSerializer(data=request.data)
    if not s.is_valid():
        return error(str(s.errors))
    tt = s.save()
    log_activity(request.user.username, "CREATE_TOP_TABLE", tt.table_name, client_ip(request))
    return Response({"id": tt.id, "message": "Added"})


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_top_table(request, tt_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    try:
        tt = TopTable.objects.get(id=tt_id)
    except TopTable.DoesNotExist:
        return error("Not found", 404)
    s = TopTableSerializer(tt, data=request.data, partial=True)
    if not s.is_valid():
        return error(str(s.errors))
    s.save()
    return Response({"message": "Updated"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_top_table(request, tt_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    TopTable.objects.filter(id=tt_id).delete()
    return Response({"message": "Deleted"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def top_tables_auto(request):
    qs = (SearchLog.objects.exclude(table_hit="")
          .values("table_hit")
          .annotate(hits=Count("id"))
          .order_by("-hits")[:20])
    return Response([{"table_name": r["table_hit"], "hits": r["hits"]} for r in qs])


# ==================== SEARCH LOG ====================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def log_search(request):
    term = (request.data.get("term") or "").strip()
    if not term:
        return Response({"ok": True})
    SearchLog.objects.create(
        username=request.user.username,
        term=term[:500],
        search_type=request.data.get("search_type", "table")[:50],
        dataset_id=request.data.get("dataset_id"),
        table_hit=(request.data.get("table_hit") or "")[:255],
    )
    return Response({"ok": True})


# ==================== API KEYS ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_api_keys(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    qs = ApiKey.objects.all().order_by("-created_at")
    return Response(ApiKeySerializer(qs, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_api_key(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    import secrets
    label = (request.data.get("label") or "Untitled").strip()
    key = secrets.token_urlsafe(32)
    obj = ApiKey.objects.create(key=key, label=label, created_by=request.user.username)
    log_activity(request.user.username, "CREATE_API_KEY", label, client_ip(request))
    return Response({"id": obj.id, "key": key, "message": "API key created"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_api_key(request, key_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    ApiKey.objects.filter(id=key_id).delete()
    return Response({"message": "Deleted"})


# ==================== BACKUP ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def backup_export(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    import shutil
    from datetime import datetime as dt
    src = settings.DATABASES["default"]["NAME"]
    backup_name = f"ebs_backup_{dt.now().strftime('%Y%m%d_%H%M%S')}.db"
    dst = Path(settings.MEDIA_ROOT) / "backups" / backup_name
    shutil.copy(str(src), str(dst))
    log_activity(request.user.username, "BACKUP_EXPORT", backup_name, client_ip(request))
    return FileResponse(open(dst, "rb"), as_attachment=True, filename=backup_name)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def backup_import(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    if "file" not in request.FILES:
        return error("No file provided")
    f = request.FILES["file"]
    if not f.name.endswith(".db"):
        return error("Only .db files allowed")
    import shutil
    from datetime import datetime as dt
    dst = settings.DATABASES["default"]["NAME"]
    safety = Path(settings.MEDIA_ROOT) / "backups" / f"pre_restore_{dt.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy(str(dst), str(safety))
    with open(str(dst), "wb") as out:
        for chunk in f.chunks():
            out.write(chunk)
    log_activity(request.user.username, "BACKUP_RESTORE", f.name, client_ip(request))
    return Response({"message": "Restored. Please re-login."})


# ==================== NOTIFICATIONS ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """
    Return notifications visible to the current user.
    Query params:
      - limit: max number (default 50)
      - unread_only: true/false (default false)
    """
    limit = min(int(request.query_params.get("limit", 50)), 200)
    unread_only = request.query_params.get("unread_only", "false").lower() == "true"

    notifications = Notification.for_user(request.user, limit=limit, unread_only=unread_only)
    unread_count = len([n for n in Notification.for_user(request.user, limit=200) if not n.is_read_by(request.user.username)])

    return Response({
        "notifications": NotificationSerializer(notifications, many=True).data,
        "unread_count": unread_count,
    })


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notif_id):
    try:
        n = Notification.objects.get(id=notif_id)
    except Notification.DoesNotExist:
        return error("Notification not found", 404)
    n.mark_read_by(request.user.username)
    return Response({"message": "Marked as read"})


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    notifications = Notification.for_user(request.user, limit=200)
    for n in notifications:
        n.mark_read_by(request.user.username)
    return Response({"message": "All marked as read"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_notification(request, notif_id):
    """Users can delete notifications targeted at them."""
    try:
        n = Notification.objects.get(id=notif_id)
    except Notification.DoesNotExist:
        return error("Not found", 404)
    # Only delete if targeted at this user
    if n.target_user and n.target_user != request.user.username:
        return error("Cannot delete others' notifications", 403)
    n.delete()
    return Response({"message": "Deleted"})


# ==================== SQL LIBRARY ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_sql_templates(request):
    qs = SqlTemplate.objects.all().order_by("-uploaded_at")
    q = (request.query_params.get("q") or "").strip().lower()
    category = (request.query_params.get("category") or "").strip()
    if category:
        qs = qs.filter(category=category)
    data = SqlTemplateSummarySerializer(qs, many=True).data
    if q:
        data = [t for t in data if
                q in (t["name"] or "").lower()
                or q in (t["description"] or "").lower()
                or q in (t["tags"] or "").lower()
                or q in (t["category"] or "").lower()]
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_sql_template(request, tpl_id):
    try:
        t = SqlTemplate.objects.get(id=tpl_id)
    except SqlTemplate.DoesNotExist:
        return error("Template not found", 404)
    return Response(SqlTemplateDetailSerializer(t).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def create_sql_template(request):
    user = request.user
    name = description = content = ""
    category = "general"
    tags = source_filename = ""

    if request.content_type and "multipart/form-data" in request.content_type and "file" in request.FILES:
        file = request.FILES["file"]
        name = (request.data.get("name") or "").strip() or Path(file.name).stem
        description = (request.data.get("description") or "").strip()
        category = (request.data.get("category") or "general").strip()
        tags = (request.data.get("tags") or "").strip()
        source_filename = file.name
        try:
            content = file.read().decode("utf-8", errors="ignore")
        except Exception as e:
            return error(f"Could not read file: {e}")
    else:
        name = (request.data.get("name") or "").strip()
        description = (request.data.get("description") or "").strip()
        content = (request.data.get("content") or "").strip()
        category = (request.data.get("category") or "general").strip()
        tags = (request.data.get("tags") or "").strip()

    if not name:
        return error("Name is required")
    if not content:
        return error("Content is required")

    t = SqlTemplate.objects.create(
        name=name, description=description, content=content,
        category=category, tags=tags,
        uploaded_by=user.username, source_filename=source_filename,
    )
    notify_template_added(t, user.username)
    log_activity(user.username, "CREATE_SQL_TEMPLATE", f"'{name}'", client_ip(request))
    return Response({"id": t.id, "name": t.name, "message": "Template created"})


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_sql_template(request, tpl_id):
    try:
        t = SqlTemplate.objects.get(id=tpl_id)
    except SqlTemplate.DoesNotExist:
        return error("Template not found", 404)
    if request.user.role != "ADMIN" and t.uploaded_by != request.user.username:
        return error("Only owner or admin can edit", 403)
    changed = False
    for k in ("name", "description", "content", "category", "tags"):
        if k in request.data:
            setattr(t, k, request.data[k])
            changed = True
    if changed:
        t.updated_at = timezone.now()
        t.save()
        log_activity(request.user.username, "UPDATE_SQL_TEMPLATE", f"#{tpl_id}", client_ip(request))
    return Response({"message": "Updated"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_sql_template(request, tpl_id):
    try:
        t = SqlTemplate.objects.get(id=tpl_id)
    except SqlTemplate.DoesNotExist:
        return error("Template not found", 404)
    if request.user.role != "ADMIN" and t.uploaded_by != request.user.username:
        return error("Only owner or admin can delete", 403)
    t.delete()
    log_activity(request.user.username, "DELETE_SQL_TEMPLATE", f"#{tpl_id}", client_ip(request))
    return Response({"message": "Deleted"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sql_template_categories(request):
    cats = SqlTemplate.objects.values_list("category", flat=True).distinct().order_by("category")
    return Response([c for c in cats if c])


# ==================== CATALOGUE ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def catalogue_view(request):
    user = request.user
    if user.role == "ADMIN":
        qs = Dataset.objects.filter(deleted=False).order_by("-uploaded_at")
    else:
        qs = Dataset.objects.filter(deleted=False).filter(
            Q(uploaded_by=user.username)
            | Q(private=False)
            | Q(shares__shared_with=user.username)
            | Q(access_requests__requested_by=user.username, access_requests__status="approved")
        ).distinct().order_by("-uploaded_at")

    if not qs.exists():
        return Response({"source": "none", "dataset": None, "rows": [], "columns": []})

    chosen = None
    for ds in qs:
        cols = ds.get_columns()
        if any(c.get("name", "").upper() == "TABLE_NAME" for c in cols):
            chosen = ds
            break
    if chosen is None:
        chosen = qs.first()

    return Response({
        "source": "dataset",
        "dataset": {
            "id": chosen.id, "name": chosen.name, "description": chosen.description,
            "uploaded_by": chosen.uploaded_by_id, "uploaded_at": chosen.uploaded_at,
            "source_format": chosen.source_format,
            "row_count": chosen.row_count, "column_count": chosen.column_count,
        },
        "columns": chosen.get_columns(),
        "rows": chosen.load_data(),
    })


# ==================== LOCAL QUERY ====================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def run_sql_query(request):
    """Execute SELECT against local datasets (all roles)."""
    import re as re_mod
    sql = (request.data.get("sql") or "").strip()
    main_ds_id = request.data.get("dataset_id")

    if not sql:
        return error("SQL is required")
    if not main_ds_id:
        return error("dataset_id is required")

    sql_clean = re_mod.sub(r"--.*?$|/\*.*?\*/", " ", sql, flags=re_mod.MULTILINE | re_mod.DOTALL).strip()
    first_word = sql_clean.split()[0].upper() if sql_clean else ""
    if first_word not in ("SELECT", "WITH"):
        return error("Only SELECT queries are allowed")

    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
                 "ATTACH", "PRAGMA", "VACUUM", "REINDEX", "TRUNCATE"]
    upper_sql = sql_clean.upper()
    for kw in forbidden:
        if re_mod.search(rf"\b{kw}\b", upper_sql):
            return error(f"Keyword '{kw}' is not allowed")

    try:
        main_ds = Dataset.objects.get(id=main_ds_id, deleted=False)
    except Dataset.DoesNotExist:
        return error("Dataset not found", 404)

    user = request.user
    if user.role != "ADMIN":
        allowed = (
            main_ds.uploaded_by_id == user.username
            or not main_ds.private
            or DatasetShare.objects.filter(dataset=main_ds, shared_with=user.username).exists()
            or AccessRequest.objects.filter(dataset=main_ds, requested_by=user.username, status="approved").exists()
        )
        if not allowed:
            return error("Access denied", 403)

    if user.role == "ADMIN":
        all_ds = Dataset.objects.filter(deleted=False)
    else:
        all_ds = Dataset.objects.filter(deleted=False).filter(
            Q(uploaded_by=user.username)
            | Q(private=False)
            | Q(shares__shared_with=user.username)
            | Q(access_requests__requested_by=user.username, access_requests__status="approved")
        ).distinct()

    dataset_ids = {main_ds_id}
    tables_to_load = [main_ds_id]
    sql_upper = sql_clean.upper()

    for d in all_ds:
        sanitized = sanitize_table_name(d.name).upper()
        if re_mod.search(rf"\b{re_mod.escape(sanitized)}\b", sql_upper):
            if d.id not in dataset_ids:
                dataset_ids.add(d.id)
                tables_to_load.append(d.id)

    try:
        conn, table_map = load_datasets_to_sqlite(tables_to_load)
        reverse_map = {}
        for d in all_ds:
            if d.id in dataset_ids:
                for tname, orig in table_map.items():
                    if orig == d.name:
                        reverse_map[d.name.upper()] = tname
                        break

        final_sql = sql_clean
        for orig_upper, sanitized in reverse_map.items():
            final_sql = re_mod.sub(rf'"{re_mod.escape(orig_upper)}"', f'"{sanitized}"',
                                   final_sql, flags=re_mod.IGNORECASE)
            final_sql = re_mod.sub(rf'\b{re_mod.escape(orig_upper)}\b', f'"{sanitized}"',
                                   final_sql, flags=re_mod.IGNORECASE)

        cur = conn.execute(final_sql)
        rows = cur.fetchall()
        col_names = [d[0] for d in cur.description] if cur.description else []
        result = [dict(zip(col_names, r)) for r in rows]
        conn.close()

        log_activity(user.username, "RUN_QUERY",
                     f"Dataset #{main_ds_id} · {len(result)} rows · {sql[:80]}", client_ip(request))

        return Response({
            "columns": col_names, "rows": result, "row_count": len(result),
            "tables_loaded": list(table_map.values()), "executed_sql": final_sql,
        })
    except Exception as e:
        return error(f"SQL error: {str(e)}")


# ==================== EBS CONNECTOR ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_db_servers(request):
    servers = DbServer.objects.filter(is_active=True)
    return Response(DbServerSerializer(servers, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_all_db_servers(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    servers = DbServer.objects.all().order_by("name")
    return Response(DbServerSerializer(servers, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_db_server(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    s = DbServerCreateSerializer(data=request.data)
    if not s.is_valid():
        return error(str(s.errors))
    server = s.save(created_by=request.user.username)
    log_activity(request.user.username, "CREATE_DB_SERVER",
                 f"{server.name} ({server.server_type})", client_ip(request))
    return Response({"id": server.id, "message": "Server created",
                     "server": DbServerSerializer(server).data})


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_db_server(request, server_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    try:
        server = DbServer.objects.get(id=server_id)
    except DbServer.DoesNotExist:
        return error("Server not found", 404)
    s = DbServerCreateSerializer(server, data=request.data, partial=True)
    if not s.is_valid():
        return error(str(s.errors))
    server = s.save()
    server.updated_at = timezone.now()
    server.save(update_fields=["updated_at"])
    return Response({"message": "Updated", "server": DbServerSerializer(server).data})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_db_server(request, server_id):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    try:
        server = DbServer.objects.get(id=server_id)
    except DbServer.DoesNotExist:
        return error("Server not found", 404)
    name = server.name
    server.delete()
    log_activity(request.user.username, "DELETE_DB_SERVER", f"Deleted '{name}'", client_ip(request))
    return Response({"message": "Deleted"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def test_db_server(request):
    """Test a DB connection without saving credentials."""
    if not is_consultant_or_above(request.user):
        return error("Consultant or Admin access required", 403)
    server_id = request.data.get("server_id")
    db_username = request.data.get("db_username")
    db_password = request.data.get("db_password")

    if not server_id or not db_username or not db_password:
        return error("server_id, db_username, db_password are required")

    try:
        server = DbServer.objects.get(id=server_id)
    except DbServer.DoesNotExist:
        return error("Server not found", 404)

    try:
        result = execute_query(
            host=server.host, port=server.port,
            service_name=server.service_name, sid=server.sid,
            username=db_username, password=db_password,
            sql="SELECT 1 AS X FROM DUAL", max_rows=1, timeout=15,
        )
        return Response({"success": True, "message": "Connection successful",
                         "duration_ms": result["duration_ms"]})
    except Exception as e:
        msg = str(e).replace(db_password, "***").replace(db_username, "***")
        return error(f"Connection failed: {msg}", 400)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ebs_connect(request):
    """
    Establish an EBS session. Multi-session supported.
    Credentials kept in memory only.
    """
    if not is_consultant_or_above(request.user):
        return error("Consultant or Admin access required to connect to EBS", 403)

    if not HAS_ORACLEDB:
        return error("oracledb library is not installed on the server", 500)

    user_id = request.user.id
    server_id = request.data.get("server_id")
    db_username = request.data.get("db_username")
    db_password = request.data.get("db_password")
    session_name = (request.data.get("session_name") or "").strip()

    if not server_id or not db_username or not db_password:
        return error("server_id, db_username, db_password are required")

    try:
        server = DbServer.objects.get(id=server_id, is_active=True)
    except DbServer.DoesNotExist:
        return error("Server not found or inactive", 404)

    if server.server_type != "EBS":
        return error("This endpoint only supports EBS servers")

    # Check max concurrent connections
    max_conn = getattr(settings, "EBS_MAX_CONNECTIONS_PER_USER", 5)
    existing = session_store.count_user_sessions(user_id)
    current_key = session_store._make_key(user_id, server.id)
    is_same_server = session_store.get_session(current_key) is not None

    if not is_same_server and existing >= max_conn:
        return error(f"Maximum {max_conn} concurrent sessions reached. Close one first.", 429)

    # Test connection
    try:
        conn = get_oracle_connection(
            host=server.host, port=server.port,
            service_name=server.service_name, sid=server.sid,
            username=db_username, password=db_password, timeout=30,
        )
        conn.close()
    except Exception as e:
        msg = str(e).replace(db_password, "***").replace(db_username, "***")
        log_activity(request.user.username, "EBS_CONNECT_FAIL", f"{server.name}", client_ip(request))
        return error(f"Connection failed: {msg}", 401)

    # Store in memory
    session_key = session_store.add_session(
        user_id=user_id, server_id=server.id,
        username=db_username, password=db_password,
        name=session_name or server.name,
    )

    log_activity(request.user.username, "EBS_CONNECT",
                 f"{server.name} as '{db_username}'", client_ip(request))

    ttl = getattr(settings, "EBS_SESSION_TTL", 1200)
    return Response({
        "message": "Connected",
        "session_key": session_key,
        "server": DbServerSerializer(server).data,
        "username": db_username,
        "expires_in": ttl,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ebs_disconnect(request):
    """Disconnect a specific session (or all)."""
    user_id = request.user.id
    session_key = request.data.get("session_key")

    if session_key:
        # Verify ownership
        s = session_store.get_session(session_key)
        if s and s["user_id"] == user_id:
            session_store.remove_session(session_key)
    else:
        session_store.clear_user(user_id)

    log_activity(request.user.username, "EBS_DISCONNECT", session_key or "all", client_ip(request))
    return Response({"message": "Disconnected"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ebs_sessions_list(request):
    """List all active EBS sessions for the current user."""
    sessions = session_store.get_user_sessions(request.user.id)

    # Enrich with server info
    server_ids = {s["server_id"] for s in sessions}
    servers = {s.id: s for s in DbServer.objects.filter(id__in=server_ids)}

    enriched = []
    for s in sessions:
        server = servers.get(s["server_id"])
        enriched.append({
            "session_key": s["session_key"],
            "server_id": s["server_id"],
            "server_name": server.name if server else "Unknown",
            "server_type": server.server_type if server else "EBS",
            "username": s["username"],
            "name": s["name"],
            "connected_at": s["connected_at"],
            "last_used": s["last_used"],
        })

    return Response({"sessions": enriched, "max_allowed": getattr(settings, "EBS_MAX_CONNECTIONS_PER_USER", 5)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ebs_session_extend(request):
    """Extend TTL of a specific session."""
    session_key = request.data.get("session_key")
    if not session_key:
        return error("session_key required")
    s = session_store.get_session(session_key)
    if not s or s["user_id"] != request.user.id:
        return error("Session not found", 404)
    session_store.touch(session_key)
    return Response({"message": "Extended"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ebs_run_query(request):
    """
    Run a SELECT query on EBS using stored session credentials.
    Body: { sql, session_key }
    """
    if not HAS_ORACLEDB:
        return error("oracledb library is not installed on the server", 500)

    user_id = request.user.id
    sql = (request.data.get("sql") or "").strip()
    session_key = request.data.get("session_key")

    if not sql:
        return error("SQL is required")
    if not session_key:
        return error("session_key is required")

    # Get session
    creds = session_store.get_session(session_key)
    if not creds or creds["user_id"] != user_id:
        return error("Session not found or expired. Please reconnect.", 401)

    # Validate SQL
    sql = clean_sql(sql)
    is_valid, err = validate_sql(sql)
    if not is_valid:
        return error(f"SQL validation failed: {err}", 400)

    try:
        server = DbServer.objects.get(id=creds["server_id"])
    except DbServer.DoesNotExist:
        session_store.remove_session(session_key)
        return error("Server not found. Please reconnect.", 404)

    start = time.time()
    try:
        result = execute_query(
            host=server.host, port=server.port,
            service_name=server.service_name, sid=server.sid,
            username=creds["username"], password=creds["password"],
            sql=sql, max_rows=50000, timeout=300,
        )

        duration_ms = result["duration_ms"]

        log_ebs_query(
            username=request.user.username, server=server, sql=sql,
            rows_returned=result["row_count"], duration_ms=duration_ms,
            success=True, ip=client_ip(request),
        )
        log_activity(request.user.username, "EBS_RUN_QUERY",
                     f"{server.name} — {result['row_count']} rows in {duration_ms}ms",
                     client_ip(request))

        session_store.touch(session_key)

        return Response({
            "columns": result["columns"],
            "rows": result["rows"],
            "row_count": result["row_count"],
            "duration_ms": duration_ms,
            "truncated": result["truncated"],
            "server": server.name,
        })
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        msg = str(e)
        msg = msg.replace(creds["password"], "***").replace(creds["username"], "***")

        log_ebs_query(
            username=request.user.username, server=server, sql=sql,
            rows_returned=0, duration_ms=duration_ms,
            success=False, error_message=msg, ip=client_ip(request),
        )
        log_activity(request.user.username, "EBS_QUERY_FAIL", f"{server.name}", client_ip(request))

        # Notify admins of failures
        notify_ebs_failure(request.user.username, server.name, msg)

        return error(f"Query failed: {msg}", 400)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ebs_query_logs(request):
    if not is_admin(request.user):
        return error("Admin access required", 403)
    limit = min(int(request.query_params.get("limit", 200)), 1000)
    username = request.query_params.get("username")
    qs = EbsQueryLog.objects.select_related("server").order_by("-created_at")
    if username:
        qs = qs.filter(username=username.upper())
    qs = qs[:limit]
    return Response(EbsQueryLogSerializer(qs, many=True).data)


# ==================== EDITOR SESSIONS ====================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_editor_sessions(request):
    """List the current user's editor sessions."""
    qs = EditorSession.objects.filter(user=request.user, closed=False).order_by("-last_used")
    return Response(EditorSessionSerializer(qs, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_editor_session(request):
    """Create or return existing editor session."""
    import secrets
    user = request.user
    name = (request.data.get("name") or "").strip() or f"Session {timezone.now().strftime('%H:%M')}"
    session_key = secrets.token_urlsafe(16)

    session = EditorSession.objects.create(
        user=user,
        name=name,
        session_key=session_key,
        editor_sql=request.data.get("editor_sql", ""),
        server_id=request.data.get("server_id"),
        db_username=request.data.get("db_username", ""),
        theme=user.editor_theme,
        case_mode=user.editor_case,
    )
    return Response(EditorSessionSerializer(session).data, status=201)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_editor_session(request, session_key):
    """Save current editor state."""
    try:
        session = EditorSession.objects.get(session_key=session_key, user=request.user)
    except EditorSession.DoesNotExist:
        return error("Session not found", 404)

    if "editor_sql" in request.data:
        session.editor_sql = request.data["editor_sql"]
    if "name" in request.data:
        session.name = request.data["name"][:255]
    if "server_id" in request.data:
        session.server_id = request.data["server_id"]
    if "db_username" in request.data:
        session.db_username = request.data["db_username"]
    if "theme" in request.data:
        session.theme = request.data["theme"]
    if "case_mode" in request.data and request.data["case_mode"] in ("upper", "lower", "asis"):
        session.case_mode = request.data["case_mode"]

    session.save()
    return Response({"message": "Saved"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def close_editor_session(request, session_key):
    try:
        session = EditorSession.objects.get(session_key=session_key, user=request.user)
    except EditorSession.DoesNotExist:
        return error("Session not found", 404)
    session.closed = True
    session.save(update_fields=["closed"])
    return Response({"message": "Closed"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def clear_my_sessions(request):
    """Close all of current user's editor sessions."""
    EditorSession.objects.filter(user=request.user, closed=False).update(closed=True)
    return Response({"message": "All sessions closed"})


# ==================== HEALTH ====================
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    from .parsers import HAS_OPENPYXL, HAS_XLRD, HAS_YAML, HAS_PDF, HAS_BS4
    return Response({
        "status": "ok",
        "version": "2.0-django",
        "excel_xlsx": HAS_OPENPYXL,
        "excel_xls": HAS_XLRD,
        "yaml": HAS_YAML,
        "pdf": HAS_PDF,
        "html": HAS_BS4,
        "oracledb": HAS_ORACLEDB,
        "time": timezone.now().isoformat(),
    })