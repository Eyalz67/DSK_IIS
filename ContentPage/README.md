# Content Page (דף תוכן)

A module of the **Data Swiss Knife** portal (IIS + Python FastAPI, air-gapped Windows server).

The user enters **Main Part** and **Main Serial**. The backend runs `dbo.usp_GetAbPartTree` once, and the result is shown in tabs:

| Tab | Page | What it does |
|---|---|---|
| **דף תוכן** | `ContentPage.html` | The main table, plus a completion ring, an open-tasks stripe ("משימות פתוחות"), filters, print/PDF and Excel. The main table has expandable hierarchies. |
| **איסוף NC** | `Collect.html` | The OK rows, with **collect cells**. A collect cell sends the row to **NiFi**, which creates a PDF in a fixed folder, and the cell then links to the file. There are also line and main buttons to collect many cells in one go. |

A JSON configuration file controls the tabs, fields, headers, order, merged columns, hierarchies, the open-tasks rules and the collect columns.

---

## 1. Architecture

```
Browser ──HTTP :80, Windows SSO──► IIS
                                    ├── /ContentPage/        static pages  (C:\inetpub\wwwroot\ContentPage)
                                    └── /api/*            ─► Python FastAPI (C:\Apps\dsk-api, HttpPlatformHandler → uvicorn)
                                          ├── /api/contentpage/*  ─► pyodbc, System DSN DSK_SQL ─► SQL Server
                                          └── /api/collect/*      ─► HTTP POST ─► NiFi HandleHttpRequest ─► PDF files
                                                                     └── reads the PDFs from connection.collectRoot
```

- **IIS** serves the pages. **Python** returns JSON only, plus the collected PDFs.
- **URLs:** the pages call the backend with relative URLs, so there is no CORS and no host name in the code.
- **Config:**
  - The configuration file lives **outside `wwwroot`**.
  - The browser receives it without the `connection` section, so the SQL password and the NiFi address never reach the browser.
- **No internet:** nothing is loaded from the internet. The Excel file and the debug logs are built in the browser.
- **One procedure call:** the procedure runs once per Run and returns the fields **all** tabs need.
- **Where calculations run:** the open-tasks calculation runs in the browser on the full procedure result.
- **NiFi and files:**
  - NiFi runs on the same Windows server and **creates the files and folders**.
  - Python only reads the files, and it builds every file path itself from the config. The browser never sends a path.

---

## 2. Repository layout and deployment

| Repository path | Server location |
|---|---|
| `wwwroot/ContentPage/ContentPage.html` | `C:\inetpub\wwwroot\ContentPage\ContentPage.html` (tab 1) |
| `wwwroot/ContentPage/Collect.html` | `C:\inetpub\wwwroot\ContentPage\Collect.html` (Collect tab) |
| `wwwroot/ContentPage/web.config` | `C:\inetpub\wwwroot\ContentPage\web.config` (default document) |
| `dsk-api/main.py` | `C:\Apps\dsk-api\main.py` (see note) |
| `dsk-api/routers/common.py` | `C:\Apps\dsk-api\routers\common.py`: config, SQL connection, response format |
| `dsk-api/routers/content_page.py` | `C:\Apps\dsk-api\routers\content_page.py`: `/api/contentpage/*` |
| `dsk-api/routers/collect_page.py` | `C:\Apps\dsk-api\routers\collect_page.py`: `/api/collect/*` |
| `dsk-api/routers/__init__.py` | `C:\Apps\dsk-api\routers\__init__.py` (empty; **do not overwrite an existing one**) |
| `dsk-api/config/content_page.example.json` | copy to `C:\Apps\dsk-api\config\content_page.json` and set the real password, NiFi URL and `collectRoot` |

**`main.py` note:** if the server's `main.py` already has other code, don't replace it. Make sure it contains:

```python
from routers import collect_page, content_page

app.include_router(content_page.router)   # /api/contentpage/...  data for all tabs
app.include_router(collect_page.router)   # /api/collect/...      NiFi and collected files
```

**After deploying:**

| Changed file | Action |
|---|---|
| `*.html` | Refresh the browser with `Ctrl+F5` |
| `content_page.json` | Refresh the page. The file is read on every request. |
| Any `.py` file | **Recycle** the `dsk-api` application pool in IIS, then `Ctrl+F5` |

