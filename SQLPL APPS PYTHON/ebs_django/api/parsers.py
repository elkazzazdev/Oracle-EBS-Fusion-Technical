"""
File parsers — converts any supported format into (rows, columns).
Supports: JSON, CSV, TSV, SQL, XLSX, XLS, YAML, XML, HTML, PDF, TXT, ZIP
"""
import io
import csv
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

# Optional libs
try:
    import openpyxl  # noqa
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    import xlrd  # noqa
    HAS_XLRD = True
except ImportError:
    HAS_XLRD = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


# ==================== HELPERS ====================
def normalize_key(k):
    """Sanitize key to SQL-friendly uppercase."""
    return re.sub(r"[^A-Z0-9_]", "_", str(k).upper()).strip("_") or "COL"


def infer_type(v):
    if v is None:
        return "VARCHAR2"
    if isinstance(v, bool):
        return "BOOLEAN"
    if isinstance(v, int):
        return "NUMBER"
    if isinstance(v, float):
        return "NUMBER"
    return "VARCHAR2"


# ==================== JSON ====================
def parse_json_content(content):
    """
    Supports:
    - Oracle-style: {results: [{columns: [...], items: [...]}]}
    - Plain array: [{...}, {...}]
    - Object with items: {items: [...]}
    """
    parsed = json.loads(content)
    rows, cols = [], []

    if isinstance(parsed, dict) and "results" in parsed and isinstance(parsed["results"], list):
        for r in parsed["results"]:
            col_map = {}
            for col in r.get("columns", []):
                n = normalize_key(col.get("name", "COL"))
                col_map[n.lower()] = n
                cols.append({"name": n, "type": col.get("type", "VARCHAR2")})
            for item in r.get("items", []):
                rows.append({col_map.get(k.lower(), normalize_key(k)): v for k, v in item.items()})
    elif isinstance(parsed, list):
        rows = [{normalize_key(k): v for k, v in row.items()} for row in parsed if isinstance(row, dict)]
        if rows:
            cols = [{"name": k, "type": infer_type(v)} for k, v in rows[0].items()]
    elif isinstance(parsed, dict) and "items" in parsed:
        rows = [{normalize_key(k): v for k, v in row.items()} for row in parsed["items"]]
        if rows:
            cols = [{"name": k, "type": infer_type(v)} for k, v in rows[0].items()]
    else:
        raise ValueError("Unsupported JSON structure")
    return rows, cols


# ==================== CSV / TSV ====================
def parse_csv_content(content):
    from io import StringIO
    sample = content[:5000]
    try:
        dialect = csv.Sniffer().sniff(sample)
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ","
    reader = csv.DictReader(StringIO(content), delimiter=delimiter)
    rows = []
    for r in reader:
        rows.append({normalize_key(k): v for k, v in r.items() if k is not None})
    cols = [{"name": k, "type": infer_type(v)} for k, v in (rows[0] if rows else {}).items()]
    return rows, cols


# ==================== SQL (INSERT INTO) ====================
def parse_sql_content(content):
    """Parse INSERT INTO ... VALUES statements."""
    rows, cols = [], []
    pattern = re.compile(
        r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)",
        re.IGNORECASE | re.DOTALL
    )
    for m in pattern.finditer(content):
        col_names = [normalize_key(c.strip().strip('"\'')) for c in m.group(2).split(",")]
        raw_vals = re.split(r",(?=(?:[^']*'[^']*')*[^']*$)", m.group(3))
        vals = []
        for v in raw_vals:
            v = v.strip()
            if v.startswith("'") and v.endswith("'"):
                v = v[1:-1]
            elif v.upper() == "NULL":
                v = None
            else:
                try:
                    v = int(v)
                except ValueError:
                    try:
                        v = float(v)
                    except ValueError:
                        pass
            vals.append(v)
        if len(col_names) == len(vals):
            rows.append(dict(zip(col_names, vals)))
            if not cols:
                cols = [{"name": c, "type": infer_type(v)} for c, v in zip(col_names, vals)]
    if not rows:
        raise ValueError(
            "No INSERT statements found in SQL. "
            "If this is a SELECT/report query, use SQL Library instead."
        )
    return rows, cols


