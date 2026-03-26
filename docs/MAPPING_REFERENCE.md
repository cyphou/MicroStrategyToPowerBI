# MicroStrategy → Power BI Mapping Reference

This document details all mappings between MicroStrategy and Power BI objects to facilitate migration.

**Version:** v16.0.0 — 2,458 tests | 39 generation modules | 50+ CLI flags

> **See also:**
> - [MSTR_TO_DAX_REFERENCE.md](MSTR_TO_DAX_REFERENCE.md) — Complete MicroStrategy expression → DAX mapping
> - [ARCHITECTURE.md](ARCHITECTURE.md) — Pipeline architecture

---

## 📊 Visual Types (30+ mappings)

### Bar & Column Charts

| MicroStrategy Visualization | Power BI visualType | Notes |
|-----------------------------|-------------------|-------|
| Vertical Bar | clusteredColumnChart | Standard vertical bar |
| Stacked Vertical Bar | stackedColumnChart | |
| 100% Stacked Vertical Bar | hundredPercentStackedColumnChart | |
| Horizontal Bar | clusteredBarChart | Standard horizontal bar |
| Stacked Horizontal Bar | stackedBarChart | |
| 100% Stacked Horizontal Bar | hundredPercentStackedBarChart | |
| Histogram | clusteredColumnChart | Binned axis |
| Pareto | lineClusteredColumnComboChart | Bar + cumulative line |

### Line & Area Charts

| MicroStrategy Visualization | Power BI visualType | Notes |
|-----------------------------|-------------------|-------|
| Line | lineChart | |
| Stacked Area | stackedAreaChart | |
| Area | areaChart | |
| Combo (Bar+Line) | lineClusteredColumnComboChart | Dual axis |
| Combo (Stacked Bar+Line) | lineStackedColumnComboChart | |

### Pie, Donut & Funnel

| MicroStrategy Visualization | Power BI visualType | Notes |
|-----------------------------|-------------------|-------|
| Pie | pieChart | |
| Ring / Donut | donutChart | |
| Funnel | funnel | |

### Scatter & Bubble

| MicroStrategy Visualization | Power BI visualType | Notes |
|-----------------------------|-------------------|-------|
| Scatter | scatterChart | X/Y axes |
| Bubble | scatterChart | Size encoding |

### Maps & Geography

| MicroStrategy Visualization | Power BI visualType | Notes |
|-----------------------------|-------------------|-------|
| Map (points) | map | Lat/long or geographic |
| Map (filled/area) | filledMap | Colored regions |
| Map (density) | map | Heat map overlay |

### Tables & Matrices

| MicroStrategy Visualization | Power BI visualType | Notes |
|-----------------------------|-------------------|-------|
| Grid | tableEx | Rows/values |
| Cross-tab / Pivot Grid | matrix | Rows/columns/values |
| Heat Map | matrix | Conditional formatting |

### Tree, Hierarchy & Flow

| MicroStrategy Visualization | Power BI visualType | Notes |
|-----------------------------|-------------------|-------|
| Treemap | treemap | |
| Waterfall | waterfall | |
| Network | Custom visual (AppSource) | Not built-in |
| Sankey | Custom visual (AppSource) | Not built-in |

### KPI & Gauges

| MicroStrategy Visualization | Power BI visualType | Notes |
|-----------------------------|-------------------|-------|
| KPI | kpi | Target + actual |
| Gauge | gauge | Min/max/target |
| Bullet | Custom visual | Not built-in |

### Special Visuals

| MicroStrategy Visualization | Power BI visualType | Notes |
|-----------------------------|-------------------|-------|
| Word Cloud | Custom visual (AppSource) | |
| Box Plot | Custom visual (AppSource) | |
| Panel Stack | Bookmarks + toggle buttons | No direct equivalent |
| Info Window | Tooltip page | |
| Filter Panel | Slicer(s) | One slicer per filter |
| Selector Control | Slicer / field parameter | |
| Text | textbox | |
| Image | image | |
| HTML Container | textbox (warning) | HTML not supported in PBI |

---

## 🔌 Data Source Connectors (15+ mappings)

