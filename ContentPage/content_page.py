"""
Content Page – backend router
  GET  /api/contentpage/config   -> display part of the config (no connection data)
  POST /api/contentpage/run      -> runs the procedure, returns only the configured fields

Config file: C:\\Apps\\dsk-api\\config\\content_page.json
It is read on every request, so edits apply without recycling the app pool.
"""
import datetime
import decimal
import json
import re
from pathlib import Path

import pyodbc
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/contentpage", tags=["Content Page"])

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "content_page.json"

# procedure name cannot be a SQL parameter, so it is validated instead
PROC_NAME_RE = re.compile(r"^(\[?[A-Za-z_][A-Za-z0-9_]*\]?\.){0,2}\[?[A-Za-z_][A-Za-z0-9_]*\]?$")


# ---------------------------------------------------------------- helpers
def ok(data, status=200):
    return JSONResponse({"data": data, "error": None}, status_code=status)


def fail(message, status=500):
    return JSONResponse({"data": None, "error": message}, status_code=status)


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8-sig") as f:   # -sig: tolerates a BOM from Notepad
        return json.load(f)


def to_json_value(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
        return v.isoformat(sep=" ") if isinstance(v, datetime.datetime) else v.isoformat()
    if isinstance(v, (bytes, bytearray)):
        return v.hex()
    return str(v)


def connect(conn_cfg: dict):
    conn_str = (
        f"DSN={conn_cfg['dsn']};"
        f"UID={conn_cfg['uid']};"
        f"PWD={conn_cfg['pwd']};"
    )
    timeout = int(conn_cfg.get("loginTimeout", 15))
    cn = pyodbc.connect(conn_str, timeout=timeout, autocommit=True)
    cn.timeout = int(conn_cfg.get("queryTimeout", 60))       # seconds per query

    # Unicode: fetch ALL text (VARCHAR too) as UTF-16 from the driver.
    # Without this, VARCHAR values pass through the server's Windows ANSI code page
    # and any character outside it (Hebrew on an English server, Ø, ±, µ, ≤ ...) becomes "?".
    cn.setdecoding(pyodbc.SQL_CHAR, encoding="utf-16le", ctype=pyodbc.SQL_WCHAR)
    cn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
    cn.setencoding(encoding="utf-16le")                      # parameters sent as NVARCHAR
    return cn


# ---------------------------------------------------------------- endpoints
@router.get("/config")
def get_config():
    try:
        cfg = load_config()
    except FileNotFoundError:
        return fail(f"Config file not found: {CONFIG_PATH}")
    except json.JSONDecodeError as e:
        return fail(f"Config file is not valid JSON: {e}")

    cfg.pop("connection", None)          # never send credentials to the browser
    return ok(cfg)


class RunRequest(BaseModel):
    mainpart: str = Field(..., min_length=1, max_length=100)
    mainserial: str | None = Field(None, max_length=100)
    dbg: bool = False          # True -> return ALL columns of the procedure, ignore the config


@router.post("/run")
def run(req: RunRequest):
    try:
        cfg = load_config()
    except Exception as e:
        return fail(f"Cannot read config: {e}")

    conn_cfg = cfg.get("connection", {})
    proc = conn_cfg.get("procedure", "")
    if not PROC_NAME_RE.match(proc):
        return fail(f"Invalid procedure name in config: {proc!r}")

    wanted = [f["field"] for f in cfg.get("fields", []) if f.get("field")]
    mainpart = req.mainpart.strip()
    mainserial = (req.mainserial or "").strip() or None

    sql = f"SET NOCOUNT ON; EXEC {proc} @mainpart = ?, @mainserial = ?;"

    try:
        with connect(conn_cfg) as cn:
            cur = cn.cursor()
            cur.execute(sql, mainpart, mainserial)

            # skip anything before the first real result set
            while cur.description is None:
                if not cur.nextset():
                    return ok({"rows": [], "missingFields": wanted})

            sql_cols = [d[0] for d in cur.description]

            if req.dbg:
                # debug: every column, original SQL names, SQL order
                rows = [{c: to_json_value(v) for c, v in zip(sql_cols, r)} for r in cur.fetchall()]
                print(f"[contentpage] DEBUG {proc} mainpart={mainpart!r} rows={len(rows)}", flush=True)
                return ok({"rows": rows, "columns": sql_cols, "missingFields": []})

            index = {name.lower(): i for i, name in enumerate(sql_cols)}
            present = [f for f in wanted if f.lower() in index]
            missing = [f for f in wanted if f.lower() not in index]

            rows = []
            for r in cur.fetchall():
                rows.append({f: to_json_value(r[index[f.lower()]]) for f in present})

    except pyodbc.Error as e:
        # message only (no connection string) is returned to the page
        msg = str(e.args[1]) if len(e.args) > 1 else str(e)
        print(f"[contentpage] SQL error: {msg}", flush=True)
        return fail(f"SQL error: {msg}")

    print(f"[contentpage] {proc} mainpart={mainpart!r} mainserial={mainserial!r} rows={len(rows)}", flush=True)
    return ok({"rows": rows, "missingFields": missing})
