// ==================== 1. THREE.JS VISUALIZATION (PERFORMANCE TUNED) ====================
let robotDrawer = null; 
let isDrawerOpen = false;

(function initThreeJS() {
    const container = document.getElementById('canvas-container');
    if(!container) return; 

    const scene = new THREE.Scene();
    // Default Aspect Ratio
    const camera = new THREE.PerspectiveCamera(45, container.clientWidth/container.clientHeight, 0.1, 100);
    
    // PERF: Force "mediump" precision (faster shaders)
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, precision: "mediump" });
    
    // PERF: DYNAMIC RESOLUTION SCALING
    // On Desktop (>800px), force 1.0 scale to save GPU. On Mobile, allow 2.0 for sharpness.
    const pixelRatio = window.innerWidth > 800 ? 1 : Math.min(window.devicePixelRatio, 2);
    renderer.setPixelRatio(pixelRatio);
    renderer.setSize(container.clientWidth, container.clientHeight);
    
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.BasicShadowMap; // Fastest shadows
    
    container.appendChild(renderer.domElement);

    // Orbit Controls
    THREE.OrbitControls = function(object, domElement) {
        this.object = object;
        this.domElement = domElement || document;
        this.enabled = true;
        this.target = new THREE.Vector3();
        this.autoRotate = true; this.autoRotateSpeed = 2.0;
        
        var scope = this;
        var spherical = new THREE.Spherical(), sphericalDelta = new THREE.Spherical();
        var rotateStart = new THREE.Vector2(), rotateEnd = new THREE.Vector2(), rotateDelta = new THREE.Vector2();
        var STATE = { NONE: -1, ROTATE: 0 }; var state = STATE.NONE;

        this.update = function() {
            var offset = new THREE.Vector3().copy(scope.object.position).sub(scope.target);
            spherical.setFromVector3(offset);
            if(scope.autoRotate && state === STATE.NONE) spherical.theta -= 0.002 * scope.autoRotateSpeed;
            spherical.theta += sphericalDelta.theta;
            spherical.phi += sphericalDelta.phi;
            spherical.makeSafe();
            offset.setFromSpherical(spherical);
            scope.object.position.copy(scope.target).add(offset);
            scope.object.lookAt(scope.target);
            sphericalDelta.set(0,0,0);
        };

        function onMouseDown(e) { if(e.button===0){ state=STATE.ROTATE; rotateStart.set(e.clientX, e.clientY); scope.autoRotate = false; } }
        function onMouseMove(e) { 
            if(state===STATE.ROTATE) {
                rotateEnd.set(e.clientX, e.clientY);
                rotateDelta.subVectors(rotateEnd, rotateStart).multiplyScalar(0.005);
                sphericalDelta.theta -= rotateDelta.x;
                sphericalDelta.phi -= rotateDelta.y;
                rotateStart.copy(rotateEnd);
            }
        }
        function onMouseUp() { state=STATE.NONE; scope.autoRotate = true; }
        this.domElement.addEventListener('mousedown', onMouseDown);
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
        this.domElement.addEventListener('touchstart', (e) => onMouseDown(e.touches[0]));
        this.domElement.addEventListener('touchmove', (e) => onMouseMove(e.touches[0]));
        this.domElement.addEventListener('touchend', onMouseUp);
    };

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dirLight = new THREE.DirectionalLight(0xffffff, 1);
    dirLight.position.set(5, 10, 7);
    dirLight.castShadow = true;
    scene.add(dirLight);

    // Robot Geometry
    const robot = new THREE.Group();
    const matBody = new THREE.MeshStandardMaterial({ color: 0x2d3748, roughness: 0.3 });
    const matChassis = new THREE.MeshStandardMaterial({ color: 0x1a202c });
    const matWheel = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.9 });
    const matSilver = new THREE.MeshStandardMaterial({ color: 0xcccccc, metalness: 0.6, roughness: 0.2 });
    const matWater = new THREE.MeshStandardMaterial({ color: 0x4299e1, transparent: true, opacity: 0.7 });
    const matPill = new THREE.MeshStandardMaterial({ color: 0xf6ad55 });
    const matPi = new THREE.MeshStandardMaterial({ color: 0x48bb78 });

    const chassis = new THREE.Mesh(new THREE.BoxGeometry(2, 0.3, 2.5), matChassis);
    chassis.position.y = 0.5; robot.add(chassis);
    const wheelGeo = new THREE.CylinderGeometry(0.7, 0.7, 0.3, 32);
    const wheelL = new THREE.Mesh(wheelGeo, matWheel);
    wheelL.rotation.z = Math.PI/2; wheelL.position.set(-1.2, 0.7, -0.8); robot.add(wheelL);
    const wheelR = new THREE.Mesh(wheelGeo, matWheel);
    wheelR.rotation.z = Math.PI/2; wheelR.position.set(1.2, 0.7, -0.8); robot.add(wheelR);
    const bodyGeo = new THREE.BoxGeometry(1.8, 1.5, 2.0);
    const mainBody = new THREE.Mesh(bodyGeo, matBody);
    mainBody.position.set(0, 1.5, 0); robot.add(mainBody);

    robotDrawer = new THREE.Group();
    robotDrawer.position.set(0, 1.2, 0); 
    const trayMesh = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.1, 1.8), matSilver);
    robotDrawer.add(trayMesh);
    const trayDoor = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.4, 0.1), matSilver);
    trayDoor.position.set(0, 0.15, 0.95); robotDrawer.add(trayDoor);
    const water = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.6, 16), matWater);
    water.position.set(0.4, 0.36, 0); robotDrawer.add(water);
    const pill = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.25, 0.4, 16), matPill);
    pill.position.set(-0.4, 0.26, 0.2); robotDrawer.add(pill);
    robot.add(robotDrawer);
    
    const piBoard = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.6, 0.1), matPi);
    piBoard.position.set(0, 2.0, -1.01); robot.add(piBoard);
    scene.add(robot);

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 1, 0);

    let isRendering = true;
    
    // PERF: FPS LIMITER (Cap at 30 FPS)
    let lastTime = 0;
    const fpsLimit = 30; 
    const interval = 1000 / fpsLimit;

    function animate(timestamp) {
        if (!isRendering) return;
        requestAnimationFrame(animate);

        const delta = timestamp - lastTime;
        if (delta > interval) {
            lastTime = timestamp - (delta % interval);

            const targetZ = isDrawerOpen ? 1.2 : 0;
            robotDrawer.position.z += (targetZ - robotDrawer.position.z) * 0.05;
            controls.update();
            renderer.render(scene, camera);
        }
    }
    requestAnimationFrame(animate);

    // Stop rendering when off-screen
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                if (!isRendering) { isRendering = true; requestAnimationFrame(animate); }
            } else { isRendering = false; }
        });
    }, { threshold: 0.1 });
    observer.observe(container);

    const resizeObserver = new ResizeObserver(() => {
        if (!container || !camera || !renderer) return;
        const width = container.clientWidth;
        const height = container.clientHeight;
        if (width === 0 || height === 0) return;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
        if (width < 350) { camera.position.set(5, 6, 7); } 
        else if (width > 600) { camera.position.set(3, 4, 4); } 
        else { camera.position.set(4, 5, 5); }
    });
    resizeObserver.observe(container);
})();