**Folder permission:** the `dsk-api` app pool identity (`IIS AppPool\dsk-api`) needs **Read** permission on the `collectRoot` folder. Without it, files are never found.

**URL:** `http://<server>/ContentPage/`, or `http://<server>/ContentPage/?mainpart=X&mainserial=Y` to run directly.

The real `content_page.json` is listed in `.gitignore` and must never be committed.

---

## 3. Configuration – `content_page.json`

- Save the file as **UTF-8**, because it contains Hebrew.
- Every section and list item is followed by a comma, **except the last one** before `}` or `]`. A missing or extra comma makes the page show "Cannot load configuration".
- The full example is `dsk-api/config/content_page.example.json`.

```json
{
  "title": "דף תוכן",
  "direction": "ltr",
  "logo": "/IMG/company_logo.png",

  "tabs": [
    { "label": "דף תוכן",  "page": "ContentPage.html" },
    { "label": "איסוף NC", "page": "Collect.html", "section": "collect" }
  ],

  "connection": {
    "dsn": "DSK_SQL", "uid": "dsk_reader", "pwd": "CHANGE_ME",
    "procedure": "dbo.usp_GetAbPartTree", "queryTimeout": 60,
    "nifiCollectUrl": "http://nifi-server:9095/collect",
    "nifiTimeout": 30,
    "collectRoot": "D:\\Collect"
  },

  "combineDelimiter": " | ",
  "fields":    [ ... ],
  "openTasks": { ... },
  "collect":   { ... }
}
```

### 3.1 Top-level keys

| Key | Description |
|---|---|
| `title` | Fallback title. Each page's heading comes from its tab `label`. |
| `direction` | `"ltr"` (default) or `"rtl"` for all tabs. A tab can override it (see `tabs`). |
| `logo` | Logo path, shown in the header and on every printed page |
| `tabs` | The tab bar (3.2). With fewer than 2 tabs no bar is shown. |
| `connection` | Server-side only: SQL and NiFi (3.3) |
| `combineDelimiter` | Separator used when values are joined: merged columns and details cells |
| `progressSeconds` | Optional, default 3. How long the progress card's steps take while the data loads. |
| `fields` | Main tab fields (3.4). **Only listed fields are shown.** |
| `openTasks` | The open-tasks rules and lists (section 4). Leave it out to turn the stripe and ring off. |
| `collect` | The Collect tab section (3.5). Its name is whatever `tabs[].section` says. |

### 3.2 `tabs`

| Key | Description |
|---|---|
| `label` | Text on the tab, also the page heading |
| `page` | The tab's HTML file, in the same folder |
| `section` | Name of the config section holding this tab's settings. The first tab has none, because it uses the top-level `fields` and `openTasks`. |
| `direction` | Optional, `"rtl"` or `"ltr"` for this tab only |

- The tabs appear in config order.
- Switching tabs keeps Main Part, Main Serial and the debug flags in the URL.
- **With `rtl`, these are mirrored:** the header (the logo moves to the left), the input panel and ring, the stripe, the tabs, the toolbar and the table columns.
- **Not affected:** the Excel export and the debug logs.

### 3.3 `connection` (never sent to the browser)

