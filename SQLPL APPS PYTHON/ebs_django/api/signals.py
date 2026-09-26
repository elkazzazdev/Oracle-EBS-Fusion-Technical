"""Signals — auto cleanup, sync, notifications."""
from django.db.models.signals import pre_delete, post_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_out
from .models import Dataset, User


@receiver(pre_delete, sender=Dataset)
def delete_dataset_file(sender, instance, **kwargs):
    instance.delete_data_file()


@receiver(post_save, sender=User)
def ensure_admin_role(sender, instance, **kwargs):
    if instance.role == "ADMIN" and not instance.is_staff:
        User.objects.filter(pk=instance.pk).update(is_staff=True, is_superuser=True)


@receiver(user_logged_out)
def clear_ebs_sessions_on_logout(sender, request, user, **kwargs):
    """Clear all in-memory EBS sessions when a user logs out."""
    if user:
        try:
            from .ebs_connector import session_store
            session_store.clear_user(user.id)
        except Exception:
            pass