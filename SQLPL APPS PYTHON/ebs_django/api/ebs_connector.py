"""
EBS Connector — Secure Oracle EBS Database Connection Layer
============================================================
Security principles:
1. Credentials are NEVER stored in the database.
2. Credentials are held in memory only (session store).
3. Credentials auto-expire after EBS_SESSION_TTL seconds.
4. All connections are ephemeral — closed after each query.
5. Query logs never contain credentials.
6. All queries are logged for audit.
7. SELECT-only (DDL/DML blocked).

Multi-Session support:
- Each user can have MULTIPLE concurrent sessions.
- Sessions are keyed by (user_id, server_id).
- Sessions persist across page reloads (in memory).
- Auto-cleanup thread runs every 60 seconds.

Oracle Mode:
- Uses Thick Mode (Oracle Instant Client) when available.
- Falls back to Thin Mode if not configured.
"""
import os
import re
import time
import hashlib
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from django.conf import settings

# ==================== ORACLE LIBRARY + THICK MODE ====================
try:
    import oracledb
    HAS_ORACLEDB = True

    _instant_client_dir = os.environ.get(
        "ORACLE_CLIENT_DIR",
        r"C:\Oracle\instantclient_23_26"
    )

    _thick_mode_enabled = False

    if os.path.isdir(_instant_client_dir):
        try:
            oracledb.init_oracle_client(lib_dir=_instant_client_dir)
            _thick_mode_enabled = True
            print("=" * 60)
            print(f"[EBS] ✔ Thick Mode ENABLED")
            print(f"[EBS]   Instant Client: {_instant_client_dir}")
            print("=" * 60)
        except Exception as _e:
            err = str(_e)
            if "already initialized" in err.lower():
                _thick_mode_enabled = True
                print(f"[EBS] ✔ Thick Mode already active")
            else:
                print("=" * 60)
                print(f"[EBS] ⚠ Thick Mode FAILED: {_e}")
                print(f"[EBS] → Falling back to Thin Mode")
                print("=" * 60)
    else:
        print("=" * 60)
        print(f"[EBS] ⚠ Instant Client not found at: {_instant_client_dir}")
        print(f"[EBS] → Using Thin Mode (may fail on Oracle 10G password verifier)")
        print("=" * 60)

except ImportError:
    HAS_ORACLEDB = False
    _thick_mode_enabled = False
    print("[EBS] ✘ oracledb library not installed")


# ==================== SESSION STORE (Multi-Session) ====================
class SessionStore:
    """
    Thread-safe in-memory store for EBS DB credentials.
    Supports MULTIPLE sessions per user.
    """
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _make_key(self, user_id: int, server_id: int) -> str:
        return f"u{user_id}_s{server_id}"

    def add_session(self, user_id: int, server_id: int, username: str,
                    password: str, name: str = None,
                    session_key: str = None) -> str:
        key = session_key or self._make_key(user_id, server_id)
        with self._lock:
            self._store[key] = {
                "user_id": user_id,
                "server_id": server_id,
                "username": username,
                "password": password,
                "connected_at": time.time(),
                "last_used": time.time(),
                "name": name or f"Session {server_id}",
            }
        return key

    def get_session(self, session_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._store.get(session_key)
            if not data:
                return None
            ttl = getattr(settings, "EBS_SESSION_TTL", 1200)
            if time.time() - data["last_used"] > ttl:
                self._purge_key(session_key)
                return None
            data["last_used"] = time.time()
            return data

    def get_user_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        with self._lock:
            ttl = getattr(settings, "EBS_SESSION_TTL", 1200)
            now = time.time()
            sessions = []
            for key, data in list(self._store.items()):
                if data["user_id"] != user_id:
                    continue
                if now - data["last_used"] > ttl:
                    self._purge_key(key)
                    continue
                sessions.append({
                    "session_key": key,
                    "server_id": data["server_id"],
                    "username": data["username"],
                    "name": data["name"],
                    "connected_at": data["connected_at"],
                    "last_used": data["last_used"],
                })
            return sessions

    def count_user_sessions(self, user_id: int) -> int:
        return len(self.get_user_sessions(user_id))

    def touch(self, session_key: str):
        with self._lock:
            if session_key in self._store:
                self._store[session_key]["last_used"] = time.time()

    def remove_session(self, session_key: str):
        with self._lock:
            self._purge_key(session_key)

    def clear_user(self, user_id: int):
        with self._lock:
            for key in list(self._store.keys()):
                if self._store[key]["user_id"] == user_id:
                    self._purge_key(key)

    def _purge_key(self, key: str):
        data = self._store.get(key)
        if not data:
            return
        try:
            pw = data.get("password", "")
            data["password"] = "\x00" * len(pw)
        except Exception:
            pass
        del self._store[key]

    def purge_expired(self) -> int:
        with self._lock:
            now = time.time()
            ttl = getattr(settings, "EBS_SESSION_TTL", 1200)
            expired = [k for k, v in self._store.items() if now - v["last_used"] > ttl]
            for k in expired:
                self._purge_key(k)
            return len(expired)

    def active_count(self) -> int:
        with self._lock:
            return len(self._store)


session_store = SessionStore()


# ==================== SQL SECURITY ====================
ALLOWED_SQL_STARTS = ("SELECT", "WITH")

FORBIDDEN_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
    "TRUNCATE", "MERGE", "GRANT", "REVOKE", "COMMIT", "ROLLBACK",
    "EXECUTE", "EXEC", "CALL", "BEGIN", "DECLARE",
    "DBMS_", "UTL_", "EXECUTE IMMEDIATE",
]