| Key | Description |
|---|---|
| `dsn` | System ODBC DSN (64-bit) |
| `uid` / `pwd` | SQL login |
| `procedure` | Procedure to run. It receives `@mainpart` and `@mainserial`. |
| `queryTimeout` | Query timeout in seconds (default 60) |
| `loginTimeout` | Connection timeout in seconds (optional, default 15) |
| `nifiCollectUrl` | Address of NiFi's **HandleHttpRequest** (host, port, path) |
| `nifiTimeout` | Seconds Python waits for NiFi's answer (default 30) |
| `collectRoot` | Root folder of the collected files (written by NiFi, read by Python). In JSON, `\` is written `\\`. |

### 3.4 Field keys (main tab `fields`)

| Key | Required | Description |
|---|---|---|
| `field` | yes | Column name exactly as the procedure returns it (matched case-insensitively) |
| `alias` | no | Column header. If empty, the SQL field name is used. |
| `fieldIndex` | yes* | Display order. *Ignored for hierarchy levels above 1. |
| `group` | no | Hierarchy name |
| `groupIndex` | no | Level inside the hierarchy: 1 = top, 2 opens under 1, and so on |

**Main table rules**

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
- **Top-level rows** are the distinct combinations of the columns left of the first group, plus the level-1 field(s) of every group.
- **Parent rows** show their first child's values in the non-hierarchy columns.
- Headers of levels 2 and up are hidden until a row of that level is expanded.

### 3.5 The Collect tab section (`collect`)

```json
"collect": {
  "fields": [
    { "field": "Eqms_Item",      "alias": "מק״ט",      "fieldIndex": 1 },
    { "field": "Eqms_Item_Desc", "alias": "תיאור",     "fieldIndex": 2 },
    { "field": "clean_lot",      "alias": "סריאלי",    "fieldIndex": 3 },
    { "field": "Inspection_Nbr", "alias": "דוח בחינה", "fieldIndex": 4,
      "send_fields": ["Eqms_Item", "clean_lot"], "send_command": "COLLECT_INSPECTION" },
    { "field": "Heter1",         "alias": "היתרים",    "fieldIndex": 5,
      "send_fields": ["Eqms_Item", "clean_lot"], "send_command": "COLLECT_HETER" }
  ],
  "line_button": { "label": "אסוף שורה", "command": "COLLECT_ROW" },
  "mainButton":  { "color": "#2e7d32", "text": "אסוף הכל", "command": "COLLECT_ALL" },
  "book_button": { "color": "#a9805b", "text": "ספר",      "command": "BOOK" }
}
```

**`fields`**

| Key | Required | Description |
|---|---|---|
| `field` | yes | Column name exactly as the procedure returns it |
| `alias` | no | Column header. Plain fields with the same alias are merged into one column. |
| `fieldIndex` | yes | Display order |
| `send_fields` | for collect | Fields sent to NiFi, **in this order**. The file name is built from their values in the same order. |
| `send_command` | for collect | Tells NiFi which collect this is. It is also the sub-folder name. |
| `hoover_alias` | no | Text in the collect cell. Default "אסוף". |

- **A field with both `send_fields` and `send_command`** is a collect field: its value column plus a collect cell right after it (to the left in RTL, to the right in LTR), both under one header.
- **A field without both** is a plain column.
- There are no hierarchies on this tab, so `group` and `groupIndex` are ignored.
- The old `collect_field` list is no longer read.

**Buttons** (leave a key out and that button isn't shown)

| Key | Description |
|---|---|
| `line_button.label` | Text of the button at the end of every row |
| `mainButton.text` / `color` | Text and background colour of the main button in the toolbar |
| `book_button.text` / `color` | Text and colour of the book button (📖 icon) next to it, **for future use**: it only writes a debug line for now |
| `*.command` | Reserved; not sent yet. Each cell is sent with its own `send_command`. |

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

---

## 5. Main tab (`ContentPage.html`) features

| Feature | Description |
|---|---|
| Run / Enter | Runs the procedure. Main Part and Main Serial are both required. |
| URL parameters | `?mainpart=X&mainserial=Y` opens the page and runs it directly |
| Progress card | Shown while the data loads: spinner, rolling headline, timer, step lines with ✓ and a circular progress. When the data arrives the card turns green and fades out. The steps are for display only. |
| Tree | ↪ expands a level. **Expand all / Collapse all** apply to all groups. |
| Filters | Excel-style ▼ on every column: a value list with counts, **(Blanks)** at the top, (Select all), search, and OK / Cancel / Clear. Filters combine across columns. **Clear filters** appears while a filter is active. |
| Print / Download PDF | Opens the browser print dialog; for Download PDF, choose *Save as PDF*. Every printed page repeats the title, Main Part / Main Serial / date, the logo and the column headers. |
| Orientation | **Landscape / Portrait** selector, remembered per user |
| Fit to width | When printing, a table wider than the page is scaled down to fit. The title and logo keep their size. |
| Download Excel | A real `.xlsx` with the filtered OK rows and all configured columns. It has a navy header, a frozen top row and Excel filters. |

### Debug mode – `&dbg`

```
/ContentPage/?mainpart=AB-1200&mainserial=SN-1&dbg
```

- **Table:** shows **every column** the procedure returns, with the original SQL names, in SQL order.
  - No aliases, merging or grouping.
  - **Only the OK rows** are shown.
- **Stripe and ring:** use the same calculation as in normal mode.
- **Download log** saves a `.txt` trace that explains every decision:
  - The header: the parameters, the time, the number of rows and the `openTasks` config.
  - The missing-serial check: each part, `[COUNTED]` or `[ok]`.
  - The missing-inspection check: each item and serial, `[COUNTED] CASE 1/2`, `[ok]` or `[ignored]`.
  - A summary, including the percentage calculation.
  - `#N` is row number N in the procedure result.

