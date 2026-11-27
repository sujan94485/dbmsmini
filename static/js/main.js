document.addEventListener("DOMContentLoaded", () => {
    // Phase 1, 3, 4 & 5: Natural Language Query UI, Gemini SQL, Execution & CSV Export
    const queryInput = document.getElementById("nl-query-input");
    const generateBtn = document.getElementById("generate-sql-btn");
    const executeBtn = document.getElementById("execute-sql-btn");
    const exportCsvBtn = document.getElementById("export-csv-btn");
    const clearBtn = document.getElementById("clear-btn");
    const uiNotice = document.getElementById("ui-notice");
    const generatedSqlCode = document.getElementById("generated-sql-code");
    const sqlStatusBadge = document.getElementById("sql-status-badge");
    const resultsMetaBadge = document.getElementById("results-meta-badge");
    const queryResultsError = document.getElementById("query-results-error");
    const queryResultsTruncation = document.getElementById("query-results-truncation");
    const queryResultsBody = document.getElementById("query-results-body");
    const sampleChips = document.querySelectorAll(".sample-chip");

    const defaultNotice = "Enter a question above and click Generate SQL.";
    const defaultSqlPlaceholder = "-- Generated SQL will appear here when you click Generate SQL.";
    let currentGeneratedSql = "";
    let currentQuestion = "";
    let currentHistoryId = null;
    let currentQueryResult = null;

    // CSV formula-injection neutralization and RFC-4180 quoting
    function sanitizeCsvCell(value) {
        if (value === null || value === undefined) {
            return "";
        }
        let text = String(value);
        if (/^[=+\-@\t\r]/.test(text)) {
            text = `'${text}`;
        }
        if (/[",\n\r]/.test(text)) {
            text = `"${text.replace(/"/g, '""')}"`;
        }
        return text;
    }

    function buildCsvContent(columns, rows) {
        const headerLine = columns.map(sanitizeCsvCell).join(",");
        const dataLines = rows.map((row) => row.map(sanitizeCsvCell).join(","));
        return `\uFEFF${[headerLine, ...dataLines].join("\r\n")}`;
    }

    function buildCsvFilename() {
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const stamp = [
            now.getFullYear(),
            pad(now.getMonth() + 1),
            pad(now.getDate()),
        ].join("-") + "_" + [
            pad(now.getHours()),
            pad(now.getMinutes()),
            pad(now.getSeconds()),
        ].join("-");
        return `query_results_${stamp}.csv`;
    }

    function setNotice(message, type = "default") {
        uiNotice.textContent = message;
        uiNotice.classList.remove("active", "error");
        if (type === "active") {
            uiNotice.classList.add("active");
        } else if (type === "error") {
            uiNotice.classList.add("error");
        }
    }

    function renderQueryEmptyState(title, description) {
        queryResultsBody.innerHTML = "";
        const emptyDiv = document.createElement("div");
        emptyDiv.className = "empty-state";

        const titleP = document.createElement("p");
        titleP.className = "empty-title";
        titleP.textContent = title;

        const descP = document.createElement("p");
        descP.className = "empty-desc";
        descP.textContent = description;

        emptyDiv.appendChild(titleP);
        emptyDiv.appendChild(descP);
        queryResultsBody.appendChild(emptyDiv);
    }

    function clearQueryResultsFeedback() {
        queryResultsError.textContent = "";
        queryResultsError.classList.add("hidden");
        queryResultsTruncation.textContent = "";
        queryResultsTruncation.classList.add("hidden");
    }

    function renderQueryResultsTable(columns, rows) {
        queryResultsBody.innerHTML = "";

        const wrapper = document.createElement("div");
        wrapper.className = "records-table-wrapper";

        const table = document.createElement("table");
        table.className = "data-table";

        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");
        columns.forEach((colName) => {
            const th = document.createElement("th");
            th.textContent = colName;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");
        rows.forEach((row) => {
            const tr = document.createElement("tr");
            row.forEach((cell) => {
                const td = document.createElement("td");
                td.textContent = cell === null || cell === undefined ? "NULL" : String(cell);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);

        wrapper.appendChild(table);
        queryResultsBody.appendChild(wrapper);
    }

    sampleChips.forEach((chip) => {
        chip.addEventListener("click", () => {
            const sampleText = chip.getAttribute("data-query") || "";
            queryInput.value = sampleText;
            queryInput.focus();
            setNotice("Sample question loaded. Click Generate SQL when ready.", "active");
        });
    });

    clearBtn.addEventListener("click", () => {
        queryInput.value = "";
        currentGeneratedSql = "";
        currentQuestion = "";
        currentHistoryId = null;
        currentQueryResult = null;
        executeBtn.disabled = true;
        exportCsvBtn.disabled = true;
        generatedSqlCode.textContent = defaultSqlPlaceholder;
        sqlStatusBadge.textContent = "Preview";
        resultsMetaBadge.textContent = "MySQL Output";
        clearQueryResultsFeedback();
        renderQueryEmptyState(
            "No results to display yet",
            "Generate a SQL query first, then click Execute Query to view live MySQL results."
        );
        setNotice(defaultNotice);
        queryInput.focus();
    });

    generateBtn.addEventListener("click", async () => {
        const question = queryInput.value.trim();
        if (!question) {
            setNotice("Please enter a natural language question first.", "error");
            queryInput.focus();
            return;
        }

        currentGeneratedSql = "";
        currentQuestion = question;
        currentHistoryId = null;
        executeBtn.disabled = true;
        generateBtn.disabled = true;
        generateBtn.textContent = "Generating...";
        sqlStatusBadge.textContent = "Generating...";
        generatedSqlCode.textContent = "-- Generating SQL query using Gemini AI...";
        setNotice("Sending question and schema to Gemini AI...", "active");

        try {
            const response = await fetch("/api/generate-sql", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ question }),
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                const errMsg = data.error || "Failed to generate SQL query.";
                sqlStatusBadge.textContent = "Error";
                generatedSqlCode.textContent = `-- Error: ${errMsg}`;
                setNotice(errMsg, "error");
                return;
            }

            currentGeneratedSql = data.sql;
            currentQuestion = data.question || question;
            currentHistoryId = data.history_id ?? null;
            executeBtn.disabled = false;
            generatedSqlCode.textContent = data.sql;
            sqlStatusBadge.textContent = data.fallback_used
                ? `Generated (${data.model})`
                : "Generated";
            const noticeText = data.fallback_used
                ? `SQL generated using fallback model '${data.model}'. Click Execute Query to run it against MySQL.`
                : "SQL query generated successfully. Click Execute Query to run it against MySQL.";
            setNotice(noticeText, "active");
        } catch (err) {
            sqlStatusBadge.textContent = "Error";
            generatedSqlCode.textContent = "-- Network error while contacting the Flask server.";
            setNotice("Could not reach /api/generate-sql. Check that Flask is running.", "error");
        } finally {
            generateBtn.disabled = false;
            generateBtn.textContent = "Generate SQL";
        }
    });

    executeBtn.addEventListener("click", async () => {
        if (!currentGeneratedSql) {
            setNotice("Generate a SQL query first before executing.", "error");
            return;
        }

        clearQueryResultsFeedback();
        currentQueryResult = null;
        exportCsvBtn.disabled = true;
        executeBtn.disabled = true;
        executeBtn.textContent = "Executing...";
        resultsMetaBadge.textContent = "Running...";
        renderQueryEmptyState("Executing query...", "Running validated read-only SQL against college_db.");
        setNotice("Executing read-only SQL query against MySQL...", "active");

        try {
            const response = await fetch("/api/execute-sql", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    sql: currentGeneratedSql,
                    question: currentQuestion || queryInput.value.trim(),
                    history_id: currentHistoryId,
                }),
            });

            const data = await response.json();
            if (data.history_id !== undefined && data.history_id !== null) {
                currentHistoryId = data.history_id;
            }

            if (!response.ok || !data.success) {
                const errMsg = data.error || "Failed to execute SQL query.";
                resultsMetaBadge.textContent = "Error";
                queryResultsError.textContent = errMsg;
                queryResultsError.classList.remove("hidden");
                renderQueryEmptyState("Query execution failed", "Review the error message above.");
                setNotice(errMsg, "error");
                return;
            }

            const rowLabel = data.row_count === 1 ? "row" : "rows";
            resultsMetaBadge.textContent = `${data.row_count} ${rowLabel} • ${data.execution_time}s`;

            if (data.truncated) {
                queryResultsTruncation.textContent = `Showing the first ${data.max_rows} rows (results were truncated).`;
                queryResultsTruncation.classList.remove("hidden");
            }

            if (!data.rows || data.rows.length === 0) {
                renderQueryEmptyState(
                    "No matching records found",
                    "The query executed successfully against college_db, but returned 0 rows."
                );
                setNotice(`Query executed in ${data.execution_time}s (0 rows returned).`, "active");
                return;
            }

            currentQueryResult = {
                columns: data.columns || [],
                rows: data.rows || [],
            };
            exportCsvBtn.disabled = currentQueryResult.columns.length === 0 || currentQueryResult.rows.length === 0;

            renderQueryResultsTable(data.columns, data.rows);
            setNotice(
                `Query executed in ${data.execution_time}s (${data.row_count} ${rowLabel} returned).`,
                "active"
            );
        } catch (err) {
            resultsMetaBadge.textContent = "Error";
            queryResultsError.textContent = "Network error while contacting /api/execute-sql.";
            queryResultsError.classList.remove("hidden");
            renderQueryEmptyState("Execution failed", "Could not reach the Flask server.");
            setNotice("Could not reach /api/execute-sql. Check that Flask is running.", "error");
        } finally {
            executeBtn.disabled = !currentGeneratedSql;
            executeBtn.textContent = "Execute Query";
        }
    });

    exportCsvBtn.addEventListener("click", () => {
        if (!currentQueryResult || !currentQueryResult.columns.length || !currentQueryResult.rows.length) {
            setNotice("No query results available to export.", "error");
            return;
        }

        const csvContent = buildCsvContent(currentQueryResult.columns, currentQueryResult.rows);
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = buildCsvFilename();
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        setNotice("Exported displayed query results to CSV.", "active");
    });

    // Support reusing a question from /history via ?question=...
    const urlParams = new URLSearchParams(window.location.search);
    const reusedQuestion = urlParams.get("question");
    if (reusedQuestion && reusedQuestion.trim()) {
        queryInput.value = reusedQuestion.trim();
        queryInput.focus();
        setNotice("Loaded question from Query History. Click Generate SQL to run it.", "active");
    }

    // Phase 2: MySQL Status & Database Explorer
    const dbStatusDot = document.getElementById("db-status-dot");
    const dbStatusName = document.getElementById("db-status-name");
    const dbStatusBadge = document.getElementById("db-status-badge");
    const explorerDbName = document.getElementById("explorer-db-name");
    const refreshDbBtn = document.getElementById("refresh-db-btn");
    const dbErrorBanner = document.getElementById("db-error-banner");
    const tableListEl = document.getElementById("table-list");
    const schemaDetailsEl = document.getElementById("schema-details");
    const schemaTableLabel = document.getElementById("selected-table-schema-label");
    const recordsTableLabel = document.getElementById("selected-table-records-label");
    const recordsCountBadge = document.getElementById("records-count-badge");
    const recordsContainer = document.getElementById("table-records-container");

    let schemaCache = [];
    let selectedTableName = null;

    function showDbError(message) {
        dbErrorBanner.textContent = message;
        dbErrorBanner.classList.remove("hidden");
    }

    function clearDbError() {
        dbErrorBanner.textContent = "";
        dbErrorBanner.classList.add("hidden");
    }

    function setDbStatusIndicator(connected, dbName, errorMsg) {
        dbStatusDot.classList.remove("status-ready", "status-pending", "status-error");
        dbStatusBadge.classList.remove("ready", "pending", "error");

        if (connected) {
            dbStatusDot.classList.add("status-ready");
            dbStatusBadge.classList.add("ready");
            dbStatusBadge.textContent = "Connected";
            dbStatusName.textContent = dbName || "MySQL";
            explorerDbName.textContent = `DB: ${dbName || "MySQL"}`;
        } else {
            dbStatusDot.classList.add("status-error");
            dbStatusBadge.classList.add("error");
            dbStatusBadge.textContent = "Offline";
            dbStatusName.textContent = dbName ? `${dbName} (unreachable)` : "Connection failed";
            explorerDbName.textContent = `DB: ${dbName || "--"}`;
            if (errorMsg) {
                showDbError(`MySQL Connection Error: ${errorMsg}`);
            }
        }
    }

    function renderEmptyRecords(title, description) {
        recordsContainer.innerHTML = "";
        const emptyDiv = document.createElement("div");
        emptyDiv.className = "empty-state";

        const titleP = document.createElement("p");
        titleP.className = "empty-title";
        titleP.textContent = title;

        const descP = document.createElement("p");
        descP.className = "empty-desc";
        descP.textContent = description;

        emptyDiv.appendChild(titleP);
        emptyDiv.appendChild(descP);
        recordsContainer.appendChild(emptyDiv);
    }

    function renderSchemaDetails(tableObj) {
        schemaDetailsEl.innerHTML = "";
        schemaTableLabel.textContent = tableObj ? tableObj.name : "";

        if (!tableObj || !tableObj.columns || tableObj.columns.length === 0) {
            const p = document.createElement("p");
            p.className = "muted-placeholder";
            p.textContent = "No column metadata available.";
            schemaDetailsEl.appendChild(p);
            return;
        }

        tableObj.columns.forEach((col) => {
            const item = document.createElement("div");
            item.className = "schema-col-item";

            const top = document.createElement("div");
            top.className = "schema-col-top";

            const nameSpan = document.createElement("span");
            nameSpan.className = "schema-col-name";
            nameSpan.textContent = col.name;

            const typeSpan = document.createElement("span");
            typeSpan.className = "schema-col-type";
            typeSpan.textContent = col.column_type || col.data_type;

            top.appendChild(nameSpan);
            top.appendChild(typeSpan);
            item.appendChild(top);

            if (col.is_primary_key || col.is_foreign_key) {
                const badges = document.createElement("div");
                badges.className = "schema-badges";

                if (col.is_primary_key) {
                    const pkBadge = document.createElement("span");
                    pkBadge.className = "key-badge key-pk";
                    pkBadge.textContent = "PK";
                    badges.appendChild(pkBadge);
                }

                if (col.is_foreign_key) {
                    const fkBadge = document.createElement("span");
                    fkBadge.className = "key-badge key-fk";
                    fkBadge.textContent = col.references ? `FK -> ${col.references}` : "FK";
                    badges.appendChild(fkBadge);
                }

                item.appendChild(badges);
            }

            schemaDetailsEl.appendChild(item);
        });
    }

    function renderRecordsTable(columns, rows) {
        recordsContainer.innerHTML = "";

        if (!rows || rows.length === 0) {
            renderEmptyRecords("No records found", "This table currently contains 0 rows.");
            return;
        }

        const table = document.createElement("table");
        table.className = "data-table";

        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");
        columns.forEach((colName) => {
            const th = document.createElement("th");
            th.textContent = colName;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");
        rows.forEach((row) => {
            const tr = document.createElement("tr");
            row.forEach((cell) => {
                const td = document.createElement("td");
                td.textContent = cell === null || cell === undefined ? "NULL" : String(cell);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);

        recordsContainer.appendChild(table);
    }

    async function selectTable(tableName) {
        selectedTableName = tableName;

        // Highlight active table button
        const buttons = tableListEl.querySelectorAll(".table-btn");
        buttons.forEach((btn) => {
            btn.classList.toggle("active", btn.dataset.table === tableName);
        });

        const tableObj = schemaCache.find((t) => t.name === tableName);
        renderSchemaDetails(tableObj);

        recordsTableLabel.textContent = tableName;
        recordsCountBadge.textContent = "Loading...";
        renderEmptyRecords("Loading records...", `Fetching rows from '${tableName}'.`);

        try {
            const res = await fetch(`/api/db/tables/${encodeURIComponent(tableName)}`);
            const data = await res.json();

            if (!res.ok) {
                recordsCountBadge.textContent = "Error";
                showDbError(data.error || `Failed to load records for '${tableName}'.`);
                renderEmptyRecords("Unable to load records", data.error || "Check MySQL connection.");
                return;
            }

            recordsCountBadge.textContent = `${data.row_count} ${data.row_count === 1 ? "row" : "rows"}`;
            renderRecordsTable(data.columns, data.rows);
        } catch (err) {
            recordsCountBadge.textContent = "Error";
            showDbError("Network error while fetching table records.");
            renderEmptyRecords("Unable to load records", "Could not reach the Flask backend.");
        }
    }

    function renderTableList(tables) {
        tableListEl.innerHTML = "";

        if (!tables || tables.length === 0) {
            const p = document.createElement("p");
            p.className = "muted-placeholder";
            p.textContent = "No tables found in this database.";
            tableListEl.appendChild(p);
            renderSchemaDetails(null);
            renderEmptyRecords("No tables available", "Run database.sql in MySQL to create tables and sample records.");
            return;
        }

        tables.forEach((table) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "table-btn";
            btn.dataset.table = table.name;

            const nameSpan = document.createElement("span");
            nameSpan.textContent = table.name;

            const countSpan = document.createElement("span");
            countSpan.className = "table-col-count";
            countSpan.textContent = `${table.columns.length} cols`;

            btn.appendChild(nameSpan);
            btn.appendChild(countSpan);

            btn.addEventListener("click", () => selectTable(table.name));
            tableListEl.appendChild(btn);
        });

        const initialTable = tables.some((t) => t.name === selectedTableName)
            ? selectedTableName
            : tables[0].name;
        selectTable(initialTable);
    }

    async function loadDatabaseExplorer() {
        clearDbError();
        tableListEl.innerHTML = '<p class="muted-placeholder">Loading tables...</p>';

        try {
            const statusRes = await fetch("/api/db-status");
            const statusData = await statusRes.json();
            setDbStatusIndicator(statusData.connected, statusData.database, statusData.error);

            if (!statusData.connected) {
                tableListEl.innerHTML = '<p class="muted-placeholder">Unavailable while MySQL is offline.</p>';
                schemaDetailsEl.innerHTML = '<p class="muted-placeholder">Connect MySQL and click Refresh.</p>';
                recordsCountBadge.textContent = "Offline";
                renderEmptyRecords(
                    "MySQL is not connected",
                    "Ensure MySQL is running, database.sql has been executed, and your .env credentials are configured."
                );
                return;
            }

            const schemaRes = await fetch("/api/db/schema");
            const schemaData = await schemaRes.json();

            if (!schemaRes.ok) {
                showDbError(schemaData.error || "Unable to fetch database schema.");
                return;
            }

            explorerDbName.textContent = `DB: ${schemaData.database}`;
            schemaCache = schemaData.tables || [];
            renderTableList(schemaCache);
        } catch (err) {
            setDbStatusIndicator(false, "", "Failed to reach /api/db-status.");
            renderEmptyRecords("Backend unreachable", "Could not connect to the Flask server.");
        }
    }

    refreshDbBtn.addEventListener("click", loadDatabaseExplorer);
    loadDatabaseExplorer();
});