# ==================== EXCEL ====================
def parse_excel_content(content_bytes, ext):
    rows, cols = [], []
    bio = io.BytesIO(content_bytes)

    if ext in (".xlsx", ".xlsm") and HAS_OPENPYXL:
        wb = openpyxl.load_workbook(bio, read_only=True, data_only=True)
        ws = wb.active
        iterator = ws.iter_rows(values_only=True)
        try:
            headers = next(iterator)
        except StopIteration:
            return [], []
        headers = [normalize_key(h) if h is not None else f"COL_{i}" for i, h in enumerate(headers)]
        for row in iterator:
            if row and any(v is not None for v in row):
                rows.append({headers[i]: (row[i] if i < len(row) else None) for i in range(len(headers))})
        wb.close()
    elif ext == ".xls" and HAS_XLRD:
        wb = xlrd.open_workbook(file_contents=content_bytes)
        ws = wb.sheet_by_index(0)
        if ws.nrows < 1:
            return [], []
        headers = [normalize_key(ws.cell_value(0, i)) for i in range(ws.ncols)]
        for r in range(1, ws.nrows):
            rows.append({headers[i]: ws.cell_value(r, i) for i in range(ws.ncols)})
    else:
        raise ValueError(
            "Excel support requires openpyxl (xlsx) or xlrd (xls). "
            "Please convert to CSV if unavailable."
        )
    if rows:
        cols = [{"name": k, "type": infer_type(v)} for k, v in rows[0].items()]
    return rows, cols


# ==================== YAML ====================
def parse_yaml_content(content):
    if not HAS_YAML:
        raise ValueError("YAML support requires pyyaml.")
    parsed = yaml.safe_load(content)
    if isinstance(parsed, list):
        return parse_json_content(json.dumps(parsed))
    if isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list) and v:
                return parse_json_content(json.dumps(v))
        return parse_json_content(json.dumps([parsed]))
    raise ValueError("Unsupported YAML structure")


# ==================== XML ====================
def parse_xml_content(content):
    """
    Smart XML parser:
    - Finds the deepest repeated element
    - Converts its children to columns
    - Flattens attributes and text
    """
    root = ET.fromstring(content)

    # Try to find the "row" container (repeated children of root or any element)
    def find_repeated_children(element):
        """Find deepest element with multiple same-tag children."""
        best = None
        best_count = 0
        for child in element:
            counts = {}
            for sub in child:
                counts[sub.tag] = counts.get(sub.tag, 0) + 1
            if counts:
                most_common_tag, most_common_count = max(counts.items(), key=lambda x: x[1])
                if most_common_count >= 2 and most_common_count > best_count:
                    best = (child, most_common_tag)
                    best_count = most_common_count
        return best

    target = root
    row_tag = None
    found = find_repeated_children(root)
    if found:
        target, row_tag = found

    rows = []
    for child in target:
        if row_tag and child.tag != row_tag:
            continue
        row = {}
        # Attributes as columns
        for attr_k, attr_v in child.attrib.items():
            row[normalize_key(f"@{attr_k}")] = attr_v
        # Children elements
        for sub in child:
            if len(sub) == 0:
                row[normalize_key(sub.tag)] = sub.text
        # Direct text
        if not row and child.text and child.text.strip():
            row[normalize_key(child.tag)] = child.text.strip()
        if row:
            rows.append(row)

    # Fallback: element itself as single row
    if not rows:
        row = {}
        for attr_k, attr_v in root.attrib.items():
            row[normalize_key(f"@{attr_k}")] = attr_v
        for sub in root.iter():
            if sub is not root and len(sub) == 0:
                row[normalize_key(sub.tag)] = sub.text
        if row:
            rows = [row]

    if not rows:
        raise ValueError("No rows extracted from XML")

    cols = [{"name": k, "type": infer_type(v)} for k, v in rows[0].items()]
    return rows, cols


# ==================== HTML ====================
def parse_html_content(content):
    rows = []
    if HAS_BS4:
        soup = BeautifulSoup(content, "lxml")
        for table in soup.find_all("table"):
            headers = [normalize_key(th.get_text(strip=True)) for th in table.find_all("th")]
            if not headers:
                first_tr = table.find("tr")
                if first_tr:
                    headers = [normalize_key(td.get_text(strip=True)) for td in first_tr.find_all("td")]
            for tr in table.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
    else:
        # Regex fallback
        tables = re.findall(r"<table[^>]*>(.*?)</table>", content, re.DOTALL | re.IGNORECASE)
        for t in tables:
            headers = re.findall(r"<th[^>]*>(.*?)</th>", t, re.DOTALL | re.IGNORECASE)
            headers = [normalize_key(re.sub(r"<[^>]+>", "", h).strip()) for h in headers]
            if not headers:
                continue
            trs = re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.DOTALL | re.IGNORECASE)
            for tr in trs[1:]:
                cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.DOTALL | re.IGNORECASE)
                cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
                if len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
    if not rows:
        raise ValueError("No tables found in HTML")
    cols = [{"name": k, "type": infer_type(v)} for k, v in rows[0].items()]
    return rows, cols


