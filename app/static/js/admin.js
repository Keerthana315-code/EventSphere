
const BASE_URL = "http://127.0.0.1:8000";

function adminHeaders() {
    const token = localStorage.getItem("access_token");

    return {
        "Authorization": `Bearer ${token}`
    };
}

async function adminRequest(endpoint) {
    const response = await fetch(BASE_URL + endpoint, {
        headers: adminHeaders()
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(data.detail || "Unable to load data");
    }

    return data;
}

// SIDEBAR NAVIGATION
document.querySelectorAll(".sidebar a[data-section]").forEach(link => {
    link.addEventListener("click", event => {
        event.preventDefault();

        document.querySelectorAll(".sidebar a").forEach(item => {
            item.classList.remove("active");
        });

        link.classList.add("active");

        document.querySelectorAll(".content-section").forEach(section => {
            section.classList.remove("active");
        });

        document.getElementById(link.dataset.section).classList.add("active");
    });
});

// LOAD EVENTS
async function loadAdminEvents() {
    const events = await adminRequest("/events/");

    document.getElementById("totalEvents").textContent = events.length;

    document.getElementById("eventsTable").innerHTML =
        events.map(event => `
            <tr>
                <td>${event.id}</td>
                <td>${event.title}</td>
                <td>${event.category || "-"}</td>
                <td>${event.status || "published"}</td>
                <td>${event.tickets_sold}</td>
            </tr>
        `).join("");
}

// LOAD VENUES
async function loadAdminVenues() {
    const venues = await adminRequest("/venues/");

    document.getElementById("totalVenues").textContent = venues.length;

    document.getElementById("venuesTable").innerHTML =
        venues.map(venue => `
            <tr>
                <td>${venue.id}</td>
                <td>${venue.name}</td>
                <td>${venue.location}</td>
                <td>${venue.capacity}</td>
                <td>${venue.hourly_rate}</td>
            </tr>
        `).join("");
}

// LOAD AGENT LOGS
async function loadAdminLogs() {
    const logs = await adminRequest("/agent-logs/");

    document.getElementById("totalLogs").textContent = logs.length;

    document.getElementById("agentLogsTable").innerHTML =
        logs.map(log => `
            <tr>
                <td>${log.sender}</td>
                <td>${log.receiver}</td>
                <td>${log.performative}</td>
                <td>${log.content || ""}</td>
                <td>${log.timestamp || ""}</td>
            </tr>
        `).join("");
}

// LOAD DASHBOARD
async function loadAdminDashboard() {
    if (!localStorage.getItem("access_token")) {
        alert("Please login first.");
        window.location.href = "/";
        return;
    }

    try {
        await loadAdminEvents();
        await loadAdminVenues();
        await loadAdminLogs();
    } catch (error) {
        alert(error.message);
    }
}

// LOGOUT
document.getElementById("adminLogout").addEventListener("click", event => {
    event.preventDefault();
    localStorage.removeItem("access_token");
    window.location.href = "/";
});

loadAdminDashboard();
