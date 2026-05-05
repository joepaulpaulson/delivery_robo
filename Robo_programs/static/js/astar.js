const canvas = document.getElementById('astarCanvas');
const ctx = canvas.getContext('2d');
const statusMsg = document.getElementById('pathStatus');
const roomNameInput = document.getElementById('roomNameInput');
const roomList = document.getElementById('roomList');

let CELL_SIZE = 25;
let COLS = 0;
let ROWS = 0;
let grid = [];
let base = { x: 2, y: 2 };
let roomMarkers = {};
let previewRoom = null;
let currentMode = 'wall';
let isDragging = false;

function normalizeRoomName(value) {
    return (value || '').trim().toUpperCase();
}

function isValidRoomName(value) {
    return /^[A-Z]-\d{3}$/.test(normalizeRoomName(value));
}

function initCanvas() {
    const maxWidth = window.innerWidth * 0.95;
    const maxHeight = window.innerHeight * 0.6;

    if (window.innerWidth < 768) {
        CELL_SIZE = 20;
        canvas.width = maxWidth;
        canvas.height = maxHeight;
    } else {
        CELL_SIZE = 25;
        canvas.width = Math.min(800, maxWidth);
        canvas.height = 500;
    }

    COLS = Math.max(Math.floor(canvas.width / CELL_SIZE), 1);
    ROWS = Math.max(Math.floor(canvas.height / CELL_SIZE), 1);

    if (base.x >= COLS) base.x = Math.max(COLS - 1, 0);
    if (base.y >= ROWS) base.y = Math.max(ROWS - 1, 0);
}

function initEmptyGrid() {
    grid = new Array(COLS).fill(0).map(() => new Array(ROWS).fill(0));
}

function ensureGridDimensions(savedGrid) {
    if (
        Array.isArray(savedGrid) &&
        savedGrid.length === COLS &&
        savedGrid.every((column) => Array.isArray(column) && column.length === ROWS)
    ) {
        grid = savedGrid;
        return;
    }
    initEmptyGrid();
}

function sanitizeBase(candidate) {
    if (!candidate || typeof candidate !== 'object') {
        return { x: 2, y: 2 };
    }
    const x = Number.isInteger(candidate.x) ? candidate.x : 2;
    const y = Number.isInteger(candidate.y) ? candidate.y : 2;
    return {
        x: Math.min(Math.max(x, 0), Math.max(COLS - 1, 0)),
        y: Math.min(Math.max(y, 0), Math.max(ROWS - 1, 0)),
    };
}

function sanitizeRooms(rooms) {
    const normalized = {};
    if (!rooms || typeof rooms !== 'object') {
        return normalized;
    }

    Object.entries(rooms).forEach(([roomName, coords]) => {
        const normalizedName = normalizeRoomName(roomName);
        if (!isValidRoomName(normalizedName) || !coords || typeof coords !== 'object') {
            return;
        }

        const x = Number.isInteger(coords.x) ? coords.x : null;
        const y = Number.isInteger(coords.y) ? coords.y : null;
        if (x === null || y === null || x < 0 || y < 0 || x >= COLS || y >= ROWS) {
            return;
        }

        normalized[normalizedName] = { x, y };
    });

    return normalized;
}

function roomAtCell(x, y) {
    return Object.entries(roomMarkers).find(([, coords]) => coords.x === x && coords.y === y)?.[0] || null;
}

function renderRoomList() {
    roomList.innerHTML = '';
    const roomNames = Object.keys(roomMarkers).sort();

    if (roomNames.length === 0) {
        roomList.innerHTML = '<div class="room-chip">No rooms mapped yet</div>';
        return;
    }

    roomNames.forEach((roomName) => {
        const chip = document.createElement('button');
        chip.className = `room-chip${previewRoom === roomName ? ' active' : ''}`;
        chip.textContent = roomName;
        chip.title = 'Click to preview route. Double-click to remove.';
        chip.addEventListener('click', () => {
            previewRoom = roomName;
            drawPreviewPath();
        });
        chip.addEventListener('dblclick', () => {
            delete roomMarkers[roomName];
            if (previewRoom === roomName) {
                previewRoom = Object.keys(roomMarkers)[0] || null;
            }
            drawPreviewPath();
        });
        roomList.appendChild(chip);
    });
}