| MicroStrategy Warehouse Type | Power Query M Function | Notes |
|------------------------------|----------------------|-------|
| Oracle | `Oracle.Database()` | TNS name or descriptor |
| SQL Server | `Sql.Database()` | Server + database |
| PostgreSQL | `PostgreSQL.Database()` | Server + database |
| MySQL | `MySQL.Database()` | Server + database |
| Teradata | `Teradata.Database()` | Server |
| Netezza | `Odbc.DataSource()` | Via ODBC driver |
| DB2 | `DB2.Database()` | Server + database |
| Snowflake | `Snowflake.Databases()` | Account + warehouse |
| Databricks | `Databricks.Catalogs()` | Host + HTTP path |
| Google BigQuery | `GoogleBigQuery.Database()` | Project ID |
| SAP HANA | `SapHana.Database()` | Server |
| Impala | `Odbc.DataSource()` | Via ODBC |
| Vertica | `Odbc.DataSource()` | Via ODBC |
| Amazon Redshift | `AmazonRedshift.Database()` | Server + database |
| ODBC / JDBC (generic) | `Odbc.DataSource()` | DSN fallback |
| Fabric Lakehouse | `Lakehouse.Contents()` | Fabric workspace |
| Fabric Warehouse | `Sql.Database()` | Fabric SQL endpoint |
| Freeform SQL | `Value.NativeQuery()` | SQL passthrough |

---

## 🧮 Expression Mapping (100+ functions)

### Aggregation Functions

| MicroStrategy | DAX | Notes |
|---------------|-----|-------|
| `Sum(Fact)` | `SUM(Table[Column])` | |
| `Avg(Fact)` | `AVERAGE(Table[Column])` | |
| `Count(Attr)` | `COUNT(Table[Column])` | |
| `Count(Distinct Attr)` | `DISTINCTCOUNT(Table[Column])` | |
| `Min(Fact)` | `MIN(Table[Column])` | |
| `Max(Fact)` | `MAX(Table[Column])` | |
| `StDev(Fact)` | `STDEV.S(Table[Column])` | Sample standard deviation |
| `StDevP(Fact)` | `STDEV.P(Table[Column])` | Population standard deviation |
| `Var(Fact)` | `VAR.S(Table[Column])` | |
| `VarP(Fact)` | `VAR.P(Table[Column])` | |
| `Median(Fact)` | `MEDIAN(Table[Column])` | |
| `Percentile(Fact, p)` | `PERCENTILEX.INC(T, T[Col], p)` | |
| `Product(Fact)` | `PRODUCTX(Table, Table[Column])` | |
| `GeoMean(Fact)` | `GEOMEANX(Table, Table[Column])` | |

### Level Metrics (Dimensionality)

| MicroStrategy | DAX | Notes |
|---------------|-----|-------|
| `Sum(Fact) {~+, Year}` | `CALCULATE([M], ALLEXCEPT(T, T[Year]))` | Report-level + Year |
| `Sum(Fact) {~, Year}` | `CALCULATE([M], ALLEXCEPT(T, T[Year]))` | Exact level |
| `Sum(Fact) {!Region}` | `CALCULATE([M], REMOVEFILTERS(T[Region]))` | Exclude filter |
| `Sum(Fact) {^}` | `CALCULATE([M], ALL(Table))` | Report-level (grand total) |
| `Sum(Fact) {Year, Region}` | `CALCULATE([M], ALLEXCEPT(T, T[Year], T[Region]))` | Multiple dimensions |

### Derived / OLAP Metrics

| MicroStrategy | DAX | Notes |
|---------------|-----|-------|
| `Rank(Metric) {Attr}` | `RANKX(ALL(T[Attr]), [Metric])` | |
| `RunningSum(Metric) {Attr}` | Window function or VAR pattern | |
| `RunningAvg(Metric) {Attr}` | Window function or VAR pattern | |
| `RunningCount(Metric) {Attr}` | Window function or VAR pattern | |
| `MovingAvg(Metric, N) {Attr}` | `AVERAGEX(TOPN(N, ...))` | |
| `MovingSum(Metric, N) {Attr}` | `SUMX(TOPN(N, ...))` | |
| `Lag(Metric, N) {Attr}` | `OFFSET(Table, -N, ...)` | |
| `Lead(Metric, N) {Attr}` | `OFFSET(Table, N, ...)` | |
| `NTile(Metric, N) {Attr}` | RANKX-based NTILE pattern | |
| `OLAPRank(Metric) {Attr}` | `RANKX(ALL(T[Attr]), [Metric])` | |
| `FirstInRange(Metric)` | `FIRSTNONBLANK(...)` | |
| `LastInRange(Metric)` | `LASTNONBLANK(...)` | |

### Logic / Conditional

