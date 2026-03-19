# MicroStrategy Expression → DAX Reference

Complete mapping of MicroStrategy metric expressions to DAX equivalents.

## Aggregation Functions

| MicroStrategy | DAX | Example |
|---------------|-----|---------|
| `Sum(Fact)` | `SUM(Table[Column])` | `Sum(Revenue)` → `SUM(Sales[Revenue])` |
| `Avg(Fact)` | `AVERAGE(Table[Column])` | `Avg(Cost)` → `AVERAGE(Products[Cost])` |
| `Count(Attr)` | `COUNT(Table[Column])` | `Count(Customer)` → `COUNT(Customers[CustomerID])` |
| `Count(Distinct Attr)` | `DISTINCTCOUNT(Table[Column])` | `Count(Distinct Customer)` → `DISTINCTCOUNT(Customers[CustomerID])` |
| `Min(Fact)` | `MIN(Table[Column])` | |
| `Max(Fact)` | `MAX(Table[Column])` | |
| `StDev(Fact)` | `STDEV.S(Table[Column])` | Sample std dev |
| `StDevP(Fact)` | `STDEV.P(Table[Column])` | Population std dev |
| `Var(Fact)` | `VAR.S(Table[Column])` | |
| `VarP(Fact)` | `VAR.P(Table[Column])` | |
| `Median(Fact)` | `MEDIAN(Table[Column])` | |
| `Percentile(Fact, p)` | `PERCENTILEX.INC(Table, Table[Column], p)` | |
| `Product(Fact)` | `PRODUCTX(Table, Table[Column])` | |
| `GeoMean(Fact)` | `GEOMEANX(Table, Table[Column])` | |

## Level Metrics (Dimensionality)

Level metrics control the grain at which a metric is calculated, independent of the report's drill level.

| MicroStrategy | DAX | Explanation |
|---------------|-----|-------------|
| `Sum(Revenue) {~+, Year}` | `CALCULATE(SUM(Sales[Revenue]), ALLEXCEPT(Sales, Sales[Year]))` | Calculate at Year level, regardless of report detail |
| `Sum(Revenue) {~, Region}` | `CALCULATE(SUM(Sales[Revenue]), ALLEXCEPT(Sales, Sales[Region]))` | Exact Region level |
| `Sum(Revenue) {Year, Region}` | `CALCULATE(SUM(Sales[Revenue]), ALLEXCEPT(Sales, Sales[Year], Sales[Region]))` | Year + Region level |
| `Sum(Revenue) {!Region}` | `CALCULATE(SUM(Sales[Revenue]), REMOVEFILTERS(Sales[Region]))` | Ignore Region filter |
| `Sum(Revenue) {^}` | `CALCULATE(SUM(Sales[Revenue]), ALL(Sales))` | Report-level total (grand total) |
| `Revenue / Sum(Revenue) {^}` | `DIVIDE([Revenue], CALCULATE([Revenue], ALL(Sales)))` | Percent of total |

## Derived / OLAP Metrics

| MicroStrategy | DAX | Notes |
|---------------|-----|-------|
| `Rank(Revenue) {Month}` | `RANKX(ALL(Calendar[Month]), [Revenue])` | Dense rank by default |
| `Rank(Revenue, ASC) {Month}` | `RANKX(ALL(Calendar[Month]), [Revenue], , ASC)` | Ascending rank |
| `RunningSum(Revenue) {Month}` | `VAR __tbl = ALLSELECTED(Calendar[Month])` ... WINDOW pattern | Running cumulative sum |
| `RunningAvg(Revenue) {Month}` | Window pattern similar to RunningSum | Running average |
| `RunningCount(Revenue) {Month}` | Window pattern | Running count |
| `MovingAvg(Revenue, 3) {Month}` | `AVERAGEX(TOPN(3, ALL(Calendar[Month]), Calendar[Month], DESC), [Revenue])` | 3-period moving average |
| `MovingSum(Revenue, 6) {Month}` | `SUMX(TOPN(6, ALL(Calendar[Month]), Calendar[Month], DESC), [Revenue])` | 6-period moving sum |
| `Lag(Revenue, 1) {Month}` | `OFFSET([Revenue], -1, Calendar, ORDERBY(Calendar[Month]))` | Previous period value |
| `Lead(Revenue, 1) {Month}` | `OFFSET([Revenue], 1, Calendar, ORDERBY(Calendar[Month]))` | Next period value |
| `NTile(Revenue, 4) {Region}` | RANKX-based quartile pattern | Break into N groups |
| `OLAPRank(Revenue) {Month}` | `RANKX(ALL(Calendar[Month]), [Revenue])` | Same as Rank |
| `FirstInRange(Revenue) {Month}` | `FIRSTNONBLANK(Calendar[Month], [Revenue])` | First non-blank value |
| `LastInRange(Revenue) {Month}` | `LASTNONBLANK(Calendar[Month], [Revenue])` | Last non-blank value |