// ==================== 2. SMART POLLING & RENDER LOGIC ====================
let lastScheduleState = ""; // Cache

function setStatusMessage(element, message, color) {
    if (!element) return;
    element.innerText = message;
    if (color) element.style.color = color;
}

function syncRobotVisualFromAction(action) {
    if (action === 'OPEN_DRAWER') isDrawerOpen = true;
    if (action === 'CLOSE_DRAWER') isDrawerOpen = false;
}

function renderSchedule(data) {
    const scheduleContainer = document.getElementById('scheduleContainer');
    if(!scheduleContainer) return;
    scheduleContainer.innerHTML = '';
    
    const groups = {};
    data.forEach(item => { if(!groups[item.day]) groups[item.day] = []; groups[item.day].push(item); });

    for (const [day, tasks] of Object.entries(groups)) {
        if(day !== 'Today') continue; 

        tasks.forEach(task => {
            const el = document.createElement('div');
            const opacity = task.is_done ? '0.5' : '1';
            const checkBg = task.is_done ? '#30d158' : 'transparent'; 
            const checkBorder = task.is_done ? 'none' : '2px solid #48bb78';
            const textDecor = task.is_done ? 'line-through' : 'none';
            const icon = task.is_done ? '✓' : '';

            el.className = `schedule-item`;
            el.style.opacity = opacity;
            
            el.innerHTML = `
                <div style="flex-grow:1; display:flex; align-items:center; gap:15px;">
                    <div onclick="toggleTask(${task.id})" 
                         style="cursor:pointer; width:28px; height:28px; 
                                border:${checkBorder}; border-radius:50%; 
                                display:flex; align-items:center; justify-content:center; 
                                color:white; background:${checkBg}; 
                                font-weight:bold; font-size:16px; transition:0.2s;">
                        ${icon}
                    </div>
                    <div style="flex-grow:1;">
                        <div class="schedule-task" style="text-decoration:${textDecor}; color:white; font-size:1.05rem;">
                            ${task.task}
                        </div>
                        <div class="schedule-time" style="color:#0a84ff; font-weight:600; font-size:0.85rem; display:flex; justify-content:space-between;">
                            <span>${task.time}</span>
                            <span style="color:#8e8e93; font-weight:400; font-size:0.8rem;">${task.patient}</span>
                        </div>
                    </div>
                </div>
                <button onclick="deleteTask(${task.id})" style="background:transparent; border:none; color:#ff453a; cursor:pointer; font-size:1.2rem; opacity:0.6; padding:10px;">✕</button>
            `;
            scheduleContainer.appendChild(el);
        });
    }
}

