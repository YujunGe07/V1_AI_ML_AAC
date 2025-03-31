// Constants
const API_URL = 'http://localhost:5000';
const ENDPOINTS = {
    process: `${API_URL}/process`,
    config: `${API_URL}/config`,
    health: `${API_URL}/health`
};

// Add these constants and classes at the top of your script.js
const KNOWN_LOCATIONS = {
    home: { lat: 37.7749, lng: -122.4194 },    // SF City Center
    work: { lat: 37.7845, lng: -122.4072 },    // Financial District
    school: { lat: 37.8719, lng: -122.2585 }   // UC Berkeley
};

// Prediction Module
class PredictionService {
    constructor() {
        this.API_URL = 'http://localhost:5000';
    }

    async getPredictions(text) {
        try {
            const response = await fetch(`${this.API_URL}/process`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text, type: 'text' })
            });
            
            const result = await response.json();
            return result.data?.predictions || [];
        } catch (error) {
            console.error('Prediction error:', error);
            return [];
        }
    }
}

// Context Detection Module
class ContextDetectionService {
    constructor() {
        this.currentContext = {
            location: 'unknown',
            timeOfDay: 'morning',
            activity: 'idle',
            confidence: 0
        };
        
        this.lastActivity = Date.now();
        this.activityTimer = null;
        this.locationWatcher = null;
        
        // Start all detection systems
        this.startLocationDetection();
        this.startTimeDetection();
        this.startActivityDetection();
    }

    startLocationDetection() {
        if (navigator.geolocation) {
            this.locationWatcher = navigator.geolocation.watchPosition(
                (position) => {
                    const { latitude, longitude } = position.coords;
                    const location = this.getLocationName(latitude, longitude);
                    
                    this.updateContext({
                        location,
                        confidence: Math.max(this.currentContext.confidence, 0.7)
                    });
                },
                () => {
                    this.updateContext({
                        location: 'unknown',
                        confidence: Math.min(this.currentContext.confidence, 0.3)
                    });
                }
            );
        }
    }

    getLocationName(latitude, longitude) {
        for (const [name, coords] of Object.entries(KNOWN_LOCATIONS)) {
            const distance = Math.sqrt(
                Math.pow(latitude - coords.lat, 2) + 
                Math.pow(longitude - coords.lng, 2)
            );
            if (distance < 0.01) { // Roughly 1km
                return name;
            }
        }
        return 'unknown';
    }

    startTimeDetection() {
        const updateTimeOfDay = () => {
            const hour = new Date().getHours();
            let timeOfDay;
            
            if (hour >= 5 && hour < 12) timeOfDay = 'morning';
            else if (hour >= 12 && hour < 17) timeOfDay = 'afternoon';
            else timeOfDay = 'evening';

            this.updateContext({
                timeOfDay,
                confidence: Math.max(this.currentContext.confidence, 0.9)
            });
        };

        updateTimeOfDay();
        this.timeInterval = setInterval(updateTimeOfDay, 60000);
    }

    startActivityDetection() {
        const updateActivity = (activity) => {
            this.lastActivity = Date.now();
            this.updateContext({
                activity,
                confidence: Math.max(this.currentContext.confidence, 0.6)
            });
        };

        // Set up event listeners
        const handlers = {
            keydown: () => updateActivity('typing'),
            mousemove: () => updateActivity('active'),
            focus: () => updateActivity('focused')
        };

        Object.entries(handlers).forEach(([event, handler]) => {
            window.addEventListener(event, handler);
        });

        // Check for idle state
        this.activityTimer = setInterval(() => {
            if (Date.now() - this.lastActivity > 60000) {
                this.updateContext({
                    activity: 'idle',
                    confidence: Math.max(this.currentContext.confidence, 0.8)
                });
            }
        }, 10000);
    }

    updateContext(newContext) {
        this.currentContext = {
            ...this.currentContext,
            ...newContext
        };
        
        // Dispatch event for UI updates
        const event = new CustomEvent('contextUpdate', { 
            detail: this.currentContext 
        });
        window.dispatchEvent(event);
    }

    getCurrentContext() {
        return this.currentContext;
    }