## Conditional Logic

| MicroStrategy | DAX | Example |
|---------------|-----|---------|
| `If(Revenue > 1000, "High", "Low")` | `IF([Revenue] > 1000, "High", "Low")` | Simple if-else |
| `If(A > 100, "A", A > 50, "B", "C")` | `IF([A] > 100, "A", IF([A] > 50, "B", "C"))` | Nested conditions |
| `Case(Status, 1, "Active", 2, "Inactive", "Unknown")` | `SWITCH([Status], 1, "Active", 2, "Inactive", "Unknown")` | Value-based switch |
| `Case(TRUE, Rev>1000, "High", Rev>500, "Med", "Low")` | `SWITCH(TRUE(), [Rev]>1000, "High", [Rev]>500, "Med", "Low")` | Boolean case |

## Null Handling

| MicroStrategy | DAX | Example |
|---------------|-----|---------|
| `NullToZero(Revenue)` | `IF(ISBLANK([Revenue]), 0, [Revenue])` | Replace null with 0 |
| `ZeroToNull(Quantity)` | `IF([Quantity] = 0, BLANK(), [Quantity])` | Replace 0 with blank |
| `IsNull(Value)` | `ISBLANK([Value])` | |
| `IsNotNull(Value)` | `NOT(ISBLANK([Value]))` | |
| `Coalesce(A, B, C)` | `COALESCE([A], [B], [C])` | First non-blank |

## String Functions

| MicroStrategy | DAX | Example |
|---------------|-----|---------|
| `Concat(First, " ", Last)` | `[First] & " " & [Last]` | Or `CONCATENATE()` |
| `ConcatAll(Name, ", ")` | `CONCATENATEX(Table, [Name], ", ")` | Aggregate concatenation |
| `Length(Name)` | `LEN([Name])` | |
| `SubStr(Name, 1, 3)` | `MID([Name], 1, 3)` | |
| `LeftStr(Code, 2)` | `LEFT([Code], 2)` | |
| `RightStr(Code, 4)` | `RIGHT([Code], 4)` | |
| `Trim(Name)` | `TRIM([Name])` | |
| `Upper(Name)` | `UPPER([Name])` | |
| `Lower(Name)` | `LOWER([Name])` | |
| `Position("abc", Name)` | `SEARCH("abc", [Name])` | 1-based position |
| `Replace(Name, "old", "new")` | `SUBSTITUTE([Name], "old", "new")` | |

## Date Functions