function saveStatus(message, color = '#8e8e93') {
    statusMsg.textContent = message;
    statusMsg.style.color = color;
}

async function loadMapFromDB() {
    initCanvas();

    try {
        const res = await fetch('/api/map/load');
        const data = await res.json();

        if (data.success) {
            ensureGridDimensions(data.grid);
            base = sanitizeBase(data.base);
            roomMarkers = sanitizeRooms(data.rooms);
            previewRoom = previewRoom && roomMarkers[previewRoom] ? previewRoom : (Object.keys(roomMarkers)[0] || null);
        } else {
            initEmptyGrid();
            roomMarkers = {};
            previewRoom = null;
        }
    } catch (error) {
        initEmptyGrid();
        roomMarkers = {};
        previewRoom = null;
    }

    drawPreviewPath();
}

async function saveMapToDB() {
    saveStatus('Saving map...', '#ffffff');

    try {
        const payload = { grid, rooms: roomMarkers, base };
        const res = await fetch('/api/map/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (data.success) {
            saveStatus(`Map saved. ${Object.keys(roomMarkers).length} room(s) mapped.`, '#30d158');
            return;
        }

        saveStatus(data.message || 'Failed to save map.', '#ff453a');
    } catch (error) {
        saveStatus('Failed to save map.', '#ff453a');
    }
}

function getNeighbors(node) {
    const neighbors = [];
    if (node.x < COLS - 1) neighbors.push({ x: node.x + 1, y: node.y });
    if (node.x > 0) neighbors.push({ x: node.x - 1, y: node.y });
    if (node.y < ROWS - 1) neighbors.push({ x: node.x, y: node.y + 1 });
    if (node.y > 0) neighbors.push({ x: node.x, y: node.y - 1 });
    return neighbors;
}

function solveAStar(target) {
    if (!target) return [];

    const start = { x: base.x, y: base.y };
    const goal = { x: target.x, y: target.y };

    if (grid[start.x]?.[start.y] === 1) grid[start.x][start.y] = 0;
    if (grid[goal.x]?.[goal.y] === 1) grid[goal.x][goal.y] = 0;

    const openSet = [{ x: start.x, y: start.y, g: 0, h: 0, f: 0, parent: null }];
    const closed = new Set();

    while (openSet.length > 0) {
        let lowestIndex = 0;
        for (let i = 1; i < openSet.length; i += 1) {
            if (openSet[i].f < openSet[lowestIndex].f) {
                lowestIndex = i;
            }
        }

        const current = openSet.splice(lowestIndex, 1)[0];
        const currentKey = `${current.x},${current.y}`;
        closed.add(currentKey);

        if (current.x === goal.x && current.y === goal.y) {
            const path = [];
            let cursor = current;
            while (cursor) {
                path.push({ x: cursor.x, y: cursor.y });
                cursor = cursor.parent;
            }
            return path.reverse();
        }

        const neighbors = getNeighbors(current);
        neighbors.forEach((neighbor) => {
            const key = `${neighbor.x},${neighbor.y}`;
            if (closed.has(key) || grid[neighbor.x][neighbor.y] === 1) {
                return;
            }

            const tentativeG = current.g + 1;
            let existing = openSet.find((node) => node.x === neighbor.x && node.y === neighbor.y);

            if (!existing) {
                existing = { ...neighbor, g: tentativeG, h: 0, f: 0, parent: current };
                openSet.push(existing);
            } else if (tentativeG >= existing.g) {
                return;
            } else {
                existing.g = tentativeG;
                existing.parent = current;
            }

            existing.h = Math.abs(existing.x - goal.x) + Math.abs(existing.y - goal.y);
            existing.f = existing.g + existing.h;
        });
    }

    return [];
}