// Smart Polling Loop
window.fetchSchedule = async function() {
    try {
        const res = await fetch('/api/schedule');
        const data = await res.json();
        
        const currentDataString = JSON.stringify(data);
        if (currentDataString !== lastScheduleState) {
            renderSchedule(data);
            lastScheduleState = currentDataString;
        }
    } catch (error) { console.error("Schedule error", error); }
};

document.addEventListener('DOMContentLoaded', () => {
    window.fetchSchedule();
    setInterval(window.fetchSchedule, 10000); // 10s is safe

    // Voice Setup
    const voiceBtn = document.getElementById('voiceBtn');
    const voiceMsg = document.getElementById('voiceMessage'); 
    const voiceSub = document.getElementById('voiceSubtext'); 
    let recognition;

    if ('webkitSpeechRecognition' in window) {
        recognition = new webkitSpeechRecognition();
        recognition.continuous = false; recognition.lang = 'en-US';

        recognition.onstart = () => { if(voiceBtn) voiceBtn.classList.add('listening'); if(voiceSub) voiceSub.innerText = "Listening..."; };
        recognition.onend = () => { if(voiceBtn) voiceBtn.classList.remove('listening'); if(voiceSub) voiceSub.innerText = "Tap to Speak"; };

        recognition.onresult = async (e) => {
            const text = e.results[0][0].transcript;
            if(voiceMsg) { voiceMsg.innerText = `"${text}"`; voiceMsg.style.color = "#fff"; }
            if(voiceSub) voiceSub.innerText = "Processing...";

            try {
                const res = await fetch('/api/voice/process', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ text: text })
                });
                const result = await res.json();
                if(result.success) {
                    setStatusMessage(voiceMsg, result.message, "#30d158");
                    syncRobotVisualFromAction(result.action);
                    window.fetchSchedule();
                } else {
                    setStatusMessage(voiceMsg, result.message || result.error || "Error", "#ff453a");
                }
            } catch(err) { console.error(err); }
            setTimeout(() => { if(voiceSub) voiceSub.innerText = "Tap to Speak"; }, 5000);
        };
        if(voiceBtn) voiceBtn.addEventListener('click', () => recognition.start());
    } else {
        if(voiceMsg) voiceMsg.innerText = "Voice not supported";
    }

    // ==================== MANUAL TEXT COMMAND (AI POWERED) ====================
    const sendBtn = document.getElementById('sendCommandBtn');
    const manualInput = document.getElementById('manualCommandInput');
    const responseArea = document.getElementById('responseArea');

    async function processManualCommand() {
        const text = manualInput.value.trim();
        if (!text) return;

        setStatusMessage(responseArea, "Queuing command...", "#aaa");

        try {
            const res = await fetch('/api/voice/process', {
                method: 'POST', 
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ text: text })
            });
            const result = await res.json();
            
            if(result.success) {
                setStatusMessage(responseArea, result.message, "#30d158");
                syncRobotVisualFromAction(result.action);
                window.fetchSchedule();
            } else {
                setStatusMessage(responseArea, result.message || result.error || "I didn't understand.", "#ff453a");
            }
        } catch(err) { 
            console.error(err);
            setStatusMessage(responseArea, "Connection Error", "#ff453a");
        }
        manualInput.value = '';
    }

    if(sendBtn){
        sendBtn.addEventListener('click', processManualCommand);
        manualInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') processManualCommand(); });
    }
});

