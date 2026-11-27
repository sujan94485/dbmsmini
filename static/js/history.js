document.addEventListener("DOMContentLoaded", () => {
    const dbStatusDot = document.getElementById("db-status-dot");
    const dbStatusName = document.getElementById("db-status-name");
    const dbStatusBadge = document.getElementById("db-status-badge");
    const historyCountBadge = document.getElementById("history-count-badge");
    const historyErrorBanner = document.getElementById("history-error-banner");
    const historyListEl = document.getElementById("history-list");
    const refreshHistoryBtn = document.getElementById("refresh-history-btn");

    function setDbStatusIndicator(connected, dbName) {
        dbStatusDot.classList.remove("status-ready", "status-pending", "status-error");
        dbStatusBadge.classList.remove("ready", "pending", "error");

        if (connected) {
            dbStatusDot.classList.add("status-ready");
            dbStatusBadge.classList.add("ready");
            dbStatusBadge.textContent = "Connected";
            dbStatusName.textContent = dbName || "MySQL";
        } else {
            dbStatusDot.classList.add("status-error");
            dbStatusBadge.classList.add("error");
            dbStatusBadge.textContent = "Offline";
            dbStatusName.textContent = dbName ? `${dbName} (unreachable)` : "Connection failed";
        }
    }

    function showError(message) {
        historyErrorBanner.textContent = message;
        historyErrorBanner.classList.remove("hidden");
    }

    function clearError() {
        historyErrorBanner.textContent = "";
        historyErrorBanner.classList.add("hidden");
    }

    function renderEmptyState(title, description) {
        historyListEl.innerHTML = "";
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
        historyListEl.appendChild(emptyDiv);
    }

    function getStatusClass(statusText) {
        const lower = (statusText || "").toLowerCase();
        if (lower.startsWith("success") || lower.startsWith("empty")) {
            return "success";
        }
        if (lower.includes("error") || lower.includes("fail")) {
            return "error";
        }
        return "neutral";
    }

    function renderHistoryItems(items) {
        historyListEl.innerHTML = "";

        if (!items || items.length === 0) {
            renderEmptyState(
                "No query history found",
                "Generate and execute a SQL query on the dashboard to see it recorded here."
            );
            return;
        }

        items.forEach((item) => {
            const card = document.createElement("article");
            card.className = "history-item";

            const header = document.createElement("div");
            header.className = "history-item-header";

            const infoDiv = document.createElement("div");
            const questionP = document.createElement("p");
            questionP.className = "history-question";
            questionP.textContent = item.natural_language_question;

            const metaDiv = document.createElement("div");
            metaDiv.className = "history-meta";

            const statusSpan = document.createElement("span");
            statusSpan.className = `history-status-pill ${getStatusClass(item.execution_status)}`;
            statusSpan.textContent = item.execution_status;

            const timeSpan = document.createElement("span");
            timeSpan.textContent = item.created_at ? `Saved: ${item.created_at}` : "";

            const idSpan = document.createElement("span");
            idSpan.textContent = `#${item.history_id}`;

            metaDiv.appendChild(statusSpan);
            if (item.created_at) {
                metaDiv.appendChild(timeSpan);
            }
            metaDiv.appendChild(idSpan);

            infoDiv.appendChild(questionP);
            infoDiv.appendChild(metaDiv);

            const actionsDiv = document.createElement("div");
            actionsDiv.className = "history-actions";

            const viewSqlBtn = document.createElement("button");
            viewSqlBtn.type = "button";
            viewSqlBtn.className = "btn btn-secondary btn-sm";
            viewSqlBtn.textContent = "View SQL";

            const reuseBtn = document.createElement("button");
            reuseBtn.type = "button";
            reuseBtn.className = "btn btn-primary btn-sm";
            reuseBtn.textContent = "Reuse Question";

            actionsDiv.appendChild(viewSqlBtn);
            actionsDiv.appendChild(reuseBtn);

            header.appendChild(infoDiv);
            header.appendChild(actionsDiv);
            card.appendChild(header);

            const sqlBox = document.createElement("div");
            sqlBox.className = "history-sql-box hidden";

            const pre = document.createElement("pre");
            pre.className = "sql-preview";
            const code = document.createElement("code");
            code.textContent = item.generated_sql;
            pre.appendChild(code);
            sqlBox.appendChild(pre);
            card.appendChild(sqlBox);

            viewSqlBtn.addEventListener("click", () => {
                const isHidden = sqlBox.classList.toggle("hidden");
                viewSqlBtn.textContent = isHidden ? "View SQL" : "Hide SQL";
            });

            reuseBtn.addEventListener("click", () => {
                const params = new URLSearchParams({
                    question: item.natural_language_question || "",
                });
                window.location.href = `/?${params.toString()}`;
            });

            historyListEl.appendChild(card);
        });
    }

    async function loadStatus() {
        try {
            const res = await fetch("/api/db-status");
            const data = await res.json();
            setDbStatusIndicator(data.connected, data.database);
        } catch (err) {
            setDbStatusIndicator(false, "");
        }
    }

    async function loadHistory() {
        clearError();
        historyCountBadge.textContent = "Loading...";

        try {
            const res = await fetch("/api/history");
            const data = await res.json();

            if (!res.ok || !data.success) {
                historyCountBadge.textContent = "Unavailable";
                showError(data.error || "Unable to retrieve query history.");
                renderEmptyState(
                    "Query History unavailable",
                    "Ensure create_history_user.sql has been executed and DB_HISTORY_USER / DB_HISTORY_PASSWORD are set in .env."
                );
                return;
            }

            const count = data.count || 0;
            historyCountBadge.textContent = `${count} ${count === 1 ? "query" : "queries"}`;
            renderHistoryItems(data.items || []);
        } catch (err) {
            historyCountBadge.textContent = "Error";
            showError("Network error while contacting /api/history.");
            renderEmptyState("Backend unreachable", "Could not reach the Flask server.");
        }
    }

    refreshHistoryBtn.addEventListener("click", () => {
        loadStatus();
        loadHistory();
    });

    loadStatus();
    loadHistory();
});