def validate_sql(sql: str) -> Tuple[bool, str]:
    if not sql or not sql.strip():
        return False, "SQL is empty"

    sql_clean = re.sub(r"--.*?$|/\*.*?\*/", " ", sql,
                       flags=re.MULTILINE | re.DOTALL).strip()

    if not sql_clean:
        return False, "SQL is empty after removing comments"

    first_word = sql_clean.split()[0].upper()
    if first_word not in ALLOWED_SQL_STARTS:
        return False, f"Only SELECT and WITH queries are allowed (got '{first_word}')"

    upper_sql = sql_clean.upper()
    for kw in FORBIDDEN_KEYWORDS:
        pattern = rf"\b{re.escape(kw)}\b"
        if re.search(pattern, upper_sql):
            return False, f"Forbidden keyword: '{kw}'"

    if len(sql) > 100_000:
        return False, "SQL query is too long (max 100,000 chars)"

    return True, ""


def clean_sql(sql: str) -> str:
    """Remove trailing semicolons / slashes."""
    sql = sql.strip()
    while sql.endswith(";") or sql.endswith("/"):
        sql = sql[:-1].rstrip()
    return sql


def hash_sql(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


# ==================== CONNECTION ====================
def get_oracle_connection(host: str, port: int, service_name: str = "",
                          sid: str = "", username: str = "", password: str = "",
                          timeout: int = 30):
    """Create an Oracle DB connection (ephemeral)."""
    if not HAS_ORACLEDB:
        raise Exception("oracledb library is not installed. Run: pip install oracledb")

    if not host or not username or not password:
        raise Exception("Missing required connection parameters")

    if service_name:
        dsn = oracledb.makedsn(host, port, service_name=service_name)
    elif sid:
        dsn = oracledb.makedsn(host, port, sid=sid)
    else:
        raise Exception("Either service_name or sid is required")

    try:
        conn = oracledb.connect(
            user=username,
            password=password,
            dsn=dsn,
            tcp_connect_timeout=timeout,
        )
        return conn
    except oracledb.DatabaseError as e:
        error_obj = e.args[0] if e.args else None
        msg = str(error_obj.message) if error_obj else str(e)
        raise Exception(f"Connection failed: {msg}")
    except Exception as e:
        raise Exception(f"Connection failed: {type(e).__name__}")


def execute_query(
    host: str,
    port: int,
    service_name: str,
    sid: str,
    username: str,
    password: str,
    sql: str,
    max_rows: int = 50000,
    timeout: int = 300,
) -> Dict[str, Any]:
    """Execute a SELECT query on Oracle EBS."""
    start = time.time()

    sql = clean_sql(sql)

    is_valid, err = validate_sql(sql)
    if not is_valid:
        raise Exception(err)

    conn = None
    cursor = None
    try:
        conn = get_oracle_connection(
            host=host, port=port,
            service_name=service_name, sid=sid,
            username=username, password=password,
            timeout=30,
        )

        cursor = conn.cursor()

        try:
            conn.call_timeout = timeout * 1000
        except Exception:
            pass

        cursor.execute(sql)
        columns = [d[0] for d in cursor.description] if cursor.description else []

        rows = []
        truncated = False
        for i, row in enumerate(cursor):
            if i >= max_rows:
                truncated = True
                break
            rows.append(dict(zip(columns, row)))

        duration_ms = int((time.time() - start) * 1000)

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "duration_ms": duration_ms,
            "truncated": truncated,
        }
    except Exception as e:
        msg = str(e)
        if password:
            msg = msg.replace(password, "***")
        if username:
            msg = msg.replace(username, "***")
        raise Exception(msg)
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass


# ==================== AUDIT LOGGING ====================
def log_ebs_query(
    username: str,
    server,
    sql: str,
    rows_returned: int,
    duration_ms: int,
    success: bool,
    error_message: str = "",
    ip: str = None,
):
    from .models import EbsQueryLog
    try:
        sql_preview = sql[:300].replace("\n", " ").replace("\r", " ")
        EbsQueryLog.objects.create(
            username=username,
            server=server,
            sql_hash=hash_sql(sql),
            sql_preview=sql_preview,
            rows_returned=rows_returned,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message[:500],
            ip=ip,
        )
    except Exception:
        pass


# ==================== PERIODIC CLEANUP ====================
_cleanup_thread = None
_cleanup_stop = threading.Event()


def start_cleanup_thread():
    global _cleanup_thread
    if _cleanup_thread and _cleanup_thread.is_alive():
        return

    def worker():
        while not _cleanup_stop.is_set():
            try:
                count = session_store.purge_expired()
                if count > 0:
                    print(f"[EBS Cleanup] Purged {count} expired session(s)")
            except Exception as e:
                print(f"[EBS Cleanup] Error: {e}")
            _cleanup_stop.wait(60)

    _cleanup_thread = threading.Thread(target=worker, daemon=True, name="ebs-cleanup")
    _cleanup_thread.start()


def stop_cleanup_thread():
    _cleanup_stop.set()
    if _cleanup_thread:
        _cleanup_thread.join(timeout=2)