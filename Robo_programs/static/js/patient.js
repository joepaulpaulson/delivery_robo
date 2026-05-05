let patientRobotDrawer = null;
let patientDrawerOpen = false;

function setPatientStatus(message, color) {
    const status = document.getElementById("patientStatus");
    if (status) {
        status.textContent = `Status: ${message}`;
        if (color) {
            status.style.color = color;
        }
    }

    const voiceMessage = document.getElementById("voiceMessage");
    if (voiceMessage) {
        voiceMessage.textContent = message;
        if (color) {
            voiceMessage.style.color = color;
        }
    }
}

function renderPatientRequests(items) {
    const list = document.getElementById("patientRequestList");
    if (!list) return;

    if (!items || !items.length) {
        list.innerHTML = `
            <div class="summary-card">
                <strong>No requests yet.</strong>
                <div class="history-meta">Your requests will appear here.</div>
            </div>
        `;
        return;
    }

    list.innerHTML = items
        .map(
            (item) => `
                <div class="history-card">
                    <div class="request-copy">
                        <strong>${item.label}</strong>
                        <span class="history-meta">${item.status}${item.message ? ` · ${item.message}` : ""}</span>
                    </div>
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
            patientDrawerOpen = type === "water" || type === "medicine";
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

async function submitPatientVoiceText(text) {
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
            refreshPatientRequests();
        } else {
            setPatientStatus(payload.message || "Request failed", "#f87171");
        }
    } catch (error) {
        console.error(error);
        setPatientStatus("Connection error", "#f87171");
    }
}

window.submitPatientSymptomCheck = async function submitPatientSymptomCheck() {
    const input = document.getElementById("symptomInput");
    const history = document.getElementById("aiChatHistory");
    const loading = document.getElementById("aiLoadingIndicator");
    if (!input || !history) return;

    const text = input.value.trim();
    if (!text) return;

    history.innerHTML += `<div class="ai-message user">${text}</div>`;
    input.value = "";
    if (loading) {
        loading.style.display = "block";
    }
    history.scrollTop = history.scrollHeight;

    try {
        const response = await fetch("/patient/api/ai/symptom-check", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ symptoms: text }),
        });
        const payload = await response.json();
        if (loading) {
            loading.style.display = "none";
        }

        if (payload.success) {
            const typeClass = payload.is_emergency ? "bot emergency" : "bot";
            history.innerHTML += `
                <div class="ai-message ${typeClass}">
                    <strong>Jacob AI:</strong><br>
                    ${String(payload.response || "").replace(/\n/g, "<br>")}
                </div>
            `;
        } else {
            history.innerHTML += `<div class="ai-message bot" style="color:#ff453a;">System: ${payload.message || payload.error || "Unable to analyze symptoms right now."}</div>`;
        }
    } catch (error) {
        console.error(error);
        if (loading) {
            loading.style.display = "none";
        }
        history.innerHTML += `<div class="ai-message bot">Connection error while checking symptoms.</div>`;
    }

    history.scrollTop = history.scrollHeight;
};

function initPatientThreeJS() {
    const container = document.getElementById("canvas-container");
    if (!container || !window.THREE) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 100);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, precision: "mediump" });

    renderer.setPixelRatio(window.innerWidth > 800 ? 1 : Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.BasicShadowMap;
    container.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dirLight = new THREE.DirectionalLight(0xffffff, 1);
    dirLight.position.set(5, 10, 7);
    scene.add(dirLight);

    const robot = new THREE.Group();
    const matBody = new THREE.MeshStandardMaterial({ color: 0x2d3748, roughness: 0.3 });
    const matChassis = new THREE.MeshStandardMaterial({ color: 0x1a202c });
    const matWheel = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.9 });
    const matSilver = new THREE.MeshStandardMaterial({ color: 0xcccccc, metalness: 0.6, roughness: 0.2 });
    const matWater = new THREE.MeshStandardMaterial({ color: 0x4299e1, transparent: true, opacity: 0.7 });
    const matPill = new THREE.MeshStandardMaterial({ color: 0xf6ad55 });

    const chassis = new THREE.Mesh(new THREE.BoxGeometry(2, 0.3, 2.5), matChassis);
    chassis.position.y = 0.5;
    robot.add(chassis);

    const wheelGeo = new THREE.CylinderGeometry(0.7, 0.7, 0.3, 24);
    const wheelL = new THREE.Mesh(wheelGeo, matWheel);
    wheelL.rotation.z = Math.PI / 2;
    wheelL.position.set(-1.2, 0.7, -0.8);
    robot.add(wheelL);

    const wheelR = new THREE.Mesh(wheelGeo, matWheel);
    wheelR.rotation.z = Math.PI / 2;
    wheelR.position.set(1.2, 0.7, -0.8);
    robot.add(wheelR);

    const mainBody = new THREE.Mesh(new THREE.BoxGeometry(1.8, 1.5, 2.0), matBody);
    mainBody.position.set(0, 1.5, 0);
    robot.add(mainBody);

    patientRobotDrawer = new THREE.Group();
    patientRobotDrawer.position.set(0, 1.2, 0);
    patientRobotDrawer.add(new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.1, 1.8), matSilver));

    const trayDoor = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.4, 0.1), matSilver);
    trayDoor.position.set(0, 0.15, 0.95);
    patientRobotDrawer.add(trayDoor);

    const water = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.6, 16), matWater);
    water.position.set(0.4, 0.36, 0);
    patientRobotDrawer.add(water);

    const pill = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.25, 0.4, 16), matPill);
    pill.position.set(-0.4, 0.26, 0.2);
    patientRobotDrawer.add(pill);
    robot.add(patientRobotDrawer);

    scene.add(robot);
    camera.position.set(5, 5, 8);
    camera.lookAt(0, 1, 0);

    let angle = 0;
    function animate() {
        requestAnimationFrame(animate);
        angle += 0.005;
        camera.position.x = Math.sin(angle) * 8;
        camera.position.z = Math.cos(angle) * 8;
        camera.lookAt(0, 1, 0);

        if (patientRobotDrawer) {
            const targetZ = patientDrawerOpen ? 1.2 : 0;
            patientRobotDrawer.position.z += (targetZ - patientRobotDrawer.position.z) * 0.05;
        }

        renderer.render(scene, camera);
    }

    animate();

    const resize = () => {
        const width = container.clientWidth;
        const height = container.clientHeight;
        if (!width || !height) return;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
    };

    window.addEventListener("resize", resize);
    if ("ResizeObserver" in window) {
        new ResizeObserver(resize).observe(container);
    }
}

function initDashboardChrome() {
    const grid = document.querySelector(".dashboard-grid");
    const dots = document.querySelectorAll(".nav-dot");
    const panels = document.querySelectorAll(".panel");

    const updateDots = () => {
        if (!grid || !dots.length || !panels.length) return;
        const center = grid.scrollLeft + grid.offsetWidth / 2;
        panels.forEach((panel, index) => {
            const panelLeft = panel.offsetLeft;
            const panelRight = panelLeft + panel.offsetWidth;
            if (center >= panelLeft && center <= panelRight) {
                dots.forEach((dot) => dot.classList.remove("active"));
                if (dots[index]) {
                    dots[index].classList.add("active");
                }
            }
        });
    };

    if (grid) {
        grid.addEventListener("scroll", updateDots);
        updateDots();
    }

    const menuBtn = document.querySelector(".menu-toggle");
    const navbar = document.querySelector(".navbar");
    if (menuBtn && navbar) {
        menuBtn.addEventListener("click", () => {
            navbar.classList.toggle("open");
            const icon = navbar.classList.contains("open")
                ? '<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>'
                : '<line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line>';
            const iconSvg = menuBtn.querySelector("svg");
            if (iconSvg) {
                iconSvg.innerHTML = icon;
            }
        });
    }
}

function initVoiceControls() {
    const voiceBtn = document.getElementById("voiceBtn");
    const voiceHint = document.getElementById("voiceSubtext");
    if (!voiceBtn || !voiceHint) return;

    if ("webkitSpeechRecognition" in window) {
        const recognition = new webkitSpeechRecognition();
        recognition.continuous = false;
        recognition.lang = "en-US";

        recognition.onstart = () => {
            voiceBtn.classList.add("listening");
            voiceHint.textContent = "Listening...";
            setPatientStatus("Listening...", "#ffffff");
        };

        recognition.onend = () => {
            voiceBtn.classList.remove("listening");
            voiceHint.textContent = "Say water, medicine, or SOS.";
        };

        recognition.onresult = async (event) => {
            const text = event.results[0][0].transcript;
            await submitPatientVoiceText(text);
        };

        voiceBtn.addEventListener("click", () => recognition.start());
    } else {
        voiceHint.textContent = "Voice input is not supported on this device.";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initPatientThreeJS();
    initDashboardChrome();
    initVoiceControls();
    refreshPatientRequests();
    setInterval(refreshPatientRequests, 10000);

    const symptomInput = document.getElementById("symptomInput");
    if (symptomInput) {
        symptomInput.addEventListener("keypress", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                submitPatientSymptomCheck();
            }
        });
    }
});