# ==================== PDF ====================
def parse_pdf_content(content_bytes):
    if not HAS_PDF:
        raise ValueError("PDF support requires pdfplumber.")
    rows = []
    bio = io.BytesIO(content_bytes)
    with pdfplumber.open(bio) as pdf:
        for page in pdf.pages:
            for table in (page.extract_tables() or []):
                if not table or len(table) < 2:
                    continue
                header = [normalize_key(h) if h else f"COL_{i}" for i, h in enumerate(table[0])]
                for r in table[1:]:
                    if any(r):
                        rows.append({header[i]: (r[i] if i < len(r) else None) for i in range(len(header))})
    if not rows:
        raise ValueError("No tables found in PDF")
    cols = [{"name": k, "type": infer_type(v)} for k, v in rows[0].items()]
    return rows, cols


# ==================== TXT ====================
def parse_txt_content(content):
    try:
        return parse_csv_content(content)
    except Exception:
        pass
    lines = content.splitlines()
    if not lines:
        raise ValueError("Empty TXT file")
    for sep in ("\t", "|", ";", ","):
        if sep in lines[0]:
            headers = [normalize_key(h.strip()) for h in lines[0].split(sep)]
            rows = []
            for ln in lines[1:]:
                if not ln.strip():
                    continue
                vals = [v.strip() for v in ln.split(sep)]
                if len(vals) == len(headers):
                    rows.append(dict(zip(headers, vals)))
            if rows:
                cols = [{"name": k, "type": infer_type(v)} for k, v in rows[0].items()]
                return rows, cols
    rows = [{"LINE": ln} for ln in lines]
    return rows, [{"name": "LINE", "type": "VARCHAR2"}]


# ==================== MASTER DISPATCH ====================
SUPPORTED_EXTENSIONS = {
    ".json", ".csv", ".tsv", ".sql",
    ".xlsx", ".xlsm", ".xls",
    ".yaml", ".yml", ".xml",
    ".html", ".htm", ".pdf", ".txt",
}


def parse_any_file(filename, content_bytes):
    """Parse any file by extension. Returns (rows, cols)."""
    ext = Path(filename).suffix.lower()

    if ext == ".json":
        return parse_json_content(content_bytes.decode("utf-8", errors="ignore"))
    if ext in (".csv", ".tsv"):
        return parse_csv_content(content_bytes.decode("utf-8", errors="ignore"))
    if ext == ".sql":
        return parse_sql_content(content_bytes.decode("utf-8", errors="ignore"))
    if ext in (".xlsx", ".xlsm", ".xls"):
        return parse_excel_content(content_bytes, ext)
    if ext in (".yaml", ".yml"):
        return parse_yaml_content(content_bytes.decode("utf-8", errors="ignore"))
    if ext == ".xml":
        return parse_xml_content(content_bytes.decode("utf-8", errors="ignore"))
    if ext in (".html", ".htm"):
        return parse_html_content(content_bytes.decode("utf-8", errors="ignore"))
    if ext == ".pdf":
        return parse_pdf_content(content_bytes)
    if ext == ".txt":
        return parse_txt_content(content_bytes.decode("utf-8", errors="ignore"))

    raise ValueError(f"Unsupported file format: {ext}")


def merge_rows(rows_list):
    """Merge multiple (rows, cols) into one unified dataset (union of columns)."""
    all_rows = []
    all_keys = []
    seen = set()

    for rows, cols in rows_list:
        for c in cols:
            if c["name"] not in seen:
                seen.add(c["name"])
                all_keys.append(c["name"])

    for rows, _ in rows_list:
        for r in rows:
            all_rows.append({k: r.get(k) for k in all_keys})

    all_cols = [{"name": k, "type": "VARCHAR2"} for k in all_keys]
    for col in all_cols:
        for r in all_rows:
            v = r.get(col["name"])
            if v is not None and v != "":
                col["type"] = infer_type(v)
                break

    return all_rows, all_cols


def process_zip(file_bytes):
    """Extract + parse + merge all supported files inside a ZIP."""
    parsed_list = []
    errors = []
    with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
        members = [
            m for m in zf.namelist()
            if not m.startswith("__MACOSX")
            and not m.endswith("/")
            and not Path(m).name.startswith(".")
            and Path(m).suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        if not members:
            raise ValueError("No supported files inside ZIP")
        for member in members:
            try:
                content = zf.read(member)
                rows, cols = parse_any_file(member, content)
                if rows:
                    parsed_list.append((rows, cols))
                else:
                    errors.append(f"{member}: no rows")
            except Exception as e:
                errors.append(f"{member}: {e}")

    if not parsed_list:
        raise ValueError(f"No valid files parsed from ZIP. Errors: {errors}")

    rows, cols = merge_rows(parsed_list)
    return rows, cols, errors