---

## 6. Collect tab (`Collect.html`)

### 6.1 What the tab shows

| Part | Behaviour |
|---|---|
| Input panel, ring, progress card, open-tasks stripe | Same as the main tab. Main Part / Main Serial are shown as text; the tab is opened from the main tab after a run. |
| Table rows | Only the **OK rows**, one row per distinct combination of the shown values |
| Toolbar | Main button and book button. Filters work as on the main tab. No Print, PDF, Excel or Expand / Collapse. |
| Column headers | Stay fixed while the table scrolls inside its own box |
| Statistics stripe | Fixed at the bottom of the window, 1.5× text size (6.4) |

### 6.2 Collect cell states

| State | Look | Click |
|---|---|---|
| Field value empty | Value and cell **light red**, no text | Nothing happens |
| Not collected yet | Dashed cell with ⤓ + `hoover_alias` | Sends to NiFi |
| Sending | Spinner + "שולח…" | Disabled |
| **File found at startup** | **Light green**: 📄 file name (link) + ⤓ alias | Link opens the PDF; alias recollects |
| **Collected now** (NiFi success, file found) | **Strong green**: 📄 file name (link) + ⤓ alias | Same |
| NiFi success, but no file at the expected path | ✓ + the `path` NiFi returned + ⤓ alias | Alias recollects |
| Failed | **Strong red** with the alias; hover shows the reason | Retries |

When the page opens, Python checks every collectable cell for an existing file (`/api/collect/status`) and marks the ones it finds light green. Clicking the alias of a cell that already has a file **recollects** it: NiFi overwrites the file.

### 6.3 Line and main buttons

- **Line button:** collects every collect cell of its row, one by one, left to right, exactly as if each cell were pressed.
- **Main button:** does the same for every row shown (after filters), top to bottom in the printed order.
  - While it runs, it shows a spinner and `done/total`.
- **During a run:** all line buttons and the main button are disabled.
- **Which cells are sent:**
  - Empty (light-red) cells are skipped.
  - Cells that already have a file **are recollected** (refreshed).
- **Requests are sequential:** one NiFi request at a time, and each waits for the answer before the next is sent.

### 6.4 Statistics stripe

| Action | The stripe shows |
|---|---|
| Cell press | The column, the row's values, then **success** with the file name (link), or **failed** with NiFi's reason |
| Line button | Progress `x/y`, then `N success · N failed` for the row |
| Main button | Progress `x/y`, then `N success · N failed` **per collect field** |

### 6.5 Collected file path

Built **only by Python**, from the config:

```
<collectRoot>\<main_part>_<main_serial>\<send_command>\<send_fields values joined with _>.pdf
```

Example: `D:\Collect\AB-1200_SN-0042\COLLECT_INSPECTION\E1_S1.pdf`

- **NiFi must save the file at exactly this path**, so that the file is found.
- **Rejected names:** a part that contains `\`, `/` or `:`, or that is `.` or `..`, is rejected. The final path must be inside `collectRoot`.

### 6.6 Debug – `&dbg1` / `&dbg2`

A debug panel at the bottom of the tab, with **Download** to save the log as `.txt`.

| Level | Logs |
|---|---|
| `&dbg1` | Config (section, fields, collect fields, buttons), parameters, row counts, `collectRoot`, an example path, the files found, and each line or main run with its counts |
| `&dbg2` | Everything in `&dbg1`, plus per cell: the path checked and whether its folder exists, the NiFi URL, the JSON sent, NiFi's raw answer, the file checked after the collect, and the file links opened |

---

## 7. NiFi contract and flow

### 7.1 What NiFi receives (one POST per cell)

```json
{ "send_command": "COLLECT_INSPECTION", "main_part": "AB-1200", "main_serial": "SN-0042",
  "Eqms_Item": "E1", "clean_lot": "S1" }
