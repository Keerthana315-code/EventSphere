
const API = window.location.origin;

// ==========================================
// AUTHENTICATION
// ==========================================

function getToken() {
    return localStorage.getItem("access_token");
}

function saveToken(token) {
    localStorage.setItem("access_token", token);
}

function logout() {
    localStorage.removeItem("access_token");
    window.location.reload();
}


// ==========================================
// API REQUEST FUNCTION
// ==========================================

async function apiRequest(url, options = {}) {
    const headers = {
        ...(options.headers || {})
    };

    const token = getToken();

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    if (options.body && !(options.body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
    }

    try {
        const response = await fetch(`${API}${url}`, {
            ...options,
            headers
        });

        const text = await response.text();

        let data = {};

        try {
            data = text ? JSON.parse(text) : {};
        } catch {
            data = { detail: text || "Invalid server response" };
        }

        if (!response.ok) {
            let message = "Request failed";

            if (typeof data.detail === "string") {
                message = data.detail;
            } else if (Array.isArray(data.detail)) {
                message = data.detail
                    .map(item => item.msg || JSON.stringify(item))
                    .join(", ");
            } else if (data.message) {
                message = data.message;
            } else if (data.detail) {
                message = JSON.stringify(data.detail);
            }

            throw new Error(message);
        }

        return data;

    } catch (error) {
        console.error("API Error:", error);
        throw error;
    }
}


// ==========================================
// SHOW MESSAGE
// ==========================================

function showMessage(message, type = "info") {
    alert(message);
}


// ==========================================
// LOGIN
// ==========================================

async function loginUser(event) {
    if (event) event.preventDefault();

    const email = document.getElementById("loginEmail")?.value.trim();
    const password = document.getElementById("loginPassword")?.value;

    if (!email || !password) {
        showMessage("Please enter email and password.", "error");
        return;
    }

    try {
        const formData = new URLSearchParams();

        formData.append("username", email);
        formData.append("password", password);

        const response = await fetch(`${API}/auth/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            let message = "Login failed";

            if (typeof data.detail === "string") {
                message = data.detail;
            } else if (Array.isArray(data.detail)) {
                message = data.detail
                    .map(item => item.msg)
                    .join(", ");
            } else if (data.detail) {
                message = JSON.stringify(data.detail);
            }

            throw new Error(message);
        }

        if (!data.access_token) {
            throw new Error("Access token was not returned by the server.");
        }

        saveToken(data.access_token);

        showMessage("Login successful!");

        window.location.reload();

    } catch (error) {
        console.error("Login error:", error);
        showMessage(error.message || "Unable to login.", "error");
    }
}


// ==========================================
// REGISTER
// ==========================================

async function registerUser(event) {
    if (event) event.preventDefault();

    const fullName = document.getElementById("registerName")?.value.trim();
    const email = document.getElementById("registerEmail")?.value.trim();
    const password = document.getElementById("registerPassword")?.value;

    if (!fullName || !email || !password) {
        showMessage("Please fill all registration fields.", "error");
        return;
    }

    if (password.length < 8) {
        showMessage("Password must contain at least 8 characters.", "error");
        return;
    }

    try {
        const data = await apiRequest("/auth/register", {
            method: "POST",
            body: JSON.stringify({
                full_name: fullName,
                email: email,
                password: password
            })
        });

        showMessage("Registration successful! Please login.");

        const registerForm = document.getElementById("registerForm");

        if (registerForm) {
            registerForm.reset();
        }

        const loginEmail = document.getElementById("loginEmail");

        if (loginEmail) {
            loginEmail.value = email;
        }

    } catch (error) {
        showMessage(error.message, "error");
    }
}


// ==========================================
// EVENTS
// ==========================================

let allEvents = [];

async function loadEvents() {
    const container = document.getElementById("eventsContainer");

    if (!container) return;

    try {
        container.innerHTML = "<p>Loading events...</p>";

        const events = await apiRequest("/events/");

        allEvents = Array.isArray(events) ? events : [];

        displayEvents(allEvents);

    } catch (error) {
        console.error("Load events:", error);

        container.innerHTML =
            `<p class="text-danger">${escapeHTML(error.message)}</p>`;
    }
}


function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[char]);
}


function displayEvents(events) {
    const container = document.getElementById("eventsContainer");

    if (!container) return;

    if (!events.length) {
        container.innerHTML = "<p>No events available currently.</p>";
        return;
    }

    container.innerHTML = events.map(event => `
        <div class="col-md-4 mb-4">
            <div class="card h-100 shadow-sm">
                <div class="card-body">
                    <h5 class="card-title">
                        ${escapeHTML(event.title)}
                    </h5>

                    <p class="text-muted">
                        ${escapeHTML(event.category || "General")}
                    </p>

                    <p>
                        ${escapeHTML(event.description || "No description")}
                    </p>

                    <p>
                        Available:
                        ${Math.max(
                            0,
                            Number(event.max_tickets || 0) -
                            Number(event.tickets_sold || 0)
                        )}
                    </p>

                    <button
                        class="btn btn-primary"
                        onclick="bookEvent(${Number(event.id)})">
                        Book Now
                    </button>
                </div>
            </div>
        </div>
    `).join("");
}


// ==========================================
// SEARCH EVENTS
// ==========================================

function searchEvents() {
    const searchInput = document.getElementById("searchInput");

    if (!searchInput) return;

    const keyword = searchInput.value.toLowerCase().trim();

    const filtered = allEvents.filter(event =>
        String(event.title || "").toLowerCase().includes(keyword) ||
        String(event.category || "").toLowerCase().includes(keyword) ||
        String(event.description || "").toLowerCase().includes(keyword)
    );

    displayEvents(filtered);
}


// ==========================================
// BOOK EVENT
// ==========================================

async function bookEvent(eventId) {
    if (!getToken()) {
        showMessage("Please login before booking.");
        return;
    }

    try {
        const ticketTypes = await apiRequest(
            `/ticket-types/${eventId}`
        );

        if (!Array.isArray(ticketTypes) || ticketTypes.length === 0) {
            showMessage("No ticket types available for this event.");
            return;
        }

        const options = ticketTypes.map(ticket =>
            `${ticket.id}: ${ticket.name} - ${ticket.price}`
        ).join("\n");

        const selectedId = prompt(
            "Select Ticket Type ID:\n" + options
        );

        if (!selectedId) return;

        const ticket = ticketTypes.find(
            item => item.id === Number(selectedId)
        );

        if (!ticket) {
            showMessage("Invalid ticket type.");
            return;
        }

        const quantity = Number(
            prompt("Enter ticket quantity (1-10):")
        );

        if (!Number.isInteger(quantity) || quantity < 1 || quantity > 10) {
            showMessage("Enter a valid quantity between 1 and 10.");
            return;
        }

        const result = await apiRequest("/bookings/", {
            method: "POST",
            body: JSON.stringify({
                event_id: Number(eventId),
                ticket_type_id: ticket.id,
                quantity: quantity
            })
        });

        showMessage(
            `Booking successful! Booking ID: ${result.id}`
        );

        await loadEvents();
        await loadBookings();

    } catch (error) {
        showMessage(error.message, "error");
    }
}


// ==========================================
// MY BOOKINGS
// ==========================================

async function loadBookings() {
    const container = document.getElementById("bookingsContainer");

    if (!container || !getToken()) return;

    try {
        const bookings = await apiRequest("/bookings/my");

        if (!Array.isArray(bookings) || bookings.length === 0) {
            container.innerHTML = "<p>No bookings found.</p>";
            return;
        }

        container.innerHTML = bookings.map(booking => `
            <div class="card mb-3">
                <div class="card-body">
                    <h6>Booking #${booking.id}</h6>

                    <p>Event ID: ${booking.event_id}</p>

                    <p>Quantity: ${booking.quantity}</p>

                    <p>Amount: ${booking.total_amount}</p>

                    <p>Status: ${escapeHTML(booking.status)}</p>

                    ${
                        booking.status === "confirmed"
                        ? `<button class="btn btn-danger btn-sm"
                            onclick="cancelBooking(${booking.id})">
                            Cancel Booking
                           </button>`
                        : ""
                    }
                </div>
            </div>
        `).join("");

    } catch (error) {
        console.error("Bookings error:", error);

        container.innerHTML =
            `<p class="text-danger">${escapeHTML(error.message)}</p>`;
    }
}


// ==========================================
// CANCEL BOOKING
// ==========================================

async function cancelBooking(bookingId) {
    if (!confirm("Are you sure you want to cancel this booking?")) {
        return;
    }

    try {
        await apiRequest(`/bookings/${bookingId}/cancel`, {
            method: "POST"
        });

        showMessage("Booking cancelled successfully.");

        await loadBookings();
        await loadEvents();

    } catch (error) {
        showMessage(error.message, "error");
    }
}


// ==========================================
// AUTHENTICATION UI
// ==========================================

function updateAuthenticationUI() {
    const token = getToken();

    const loginButton = document.getElementById("loginNavButton");
    const registerButton = document.getElementById("registerNavButton");
    const logoutButton = document.getElementById("logoutButton");

    if (loginButton) {
        loginButton.style.display = token ? "none" : "inline-block";
    }

    if (registerButton) {
        registerButton.style.display = token ? "none" : "inline-block";
    }

    if (logoutButton) {
        logoutButton.style.display = token ? "inline-block" : "none";
    }
}


// ==========================================
// INITIALIZE APPLICATION
// ==========================================

document.addEventListener("DOMContentLoaded", () => {

    const loginForm = document.getElementById("loginForm");
    const registerForm = document.getElementById("registerForm");

    loginForm?.addEventListener("submit", loginUser);

    registerForm?.addEventListener("submit", registerUser);

    document.getElementById("searchInput")
        ?.addEventListener("input", searchEvents);

    document.getElementById("logoutButton")
        ?.addEventListener("click", logout);

    updateAuthenticationUI();

    loadEvents();
    loadBookings();

});
