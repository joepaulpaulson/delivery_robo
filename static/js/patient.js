function setPatientStatus(message, color) {
    const status = document.getElementById("patientStatus");
    if (!status) return;
    status.textContent = `Status: ${message}`;
    if (color) status.style.color = color;
}

function renderPatientRequests(items) {
    const list = document.getElementById("patientRequestList");
    if (!list) return;
    if (!items || !items.length) {
        list.innerHTML = '<div class="request-item"><strong>No requests yet</strong><div class="muted">Your requests will appear here.</div></div>';
        return;
    }

    list.innerHTML = items
        .map(
            (item) => `
                <div class="request-item">
                    <strong>${item.label}</strong>
                    <div class="muted">${item.status}${item.message ? ` · ${item.message}` : ""}</div>
                </div>
            `
        )
        .join("");
}

async function refreshPatientRequests() {
    try {
        const response = await fetch("/patient/api/requests");
        const payload = await response.json();
        if (payload.success) {
            renderPatientRequests(payload.items);
        }
    } catch (error) {
        console.error("Patient request refresh failed", error);
    }
}

window.sendPatientRequest = async function sendPatientRequest(type) {
    try {
        const response = await fetch("/patient/api/request", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type }),
        });
        const payload = await response.json();
        if (payload.success) {
            setPatientStatus(payload.message, "#34d399");
            refreshPatientRequests();
        } else {
            setPatientStatus(payload.message || "Request failed", "#f87171");
        }
    } catch (error) {
        console.error(error);
        setPatientStatus("Request failed", "#f87171");
    }
};

window.submitManualPatientCommand = async function submitManualPatientCommand() {
    const input = document.getElementById("manualCommandInput");
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    setPatientStatus("Sending request...", "#9ca3af");
    try {
        const response = await fetch("/patient/api/voice/process", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text }),
        });
        const payload = await response.json();
        if (payload.success) {
            setPatientStatus(payload.message, "#34d399");
            input.value = "";
            refreshPatientRequests();
        } else {
            setPatientStatus(payload.message || "Request failed", "#f87171");
        }
    } catch (error) {
        console.error(error);
        setPatientStatus("Connection error", "#f87171");
    }
};

window.submitPatientSymptomCheck = async function submitPatientSymptomCheck() {
    const input = document.getElementById("symptomInput");
    const output = document.getElementById("symptomResponse");
    if (!input || !output) return;

    const text = input.value.trim();
    if (!text) return;

    output.textContent = "Analyzing symptoms...";
    output.style.color = "#9ca3af";

    try {
        const response = await fetch("/patient/api/ai/symptom-check", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ symptoms: text }),
        });
        const payload = await response.json();
        if (payload.success) {
            output.textContent = payload.response;
            output.style.color = payload.is_emergency ? "#f87171" : "#34d399";
            input.value = "";
        } else {
            output.textContent = payload.message || payload.error || "Unable to analyze symptoms right now.";
            output.style.color = "#f87171";
        }
    } catch (error) {
        console.error(error);
        output.textContent = "Connection error while checking symptoms.";
        output.style.color = "#f87171";
    }
};

document.addEventListener("DOMContentLoaded", () => {
    refreshPatientRequests();
    setInterval(refreshPatientRequests, 10000);

    const input = document.getElementById("manualCommandInput");
    if (input) {
        input.addEventListener("keypress", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submitManualPatientCommand();
            }
        });
    }

    const symptomInput = document.getElementById("symptomInput");
    if (symptomInput) {
        symptomInput.addEventListener("keypress", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                submitPatientSymptomCheck();
            }
        });
    }

    const voiceBtn = document.getElementById("voiceBtn");
    const voiceHint = document.getElementById("voiceHint");
    if ("webkitSpeechRecognition" in window && voiceBtn) {
        const recognition = new webkitSpeechRecognition();
        recognition.continuous = false;
        recognition.lang = "en-US";

        recognition.onstart = () => {
            voiceHint.textContent = "Listening...";
        };

        recognition.onend = () => {
            voiceHint.textContent = "Say water, medicine, SOS, or return robot.";
        };

        recognition.onresult = async (event) => {
            const text = event.results[0][0].transcript;
            const inputEl = document.getElementById("manualCommandInput");
            if (inputEl) {
                inputEl.value = text;
            }
            await submitManualPatientCommand();
        };

        voiceBtn.addEventListener("click", () => recognition.start());
    } else if (voiceHint) {
        voiceHint.textContent = "Voice input is not supported on this device.";
    }
});
