# Content Page (דף תוכן)

A module of the **Data Swiss Knife** portal (IIS + Python FastAPI, air-gapped Windows server).

The user enters **Main Part** and **Main Serial** and clicks **Run**. The backend executes
`dbo.usp_GetAbPartTree` and the page shows the result as a table. A JSON configuration file
controls the table: which fields appear, their headers, their order, merged columns and
expandable hierarchies. The table can be filtered, printed, saved as PDF and downloaded to Excel.

---

## 1. Architecture

```
Browser ──HTTP :80, Windows SSO──► IIS
                                    ├── /ContentPage/          static page   (C:\inetpub\wwwroot\ContentPage)
                                    └── /api/contentpage/*  ─► Python FastAPI (C:\Apps\dsk-api)
                                                                   └── pyodbc, System DSN DSK_SQL ─► SQL Server
```

- IIS serves the page. Python returns JSON only.
- The page calls the backend with relative URLs, so there is no CORS and no host name in the code.
- The configuration file lives **outside `wwwroot`**. The browser receives it without the
  `connection` section, so the SQL password never reaches it.
- Nothing is loaded from the internet. The Excel file is built in the browser without a library.

---

## 2. Repository layout and deployment

| Repository path | Server location |
|---|---|
| `wwwroot/ContentPage/ContentPage.html` | `C:\inetpub\wwwroot\ContentPage\ContentPage.html` |
| `wwwroot/ContentPage/web.config` | `C:\inetpub\wwwroot\ContentPage\web.config` (default document) |
| `dsk-api/routers/content_page.py` | `C:\Apps\dsk-api\routers\content_page.py` |
| `dsk-api/routers/__init__.py` | `C:\Apps\dsk-api\routers\__init__.py` (empty; **do not overwrite an existing one**) |
| `dsk-api/main.py` | `C:\Apps\dsk-api\main.py` (see note) |
| `dsk-api/config/content_page.example.json` | copy to `C:\Apps\dsk-api\config\content_page.json` and set the real password |

**`main.py` note:** if the server's `main.py` already has other code, don't replace it. Add these two lines:

```python
from routers import content_page
app.include_router(content_page.router)
```

**After deploying:**

| Changed file | Action |
|---|---|
| `ContentPage.html` | Refresh the browser with `Ctrl+F5` |
| `content_page.json` | Refresh the page. The file is read on every request. |
| Any `.py` file | **Recycle** the `dsk-api` application pool in IIS |

**URL:** `http://<server>/ContentPage/`

The real `content_page.json` is listed in `.gitignore` and must never be committed.

---

## 3. Configuration – `content_page.json`

```json
{
  "title": "דף תוכן",
  "logo": "/IMG/company_logo.png",

  "connection": {
    "dsn": "DSK_SQL",
    "uid": "dsk_reader",
    "pwd": "CHANGE_ME",
    "procedure": "dbo.usp_GetAbPartTree",
    "queryTimeout": 60
  },

  "combineDelimiter": " | ",

  "fields": [
    { "field": "Inspection_Nbr", "alias": "דוח בחינה", "fieldIndex": 1 },
    { "field": "Clean_Lot",      "alias": "Serial",    "fieldIndex": 5, "group": "Serial", "groupIndex": 1 },
    { "field": "Document",                                              "group": "Serial", "groupIndex": 2 },
    { "field": "Heter1",         "alias": "התרים",     "fieldIndex": 6 },
    { "field": "Heter2",         "alias": "התרים" }
  ]
}
```

Save the file as **UTF-8**, because it contains Hebrew.

### Top-level keys

| Key | Description |
|---|---|
| `title` | Main title: page header, browser tab and the header of every printed page |
| `logo` | Logo path, shown top right on screen and on every printed page |
| `connection.dsn` | System ODBC DSN (64-bit) |
| `connection.uid` / `pwd` | SQL login |
| `connection.procedure` | Procedure to run. It receives `@mainpart` and `@mainserial`. |
| `connection.queryTimeout` | Query timeout in seconds (default 60) |
| `connection.loginTimeout` | Connection timeout in seconds (optional, default 15) |
| `combineDelimiter` | Separator used when several fields are merged into one column |
| `fields` | The fields to display. **Only listed fields are shown.** |

### Field keys

| Key | Required | Description |
|---|---|---|
| `field` | yes | Column name exactly as the procedure returns it (matched case-insensitively) |
| `alias` | no | Column header. If empty, the SQL field name is used. |
| `fieldIndex` | yes* | Display order. *Ignored for hierarchy levels above 1. |
| `group` | no | Hierarchy name |
| `groupIndex` | no | Level inside the hierarchy: 1 = top, 2 opens under 1, and so on |

### Rules

**Column order**
- Columns are sorted by `fieldIndex`.
- A field without `fieldIndex` goes after the indexed fields, in config order.
- A hierarchy's deeper levels are placed directly after its level 1, in `groupIndex` order.

**Merged columns**
- Fields with the same `alias` (outside a group) become one column.
- That column takes the position of the lowest `fieldIndex` among them.
- Values are joined with `combineDelimiter`, and empty values are skipped.

**Hierarchies (groups)**
- Every `group` is an independent hierarchy with its own ↪ button. Any number of groups is supported.
- Each level has its own column.
- Fields of the same group that share a `groupIndex` form **one level**: they open and close
  together under a single ↪ button.
- The table opens **fully collapsed**.
- **Top-level rows** are the distinct combinations of the columns left of the first group, plus
  the level-1 field(s) of every group. Duplicate serials under different documents therefore
  each get their own row.
