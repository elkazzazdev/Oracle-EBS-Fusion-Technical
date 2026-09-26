"""API URL configuration."""
from django.urls import path
from . import views

urlpatterns = [
    # ===== Setup Wizard =====
    path("setup/status/", views.setup_status, name="setup_status"),
    path("setup/create-admin/", views.setup_create_admin, name="setup_create_admin"),

    # ===== Public =====
    path("health/", views.health, name="health"),
    path("public/settings/", views.public_settings, name="public_settings"),

    # ===== Auth =====
    path("auth/login/", views.login_view, name="login"),
    path("auth/refresh/", views.refresh_token_view, name="refresh"),
    path("auth/me/", views.me_view, name="me"),
    path("auth/preferences/", views.update_my_preferences, name="update_preferences"),

    # ===== Datasets =====
    path("datasets/my/", views.my_datasets, name="my_datasets"),
    path("datasets/all/", views.all_datasets, name="all_datasets"),
    path("datasets/upload/", views.upload_dataset, name="upload_dataset"),
    path("datasets/trash/", views.trash_list, name="trash_list"),
    path("datasets/bulk-delete/", views.bulk_delete, name="bulk_delete"),
    path("datasets/<int:ds_id>/", views.get_dataset, name="get_dataset"),
    path("datasets/<int:ds_id>/update/", views.update_dataset, name="update_dataset"),
    path("datasets/<int:ds_id>/delete/", views.delete_dataset, name="delete_dataset"),
    path("datasets/<int:ds_id>/restore/", views.restore_dataset, name="restore_dataset"),
    path("datasets/<int:ds_id>/permanent/", views.permanent_delete, name="permanent_delete"),

    # ===== Shares =====
    path("datasets/<int:ds_id>/shares/", views.list_shares, name="list_shares"),
    path("datasets/<int:ds_id>/shares/add/", views.add_share, name="add_share"),
    path("datasets/<int:ds_id>/shares/<str:username>/", views.remove_share, name="remove_share"),

    # ===== Access Requests =====
    path("access-requests/", views.list_access_requests, name="list_access_requests"),
    path("access-requests/request/", views.request_access, name="request_access"),
    path("access-requests/approved/", views.list_approved_requests, name="list_approved_requests"),
    path("access-requests/<int:req_id>/resolve/", views.resolve_request, name="resolve_request"),
    path("access-requests/<int:req_id>/revoke/", views.revoke_access, name="revoke_access"),

    # ===== Users =====
    path("users/", views.list_users, name="list_users"),
    path("users/create/", views.create_user, name="create_user"),
    path("users/<int:user_id>/update/", views.update_user, name="update_user"),
    path("users/<int:user_id>/delete/", views.delete_user, name="delete_user"),
    path("users/<str:username>/activity/", views.user_activity, name="user_activity"),
    path("users/<str:username>/stats/", views.user_stats, name="user_stats"),

    # ===== Activity =====
    path("activity/", views.get_activity, name="get_activity"),

    # ===== Settings =====
    path("settings/", views.get_all_settings, name="get_all_settings"),
    path("settings/update/", views.update_settings, name="update_settings"),

    # ===== Notes =====
    path("notes/", views.list_notes, name="list_notes"),
    path("notes/create/", views.create_note, name="create_note"),
    path("notes/<int:note_id>/update/", views.update_note, name="update_note"),
    path("notes/<int:note_id>/delete/", views.delete_note, name="delete_note"),

    # ===== Top Tables =====
    path("top-tables/", views.list_top_tables, name="list_top_tables"),
    path("top-tables/create/", views.create_top_table, name="create_top_table"),
    path("top-tables/auto/", views.top_tables_auto, name="top_tables_auto"),
    path("top-tables/<int:tt_id>/update/", views.update_top_table, name="update_top_table"),
    path("top-tables/<int:tt_id>/delete/", views.delete_top_table, name="delete_top_table"),

    # ===== Search Log =====
    path("search-log/", views.log_search, name="log_search"),

    # ===== API Keys =====
    path("api-keys/", views.list_api_keys, name="list_api_keys"),
    path("api-keys/create/", views.create_api_key, name="create_api_key"),
    path("api-keys/<int:key_id>/delete/", views.delete_api_key, name="delete_api_key"),

    # ===== Backup =====
    path("backup/export/", views.backup_export, name="backup_export"),
    path("backup/import/", views.backup_import, name="backup_import"),

    # ===== Notifications =====
    path("notifications/", views.get_notifications, name="notifications"),
    path("notifications/<int:notif_id>/read/", views.mark_notification_read, name="mark_notification_read"),
    path("notifications/read-all/", views.mark_all_notifications_read, name="mark_all_notifications_read"),
    path("notifications/<int:notif_id>/delete/", views.delete_notification, name="delete_notification"),

    # ===== SQL Library =====
    path("sql-templates/", views.list_sql_templates, name="list_sql_templates"),
    path("sql-templates/create/", views.create_sql_template, name="create_sql_template"),
    path("sql-templates/categories/", views.sql_template_categories, name="sql_template_categories"),
    path("sql-templates/<int:tpl_id>/", views.get_sql_template, name="get_sql_template"),
    path("sql-templates/<int:tpl_id>/update/", views.update_sql_template, name="update_sql_template"),
    path("sql-templates/<int:tpl_id>/delete/", views.delete_sql_template, name="delete_sql_template"),

    # ===== Catalogue =====
    path("catalogue/", views.catalogue_view, name="catalogue"),

    # ===== Local SQL Query =====
    path("query/", views.run_sql_query, name="run_sql_query"),

    # ===== EBS Connector =====
    path("db-servers/", views.list_db_servers, name="list_db_servers"),
    path("db-servers/all/", views.list_all_db_servers, name="list_all_db_servers"),
    path("db-servers/create/", views.create_db_server, name="create_db_server"),
    path("db-servers/<int:server_id>/update/", views.update_db_server, name="update_db_server"),
    path("db-servers/<int:server_id>/delete/", views.delete_db_server, name="delete_db_server"),
    path("db-servers/test/", views.test_db_server, name="test_db_server"),

    path("ebs/connect/", views.ebs_connect, name="ebs_connect"),
    path("ebs/disconnect/", views.ebs_disconnect, name="ebs_disconnect"),
    path("ebs/sessions/", views.ebs_sessions_list, name="ebs_sessions_list"),
    path("ebs/session/extend/", views.ebs_session_extend, name="ebs_session_extend"),
    path("ebs/query/", views.ebs_run_query, name="ebs_run_query"),
    path("ebs/query-logs/", views.ebs_query_logs, name="ebs_query_logs"),

    # ===== Editor Sessions =====
    path("editor-sessions/", views.list_editor_sessions, name="list_editor_sessions"),
    path("editor-sessions/create/", views.create_editor_session, name="create_editor_session"),
    path("editor-sessions/<str:session_key>/update/", views.update_editor_session, name="update_editor_session"),
    path("editor-sessions/<str:session_key>/close/", views.close_editor_session, name="close_editor_session"),
    path("editor-sessions/clear/", views.clear_my_sessions, name="clear_my_sessions"),
]