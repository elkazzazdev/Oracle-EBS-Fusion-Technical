"""Utility functions."""
import gzip
import json
from pathlib import Path
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """Return clean JSON errors."""
    response = exception_handler(exc, context)
    if response is not None:
        data = response.data
        if isinstance(data, dict) and "detail" in data:
            return Response({"error": str(data["detail"])}, status=response.status_code)
        if isinstance(data, dict):
            # Flatten field errors
            for key in list(data.keys()):
                if isinstance(data[key], list) and data[key]:
                    data[key] = data[key][0]
            return Response({"error": str(data)}, status=response.status_code)
        return Response({"error": str(data)}, status=response.status_code)
    return Response(
        {"error": f"Internal server error: {str(exc)}"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def log_activity(username, action, details="", ip=None):
    """Insert into ActivityLog."""
    from .models import ActivityLog
    try:
        ActivityLog.objects.create(
            username=username or "SYSTEM",
            action=action[:64],
            details=str(details)[:2000],
            ip=ip,
        )
    except Exception:
        pass


def client_ip(request):
    """Extract client IP from request."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def sanitize_table_name(name):
    """Convert dataset name to a valid SQLite identifier."""
    import re
    s = re.sub(r"[^A-Za-z0-9_]", "_", str(name))
    if not s or s[0].isdigit():
        s = "T_" + s
    return s


def load_datasets_to_sqlite(dataset_ids):
    """
    Load datasets from disk into an in-memory SQLite DB.
    Returns: (conn, {sanitized_table_name: original_dataset_name})
    """
    import sqlite3
    from .models import Dataset

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    table_map = {}

    for ds_id in dataset_ids:
        try:
            ds = Dataset.objects.get(id=ds_id, deleted=False)
        except Dataset.DoesNotExist:
            continue

        data = ds.load_data()
        cols_meta = ds.get_columns()
        if not data:
            continue

        col_names = [c["name"] for c in cols_meta] if cols_meta else list(data[0].keys())
        if not col_names:
            continue

        table_name = sanitize_table_name(ds.name)
        base_name = table_name
        suffix = 1
        while table_name in table_map:
            table_name = f"{base_name}_{suffix}"
            suffix += 1
        table_map[table_name] = ds.name

        col_defs = ", ".join([f'"{c}" TEXT' for c in col_names])
        conn.execute(f'CREATE TABLE "{table_name}" ({col_defs})')

        placeholders = ", ".join(["?"] * len(col_names))
        insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'

        rows_to_insert = []
        for row in data:
            vals = []
            for c in col_names:
                v = row.get(c)
                if v is None:
                    vals.append(None)
                elif isinstance(v, (int, float, str)):
                    vals.append(v)
                else:
                    vals.append(json.dumps(v))
            rows_to_insert.append(vals)

        conn.executemany(insert_sql, rows_to_insert)
        conn.commit()

    return conn, table_map