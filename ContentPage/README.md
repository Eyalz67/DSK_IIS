# Content Page (דף תוכן)

A module of the **Data Swiss Knife** portal (IIS + Python FastAPI, air-gapped Windows server).

The user enters **Main Part** and **Main Serial** and clicks **Run**. The backend executes
`dbo.usp_GetAbPartTree`, and the page then shows:

- a **completion ring**: the share of the result that is complete
- an **open tasks stripe** ("משימות פתוחות"): missing serials and missing inspection reports,
  each with a **פרטים** details table
- the **main table** of the OK rows, with expandable hierarchies, Excel-style filters,
  print / PDF and Excel export

A JSON configuration file controls the fields, headers, order, merged columns, hierarchies
and the open-tasks rules.

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
- Nothing is loaded from the internet. The Excel file and the trace log are built in the browser.
- The open-tasks calculation runs in the browser on the full procedure result.

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
| Any `.py` file | **Recycle** the `dsk-api` application pool in IIS, then `Ctrl+F5` |

**URL:** `http://<server>/ContentPage/`

The real `content_page.json` is listed in `.gitignore` and must never be committed.

---

## 3. Configuration – `content_page.json`

Save the file as **UTF-8**, because it contains Hebrew. Commas between items are required;
a missing comma makes the page show "Cannot load configuration".

```json
{
  "title": "דף תוכן",
  "direction": "ltr",
  "logo": "/IMG/company_logo.png",

  "connection": {
    "dsn": "DSK_SQL", "uid": "dsk_reader", "pwd": "CHANGE_ME",
    "procedure": "dbo.usp_GetAbPartTree", "queryTimeout": 60
  },

  "combineDelimiter": " | ",

  "fields": [
    { "field": "Inspection_Nbr", "alias": "דוח בחינה", "fieldIndex": 1 },
    { "field": "Clean_Lot",      "alias": "Serial",    "fieldIndex": 5, "group": "Serial", "groupIndex": 1 },
    { "field": "Document",                                              "group": "Serial", "groupIndex": 2 },
    { "field": "Heter1",         "alias": "התרים",     "fieldIndex": 6 },
    { "field": "Heter2",         "alias": "התרים" }
  ],

  "openTasks": {
    "calcPart":    "Result_Part",
    "calcSR":      "Result_Serial",
    "calcSerial":  "clean_lot",
    "calcINSP":    "Inspection_Nbr",
    "inspGroupBy": ["Eqms_Item", "Eqms_Item_Desc"],
    "missingSR":   { "label": "סריאלי לא ידוע, לא דווחה הרכבה",
                     "fields": [ { "field": "Result_Part", "alias": "פריט" } ] },
    "missingINSP": { "label": "חסר דוח בחינה",
                     "fields": [ { "field": "Eqms_Item" }, { "field": "Eqms_Item_Desc" },
                                 { "field": "clean_lot", "alias": "serial" } ] }
  }
}
```

### Top-level keys

| Key | Description |
|---|---|
| `title` | Main title: page header, browser tab and the header of every printed page |
| `direction` | `"ltr"` (default) or `"rtl"` for the whole page. *Planned: the key is read but not applied yet.* |
| `logo` | Logo path, shown top right on screen and on every printed page |
| `connection.dsn` | System ODBC DSN (64-bit) |
| `connection.uid` / `pwd` | SQL login |
| `connection.procedure` | Procedure to run. It receives `@mainpart` and `@mainserial`. |
| `connection.queryTimeout` | Query timeout in seconds (default 60) |
| `connection.loginTimeout` | Connection timeout in seconds (optional, default 15) |
| `combineDelimiter` | Separator used when values are joined: merged columns and details cells |
| `progressSeconds` | Optional, default 3. How long the progress card's steps take while the data loads. |
| `fields` | The main table fields. **Only listed fields are shown.** |
| `openTasks` | The open-tasks rules and lists (section 4). Leave it out to turn the stripe and ring off. |

### Field keys (`fields`)

| Key | Required | Description |
|---|---|---|
| `field` | yes | Column name exactly as the procedure returns it (matched case-insensitively) |
| `alias` | no | Column header. If empty, the SQL field name is used. |
| `fieldIndex` | yes* | Display order. *Ignored for hierarchy levels above 1. |
| `group` | no | Hierarchy name |
| `groupIndex` | no | Level inside the hierarchy: 1 = top, 2 opens under 1, and so on |

### Main table rules

**Column order**
- Columns are sorted by `fieldIndex`.
- A field without `fieldIndex` goes after the indexed fields, in config order.
- A hierarchy's deeper levels are placed directly after its level 1.

**Merged columns**
- Fields with the same `alias` (outside a group) become one column.
- Values are joined with `combineDelimiter`, and empty values are skipped.

**Hierarchies**
- Every `group` is an independent hierarchy with its own ↪ button. Each level has its own column.
- Fields of a group that share a `groupIndex` form **one level**: they open and close together.
- The table opens **fully collapsed**.
- **Top-level rows** are the distinct combinations of the columns left of the first group, plus
  the level-1 field(s) of every group.
