const API_BASE = window.location.origin;

let html5QrCode = null;
let isScanning = false;

const readerElement = document.getElementById("reader");
const eventIdElement = document.getElementById("eventId");
const startButton = document.getElementById("startScanner");
const stopButton = document.getElementById("stopScanner");
const manualCodeElement = document.getElementById("manualTicketCode");
const verifyButton = document.getElementById("verifyTicket");
const resultElement = document.getElementById("scanResult");


function showResult(message, success = false) {
    if (!resultElement) return;

    resultElement.textContent = message;
    resultElement.className = success
        ? "alert alert-success"
        : "alert alert-danger";

    resultElement.style.display = "block";
}


async function verifyTicket(ticketCode) {
    const eventId = Number(eventIdElement?.value);

    if (!eventId || eventId <= 0) {
        showResult("Please enter a valid Event ID.");
        return;
    }

    if (!ticketCode || !ticketCode.trim()) {
        showResult("Please scan or enter a ticket code.");
        return;
    }

    const token = localStorage.getItem("access_token");

    if (!token) {
        showResult("Please login as gate staff or admin.");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/tickets/scan`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                ticket_code: ticketCode.trim(),
                event_id: eventId
            })
        });

        const data = await response.json();

        if (!response.ok) {
            showResult(data.detail || "Ticket verification failed.");
            return;
        }

        showResult(
            data.message || "Ticket verified successfully. Admission allowed.",
            true
        );

    } catch (error) {
        console.error(error);
        showResult("Cannot connect to EventSphere server.");
    }
}


async function startScanner() {
    if (isScanning) return;

    if (!readerElement) {
        showResult("Scanner area was not found in scanner.html.");
        return;
    }

    try {
        html5QrCode = new Html5Qrcode("reader");

        await html5QrCode.start(
            { facingMode: "environment" },
            {
                fps: 10,
                qrbox: { width: 250, height: 250 }
            },
            async (decodedText) => {
                await stopScanner();
                await verifyTicket(decodedText);
            },
            () => {}
        );

        isScanning = true;
        showResult("Camera started. Scan a ticket QR code.", true);

    } catch (error) {
        console.error(error);
        showResult(
            "Unable to start camera. Allow camera permission and use HTTPS or localhost."
        );
    }
}


async function stopScanner() {
    if (!html5QrCode || !isScanning) return;

    try {
        await html5QrCode.stop();
        await html5QrCode.clear();
    } catch (error) {
        console.error(error);
    }

    isScanning = false;
}


startButton?.addEventListener("click", startScanner);

stopButton?.addEventListener("click", stopScanner);

verifyButton?.addEventListener("click", () => {
    verifyTicket(manualCodeElement?.value);
});