"""
Notification helper functions.
Central place to create notifications for various events.
"""
from .models import Notification


def notify_access_request(dataset, requested_by):
    """Notify admins when a user requests access."""
    Notification.create_for(
        target_role="ADMIN",
        title=f"Access request: {dataset.name}",
        message=f"{requested_by} requested access to '{dataset.name}'",
        level="info",
        icon="fa-key",
        link="settings",
        link_label="Review Request",
        action_type="access_request",
        action_ref=dataset.name,
    )


def notify_access_resolved(dataset, username, status):
    """Notify the user when their request is approved/rejected/revoked."""
    labels = {
        "approved": ("Access Granted", "fa-check-circle", "success"),
        "rejected": ("Access Denied", "fa-times-circle", "warning"),
        "revoked": ("Access Revoked", "fa-ban", "danger"),
    }
    title, icon, level = labels.get(status, ("Update", "fa-bell", "info"))
    Notification.create_for(
        target_user=username,
        title=f"{title}: {dataset.name}",
        message=f"Your access to '{dataset.name}' was {status}",
        level=level,
        icon=icon,
        link="lakes",
        link_label="Open Lakes",
        action_type="access_resolved",
        action_ref=dataset.name,
    )


def notify_dataset_uploaded(dataset, uploaded_by):
    """Notify others when a public dataset is uploaded."""
    Notification.create_for(
        target_role="ALL",
        title=f"New public dataset: {dataset.name}",
        message=f"{uploaded_by} uploaded '{dataset.name}' ({dataset.row_count} rows)",
        level="success",
        icon="fa-cloud-upload-alt",
        link="lakes",
        link_label="Browse Datasets",
        action_type="dataset_upload",
        action_ref=dataset.name,
    )


def notify_ebs_failure(username, server_name, error):
    """Notify admins when an EBS query fails."""
    Notification.create_for(
        target_role="ADMIN",
        title=f"EBS Query Failed — {server_name}",
        message=f"{username}: {error[:200]}",
        level="danger",
        icon="fa-exclamation-triangle",
        link="ebslogs",
        link_label="View Logs",
        action_type="ebs_fail",
        action_ref=server_name,
    )


def notify_template_added(template, uploaded_by):
    """Notify when a new SQL template is added."""
    Notification.create_for(
        target_role="ALL",
        title=f"New SQL template: {template.name}",
        message=f"{uploaded_by} added a new {template.category} template",
        level="info",
        icon="fa-book",
        link="sqlibrary",
        link_label="Open Library",
        action_type="template_add",
        action_ref=template.name,
    )


def notify_announcement(title, message):
    """Broadcast an announcement."""
    Notification.create_for(
        target_role="ALL",
        title=title,
        message=message,
        level="info",
        icon="fa-bullhorn",
        action_type="announcement",
    )


def notify_user_created(username, role, created_by):
    """Notify admins when a new user is created."""
    Notification.create_for(
        target_role="ADMIN",
        title=f"New user: {username}",
        message=f"{created_by} created user '{username}' with role {role}",
        level="info",
        icon="fa-user-plus",
        link="settings",
        link_label="View Users",
        action_type="user_create",
        action_ref=username,
    )