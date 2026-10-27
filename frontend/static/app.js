
const titles = {
    overview: ["Overview Dashboard", "Real-time disaster recovery infrastructure monitoring"],
    api: ["API Explorer", "Test your CloudGuardians REST APIs"],
    chaos: ["Chaos Engineering", "Controlled disaster recovery experiments"],
    monitoring: ["Monitoring", "Live infrastructure status and events"],
    replication: ["Data Replication", "Inspect replicated application data"],
    results: ["Test Results", "Recovery measurements and experiment results"]
};

let lastStatus = null;

function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
}

function formatSeconds(value) {
    if (value === null || value === undefined || value === "") {
        return "Not measured";
    }

    const number = Number(value);
    return Number.isFinite(number)
        ? `${number.toFixed(2)} s`
        : "Not measured";
}

function showJSON(id, data) {
    setText(id, JSON.stringify(data, null, 2));
}

async function requestJSON(url, options = {}) {
    const response = await fetch(url, {
        cache: "no-store",
        ...options
    });

    const text = await response.text();
    let data;

    try {
        data = JSON.parse(text);
    } catch {
        throw new Error(`Invalid server response (${response.status})`);
    }

    if (!response.ok) {
        throw new Error(data.details || data.error || `HTTP ${response.status}`);
    }

    return data;
}

function updateDashboard(status) {
    lastStatus = status;

    const active = String(status.active_region || "unknown").toLowerCase();

    setText("active-region", active.toUpperCase());
    setText("failures", status.primary_failures ?? "—");
    setText("recoveries", status.primary_recoveries ?? "—");
    setText("rto", formatSeconds(status.rto_seconds));
    setText("last-event", status.last_event || "No event reported");
    setText("recovery-time", formatSeconds(status.recovery_detection_seconds));

    setText("result-rto", formatSeconds(status.rto_seconds));
    setText("result-recovery", formatSeconds(status.recovery_detection_seconds));
    setText("result-failures", status.primary_failures ?? 0);
    setText("result-recoveries", status.primary_recoveries ?? 0);

    const primaryBadge = document.getElementById("primary-role");
    const secondaryBadge = document.getElementById("secondary-role");

    primaryBadge.classList.remove("selected");
    secondaryBadge.classList.remove("selected");

    if (active === "primary") {
        primaryBadge.textContent = "ACTIVE";
        primaryBadge.classList.add("selected");
        secondaryBadge.textContent = "STANDBY";
    } else if (active === "secondary") {
        primaryBadge.textContent = "INACTIVE ROUTE";
        secondaryBadge.textContent = "ACTIVE";
        secondaryBadge.classList.add("selected");
    } else {
        primaryBadge.textContent = "UNKNOWN";
        secondaryBadge.textContent = "UNKNOWN";
    }

    showJSON("monitoring-response", status);

    const connection = document.getElementById("connection-badge");
    connection.textContent = "GATEWAY ONLINE";
    connection.className = "connection online";
}

function showOffline(error) {
    const connection = document.getElementById("connection-badge");
    connection.textContent = "GATEWAY OFFLINE";
    connection.className = "connection offline";

    setText("active-region", "OFFLINE");
    setText("last-event", `Unable to reach gateway: ${error.message}`);

    const primaryBadge = document.getElementById("primary-role");
    const secondaryBadge = document.getElementById("secondary-role");

    primaryBadge.textContent = "UNKNOWN";
    secondaryBadge.textContent = "UNKNOWN";
    primaryBadge.classList.remove("selected");
    secondaryBadge.classList.remove("selected");

    showJSON("monitoring-response", {
        error: error.message
    });
}

async function refreshDashboard() {
    try {
        const status = await requestJSON("/api/status");
        updateDashboard(status);
    } catch (error) {
        showOffline(error);
    }
}

async function testAPI(endpoint) {
    setText("api-response", "Sending request...");

    try {
        const data = await requestJSON(endpoint);
        showJSON("api-response", data);
    } catch (error) {
        showJSON("api-response", {
            error: error.message
        });
    }
}

async function writeData() {
    const input = document.getElementById("write-message");
    const message = input.value.trim();

    if (!message) {
        showJSON("api-response", {
            error: "Please enter a message before writing."
        });
        return;
    }

    setText("api-response", "Writing data...");

    try {
        const data = await requestJSON("/api/write", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message })
        });

        showJSON("api-response", data);
        input.value = "";
    } catch (error) {
        showJSON("api-response", {
            error: error.message
        });
    }
}

async function loadReplication() {
    setText("replication-response", "Loading records...");

    try {
        const data = await requestJSON("/api/data");
        showJSON("replication-response", data);
    } catch (error) {
        showJSON("replication-response", {
            error: error.message
        });
    }
}

function navigateTo(pageName) {
    document.querySelectorAll(".page").forEach(page => {
        page.classList.toggle("active", page.id === pageName);
    });

    document.querySelectorAll(".nav-item").forEach(button => {
        button.classList.toggle(
            "active",
            button.dataset.page === pageName
        );
    });

    const [title, subtitle] = titles[pageName];

    setText("page-title", title);
    setText("page-subtitle", subtitle);

    if (pageName === "monitoring" || pageName === "results") {
        refreshDashboard();
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelectorAll(".nav-item").forEach(button => {
    button.addEventListener("click", () => {
        navigateTo(button.dataset.page);
    });
});

refreshDashboard();

// Refresh live gateway status every 3 seconds.
setInterval(refreshDashboard, 3000);