| MicroStrategy | DAX | Example |
|---------------|-----|---------|
| `CurrentDate()` | `TODAY()` | |
| `CurrentDateTime()` | `NOW()` | |
| `Year(OrderDate)` | `YEAR([OrderDate])` | |
| `Month(OrderDate)` | `MONTH([OrderDate])` | |
| `Day(OrderDate)` | `DAY([OrderDate])` | |
| `Hour(Timestamp)` | `HOUR([Timestamp])` | |
| `Minute(Timestamp)` | `MINUTE([Timestamp])` | |
| `Second(Timestamp)` | `SECOND([Timestamp])` | |
| `DayOfWeek(OrderDate)` | `WEEKDAY([OrderDate])` | |
| `WeekOfYear(OrderDate)` | `WEEKNUM([OrderDate])` | |
| `Quarter(OrderDate)` | `QUARTER([OrderDate])` | |
| `DaysBetween(Start, End)` | `DATEDIFF([Start], [End], DAY)` | |
| `MonthsBetween(Start, End)` | `DATEDIFF([Start], [End], MONTH)` | |
| `YearsBetween(Start, End)` | `DATEDIFF([Start], [End], YEAR)` | |
| `AddDays(Date, 30)` | `[Date] + 30` | |
| `AddMonths(Date, 6)` | `EDATE([Date], 6)` | |
| `MonthStartDate(Date)` | `STARTOFMONTH([Date])` | Time intelligence |
| `MonthEndDate(Date)` | `ENDOFMONTH([Date])` | Time intelligence |
| `YearStartDate(Date)` | `STARTOFYEAR([Date])` | Time intelligence |
| `YearEndDate(Date)` | `ENDOFYEAR([Date])` | Time intelligence |

## Math Functions

| MicroStrategy | DAX |
|---------------|-----|
| `Abs(x)` | `ABS(x)` |
| `Round(x, 2)` | `ROUND(x, 2)` |
| `Ceiling(x)` | `CEILING(x, 1)` |
| `Floor(x)` | `FLOOR(x, 1)` |
| `Truncate(x, 2)` | `TRUNC(x, 2)` |
| `Power(x, 3)` | `POWER(x, 3)` |
| `Sqrt(x)` | `SQRT(x)` |
| `Ln(x)` | `LN(x)` |
| `Log(x)` | `LOG(x, 10)` |
| `Log2(x)` | `LOG(x, 2)` |
| `Exp(x)` | `EXP(x)` |
| `Mod(x, 5)` | `MOD(x, 5)` |
| `Int(x)` | `INT(x)` |
| `Sign(x)` | `SIGN(x)` |

## Apply Functions (SQL Passthrough)

`ApplySimple`, `ApplyAgg`, `ApplyComparison`, `ApplyLogic`, and `ApplyOLAP` pass raw SQL to the database engine. The migration tool converts **common patterns** automatically:

| ApplySimple Pattern | DAX Equivalent |
|---------------------|----------------|
| `ApplySimple("CASE WHEN #0 > 0 THEN 'Yes' ELSE 'No' END", Revenue)` | `IF([Revenue] > 0, "Yes", "No")` |
| `ApplySimple("COALESCE(#0, #1)", A, B)` | `COALESCE([A], [B])` |
| `ApplySimple("NVL(#0, #1)", A, B)` | `COALESCE([A], [B])` |
| `ApplySimple("DECODE(#0, 1, 'A', 2, 'B', 'C')", Status)` | `SWITCH([Status], 1, "A", 2, "B", "C")` |
| `ApplySimple("CAST(#0 AS VARCHAR)", Num)` | `FORMAT([Num], "")` |
| `ApplySimple("EXTRACT(YEAR FROM #0)", Date)` | `YEAR([Date])` |
| `ApplySimple("TRUNC(#0)", x)` | `TRUNC([x])` |

**Complex ApplySimple patterns** that are database-specific (e.g., Oracle `CONNECT BY`, Teradata `QUALIFY`, database-specific window functions) are flagged as **manual review items** in the migration report.

## Banding Functions

| MicroStrategy | DAX |
|---------------|-----|
| `Band(Revenue, 0, 1000, 5000, 10000)` | `SWITCH(TRUE(), [Revenue] < 0, "< 0", [Revenue] < 1000, "0 - 999", [Revenue] < 5000, "1000 - 4999", [Revenue] < 10000, "5000 - 9999", ">= 10000")` |
| `BandNames(Revenue, "Low;Med;High", 0, 1000, 5000)` | `SWITCH(TRUE(), [Revenue] < 0, "Below", [Revenue] < 1000, "Low", [Revenue] < 5000, "Med", "High")` |