- **Parent rows** show their first child's values in the non-hierarchy columns.
- Headers of levels 2 and up are hidden until a row of that level is expanded.

---

## 4. Open tasks – stripe, details and ring

The calculation always runs on the **full procedure result**. The ▼ filters of the main table do not change it.
Rows counted in either list are **removed from the main table**, so the main table shows only OK rows.

### 4.1 `openTasks` keys

| Key | Description |
|---|---|
| `calcPart` | Part field for the missing serial check (e.g. `Result_Part`) |
| `calcSR` | Field checked for an empty serial (e.g. `Result_Serial`). Used **only** by the missing serial check. |
| `calcSerial` | Serial field for the missing inspection check (e.g. `clean_lot`) |
| `calcINSP` | Inspection field (e.g. `Inspection_Nbr`) |
| `inspGroupBy` | Fields that define an **item** for the missing inspection check (e.g. `Eqms_Item`, `Eqms_Item_Desc`). Default: `calcPart`. |
| `missingSR.label` / `missingINSP.label` | Text of each line in the stripe |
| `missingSR.fields` / `missingINSP.fields` | Columns of each פרטים table (`field` + optional `alias`). They may include fields that aren't in the main table; the backend returns them too. |

### 4.2 Missing serial – "סריאלי לא ידוע, לא דווחה הרכבה"

- The rows are grouped by `calcPart`.
- A part counts as **1** when **every** row has an empty `calcSR`. Empty means NULL, `''` or spaces.
- All rows of a counted part leave the main table.

### 4.3 Missing inspection – "חסר דוח בחינה"

This check uses only the rows of parts **not** counted in 4.2. Those rows are grouped into items by `inspGroupBy`.

| Case | Rule | Count | Details row |
|---|---|---|---|
| Case 1 | The item has no `calcSerial` on **any** row | 1 per item | item, serial empty |
| Case 2 | A `calcSerial` of the item where **no** row has a `calcINSP` | 1 per serial | item + that serial |
| Ignored | A row with a NULL `calcSerial` in an item that **does** have serials | not counted | the row is hidden from the main table |

- Only **NULL** counts as missing in this check. `''` and spaces are values, as in SQL.
- The rows of counted items and serials leave the main table.

Example:

| Item | Rows | Result |
|---|---|---|
| E1 | S1 + INS-1, S2 + NULL | 1 (E1 / S2); the S1 row stays in the main table |
| E2 | no serial at all | 1 (E2 / empty) |
| E3 | S3 + NULL, S5 + NULL | 2 (E3 / S3, E3 / S5) |
| P1 | 14 × S + INS, 1 × NULL serial + NULL | 0; the NULL row is hidden from the main table |

### 4.4 Stripe and details

- The stripe sits between the input panel and the main table, with "משימות פתוחות" and an orange badge holding the total.
- "חסר דוח בחינה" is the orange line with the ⚠ icon. "סריאלי לא ידוע" is the grey dashed line with the ? icon.
- **פרטים** opens a details table: one row per counted item, with the columns from the list's `fields`.
  A cell shows all distinct values of the item's rows, joined with `combineDelimiter`.
- A line with 0 still shows; its פרטים is disabled.
- The stripe is shown in debug mode too.

### 4.5 Completion ring

Shown at the far end of the input panel, in blue on a light track. Hover over it to see the calculation.

```
complete % = main table rows (collapsed, before filters)
             / (main table rows + missing serial + missing inspection) × 100
```

The ring is screen only: it is not printed and not exported to Excel.

---

## 5. Page features

| Feature | Description |
|---|---|
| Run / Enter | Runs the procedure. Main Part is required, and an empty Main Serial is sent as `NULL`. |
| URL parameters | `?mainpart=X&mainserial=Y` opens the page and runs it directly |
| Progress card | While the data loads: spinner, rolling headline, timer, step lines with ✓ and a circular progress. When the data arrives the steps finish quickly, the card turns green and fades out. The steps are for display only. |
| Tree | ↪ expands a level. **Expand all / Collapse all** apply to all groups. |
| Filters | Excel-style ▼ on every column: value list with counts, **(Blanks)** at the top, (Select all), search, OK / Cancel / Clear. Filters combine across columns. **Clear filters** appears while a filter is active. |
| Print / Download PDF | Browser print dialog; Download PDF means choosing *Save as PDF*. Every page repeats the title, Main Part / Main Serial / date, the logo and the column headers. |
| Orientation | **Landscape / Portrait** selector, remembered per user |
| Fit to width | A table wider than the page is scaled down to fit when printing. Title and logo keep their size. |
| Download Excel | A real `.xlsx` with the filtered OK rows, all configured columns, a navy header, a frozen top row and Excel filters |
| Links area | Empty `<nav id="panelLinks">` in the input panel, for future links |

### Debug mode – `&dbg`

```
/ContentPage/?mainpart=AB-1200&mainserial=SN-1&dbg
```

