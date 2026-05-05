// Register GSAP ScrollTrigger
gsap.registerPlugin(ScrollTrigger);

// --- 1. THREE.JS SETUP ---
const container = document.getElementById('webgl-container');
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });

renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // Performance fix
container.appendChild(renderer.domElement);

// Lighting
const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
scene.add(ambientLight);

const spotLight = new THREE.SpotLight(0xffffff, 2);
spotLight.position.set(5, 10, 5);
spotLight.castShadow = true;
scene.add(spotLight);

const blueRimLight = new THREE.PointLight(0x4299e1, 1, 10);
blueRimLight.position.set(-2, 2, -2);
scene.add(blueRimLight);

// --- 2. BUILD ROBOT ---
const robot = new THREE.Group();

// Materials
const matBody = new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 0.2, metalness: 0.8 }); 
const matChassis = new THREE.MeshStandardMaterial({ color: 0x000000 });
const matWheel = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.9 });
const matSilver = new THREE.MeshStandardMaterial({ color: 0xeeeeee, metalness: 0.9, roughness: 0.1 });
const matPi = new THREE.MeshStandardMaterial({ color: 0x48bb78, emissive: 0x0f3c25 });
const matPill = new THREE.MeshStandardMaterial({ color: 0xf6ad55 });
const matWater = new THREE.MeshStandardMaterial({ color: 0x4299e1, transparent: true, opacity: 0.6 });

// Build
const chassis = new THREE.Mesh(new THREE.BoxGeometry(2, 0.3, 2.5), matChassis);
chassis.position.y = 0.5; robot.add(chassis);

const wheelGeo = new THREE.CylinderGeometry(0.7, 0.7, 0.3, 32);
const wheelL = new THREE.Mesh(wheelGeo, matWheel);
wheelL.rotation.z = Math.PI/2; wheelL.position.set(-1.2, 0.7, -0.8); robot.add(wheelL);
const wheelR = new THREE.Mesh(wheelGeo, matWheel);
wheelR.rotation.z = Math.PI/2; wheelR.position.set(1.2, 0.7, -0.8); robot.add(wheelR);

const mainBody = new THREE.Mesh(new THREE.BoxGeometry(1.8, 1.5, 2.0), matBody);
mainBody.position.set(0, 1.5, 0); robot.add(mainBody);

const robotDrawer = new THREE.Group();
robotDrawer.position.set(0, 1.2, 0); 
robotDrawer.add(new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.1, 1.8), matSilver));
const trayDoor = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.4, 0.1), matSilver);
trayDoor.position.set(0, 0.15, 0.95); robotDrawer.add(trayDoor);

// Items
const pill = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.25, 0.4, 16), matPill);
pill.position.set(-0.4, 0.26, 0.2); robotDrawer.add(pill);
const water = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.6, 16), matWater);
water.position.set(0.4, 0.36, 0); robotDrawer.add(water);
robot.add(robotDrawer);

const piBoard = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.6, 0.1), matPi);
piBoard.position.set(0, 2.0, -1.01); robot.add(piBoard);

scene.add(robot);

// --- 3. RESPONSIVE CAMERA LOGIC ---
function adjustCameraForMobile() {
    const width = window.innerWidth;
    
    if (width < 768) {
        // MOBILE: Move camera further back and up
        camera.position.set(0, 3, 9);
        // Reduce scale slightly
        robot.scale.set(0.8, 0.8, 0.8);
    } else {
        // DESKTOP: Standard Position
        camera.position.set(0, 2, 5);
        robot.scale.set(1, 1, 1);
    }
    camera.lookAt(0, 1.5, 0);
}

// Initial Call
adjustCameraForMobile();

// Resize Handler
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    adjustCameraForMobile(); // Re-adjust on resize
});

function animate() {
    requestAnimationFrame(animate);
    robot.position.y = Math.sin(Date.now() * 0.001) * 0.05; 
    renderer.render(scene, camera);
}
animate();

// --- 4. SCROLL ANIMATIONS ---
robot.rotation.set(0, 0, 0);

// Sec 1 -> Sec 2 (Open Drawer)
gsap.to(robot.rotation, {
    y: -Math.PI / 4, x: 0.2, 
    scrollTrigger: { trigger: "#sec-2", start: "top bottom", end: "center center", scrub: 1 }
});
gsap.to(robotDrawer.position, {
    z: 1.2, 
    scrollTrigger: { trigger: "#sec-2", start: "top bottom", end: "center center", scrub: 1 }
});

// Sec 2 -> Sec 3 (Show Back/Pi)
gsap.to(robot.rotation, {
    y: Math.PI, x: 0,
    scrollTrigger: { trigger: "#sec-3", start: "top bottom", end: "center center", scrub: 1 }
});
gsap.to(robotDrawer.position, {
    z: 0, 
    scrollTrigger: { trigger: "#sec-3", start: "top bottom", end: "center center", scrub: 1 }
});

// Final Section
gsap.to(camera.position, {
    z: 3.5, y: 1.5,
    scrollTrigger: { trigger: "#sec-4", start: "top bottom", end: "center center", scrub: 1 }
});
gsap.to(robot.rotation, {
    y: Math.PI * 2, 
    scrollTrigger: { trigger: "#sec-4", start: "top bottom", end: "center center", scrub: 1 }
});

// Text Fade
gsap.utils.toArray('.section').forEach(section => {
    gsap.to(section, {
        opacity: 1, y: 0, duration: 1,
        scrollTrigger: { trigger: section, start: "top 75%", end: "top 25%", toggleActions: "play none none reverse" }
    })
});