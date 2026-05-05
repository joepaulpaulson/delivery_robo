/**
 * Medical Robot Dashboard - Main JavaScript
 * Handles real-time data updates, UI interactions, and API communication
 */

// ==================== CONFIGURATION ====================
const CONFIG = {
    UPDATE_INTERVALS: {
        vitals: 2000,      // Update vitals every 2 seconds
        schedule: 10000,   // Update schedule every 10 seconds
        inventory: 5000,   // Update inventory every 5 seconds
        status: 3000       // Update robot status every 3 seconds
    },
    API_BASE: '',  // Same origin
    ALERT_THRESHOLDS: {
        heartRate: { min: 50, max: 120 },
        spo2: { min: 92 },
        battery: { critical: 20 },
        water: { critical: 2 },
        pills: { critical: 3 }
    }
};

// ==================== STATE MANAGEMENT ====================
const AppState = {
    privacyMode: false,
    audioEnabled: false,
    lastVitals: null,
    alerts: [],
    isEmergency: false
};

// ==================== UTILITY FUNCTIONS ====================
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 
                          type === 'warning' ? 'exclamation-triangle' : 
                          type === 'error' ? 'times-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    container.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function formatTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
}

function isInRange(value, min, max) {
    return value >= min && value <= max;
}

// ==================== API CALLS ====================
async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(`${CONFIG.API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        showToast(`Failed to fetch ${endpoint}`, 'error');
        return null;
    }
}

// ==================== VITALS UPDATES ====================
async function updateVitals() {
    const data = await fetchAPI('/api/vitals/current');
    if (!data) return;
    
    AppState.lastVitals = data;
    
    // Update UI
    document.getElementById('heartRate').textContent = data.heart_rate || '--';
    document.getElementById('spo2').textContent = data.spo2 || '--';
    document.getElementById('temperature').textContent = data.temperature ? 
        data.temperature.toFixed(1) : '--';
    
    // Check for alerts
    const hrCard = document.getElementById('heartRateCard');
    const spo2Card = document.getElementById('spo2Card');
    
    if (data.heart_rate) {
        const { min, max } = CONFIG.ALERT_THRESHOLDS.heartRate;
        if (!isInRange(data.heart_rate, min, max)) {
            hrCard.classList.add('alert');
            if (!AppState.alerts.includes('heart_rate')) {
                showToast(`⚠️ Heart Rate Alert: ${data.heart_rate} BPM`, 'warning');
                AppState.alerts.push('heart_rate');
            }
        } else {
            hrCard.classList.remove('alert');
            AppState.alerts = AppState.alerts.filter(a => a !== 'heart_rate');
        }
    }
    
    if (data.spo2 && data.spo2 < CONFIG.ALERT_THRESHOLDS.spo2.min) {
        spo2Card.classList.add('alert');
        if (!AppState.alerts.includes('spo2')) {
            showToast(`⚠️ Low Blood Oxygen: ${data.spo2}%`, 'warning');
            AppState.alerts.push('spo2');
        }
    } else {
        spo2Card.classList.remove('alert');
        AppState.alerts = AppState.alerts.filter(a => a !== 'spo2');
    }
}

// ==================== SCHEDULE/TIMELINE ====================
async function updateSchedule() {
    const schedule = await fetchAPI('/api/schedule/today');
    if (!schedule) return;
    
    const container = document.getElementById('timeline');
    container.innerHTML = '';
    
    schedule.forEach(item => {
        const timelineItem = document.createElement('div');
        timelineItem.className = 'timeline-item';
        
        const status = item.status || 'pending';
        const icon = status === 'completed' ? 'fa-check' : 
                    status === 'pending' ? 'fa-clock' : 'fa-times';
        
        timelineItem.innerHTML = `
            <div class="timeline-marker ${status}">
                <i class="fas ${icon}"></i>
            </div>
            <div class="timeline-content">
                <div class="timeline-time">${formatTime(item.time)}</div>
                <div class="timeline-task">${item.task}</div>
                ${item.notes ? `<div class="timeline-notes">${item.notes}</div>` : ''}
            </div>
        `;
        
        container.appendChild(timelineItem);
    });
}

// ==================== INVENTORY ====================
async function updateInventory() {
    const data = await fetchAPI('/api/inventory');
    if (!data) return;
    
    const container = document.getElementById('inventoryGrid');
    container.innerHTML = '';
    
    data.inventory.forEach(item => {
        const percentage = item.item === 'Battery' ? item.quantity : 
                          (item.quantity / (item.item === 'Medicine Pills' ? 30 : 10)) * 100;
        
        let statusClass = '';
        if (item.item === 'Medicine Pills' && item.quantity < CONFIG.ALERT_THRESHOLDS.pills.critical) {
            statusClass = 'critical';
        } else if (item.item === 'Water' && item.quantity < CONFIG.ALERT_THRESHOLDS.water.critical) {
            statusClass = 'warning';
        } else if (item.item === 'Battery' && item.quantity < CONFIG.ALERT_THRESHOLDS.battery.critical) {
            statusClass = 'critical';
        }
        
        const inventoryItem = document.createElement('div');
        inventoryItem.className = 'inventory-item';
        inventoryItem.innerHTML = `
            <div class="inventory-header">
                <span class="inventory-name">${item.item}</span>
                <span class="inventory-value ${statusClass}">
                    ${item.quantity} ${item.unit}
                </span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill ${statusClass}" 
                     style="width: ${Math.min(percentage, 100)}%"></div>
            </div>
        `;
        container.appendChild(inventoryItem);
    });
    
    // Show alerts
    data.alerts.forEach(alert => {
        const alertKey = `inventory_${alert.item}`;
        if (!AppState.alerts.includes(alertKey)) {
            showToast(`🔔 ${alert.item} is ${alert.level === 'critical' ? 'critically' : ''} low!`, 
                     alert.level === 'critical' ? 'error' : 'warning');
            AppState.alerts.push(alertKey);
        }
    });
}

// ==================== ROBOT STATUS ====================
async function updateRobotStatus() {
    const status = await fetchAPI('/api/robot/status');
    if (!status) return;
    
    // Update battery in inventory display
    // This will be caught by the next inventory update
}

// ==================== CAMERA CONTROLS ====================
function setupCameraControls() {
    const privacyBtn = document.getElementById('privacyBtn');
    const audioBtn = document.getElementById('audioBtn');
    const privacyOverlay = document.getElementById('privacyOverlay');
    
    privacyBtn.addEventListener('click', async () => {
        const response = await fetchAPI('/camera/privacy', { method: 'POST' });
        if (response && response.success) {
            AppState.privacyMode = response.privacy_mode;
            privacyBtn.classList.toggle('active', AppState.privacyMode);
            privacyOverlay.classList.toggle('active', AppState.privacyMode);
            showToast(`Privacy mode ${AppState.privacyMode ? 'enabled' : 'disabled'}`, 'info');
        }
    });
    
    audioBtn.addEventListener('click', () => {
        AppState.audioEnabled = !AppState.audioEnabled;
        audioBtn.classList.toggle('active', AppState.audioEnabled);
        showToast(`Two-way audio ${AppState.audioEnabled ? 'enabled' : 'disabled'}`, 'info');
    });
}

// ==================== ROBOT CONTROLS ====================
function setupRobotControls() {
    // D-Pad controls
    document.querySelectorAll('.d-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const command = btn.dataset.cmd;
            const response = await fetchAPI('/api/robot/command', {
                method: 'POST',
                body: JSON.stringify({ command })
            });
            
            if (response && response.success) {
                showToast(response.message, response.alert ? 'warning' : 'success');
            }
        });
    });
    
    // Dock button
    document.querySelector('.dock-btn').addEventListener('click', async () => {
        const response = await fetchAPI('/api/robot/command', {
            method: 'POST',
            body: JSON.stringify({ command: 'dock' })
        });
        
        if (response && response.success) {
            showToast(response.message, 'info');
        }
    });
}

// ==================== EMERGENCY HANDLING ====================
function setupEmergencyButton() {
    const emergencyBtn = document.getElementById('emergencyBtn');
    const modal = document.getElementById('emergencyModal');
    const cancelBtn = document.getElementById('cancelEmergency');
    const confirmBtn = document.getElementById('confirmEmergency');
    
    emergencyBtn.addEventListener('click', () => {
        modal.classList.add('active');
    });
    
    cancelBtn.addEventListener('click', () => {
        modal.classList.remove('active');
    });
    
    confirmBtn.addEventListener('click', async () => {
        modal.classList.remove('active');
        
        const response = await fetchAPI('/api/emergency', {
            method: 'POST',
            body: JSON.stringify({ type: 'user_initiated' })
        });
        
        if (response && response.success) {
            showToast('🚨 EMERGENCY ALERT SENT', 'error');
            AppState.isEmergency = true;
            
            // Visual feedback
            document.body.style.animation = 'emergencyFlash 1s infinite';
        }
    });
}

// ==================== DATETIME UPDATE ====================
function updateDateTime() {
    const now = new Date();
    const formatted = now.toLocaleString('en-US', {
        weekday: 'short',
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    document.getElementById('datetime').textContent = formatted;
}

// ==================== INITIALIZATION ====================
function init() {
    console.log('🏥 Medical Robot Dashboard Initializing...');
    
    // Setup controls
    setupCameraControls();
    setupRobotControls();
    setupEmergencyButton();
    
    // Initial data fetch
    updateVitals();
    updateSchedule();
    updateInventory();
    updateRobotStatus();
    
    // Setup periodic updates
    setInterval(updateVitals, CONFIG.UPDATE_INTERVALS.vitals);
    setInterval(updateSchedule, CONFIG.UPDATE_INTERVALS.schedule);
    setInterval(updateInventory, CONFIG.UPDATE_INTERVALS.inventory);
    setInterval(updateRobotStatus, CONFIG.UPDATE_INTERVALS.status);
    setInterval(updateDateTime, 1000);
    
    // Initial datetime
    updateDateTime();
    
    console.log('✓ Dashboard Ready');
    showToast('Dashboard connected', 'success');
}

// Start when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}