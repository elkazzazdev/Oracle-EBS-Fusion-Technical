from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    verbose_name = 'EBS R12 Explorer'

    def ready(self):
        import api.signals  # noqa
        try:
            from api.ebs_connector import start_cleanup_thread
            start_cleanup_thread()
        except Exception as e:
            print(f"[Startup] Could not start EBS cleanup: {e}")