- The table shows **every column** the procedure returns, with the original SQL names, in SQL order.
  It has no aliases, merging or grouping, and it contains **only the OK rows**.
- The stripe and the ring are shown with the same calculation as in normal mode.
- **Download log** (debug only) saves a `.txt` trace that explains every decision:
  - **Header:** Main Part / Main Serial, the time, the number of rows returned and the `openTasks` config.
  - **1. Missing serial:** every part, `[COUNTED]` with the empty values found, or `[ok]` with the first serial found.
  - **2. Missing inspection:** every item and serial, marked `[COUNTED] CASE 1`, `[COUNTED] CASE 2`, `[ok]` (with the inspection found) or `[ignored]`.
  - **3. Summary:** the counts, the rows removed from the table and the percentage calculation.
  - `#N` = row number N in the procedure result (#1 = first row).
- There is no button to enter debug mode; it is enabled only through the URL parameter.

---

## 6. Backend API – `routers/content_page.py`

Responses use the shape `{ "data": ..., "error": null | "message" }`.

| Endpoint | Description |
|---|---|
| `GET /api/contentpage/config` | The configuration without `connection` |
| `POST /api/contentpage/run` | Body `{ "mainpart": "...", "mainserial": "..." \| null, "dbg": false }`. Returns `{ rows, missingFields }`, and in debug mode also `columns`. |

- SQL runs as `SET NOCOUNT ON; EXEC <procedure> @mainpart = ?, @mainserial = ?;`, fully parameterised.
- The procedure name can't be a parameter, so it is validated with a regex instead.
- **Returned fields:** the main `fields`, the `openTasks` role fields, `inspGroupBy`, and the details
  `fields`, without duplicates. In debug mode all columns are returned.
- `missingFields` lists configured fields the procedure did not return. The page shows them as a red warning under Run.
- All text, including `VARCHAR`, is fetched as UTF-16, so characters outside the server code page are not turned into `?`.
- Runs and SQL errors are logged to `C:\Apps\dsk-api\logs\stdout_*.log`. The connection string is never logged or returned.

---

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Data source name not found and no default driver specified` | The DSN must be a **System** DSN in the **64-bit** ODBC tool, with exactly the name in the config. Check with `c:\PYTHON\python.exe -c "import pyodbc; print(pyodbc.dataSources())"`. |
| Characters show as `?` | The backend already reads Unicode. If `?` remains, it is stored in the data: write with `N'...'` and keep `NVARCHAR` in the procedure, temp tables and variables. |
| "Cannot load configuration" | The config is missing or isn't valid JSON (watch for missing commas) |
| Red "fields in the config not returned by SQL" | A `field` name (main, `openTasks` or details) doesn't match a procedure column |
| Counts look wrong | Open with `&dbg`, press **Download log**, and find the part or item. The log says why it was counted or not. Check that the `openTasks` keys are spelled exactly `calcSR`, `calcINSP` and so on, because a misspelled key is treated as an always-empty field. Compare against the same Main Part / Main Serial in SQL. |
| 502 / timeout | Check `C:\Apps\dsk-api\logs\stdout_*.log`, then recycle the app pool |
| Page shows old version | `Ctrl+F5` |

---

## 8. Open items

- `direction: "rtl"`: right-to-left layout for the whole page (the config key is already in place)
- Print: the stripe with both details tables fully opened, before the main table
- Excel: extra sheets for "סריאלי לא ידוע" and "חסר דוח בחינה"
- Optional: compare values like SQL Server (ignore trailing spaces and upper/lower case) when grouping

---

## 9. Change log

| Date | Change |
|---|---|
| 2026-11-10 | Config schema, page mock-up, LTR layout; FastAPI router and SQL connection |
| 2026-11-10 | Grouping: top rows = distinct (left columns + level 1), only deeper levels hidden |
| 2026-11-10 | Level labels hidden until expanded; centred title; print header on every page; Hebrew title |
| 2026-11-11 | Multiple groups; corporate colours; Unicode fix (UTF-16 fetch) |
| 2026-11-11 | `&dbg` debug mode with Excel-style filters; ↪ expand button |
| 2026-11-11 | Filters in normal mode; logo in print header; shared `groupIndex`; fit-to-width; landscape / portrait |
| 2026-11-11 | Taller input panel with links area; wider report area; Download Excel |
| 2026-11-16 | `openTasks` config and `direction` key; backend returns role and details fields |
| 2026-11-16 | Open-tasks calculation; missing rows removed from the main table; completion % |
| 2026-11-16 | Open tasks stripe with פרטים details; completion ring; progress card |
| 2026-11-17 | Circular progress inside the progress card |
| 2026-11-18 | Missing inspection redefined per item (`inspGroupBy`): case 1 / case 2, NULL-serial rows ignored |
| 2026-11-18 | Debug **Download log** trace with `#N` row numbers |
| 2026-11-18 | Ignored NULL-serial rows hidden from the main table; (Blanks) filter fixed and moved to the top |