// ==================== 3. GLOBAL FUNCTIONS ====================
window.toggleTask = async (id) => { 
    await fetch('/api/task/toggle', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id}) });
    lastScheduleState = ""; // Force Refresh
    window.fetchSchedule();
};
window.deleteTask = async (id) => { 
    await fetch('/api/task/delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id}) });
    lastScheduleState = ""; 
    window.fetchSchedule();
};
window.openAddModal = () => document.getElementById('addTaskModal').style.display = 'flex';

window.submitNewTask = async () => {
    const name = document.getElementById('newTaskName').value.trim();
    const dosage = document.getElementById('newTaskDosage').value.trim();
    const time = document.getElementById('newTaskTime').value;
    const patientSelect = document.getElementById('newTaskPatient');
    const pid = patientSelect ? patientSelect.value : null;
    
    if(!name || !time) return alert("Please enter at least a Medicine Name and Time.");
    
    try {
        const res = await fetch('/api/task/add', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name: name, dosage: dosage, time: time, patient_id: pid, instructions: "Manual Add" })
        });
        const data = await res.json();
        if(data.success) {
            document.getElementById('addTaskModal').style.display = 'none';
            document.getElementById('newTaskName').value = '';
            document.getElementById('newTaskDosage').value = '';
            lastScheduleState = ""; 
            window.fetchSchedule();
        } else { alert("Error: " + data.message); }
    } catch(e) { console.error(e); alert("Server connection failed."); }
};

window.sendRequest = async (type) => {
    const voiceMsg = document.getElementById('voiceMessage');
    const responseArea = document.getElementById('responseArea');

    try {
        const res = await fetch('/api/request', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ type })
        });
        const data = await res.json();
        if (data.success) {
            setStatusMessage(voiceMsg, data.message, "#30d158");
            setStatusMessage(responseArea, data.message, "#30d158");
        } else {
            setStatusMessage(voiceMsg, data.message || "Request failed", "#ff453a");
            setStatusMessage(responseArea, data.message || "Request failed", "#ff453a");
        }
    } catch(e) {
        console.error(e);
        setStatusMessage(voiceMsg, "Request failed", "#ff453a");
        setStatusMessage(responseArea, "Request failed", "#ff453a");
    }
};