function draw(path = []) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < COLS; i += 1) {
        for (let j = 0; j < ROWS; j += 1) {
            if (grid[i][j] === 1) {
                ctx.fillStyle = '#4a4a4a';
                ctx.fillRect(i * CELL_SIZE + 1, j * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2);
            } else {
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
                ctx.strokeRect(i * CELL_SIZE, j * CELL_SIZE, CELL_SIZE, CELL_SIZE);
            }
        }
    }

    path.forEach((node) => {
        ctx.fillStyle = 'rgba(10, 132, 255, 0.4)';
        ctx.fillRect(node.x * CELL_SIZE + 1, node.y * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2);
    });

    Object.entries(roomMarkers).forEach(([roomName, coords]) => {
        ctx.fillStyle = previewRoom === roomName ? '#ff9f0a' : '#ff453a';
        ctx.fillRect(coords.x * CELL_SIZE + 3, coords.y * CELL_SIZE + 3, CELL_SIZE - 6, CELL_SIZE - 6);

        ctx.fillStyle = '#ffffff';
        ctx.font = '12px Inter, sans-serif';
        ctx.fillText(roomName, coords.x * CELL_SIZE + 4, coords.y * CELL_SIZE + CELL_SIZE - 6);
    });

    ctx.fillStyle = '#30d158';
    ctx.fillRect(base.x * CELL_SIZE + 1, base.y * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2);
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 12px Inter, sans-serif';
    ctx.fillText('BASE', base.x * CELL_SIZE + 2, base.y * CELL_SIZE + 14);

    renderRoomList();
}

function drawPreviewPath() {
    const target = previewRoom ? roomMarkers[previewRoom] : null;
    if (!target) {
        draw([]);
        saveStatus(`Mapped rooms: ${Object.keys(roomMarkers).length}. Select "Place Room" to assign destinations.`);
        return;
    }

    const path = solveAStar(target);
    draw(path);

    if (path.length > 0) {
        saveStatus(`Preview route to ${previewRoom}: ${Math.max(path.length - 1, 0)} step(s).`, '#30d158');
    } else {
        saveStatus(`No path available from BASE to ${previewRoom}.`, '#ff453a');
    }
}

function setMode(mode) {
    currentMode = mode;
    document.getElementById('btnWall').classList.toggle('active', mode === 'wall');
    document.getElementById('btnBase').classList.toggle('active', mode === 'base');
    document.getElementById('btnRoom').classList.toggle('active', mode === 'room');
}

function handleInput(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((clientX - rect.left) / CELL_SIZE);
    const y = Math.floor((clientY - rect.top) / CELL_SIZE);

    if (x < 0 || x >= COLS || y < 0 || y >= ROWS) return;

    if (currentMode === 'wall') {
        const mappedRoom = roomAtCell(x, y);
        if ((base.x === x && base.y === y) || mappedRoom) {
            return;
        }
        grid[x][y] = grid[x][y] === 1 ? 0 : 1;
    }

    if (currentMode === 'base') {
        base = { x, y };
        grid[x][y] = 0;
        const roomName = roomAtCell(x, y);
        if (roomName) delete roomMarkers[roomName];
    }

    if (currentMode === 'room') {
        const roomName = normalizeRoomName(roomNameInput.value);
        if (!isValidRoomName(roomName)) {
            saveStatus('Enter a room like A-101 before placing a marker.', '#ff453a');
            return;
        }
        grid[x][y] = 0;
        roomMarkers[roomName] = { x, y };
        previewRoom = roomName;
    }

    drawPreviewPath();
}

function clearWalls() {
    initEmptyGrid();
    Object.values(roomMarkers).forEach((coords) => {
        if (coords.x < COLS && coords.y < ROWS) {
            grid[coords.x][coords.y] = 0;
        }
    });
    if (base.x < COLS && base.y < ROWS) {
        grid[base.x][base.y] = 0;
    }
    drawPreviewPath();
}

canvas.addEventListener('mousedown', (event) => {
    isDragging = true;
    handleInput(event.clientX, event.clientY);
});

canvas.addEventListener('mousemove', (event) => {
    if (isDragging && currentMode === 'wall') {
        handleInput(event.clientX, event.clientY);
    }
});

window.addEventListener('mouseup', () => {
    isDragging = false;
});

canvas.addEventListener('touchstart', (event) => {
    isDragging = true;
    handleInput(event.touches[0].clientX, event.touches[0].clientY);
    event.preventDefault();
}, { passive: false });

canvas.addEventListener('touchmove', (event) => {
    if (isDragging && currentMode === 'wall') {
        handleInput(event.touches[0].clientX, event.touches[0].clientY);
    }
    event.preventDefault();
}, { passive: false });

window.addEventListener('touchend', () => {
    isDragging = false;
});

window.addEventListener('resize', () => {
    loadMapFromDB();
});

loadMapFromDB();
setMode('wall');