    cleanup() {
        if (this.locationWatcher) {
            navigator.geolocation.clearWatch(this.locationWatcher);
        }
        if (this.timeInterval) {
            clearInterval(this.timeInterval);
        }
        if (this.activityTimer) {
            clearInterval(this.activityTimer);
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

// Add this class after your existing ContextDetectionService class

class ContextModelService {
    constructor() {
        this.phraseHistory = [];
        this.currentPrediction = {
            context: {
                location: 'unknown',
                timeOfDay: 'morning',
                activity: 'idle',
                confidence: 0
            },
            confidence: 0
        };
    }

    addPhraseUsage(phrase, context) {
        this.phraseHistory.push({
            phrase,
            timestamp: Date.now(),
            context
        });
        
        // Update prediction when new phrase is added
        this.predictContext();
    }

    predictContext() {
        if (this.phraseHistory.length === 0) return;

        // Get recent history (last hour)
        const recentHistory = this.phraseHistory.filter(
            usage => Date.now() - usage.timestamp < 3600000
        );

        if (recentHistory.length === 0) return;

        // Simple frequency-based prediction
        const contextFrequency = recentHistory.reduce((acc, curr) => {
            const key = `${curr.context.location}-${curr.context.timeOfDay}-${curr.context.activity}`;
            acc[key] = (acc[key] || 0) + 1;
            return acc;
        }, {});

        // Find most frequent context
        const sortedContexts = Object.entries(contextFrequency)
            .sort(([, a], [, b]) => b - a);

        if (sortedContexts.length === 0) return;

        const [mostFrequent] = sortedContexts;
        const [context] = mostFrequent;
        const [location, timeOfDay, activity] = context.split('-');

        // Calculate confidence based on frequency
        const totalUsage = Object.values(contextFrequency)
            .reduce((a, b) => a + b, 0);
        const confidence = contextFrequency[context] / totalUsage;

        this.currentPrediction = {
            context: {
                location,
                timeOfDay,
                activity,
                confidence
            },
            confidence
        };

        // Dispatch event for UI updates
        const event = new CustomEvent('contextModelUpdate', {
            detail: this.currentPrediction.context
        });
        window.dispatchEvent(event);
    }

    getCurrentPrediction() {
        return this.currentPrediction;
    }
}

// Main AAC Interface Class
class AACInterface {
    constructor() {
        // Initialize services
        this.predictionService = new PredictionService();
        this.contextService = new ContextDetectionService();
        this.speechService = new SpeechService();
        
        // Initialize interface elements
        this.initializeElements();
        this.bindEvents();
        
        // Initialize context detection
        this.contextDetection = new ContextDetectionService();
        
        // Add context update listener
        window.addEventListener('contextUpdate', (event) => {
            this.updateContextDisplay(event.detail);
        });

        // Add context model service
        this.contextModelService = new ContextModelService();
        
        // Add context model update listener
        window.addEventListener('contextModelUpdate', (event) => {
            this.updateContextModelDisplay(event.detail);
        });

        // Enhance speech-related bindings
        this.enhanceSpeechBindings();
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

    async processInput(text) {
        try {
            this.setLoading(true);
            const response = await fetch(ENDPOINTS.process, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text })
            });

            const data = await response.json();
            
            if (data.status === 'success') {
                // Update context from backend response
                if (data.data.context) {
                    this.updateContextDisplay(data.data.context);
                    // Also update context model
                    this.contextModelService.addPhraseUsage(text, data.data.context);
                }
                
                // Update predictions
                this.updatePredictions(data.data.predictions || []);
            } else {
                this.showError(data.message || 'Error processing input');
            }
        } catch (error) {
            this.showError('Network error: Could not process input');
        } finally {
            this.setLoading(false);
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

    updateContextDisplay(context) {
        if (this.contextDisplay) {
            const confidence = Math.round((context.confidence || 0) * 100);
            this.contextDisplay.innerHTML = `
                <div class="context-info">
                    <div class="context-label">
                        <strong>Context:</strong> ${context.label || 'unknown'}
                    </div>
                    <div class="context-details">
                        <span class="confidence">Confidence: ${confidence}%</span>
                        ${context.location ? `<span class="location">Location: ${context.location}</span>` : ''}
                        ${context.timeOfDay ? `<span class="time">Time: ${context.timeOfDay}</span>` : ''}
                    </div>
                </div>
            `;
        }
    }

    updateContextModelDisplay(contextModel) {
        const contextDisplay = document.getElementById('context-display');
        if (contextDisplay) {
            const confidence = Math.round(contextModel.confidence * 100);
            contextDisplay.innerHTML = `
                <div class="flex flex-col space-y-1">
                    <div class="text-sm text-gray-600">
                        Location: ${contextModel.location} | Time: ${contextModel.timeOfDay} | Activity: ${contextModel.activity}
                    </div>
                    <div class="text-xs text-gray-500">
                        Confidence: ${confidence}%
                    </div>
                </div>
            `;
        }
    }

    updatePredictions(predictions) {
        // Clear previous predictions
        this.predictionsDiv.innerHTML = '';

        // Create prediction buttons
        predictions.forEach(prediction => {
            const button = document.createElement('button');
            button.className = 'suggestion-btn';
            button.textContent = prediction;
            this.predictionsDiv.appendChild(button);
        });
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
        this.showMessage(message, 'error');
    }

    showMessage(message, type = 'info') {
        const messageElement = document.getElementById('message-display');
        messageElement.textContent = message;
        messageElement.className = `message ${type}`;
        
        // Clear message after 3 seconds
        setTimeout(() => {
            messageElement.textContent = '';
            messageElement.className = 'message';
        }, 3000);
    }
}

// Initialize interface when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.aacInterface = new AACInterface();
}); 