// ==================== MOBILE MENU & DOTS ====================
document.addEventListener('DOMContentLoaded', () => {
    const grid = document.querySelector('.dashboard-grid');
    const dots = document.querySelectorAll('.nav-dot');
    const panels = document.querySelectorAll('.panel');
    const updateDots = () => {
        const center = grid.scrollLeft + (grid.offsetWidth / 2);
        panels.forEach((panel, index) => {
            const panelLeft = panel.offsetLeft;
            const panelRight = panelLeft + panel.offsetWidth;
            if (center >= panelLeft && center <= panelRight) {
                dots.forEach(d => d.classList.remove('active'));
                if(dots[index]) dots[index].classList.add('active');
            }
        });
    };
    if(grid) grid.addEventListener('scroll', updateDots);

    const menuBtn = document.querySelector('.menu-toggle');
    const navbar = document.querySelector('.navbar');
    if (menuBtn && navbar) {
        menuBtn.addEventListener('click', () => {
            navbar.classList.toggle('open');
            const icon = navbar.classList.contains('open') 
                ? '<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>' 
                : '<line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line>';
            menuBtn.querySelector('svg').innerHTML = icon;
        });
    }
});
// ==================== 4. AI DIAGNOSTIC AGENT LOGIC ====================
window.submitSymptomCheck = async () => {
    const input = document.getElementById('aiSymptomInput');
    const history = document.getElementById('aiChatHistory');
    const loading = document.getElementById('aiLoadingIndicator');
    
    if (!input || !history) return;
    
    const text = input.value.trim();
    if (!text) return;

    // 1. UI Feedback: Add user message & show loading
    history.innerHTML += `<div class="ai-message user">${text}</div>`;
    input.value = '';
    loading.style.display = 'block';
    history.scrollTop = history.scrollHeight;

    try {
        const response = await fetch('/api/ai/symptom-check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symptoms: text })
        });

        const data = await response.json();
        loading.style.display = 'none';

        if (data.success) {
            // Apply emergency styling if the backend flagged RED_FLAGS
            const typeClass = data.is_emergency ? 'bot emergency' : 'bot';
            
            // If it's an emergency, we can also trigger the robot drawer for help/water
            if (data.is_emergency) isDrawerOpen = true;

            history.innerHTML += `
                <div class="ai-message ${typeClass}">
                    <strong>MediBot:</strong><br>
                    ${data.response.replace(/\n/g, '<br>')}
                </div>`;
        } else {
            history.innerHTML += `<div class="ai-message bot" style="color:#ff453a;">System: ${data.message}</div>`;
        }
    } catch (err) {
        loading.style.display = 'none';
        console.error("AI Agent Error:", err);
        history.innerHTML += `<div class="ai-message bot">Connection to Jacob's AI failed.</div>`;
    }
    
    // Auto-scroll to latest message
    history.scrollTop = history.scrollHeight;
};


// ==================== 5. CONCIERGE REDIRECT LOGIC ====================
let activeConciergeTab = 'meds';

window.switchConciergeTab = (tab) => {
    activeConciergeTab = tab;
    const medsBtn = document.getElementById('tab-meds');
    const foodBtn = document.getElementById('tab-food');
    const input = document.getElementById('conciergeSearch');

    if (tab === 'meds') {
        medsBtn.classList.add('active');
        foodBtn.classList.remove('active');
        input.placeholder = "Search 1mg for medicines...";
    } else {
        foodBtn.classList.add('active');
        medsBtn.classList.remove('active');
        input.placeholder = "Search Swiggy for healthy food...";
    }
};

window.handleConciergeRedirect = () => {
    const query = document.getElementById('conciergeSearch').value.trim();
    if (!query) return alert("Please enter what you are looking for.");

    let url = "";
    if (activeConciergeTab === 'meds') {
        // Direct search on 1mg.com
        url = `https://www.1mg.com/search/all?name=${encodeURIComponent(query)}`;
    } else {
        // Direct search on Swiggy.com
        // Note: Swiggy's web search uses the following structure
        url = `https://www.swiggy.com/search?query=${encodeURIComponent(query)}`;
    }

    // Open in a new tab so the Jacob Control Center stays active
    window.open(url, '_blank');
};

// Allow pressing "Enter" in the symptom input box
document.addEventListener('DOMContentLoaded', () => {
    const aiInput = document.getElementById('aiSymptomInput');
    if (aiInput) {
        aiInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') window.submitSymptomCheck();
        });
    }
});
