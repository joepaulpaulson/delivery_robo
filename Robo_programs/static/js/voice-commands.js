/**
 * Voice Command Recognition Module
 * Uses Web Speech API to capture voice and send to backend
 */

class VoiceCommandSystem {
    constructor() {
        this.recognition = null;
        this.isListening = false;
        this.initElements();
        this.initSpeechRecognition();
        this.setupEventListeners();
    }

    initElements() {
        this.voiceBtn = document.getElementById('voiceBtn');
        this.voiceBtnText = document.getElementById('voiceBtnText');
        this.voiceOverlay = document.getElementById('voiceOverlay');
        this.voiceStatus = document.getElementById('voiceStatus');
        this.transcriptBox = document.getElementById('transcriptBox');
        this.toast = document.getElementById('toast');
        this.toastMessage = document.getElementById('toastMessage');
    }

    initSpeechRecognition() {
        // Check browser support
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (!SpeechRecognition) {
            console.error('Speech Recognition not supported in this browser');
            this.voiceBtn.disabled = true;
            this.voiceBtn.innerHTML = '<i class="fas fa-microphone-slash"></i> Not Supported';
            return;
        }

        // Initialize Speech Recognition
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;  // Stop after one result
        this.recognition.interimResults = true;  // Show partial results
        this.recognition.lang = 'en-US';  // Language

        // Event Handlers
        this.recognition.onstart = () => {
            console.log('Voice recognition started');
            this.onRecognitionStart();
        };

        this.recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(result => result[0])
                .map(result => result.transcript)
                .join('');

            console.log('Transcript:', transcript);
            this.transcriptBox.textContent = transcript;

            // If final result, process it
            if (event.results[0].isFinal) {
                this.processVoiceCommand(transcript);
            }
        };

        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.onRecognitionError(event.error);
        };

        this.recognition.onend = () => {
            console.log('Voice recognition ended');
            this.onRecognitionEnd();
        };
    }

    setupEventListeners() {
        this.voiceBtn.addEventListener('click', () => {
            if (this.isListening) {
                this.stopListening();
            } else {
                this.startListening();
            }
        });

        // Close overlay on click outside
        this.voiceOverlay.addEventListener('click', (e) => {
            if (e.target === this.voiceOverlay) {
                this.stopListening();
            }
        });

        // Keyboard shortcut: Press 'V' to activate voice
        document.addEventListener('keydown', (e) => {
            if (e.key === 'v' || e.key === 'V') {
                // Don't trigger if typing in input
                if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
                    this.startListening();
                }
            }
        });
    }

    startListening() {
        if (!this.recognition) {
            this.showToast('Voice recognition not available', 'error');
            return;
        }

        try {
            this.recognition.start();
        } catch (error) {
            console.error('Failed to start recognition:', error);
            this.showToast('Failed to start voice recognition', 'error');
        }
    }

    stopListening() {
        if (this.recognition && this.isListening) {
            this.recognition.stop();
        }
    }

    onRecognitionStart() {
        this.isListening = true;
        this.voiceBtn.classList.add('listening');
        this.voiceBtnText.textContent = 'Listening...';
        this.voiceOverlay.classList.add('active');
        this.voiceStatus.textContent = 'Listening...';
        this.transcriptBox.textContent = 'Waiting for voice input...';
    }

    onRecognitionEnd() {
        this.isListening = false;
        this.voiceBtn.classList.remove('listening');
        this.voiceBtnText.textContent = 'Voice Command';
        this.voiceOverlay.classList.remove('active');
    }

    onRecognitionError(error) {
        this.showToast(`Voice error: ${error}`, 'error');
        this.onRecognitionEnd();
    }

    async processVoiceCommand(transcript) {
        // Update UI
        this.voiceStatus.textContent = 'Processing...';
        
        try {
            // Send to backend
            const response = await fetch('/api/voice/process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: transcript
                })
            });

            const data = await response.json();

            if (data.success) {
                // Success!
                this.voiceStatus.textContent = '✓ Command Scheduled';
                this.showToast(data.message, 'success');
                
                // Close overlay after 2 seconds
                setTimeout(() => {
                    this.onRecognitionEnd();
                    this.refreshSchedule();
                }, 2000);
            } else {
                // Failed to parse
                this.voiceStatus.textContent = '✗ Could not understand';
                this.transcriptBox.innerHTML = `
                    <div style="color: var(--danger)">${data.error}</div>
                    <div style="font-size: 0.8rem; margin-top: 10px;">
                        ${data.details || 'Please try again'}
                    </div>
                `;
                this.showToast(data.error, 'error');
                
                // Auto-restart listening after 3 seconds
                setTimeout(() => {
                    this.onRecognitionEnd();
                }, 3000);
            }
        } catch (error) {
            console.error('Failed to process command:', error);
            this.voiceStatus.textContent = '✗ Server Error';
            this.showToast('Failed to process command', 'error');
            
            setTimeout(() => {
                this.onRecognitionEnd();
            }, 3000);
        }
    }

    showToast(message, type = 'info') {
        this.toastMessage.textContent = message;
        this.toast.className = `toast show ${type}`;
        
        setTimeout(() => {
            this.toast.classList.remove('show');
        }, 5000);
    }

    async refreshSchedule() {
        // Reload schedule from backend
        try {
            const response = await fetch('/api/schedule/today');
            const schedule = await response.json();
            
            // Update schedule list
            const scheduleList = document.getElementById('scheduleList');
            if (scheduleList && schedule) {
                this.renderSchedule(schedule);
            }
        } catch (error) {
            console.error('Failed to refresh schedule:', error);
        }
    }

    renderSchedule(schedule) {
        const scheduleList = document.getElementById('scheduleList');
        scheduleList.innerHTML = '';

        schedule.forEach(item => {
            const time = new Date(item.time);
            const timeStr = time.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit'
            });

            const itemEl = document.createElement('div');
            itemEl.className = `timeline-item ${item.status === 'pending' ? 'active' : ''}`;
            
            const statusIcon = item.status === 'completed' 
                ? '<i class="fas fa-check-circle" style="color:var(--accent-green)"></i> Completed'
                : item.status === 'pending'
                ? '<small style="color:var(--accent-blue)">Pending</small>'
                : '';

            itemEl.innerHTML = `
                <div class="time-box" style="${item.status === 'pending' ? 'color:var(--accent-blue)' : ''}">${timeStr}</div>
                <div class="med-details">
                    <h4>${item.task}</h4>
                    <p>${item.notes || ''}</p>
                    ${statusIcon}
                </div>
            `;

            scheduleList.appendChild(itemEl);
        });
    }

    // Test function
    async testParsing(testText) {
        const response = await fetch('/api/voice/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: testText })
        });
        const data = await response.json();
        console.log('Test parsing result:', data);
        return data;
    }
}

// Initialize on page load
let voiceSystem;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        voiceSystem = new VoiceCommandSystem();
        console.log('✓ Voice Command System initialized');
        console.log('💡 Press "V" key or click the Voice Command button to start');
    });
} else {
    voiceSystem = new VoiceCommandSystem();
    console.log('✓ Voice Command System initialized');
}

// Expose for debugging
window.voiceSystem = voiceSystem;