- **Parent rows** show their first child's values in the non-hierarchy columns.
- Headers of levels 2 and up are hidden until a row of that level is expanded.

Example with two groups, where `DocNumber` and `DocNote` open together:

```json
{ "field": "NcGroup",   "fieldIndex": 11, "group": "NC",  "groupIndex": 1 },
{ "field": "NcNumber",                    "group": "NC",  "groupIndex": 2 },
{ "field": "DocGroup",  "fieldIndex": 12, "group": "DOC", "groupIndex": 1 },
{ "field": "DocNumber",                   "group": "DOC", "groupIndex": 2 },
{ "field": "DocNote",                     "group": "DOC", "groupIndex": 2 }
```

---

## 4. Page features

| Feature | Description |
|---|---|
| Run / Enter | Runs the procedure. Main Part is required, and an empty Main Serial is sent as `NULL`. |
| URL parameters | `?mainpart=X&mainserial=Y` opens the page and runs it directly, so results can be bookmarked and shared |
| Tree | ↪ expands a level, and the arrow turns down when open. **Expand all / Collapse all** apply to all groups. |
| Filters | Excel-style ▼ on every column header: value list with counts, (Blanks), (Select all), search, OK / Cancel / Clear. Filters combine across columns, and each list respects the other filters. **Clear filters** appears while a filter is active. Expanded rows stay expanded when filters change. |
| Print / Download PDF | Opens the browser print dialog, where Download PDF means choosing *Save as PDF*. Every page repeats the title, Main Part / Main Serial / date, the logo and the column headers. The printout follows the tree as shown on screen. |
| Orientation | **Landscape / Portrait** selector, remembered per user in the browser |
| Fit to width | Before printing, a table wider than the page is scaled down to fit (A4 printable width: 273 mm landscape, 186 mm portrait). Title and logo keep their size. |
| Download Excel | A real `.xlsx` built in the browser: filtered rows, one line per SQL row, all configured columns (every hierarchy level, merged columns joined). It has a navy header, frozen top row, Excel filters and auto column widths. File name: `<title> - <Main Part> - <Main Serial>.xlsx`. |
| Links area | Empty `<nav id="panelLinks">` on the right of the input panel, for future links |
| Layout | Left to right, centred title, logo top right. Colours come from the corporate report design (navy `#153e70`). |

### Debug mode – `&dbg`

```
/ContentPage/?mainpart=AB-1200&mainserial=SN-1&dbg
```

- Shows **every column the procedure returns**, with the original SQL names, in SQL order.
- The JSON field list is ignored: no aliases, merging or grouping.
- Uses the full window width, in a scroll box with both scrollbars visible and fixed headers.
- Filters, print and Excel export all work and use all columns.
- There is no button for it. It is enabled only through the URL parameter.

---

## 5. Backend API – `routers/content_page.py`

Responses use the shape `{ "data": ..., "error": null | "message" }`.

| Endpoint | Description |
|---|---|
| `GET /api/contentpage/config` | The configuration without `connection` |
| `POST /api/contentpage/run` | Body `{ "mainpart": "...", "mainserial": "..." \| null, "dbg": false }`. Returns `{ rows, missingFields }`, and in debug mode also `columns`. |

- SQL runs as `SET NOCOUNT ON; EXEC <procedure> @mainpart = ?, @mainserial = ?;`, fully parameterised.
- The procedure name can't be a parameter, so it is validated with a regex instead.
- Only configured fields are returned, unless `dbg` is set.
- `missingFields` lists configured fields the procedure did not return. The page shows them as a warning.
- All text, including `VARCHAR`, is fetched as UTF-16 (`setdecoding`), so characters outside the
  server's Windows code page are not turned into `?`.
- Every run and SQL error is logged to `C:\Apps\dsk-api\logs\stdout_*.log`. The connection string is never logged or returned.

---

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Data source name not found and no default driver specified` | The DSN isn't visible to Python. It must be a **System** DSN in the **64-bit** ODBC tool, with exactly the name in the config. Check with `c:\PYTHON\python.exe -c "import pyodbc; print(pyodbc.dataSources())"`. |
| Characters show as `?` | Already fixed in the backend for reading. If `?` remains, it is stored in the data: write with `N'...'`, and keep `NVARCHAR` in the procedure, temp tables and variables. Check with `CAST(col AS VARBINARY(200))`, where `3F` means a stored `?`. |
| "Cannot load configuration" | The config is missing or isn't valid JSON (watch for missing commas). Python still opens a file saved with a BOM. |
| Warning "fields in the config not returned by SQL" | A `field` name doesn't match a procedure column |
| 502 / timeout | Check `C:\Apps\dsk-api\logs\stdout_*.log`, then recycle the app pool |
| Page shows old version | `Ctrl+F5` |

---

## 7. Change log

| Date | Change |
|---|---|
| 2026-11-10 | Config schema, page mock-up, LTR layout; FastAPI router and SQL connection |
| 2026-11-10 | Grouping changed: top rows = distinct (left columns + level 1), only deeper levels hidden |
| 2026-11-10 | Level labels hidden until expanded; centred title; print header repeated on every page; Hebrew title |
| 2026-11-11 | Multiple groups; corporate colour design; Unicode fix (UTF-16 fetch) |
| 2026-11-11 | `&dbg` debug mode with Excel-style filters; ↪ expand button |
| 2026-11-11 | Filters in normal mode; logo in print header; shared `groupIndex` = one level; fit-to-width printing; landscape / portrait selector |
| 2026-11-11 | Taller input panel with links area; wider report area; Download Excel |
