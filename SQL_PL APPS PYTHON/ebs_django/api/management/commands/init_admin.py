"""
Management command: initialize default settings + ensure ADMIN exists.
⚠️ Password is NOT hardcoded anymore — user sets it via setup wizard or CLI.
"""
from django.core.management.base import BaseCommand
from django.conf import settings as django_settings
from api.models import User, AppSetting


class Command(BaseCommand):
    help = "Initialize settings + ensure ADMIN/CONSULTANT/USER accounts exist"

    def add_arguments(self, parser):
        parser.add_argument("--admin-password", type=str, help="Set ADMIN password (optional)")
        parser.add_argument("--consultant-password", type=str, help="Set CONSULTANT password")
        parser.add_argument("--user-password", type=str, help="Set USER password")

    def handle(self, *args, **options):
        # ===== DEFAULT SETTINGS =====
        defaults = {
            "site_name": "EBS R12 Explorer",
            "site_tagline": "Oracle EBS R12 Schema & Dataset Explorer",
            "announcement": "",
            "brand_color": "#2563eb",
            "rate_limit_per_minute": "120",
            "notifications_enabled": "true",
        }
        for k, v in defaults.items():
            if not AppSetting.objects.filter(key=k).exists():
                AppSetting.set(k, v)
        self.stdout.write(self.style.SUCCESS("✓ Default settings ensured"))

        # ===== ADMIN =====
        admin_username = "ADMIN"
        admin_password = options.get("admin_password")

        if not User.objects.filter(username=admin_username).exists():
            if admin_password:
                User.objects.create_superuser(
                    username=admin_username,
                    password=admin_password,
                    role="ADMIN",
                    full_name="System Administrator",
                )
                self.stdout.write(self.style.SUCCESS(f"✓ Created ADMIN with provided password"))
                self.stdout.write(self.style.WARNING(
                    "  ⚠️  Change this password from Settings after first login!"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    "⚠️  ADMIN user does NOT exist yet.\n"
                    "   Please run the setup wizard at: http://localhost:8000/setup/\n"
                    "   OR re-run this command with: --admin-password YOUR_PASSWORD"
                ))
        else:
            self.stdout.write(f"✓ ADMIN user already exists")

        # ===== CONSULTANT =====
        consultant_username = "CONSULTANT"
        consultant_password = options.get("consultant_password")
        if not User.objects.filter(username=consultant_username).exists():
            if consultant_password:
                User.objects.create_user(
                    username=consultant_username,
                    password=consultant_password,
                    role="CONSULTANT",
                    full_name="Default Consultant",
                )
                self.stdout.write(self.style.SUCCESS("✓ Created CONSULTANT"))
            else:
                self.stdout.write(self.style.WARNING(
                    "⚠️  CONSULTANT does not exist — skipping (optional)"
                ))
        else:
            self.stdout.write("✓ CONSULTANT already exists")

        # ===== USER (Standard) =====
        user_username = "USER"
        user_password = options.get("user_password")
        if not User.objects.filter(username=user_username).exists():
            if user_password:
                User.objects.create_user(
                    username=user_username,
                    password=user_password,
                    role="USER",
                    full_name="Standard User",
                )
                self.stdout.write(self.style.SUCCESS("✓ Created USER"))
            else:
                self.stdout.write(self.style.WARNING(
                    "⚠️  USER does not exist — skipping (optional)"
                ))
        else:
            self.stdout.write("✓ USER already exists")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        if User.objects.filter(username="ADMIN").exists() and admin_password:
            self.stdout.write(self.style.SUCCESS("  Login credentials:"))
            self.stdout.write(self.style.SUCCESS(f"    ADMIN : {admin_username}"))
            if consultant_password:
                self.stdout.write(self.style.SUCCESS(f"    CONSULTANT : {consultant_username}"))
            if user_password:
                self.stdout.write(self.style.SUCCESS(f"    USER : {user_username}"))
        self.stdout.write(self.style.SUCCESS("=" * 60))