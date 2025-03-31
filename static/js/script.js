// Constants

    
const API_URL = 'http://localhost:5000';
const ENDPOINTS = {
    process: `${API_URL}/process`,
    config: `${API_URL}/config`,
    health: `${API_URL}/health`
};


navigator.geolocation.getCurrentPosition(
    (position) => {
      console.log("Latitude:", position.coords.latitude);
      console.log("Longitude:", position.coords.longitude);
    },
    (error) => {
      console.error("Geolocation error:", error);
    }
  );
  

// Context Detection Module
class ContextDetectionService {
    constructor() {
        this.currentContext = {
            timeOfDay: '',
            location: '',
            dayType: ''
        };

        // Start context detection
        this.updateContext();
        // Update every minute
        setInterval(() => this.updateContext(), 60000);
    }

    async updateContext() {
        // Get time context
        const hour = new Date().getHours();
        if (hour >= 5 && hour < 12) {
            this.currentContext.timeOfDay = 'Morning';
        } else if (hour >= 12 && hour < 17) {
            this.currentContext.timeOfDay = 'Afternoon';
        } else {
            this.currentContext.timeOfDay = 'Evening';
        }

        // Get day type
        const day = new Date().getDay();
        this.currentContext.dayType = day === 0 || day === 6 ? 'Weekend' : 'Weekday';

        // Update UI immediately for time and day
        this.updateUI();

        // Get location
        if ('geolocation' in navigator) {
            navigator.geolocation.getCurrentPosition(
                async (position) => {
                    try {
                        const { latitude, longitude } = position.coords;
                        const response = await fetch(
                            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}`
                        );
                        const data = await response.json();
                        this.currentContext.location = data.address.city || 
                                                     data.address.town || 
                                                     data.address.village || 
                                                     'Unknown';
                        // Update UI again after getting location
                        this.updateUI();
                        // Send to backend
                        this.sendContextToBackend();
                    } catch (error) {
                        console.error("Location error:", error);
                        this.currentContext.location = 'Location unavailable';
                        this.updateUI();
                    }
                },
                (error) => {
                    console.error("Geolocation error:", error);
                    this.currentContext.location = 'Location unavailable';
                    this.updateUI();
                }
            );
        }
    }

    updateUI() {
        // Update time of day
        const timeTag = document.getElementById('time-of-day');
        if (timeTag) {
            timeTag.innerHTML = `
                <span class="text-xl">🕐</span>
                <div>
                    <p class="text-sm text-gray-500">Time of Day</p>
                    <p class="text-lg font-semibold text-gray-900">${this.currentContext.timeOfDay}</p>
                </div>
            `;
        }

        // Update location
        const locationTag = document.getElementById('location');
        if (locationTag) {
            locationTag.innerHTML = `
                <span class="text-xl">📍</span>
                <div>
                    <p class="text-sm text-gray-500">Location</p>
                    <p class="text-lg font-semibold text-gray-900">${this.currentContext.location}</p>
                </div>
            `;
        }

        // Update day type
        const dayTag = document.getElementById('day-type');
        if (dayTag) {
            dayTag.innerHTML = `
                <span class="text-xl">📆</span>
                <div>
                    <p class="text-sm text-gray-500">Day Type</p>
                    <p class="text-lg font-semibold text-gray-900">${this.currentContext.dayType}</p>
                </div>
            `;
        }
    }

    async sendContextToBackend() {
        try {
            const response = await fetch('http://localhost:5001/update-context', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(this.currentContext)
            });
            const data = await response.json();
            console.log("Backend context update:", data);
        } catch (error) {
            console.error("Failed to update backend context:", error);
        }
    }
}

// Speech Service Module
class SpeechService {
    constructor() {
        this.recognition = null;
        this.synthesis = window.speechSynthesis;
        this.isListening = false;
        this.initializeSpeechRecognition();
        this.voices = [];
        
        // Load available voices
        if (this.synthesis) {
            // Chrome loads voices asynchronously
            this.synthesis.onvoiceschanged = () => {
                this.voices = this.synthesis.getVoices();
            };
            // For browsers that load voices synchronously
            this.voices = this.synthesis.getVoices();
        }
    }

    initializeSpeechRecognition() {
        const SpeechRecognition = window.webkitSpeechRecognition || window.SpeechRecognition;
        if (SpeechRecognition) {
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = true;
            this.recognition.interimResults = true;
        }
    }

    startListening(onResult, onError) {
        if (!this.recognition) {
            onError?.('Speech recognition not supported in this browser.');
            return;
        }

        this.recognition.onstart = () => {
            this.isListening = true;
            // Dispatch event for UI updates
            window.dispatchEvent(new CustomEvent('speechStateChange', { 
                detail: { isListening: true } 
            }));
        };

        this.recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(result => result[0])
                .map(result => result.transcript)
                .join('');
            
            onResult?.(transcript);
        };

        this.recognition.onend = () => {
            this.isListening = false;
            // Dispatch event for UI updates
            window.dispatchEvent(new CustomEvent('speechStateChange', { 
                detail: { isListening: false } 
            }));
        };

        this.recognition.onerror = (event) => {
            onError?.(event.error);
            this.isListening = false;
        };

        this.recognition.start();
    }

    stopListening() {
        if (this.recognition && this.isListening) {
            this.recognition.stop();
            this.isListening = false;
        }
    }

    speak(text, options = {}, onEnd = null) {
        if (!this.synthesis || !text) return;

        const utterance = new SpeechSynthesisUtterance(text);
        
        // Apply speech options
        utterance.voice = options.voice || this.voices[0];
        utterance.pitch = options.pitch || 1;
        utterance.rate = options.rate || 1;
        utterance.volume = options.volume || 1;

        if (onEnd) utterance.onend = onEnd;
        
        // Cancel any ongoing speech
        this.synthesis.cancel();
        this.synthesis.speak(utterance);
    }
}

// Main AAC Interface Class
class AACInterface {
    constructor() {
        // Remove unused services
        this.contextService = new ContextDetectionService();
        this.speechService = new SpeechService();
        
        // Initialize interface elements
        this.initializeElements();
        this.bindEvents();
        
        // Add context update listener
        window.addEventListener('contextUpdate', (event) => {
            this.updateContextDisplay(event.detail);
        });

        // Initialize context display with current values
        const initialContext = this.contextService.getCurrentContext();
        this.updateContextDisplay({
            ...initialContext,
            label: 'general',
            confidence: 0.5,
            formality: 'neutral'
        });
    }

    initializeElements() {
        this.inputField = document.getElementById('user-input');
        this.submitBtn = document.querySelector('button[type="submit"]');
        this.predictionsDiv = document.getElementById('predictions');
        this.contextDisplay = document.getElementById('context-display');
        this.formalityDisplay = document.getElementById('formality-display');
        this.loadingIndicator = document.getElementById('loading-indicator');
        this.outputArea = document.getElementById('outputArea');
        this.suggestions = document.getElementById('suggestions');
        this.speakBtn = document.getElementById('speakBtn');
        this.micBtn = document.getElementById('micBtn');
        this.clearBtn = document.getElementById('clearBtn');
    }

    bindEvents() {
        // Enhanced speech button handling
        this.speakBtn?.addEventListener('click', () => {
            const text = this.inputField?.value.trim();
            if (text) {
                this.speakText(text);
            }
        });

        // Enhanced submit button handling
        this.submitBtn?.addEventListener('click', (e) => {
            e.preventDefault();
            const text = this.inputField?.value.trim();
            if (text) {
                this.processInput(text);
            }
        });

        // Handle suggestion clicks
        this.predictionsDiv.addEventListener('click', (e) => {
            if (e.target.classList.contains('suggestion-btn')) {
                this.handleSuggestionClick(e.target.textContent);
            }
        });

        // Listen for speech state changes
        window.addEventListener('speechStateChange', (event) => {
            this.updateSpeechUI(event.detail.isListening);
        });
    }

    enhanceSpeechBindings() {
        // Handle microphone button clicks
        this.micBtn?.addEventListener('click', () => {
            if (this.speechService.isListening) {
                this.stopListening();
            } else {
                this.startListening();
            }
        });
    }

    bindSubmitEvents() {
        // Handle form submission
        const form = document.querySelector('form');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleSubmit();
            });
        }

        // Handle input events
        this.inputField?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.handleSubmit();
            }
        });
    }

    async handleSubmit() {
        const text = this.inputField?.value.trim();
        if (!text) return;

        try {
            this.setLoading(true);
            await this.processInput(text);
            // Optionally clear input after processing
            // this.inputField.value = '';
        } catch (error) {
            this.showError('Failed to process input');
            console.error('Submit error:', error);
        } finally {
            this.setLoading(false);
        }
    }

    async processInput(text) {
        try {
            // Get current context from context service
            const currentContext = this.contextService.getCurrentContext();
            
            const response = await fetch(`${this.API_URL}/process`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    text,
                    context: {
                        timeOfDay: currentContext.timeOfDay,
                        dayType: currentContext.dayType,
                        location: currentContext.location,
                        activity: currentContext.activity
                    }
                })
            });

            const data = await response.json();
            
            if (data.status === 'success') {
                // Update predictions
                this.updatePredictions(data.data.predictions);
                
                // Combine backend and frontend context
                const combinedContext = {
                    ...data.data.context,
                    timeOfDay: currentContext.timeOfDay,
                    dayType: currentContext.dayType,
                    location: currentContext.location,
                    activity: currentContext.activity
                };
                
                // Update context display
                this.updateContextDisplay(combinedContext);
                
                if (data.data.processed_text) {
                    this.updateProcessedText(data.data.processed_text);
                }
            } else {
                throw new Error(data.message || 'Failed to process input');
            }
        } catch (error) {
            this.showError(error.message);
            throw error;
        }
    }

    handleSuggestionClick(text) {
        // Set the clicked suggestion as input
        this.inputField.value = text;
        
        // Process the new input
        this.processInput(text);
    }

    startListening() {
        this.updateSpeechUI(true);
        this.speechService.startListening(
            // On result
            (transcript) => {
                if (this.inputField) {
                    this.inputField.value = transcript;
                    // Optionally trigger input processing
                    this.processInput(transcript);
                }
            },
            // On error
            (error) => {
                this.showError(`Speech recognition error: ${error}`);
                this.updateSpeechUI(false);
            }
        );
    }

    stopListening() {
        this.speechService.stopListening();
        this.updateSpeechUI(false);
    }

    updateSpeechUI(isListening) {
        if (this.micBtn) {
            if (isListening) {
                this.micBtn.classList.add('mic-recording');
                this.micBtn.querySelector('i')?.classList.replace('ri-mic-line', 'ri-mic-fill');
            } else {
                this.micBtn.classList.remove('mic-recording');
                this.micBtn.querySelector('i')?.classList.replace('ri-mic-fill', 'ri-mic-line');
            }
        }
    }

    speakText(text) {
        if (!text) {
            text = this.inputField?.value?.trim();
        }
        
        if (!text) return;

        const options = {
            pitch: 1,
            rate: 1,
            volume: 1
        };

        // Disable speak button while speaking
        if (this.speakBtn) {
            this.speakBtn.disabled = true;
        }

        this.speechService.speak(text, options, () => {
            // Re-enable speak button after speech ends
            if (this.speakBtn) {
                this.speakBtn.disabled = false;
            }
        });
    }

    updatePredictions(predictions) {
        if (!this.predictionsDiv) return;
        
        this.predictionsDiv.innerHTML = predictions
            .map(prediction => `
                <button class="prediction-btn" 
                        onclick="window.aacInterface.usePrediction('${prediction}')">
                    ${prediction}
                </button>
            `).join('');
    }

    updateProcessedText(text) {
        if (this.outputArea) {
            this.outputArea.textContent = text;
        }
    }

    usePrediction(text) {
        if (this.inputField) {
            this.inputField.value = text;
            this.handleSubmit();
        }
    }

    setLoading(isLoading) {
        if (isLoading) {
            this.loadingIndicator.style.display = 'block';
            this.submitBtn.disabled = true;
        } else {
            this.loadingIndicator.style.display = 'none';
            this.submitBtn.disabled = false;
        }
    }

    showError(message) {
        const errorDiv = document.getElementById('error-message');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 3000);
        }
    }
}

// Initialize interface when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.aacInterface = new AACInterface();
    console.log('AACInterface initialized');

    // Test location detection
    navigator.geolocation.getCurrentPosition(
        (position) => {
            console.log("=== Location Test ===");
            console.log("Raw coordinates:", {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude
            });

            // Test the Nominatim API directly
            fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${position.coords.latitude}&lon=${position.coords.longitude}&addressdetails=1`)
                .then(res => res.json())
                .then(data => {
                    console.log("OpenStreetMap Data:", data);
                    console.log("Address:", data.address);
                    console.log("Display Name:", data.display_name);
                })
                .catch(err => console.error("API Error:", err));
        },
        (error) => {
            console.error("Geolocation Error:", error);
        }
    );

    // Initialize context detection
    const contextService = new ContextDetectionService();
    
    // Add click handler for location permission
    const locationTag = document.getElementById('location');
    if (locationTag) {
        locationTag.addEventListener('click', () => {
            contextService.updateContext();
        });
    }
});