| MicroStrategy | DAX | Notes |
|---------------|-----|-------|
| `If(cond, a, b)` | `IF(cond, a, b)` | |
| `If(c1, a, c2, b, c)` | `IF(c1, a, IF(c2, b, c))` | Nested |
| `Case/When(expr, v1:r1, v2:r2, default)` | `SWITCH(expr, v1, r1, v2, r2, default)` | |
| `Case/When(TRUE, c1:r1, ...)` | `SWITCH(TRUE(), c1, r1, ...)` | Boolean case |
| `And(a, b)` | `a && b` | |
| `Or(a, b)` | `a \|\| b` | |
| `Not(a)` | `NOT(a)` | |
| `Between(x, a, b)` | `x >= a && x <= b` | |
| `In(x, list)` | `x IN {v1, v2, ...}` | |

### Null Handling

| MicroStrategy | DAX | Notes |
|---------------|-----|-------|
| `NullToZero(x)` | `IF(ISBLANK(x), 0, x)` | |
| `ZeroToNull(x)` | `IF(x = 0, BLANK(), x)` | |
| `IsNull(x)` | `ISBLANK(x)` | |
| `IsNotNull(x)` | `NOT(ISBLANK(x))` | |
| `Coalesce(a, b, ...)` | `COALESCE(a, b, ...)` | |

### String Functions

| MicroStrategy | DAX | Notes |
|---------------|-----|-------|
| `Concat(a, b)` | `CONCATENATE(a, b)` | |
| `ConcatAll(list, sep)` | `CONCATENATEX(Table, [Col], sep)` | |
| `Length(s)` | `LEN(s)` | |
| `SubStr(s, start, len)` | `MID(s, start, len)` | |
| `LeftStr(s, n)` | `LEFT(s, n)` | |
| `RightStr(s, n)` | `RIGHT(s, n)` | |
| `Trim(s)` | `TRIM(s)` | |
| `LTrim(s)` | `TRIM(s)` | No direct LTrim in DAX |
| `RTrim(s)` | `TRIM(s)` | No direct RTrim in DAX |
| `Upper(s)` | `UPPER(s)` | |
| `Lower(s)` | `LOWER(s)` | |
| `InitCap(s)` | Custom DAX expression | No built-in |
| `Position(substr, s)` | `SEARCH(substr, s)` | |
| `Replace(s, old, new)` | `SUBSTITUTE(s, old, new)` | |

### Date Functions

| MicroStrategy | DAX | Notes |
|---------------|-----|-------|
| `CurrentDate()` | `TODAY()` | |
| `CurrentDateTime()` | `NOW()` | |
| `Year(d)` | `YEAR(d)` | |
| `Month(d)` | `MONTH(d)` | |
| `Day(d)` | `DAY(d)` | |
| `Hour(d)` | `HOUR(d)` | |
| `Minute(d)` | `MINUTE(d)` | |
| `Second(d)` | `SECOND(d)` | |
| `DayOfWeek(d)` | `WEEKDAY(d)` | |
| `DayOfYear(d)` | `d - DATE(YEAR(d), 1, 1) + 1` | No direct DAX |
| `WeekOfYear(d)` | `WEEKNUM(d)` | |
| `Quarter(d)` | `QUARTER(d)` | |
| `DaysBetween(a, b)` | `DATEDIFF(a, b, DAY)` | |
| `MonthsBetween(a, b)` | `DATEDIFF(a, b, MONTH)` | |
| `YearsBetween(a, b)` | `DATEDIFF(a, b, YEAR)` | |
| `AddDays(d, n)` | `d + n` | |
| `AddMonths(d, n)` | `EDATE(d, n)` | |
| `MonthStartDate(d)` | `STARTOFMONTH(d)` | DAX time intelligence |
| `MonthEndDate(d)` | `ENDOFMONTH(d)` | DAX time intelligence |
| `YearStartDate(d)` | `STARTOFYEAR(d)` | DAX time intelligence |
| `YearEndDate(d)` | `ENDOFYEAR(d)` | DAX time intelligence |

### Math Functions

| MicroStrategy | DAX | Notes |
|---------------|-----|-------|
| `Abs(x)` | `ABS(x)` | |
| `Round(x, n)` | `ROUND(x, n)` | |
| `Ceiling(x)` | `CEILING(x, 1)` | |
| `Floor(x)` | `FLOOR(x, 1)` | |
| `Truncate(x, n)` | `TRUNC(x, n)` | |
| `Power(x, n)` | `POWER(x, n)` | |
| `Sqrt(x)` | `SQRT(x)` | |
| `Ln(x)` | `LN(x)` | |
| `Log(x)` | `LOG(x, 10)` | |
| `Log2(x)` | `LOG(x, 2)` | |
| `Exp(x)` | `EXP(x)` | |
| `Mod(x, n)` | `MOD(x, n)` | |
| `Int(x)` | `INT(x)` | |
| `Sign(x)` | `SIGN(x)` | |