```

The body is UTF-8 JSON (`Content-Type: application/json`). The keys after `main_serial` are the cell's `send_fields`.

### 7.2 What NiFi must answer (HandleHttpResponse)

| Result | HTTP | Body |
|---|---|---|
| Success | 200 | `{"status":"success","path":"<full file path>"}` |
| Fail | 200 or 5xx | `{"status":"fail","reason":"<text>"}` |

- **Mind the punctuation:** separate the JSON keys with a comma, not a colon: `"success","path"`.
- **What Python treats as a fail, with a clear reason:**
  - NiFi down or a timeout
  - a non-JSON answer
  - an answer without a valid `status`
  - `success` with a non-2xx code
- **After a success**, Python checks the file at the path from 6.5 and returns `exists`, `file_name` and `modified`.

### 7.3 Reference flow

```
HandleHttpRequest  (port 9095, path /collect, POST, StandardHttpContextMap)
  → EvaluateJsonPath   Destination = flowfile-attribute, Path Not Found Behavior = ignore
                       send_command, main_part, main_serial, <send_fields> ...
  → RouteOnAttribute   one route per send_command, e.g. COLLECT_NC = ${send_command:equals('COLLECT_NC')}
        unmatched → ReplaceText {"status":"fail","reason":"Unknown send_command"} → HandleHttpResponse
  → Output Port → the report process group (Input Port) → ... → PutFile (path of 6.5)
  → ReplaceText  {"status":"success","path":"..."}  → HandleHttpResponse (200)
  → failure branches → ReplaceText {"status":"fail","reason":"..."} → HandleHttpResponse
```

- **Context map:**
  - HandleHttpRequest and every HandleHttpResponse must use **the same StandardHttpContextMap**.
  - Define it once, in a common parent process group.
- **Keep `http.context.identifier`:** the attribute must survive the whole flow. Processors that create **new** flowfiles must copy it to them. Processors that change content keep it.
- **Request Expiration:** the context map drops requests older than this setting, which is **1 minute** by default. Slow flows (for example a remote NiFi + FetchSFTP) need a longer value, for example `5 min`. Keep `nifiTimeout` in step with it.

---

## 8. Backend API

Responses use the shape `{ "data": ..., "error": null | "message" }`.

| Endpoint | File | Description |
|---|---|---|
| `GET /api/contentpage/config` | `content_page.py` | The configuration without `connection` |
| `POST /api/contentpage/run` | `content_page.py` | Body `{ "mainpart", "mainserial", "dbg" }`. Runs the procedure **once for all tabs**. Returns `{ rows, missingFields }`, and with `dbg` also `columns`. |
| `POST /api/collect/send` | `collect_page.py` | Body `{ section, collect_field, record, main_part, main_serial, debug }`. Sends one record to NiFi. Returns `{ status, path, reason }`, plus `exists`, `file_name` and `modified` after a success. |
| `POST /api/collect/status` | `collect_page.py` | Body `{ section, main_part, main_serial, items: [{ collect_field, record }], debug }`. Returns `{ exists, file_name, modified }` for each item, in the same order. |
| `GET /api/collect/file` | `collect_page.py` | Query `section`, `collect_field`, `main_part`, `main_serial`, `v` (repeated, the `send_fields` values in order). Opens the PDF inline. |

- **SQL:**
  - Runs as `SET NOCOUNT ON; EXEC <procedure> @mainpart = ?, @mainserial = ?;`, fully parameterised.
  - The procedure name can't be a parameter, so it is validated with a regex.
- **Returned fields:**
  - The main `fields`, the `openTasks` role fields, `inspGroupBy` and the details fields.
  - For every tab section: its `fields` plus their `send_fields`.
  - No duplicates.
- **`missingFields`** lists the configured fields that the procedure did not return. The page shows them as a red warning.
- **Unicode:** all text, including `VARCHAR`, is fetched as UTF-16, so Hebrew is not turned into `?`.
- **NiFi requests:** sent with a direct connection, ignoring any Windows proxy.
- **`debug`:** with `debug: true`, `/send` and `/status` add a `debug` block to their answer.
- **Logs:** written to `C:\Apps\dsk-api\logs\stdout_*.log`, with lines starting `[contentpage]` or `[collect]`. The connection string is never logged or returned.

### Testing without the page

```cmd
curl -X POST http://localhost/api/collect/send -H "Content-Type: application/json" --negotiate -u : --data-binary @body.json
```

`body.json`:

```json
{ "section": "collect", "collect_field": "Inspection_Nbr", "main_part": "AB-1200", "main_serial": "SN-0042",
  "record": { "Eqms_Item": "E1", "clean_lot": "S1" } }
```

---

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Data source name not found and no default driver specified` | The DSN must be a **System** DSN in the **64-bit** ODBC tool, with exactly the name in the config. Check with `c:\PYTHON\python.exe -c "import pyodbc; print(pyodbc.dataSources())"`. |
| Characters show as `?` | The backend already reads Unicode. If `?` remains, it is in the stored data itself: write it with `N'...'`, and keep `NVARCHAR` in the procedure, its temp tables and its variables. |
| "Cannot load configuration" | The config is missing or isn't valid JSON (watch for commas) |
| Red "fields in the config not returned by SQL" | A `field` or `send_fields` name doesn't match a procedure column |
| Counts look wrong | Open with `&dbg`, press **Download log**, and find the part or item. Check the spelling of the `openTasks` keys. |
| Collect: `'X' is not a collect field ...` | The field has no `send_fields` + `send_command` in the tab's `fields`, or the page and the config don't match (press `Ctrl+F5`) |
| Collect: `Field 'X' is missing or empty – record not sent` | A `send_fields` value is empty in that row |
| Collect: `Cannot reach NiFi: ...` | Wrong `nifiCollectUrl`, HandleHttpRequest is stopped, or Python's `nifiTimeout` ran out |
| Collect: `NiFi answer is not valid JSON` | The ReplaceText replacement value isn't valid JSON. Check for a `:` where a `,` should be. |
| Collect cell shows the NiFi `path` instead of the file name | NiFi answered success, but the file isn't at the path of 6.5. Check the file name, the folder and the `send_fields` order with `&dbg2`. Also check the app pool's Read permission on `collectRoot`. |
| Files never found at startup | Check `collectRoot` and the folder permission. `&dbg1` shows where Python searches. |
| NiFi HandleHttpResponse → failure: *could not find an HTTP response object for this identifier* | The request expired in the StandardHttpContextMap before the answer was ready. Raise its **Request Expiration** (default 1 min). Also make sure every processor uses the same context map and that `http.context.identifier` is kept. |
| 502 / timeout | Check `C:\Apps\dsk-api\logs\stdout_*.log`, then recycle the app pool |
| Page shows an old version | `Ctrl+F5` |

---

## 10. Open items

- `line_button` / `mainButton` / `book_button` `command`: not sent to NiFi yet
- Book button: functionality to be defined
- Use the file's modified date (already returned by Python)
- NiFi flows for the remaining `send_command`s
- Main tab: fixed column headers, as on the Collect tab
- Print: the stripe with both details tables opened, before the main table
- Excel: extra sheets for "סריאלי לא ידוע" and "חסר דוח בחינה"

---

## 11. Change log

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
| 2026-11-19 | `direction` applied (per tab); Main Serial required |
| 2026-11-20 | Tabs (`tabs[]`); Collect tab with OK rows and collect cells; backend split into `common.py`, `content_page.py`, `collect_page.py` |
| 2026-11-22 | Collect cell → NiFi (`/api/collect/send`): JSON contract `status` / `path` / `reason`; strong green / red states; NiFi routing by `send_command` |
| 2026-11-23 | File path `collectRoot\main_part_main_serial\send_command\values.pdf`; startup file check (`/status`); link + recollect; PDF viewer (`/file`) |
| 2026-11-23 | Collect debug levels `&dbg1` / `&dbg2` with Download |
| 2026-11-24 | Line and main buttons (sequential bulk collect); light green for files found at startup |
| 2026-11-24 | Book button; statistics stripe at the bottom; fixed column headers on the Collect tab |
| 2026-11-25 | `collect_field` replaced by `send_fields` + `send_command` on `fields` (value + collect cell under one header); stripe 1.5×; `collectRoot` in the example config |