### Apply Functions (SQL Passthrough)

| MicroStrategy | DAX | Notes |
|---------------|-----|-------|
| `ApplySimple("SQL", args)` | Manual review / best-effort | Database-specific SQL |
| `ApplyAgg("SQL", args)` | Manual review / best-effort | Aggregate SQL passthrough |
| `ApplyComparison("SQL", args)` | Manual review / best-effort | Comparison SQL passthrough |
| `ApplyLogic("SQL", args)` | Manual review / best-effort | Logic SQL passthrough |
| `ApplyOLAP("SQL", args)` | Manual review / best-effort | OLAP SQL passthrough |

**Common ApplySimple patterns with automatic conversion:**

| ApplySimple Pattern | DAX Conversion |
|---------------------|----------------|
| `ApplySimple("CASE WHEN #0 > 0 THEN 'Yes' ELSE 'No' END", Fact)` | `IF([Fact] > 0, "Yes", "No")` |
| `ApplySimple("COALESCE(#0, #1)", a, b)` | `COALESCE(a, b)` |
| `ApplySimple("NVL(#0, #1)", a, b)` | `COALESCE(a, b)` |
| `ApplySimple("DECODE(#0, val1, res1, default)", x)` | `SWITCH(x, val1, res1, default)` |
| `ApplySimple("CAST(#0 AS VARCHAR)", x)` | `FORMAT(x, "")` |
| `ApplySimple("EXTRACT(YEAR FROM #0)", d)` | `YEAR(d)` |
| `ApplySimple("TRUNC(#0)", x)` | `TRUNC(x)` |

---

## 🔐 Security Mapping

| MicroStrategy | Power BI | Notes |
|---------------|----------|-------|
| Security Filter (attribute-based) | RLS Role with DAX filter | `[Column] IN {"allowed_values"}` |
| Security Filter (metric qualification) | RLS Role with DAX expression | More complex filter logic |
| User/Group assignment | Role membership | Mapped via Azure AD groups |
| Connection-level security | Workspace permissions | Admin/Member/Contributor/Viewer |
| Object-level ACLs | Not directly mapped | Workspace + app permissions as proxy |

---

## 📋 Prompt → Slicer/Parameter Mapping

| MicroStrategy Prompt | Power BI Equivalent | Notes |
|---------------------|--------------------|----|
| Value Prompt (single) | What-if Parameter | Numeric parameter with default |
| Value Prompt (list) | Dropdown Slicer | Static list of values |
| Object Prompt (attribute) | Field Parameter | User selects which attribute to display |
| Object Prompt (metric) | Field Parameter | User selects which metric to display |
| Hierarchy Prompt | Hierarchy Slicer | Drill-down slicer |
| Expression Prompt | Not supported | Flag for manual review |
| Date Prompt | Date Range Slicer | Between slicer with calendar |
| Required Prompt | Slicer with default | Default value pre-selected |
| Optional Prompt | Slicer without default | All selected by default |

---

## 📐 Layout & Formatting

| MicroStrategy | Power BI | Notes |
|---------------|----------|-------|
| Dossier canvas (absolute position) | PBI canvas (1280×720 default) | Proportional scaling |
| Chapter | Page group (section) | |
| Page | Report page | |
| Panel Stack | Bookmark navigator | Tabs → bookmarks with toggle |
| Info Window | Tooltip page | Viz-in-tooltip |
| Custom color palette | Report theme JSON | Colors mapped |
| Font settings | Report theme JSON | Font family/size mapped |
| Threshold (background color) | Conditional formatting (background) | |
| Threshold (font color) | Conditional formatting (font color) | |
| Threshold (icon) | Conditional formatting (icon set) | |
| Threshold (data bar) | Conditional formatting (data bar) | |
| Grid banding | Table style (alternating rows) | |
| Grid totals (top/bottom) | Matrix subtotals | Position mapped |
| Number format (#,##0.00) | DAX FORMAT string | Direct mapping |
| Currency format ($#,##0) | DAX FORMAT string | Currency symbol preserved |
| Percentage format (0.0%) | DAX FORMAT string | Direct mapping |

---

## ⚠️ Known Gaps & Limitations

| MicroStrategy Feature | Status | Workaround |
|----------------------|--------|------------|
| Transaction Services (write-back) | ❌ Not supported | Use Power Apps embedded |
| HTML Container visualization | ⚠️ Approximated | Text box with warning |
| Custom visualization plugins | ❌ Not supported | Manual recreation |
| Distribution Services (subscriptions) | ❌ Not mapped | Configure PBI subscriptions manually |
| Prompted Intelligence Cubes | ⚠️ Partial | Static import from default prompt answers |
| Multi-source reports (multiple cubes) | ⚠️ Partial | Merged into single model with warnings |
| Custom color themes (CSS-based) | ⚠️ Partial | Basic colors mapped to PBI theme |
| Nested panel stacks | ⚠️ Approximated | Flattened to single bookmark level |
| ApplySimple with database-specific SQL | ⚠️ Best-effort | Common patterns converted, complex flagged |
| Derived metrics with OLAP functions | ⚠️ Partial | Common patterns (Rank, Running) handled; use `--ai-assist` for complex patterns |
| Object prompts with dynamic attributes | ⚠️ Approximated | Field parameter with static list |

---

## 🏭 Fabric-Native Mappings (v5.0+/v16.0+)

### Data Type Mapping — MSTR → Delta/Spark (50+ types)

| MicroStrategy Type | Spark/Delta Type | Notes |
|-------------------|------------------|-------|
| integer | IntegerType | |
| long | LongType | |
| real / double | DoubleType | |
| decimal | DecimalType(18,2) | |
| nVarChar / char | StringType | |
| date | DateType | |
| timestamp / datetime | TimestampType | |
| boolean | BooleanType | |
| binary | BinaryType | |
| smallint | ShortType | |
| bigDecimal | DecimalType(38,10) | |
| float | FloatType | |
| time | StringType | Stored as string |

### Expression Classification — Lakehouse vs DAX-only

| Expression Pattern | Classification | Destination |
|-------------------|----------------|-------------|
| Simple arithmetic (`a + b`, `a * b`) | `lakehouse` | PySpark `withColumn()` |
| String functions (`Upper`, `Lower`, `Trim`) | `lakehouse` | PySpark built-in functions |
| Date functions (`Year`, `Month`, `Day`) | `lakehouse` | PySpark `year()`, `month()`, etc. |
| CALCULATE with context transition | `dax_only` | DAX measure |
| Level metrics `{~+}`, `{^}`, `{!}` | `dax_only` | DAX CALCULATE + ALL/ALLEXCEPT |
| Window functions (Rank, Running) | `dax_only` | DAX RANKX / WINDOW |
| Cross-table references | `dax_only` | DAX with RELATED/RELATEDTABLE |

### Dataflow Gen2 Connector Templates

| Source Type | M Connector Template | Notes |
|------------|---------------------|-------|
| SQL Server | `Sql.Database(server, db)` | With native query support |
| PostgreSQL | `PostgreSQL.Database(server, db)` | |
| Oracle | `Oracle.Database(server)` | TNS/descriptor |
| MySQL | `MySQL.Database(server, db)` | |
| Snowflake | `Snowflake.Databases(account, wh)` | |
| BigQuery | `GoogleBigQuery.Database(project)` | |
| Freeform SQL | `Value.NativeQuery(source, sql)` | SQL passthrough |

### Scorecard → PBI Goals Mapping

| MicroStrategy | Power BI Goals | Notes |
|---------------|---------------|-------|
| Scorecard | Goals Scorecard | Container for objectives |
| Objective | Goal | Individual tracked metric |
| KPI current value | Goal current value | Metric value |
| KPI target | Goal target | Target value |
| KPI status (color) | Goal status icon | Red/Yellow/Green mapping |
| Perspective | Goal category/tag | Grouping mechanism |

### i18n Culture Mapping (v8.0+)

| Component | TMDL Artifact | Notes |
|----------|--------------|-------|
| Primary culture | `model.tmdl` → `culture:` + `sourceQueryCulture:` | e.g., `en-US` |
| Additional cultures | `cultures.tmdl` + `translations.tmdl` | Separate TMDL files per locale |
| RTL cultures | Visual x-coordinate mirroring + `textDirection: RTL` | Arabic, Hebrew, Farsi, Urdu |
| Format strings | Culture-specific currency, date, number patterns | 30+ locales supported |

### Streaming/Real-Time Mapping (v9.0+)

| MicroStrategy | Power BI / Fabric | Notes |
|---------------|------------------|-------|
| Auto-refresh cache (≤1min) | Push Dataset (REST API) | Real-time streaming |
| Subscription-based refresh | Eventstream (Fabric RTI) | Event-driven |
| Scheduled cache refresh | Dataset Refresh Schedule | Time-slot based |
| Manual refresh | On-demand refresh | User-triggered |
