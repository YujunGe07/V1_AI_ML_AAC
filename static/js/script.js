// === Constants ===
const API_URL = 'http://127.0.0.1:5001';
const ENDPOINTS = {
    process: `${API_URL}/process`,
    config: `${API_URL}/config`,
    health: `${API_URL}/health`
};

let isRecording = false;
let currentLanguage = 'en-US';
let selectedVoiceGender = 'male';
let ttsVoicePitch = 1.0;
let ttsVoiceRate = 1.0;
let isSpeaking = false;

function updateSpeakButtonState(isSpeaking) {
    const speakBtn = document.getElementById('speakBtn');
    if (speakBtn) {
        if (isSpeaking) {
            speakBtn.classList.add('speaking');
            speakBtn.innerHTML = `
                <i class="ri-volume-up-fill"></i>
                <span class="action-button-label">Speaking...</span>
                <div class="absolute bottom-0 left-0 w-full h-1 bg-white opacity-20 speaking-indicator"></div>
            `;
            speakBtn.disabled = true;
        } else {
            speakBtn.classList.remove('speaking');
            speakBtn.innerHTML = `
                <i class="ri-volume-up-line"></i>
                <span class="action-button-label">Speak</span>
                <div class="absolute bottom-0 left-0 w-full h-1 bg-white opacity-20 speaking-indicator"></div>
            `;
            speakBtn.disabled = false;
        }
    }
}

function ensureVoicesLoaded() {
    return new Promise((resolve) => {
      let voices = speechSynthesis.getVoices();
      if (voices.length) return resolve(voices);
  
      speechSynthesis.onvoiceschanged = () => {
        voices = speechSynthesis.getVoices();
        resolve(voices);
      };
    });
  }

// === Context Detection ===
class ContextDetectionService {
    constructor() {
        this.currentContext = { timeOfDay: '', location: '', dayType: '' };
        this.updateContext();
        setInterval(() => this.updateContext(), 60000);
    }

    async updateContext() {
        const hour = new Date().getHours();
        if (hour >= 5 && hour < 12) this.currentContext.timeOfDay = 'Morning';
        else if (hour >= 12 && hour < 17) this.currentContext.timeOfDay = 'Afternoon';
        else this.currentContext.timeOfDay = 'Evening';

        const day = new Date().getDay();
        this.currentContext.dayType = day === 0 || day === 6 ? 'Weekend' : 'Weekday';

        if ('geolocation' in navigator) {
            navigator.geolocation.getCurrentPosition(async (position) => {
                try {
                    const { latitude, longitude } = position.coords;
                    const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}`);
                    const data = await response.json();
                    this.currentContext.location = data.address.city || data.address.town || data.address.village || 'Unknown';
                    this.updateUI();
                    this.sendContextToBackend();
                } catch (error) {
                    this.currentContext.location = 'Location unavailable';
                    this.updateUI();
                }
            }, () => {
                this.currentContext.location = 'Location unavailable';
                this.updateUI();
            });
        } else {
            this.updateUI();
        }
    }

    updateUI() {
        const timeTag = document.getElementById('time-of-day');
        if (timeTag) timeTag.textContent = this.currentContext.timeOfDay;
        const locTag = document.getElementById('location');
        if (locTag) locTag.textContent = this.currentContext.location;
        const dayTag = document.getElementById('day-type');
        if (dayTag) dayTag.textContent = this.currentContext.dayType;
    }

    async sendContextToBackend() {
        try {
            await fetch(`${API_URL}/update-context`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.currentContext)
            });
        } catch (err) {
            console.error('Context update failed:', err);
        }
    }

    getCurrentContext() {
        return this.currentContext;
    }
}

// === Speech Service ===
class SpeechService {
    constructor() {
        this.recognition = null;
        this.synthesis = window.speechSynthesis;
        this.voices = [];
        this.isListening = false;

        // Initialize speech recognition
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = true;
            this.recognition.interimResults = true;
            this.recognition.lang = currentLanguage || 'en-US';

            // Set up event handlers
            this.recognition.onresult = (event) => {
                const transcript = Array.from(event.results)
                    .map(result => result[0].transcript)
                    .join('');
                
                // Update both transcript displays
                const liveTranscript = document.getElementById('liveTranscript');
                const overlayTranscript = document.getElementById('overlayTranscript');
                const outputText = document.getElementById('outputText');
                
                if (liveTranscript) liveTranscript.textContent = transcript;
                if (overlayTranscript) overlayTranscript.textContent = transcript;
                
                // Update output text if it's a final result
                if (event.results[event.results.length - 1].isFinal) {
                    if (outputText) outputText.value = transcript;
                }
            };

            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                showFeedbackToast(`Speech recognition error: ${event.error}`);
                this.isListening = false;
            };

            this.recognition.onend = () => {
                this.isListening = false;
            };
        }

        // Initialize speech synthesis voices
        if (this.synthesis) {
            this.synthesis.onvoiceschanged = () => {
                this.voices = this.synthesis.getVoices();
            };
            this.voices = this.synthesis.getVoices();
        }
    }

    startListening() {
        if (!this.recognition) {
            showFeedbackToast('Speech recognition not supported in your browser');
            return false;
        }

        if (this.isListening) {
            console.log('Speech recognition is already running');
            return true;
        }

        try {
            this.recognition.start();
            this.isListening = true;
            return true;
        } catch (error) {
            console.error('Error starting speech recognition:', error);
            showFeedbackToast('Failed to start speech recognition');
            this.isListening = false;
            return false;
        }
    }

    stopListening() {
        if (this.recognition) {
            this.isListening = false;
            this.recognition.stop();
        }
    }

    speakText(text) {
        if (isSpeaking) {
            console.warn("Already speaking, skipping");
            return false;
        }
        isSpeaking = true;
    
        try {
            if (!text) {
                const outputText = document.getElementById('outputText');
                text = outputText?.value?.trim();
            }
    
            if (!text) {
                showFeedbackToast('No text to speak');
                isSpeaking = false;
                return false;
            }
    
            fetch(`${API_URL}/speak`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    text: text,
                    voice: selectedVoiceGender || 'male'
                })
            })
            .then(res => res.blob())
            .then(blob => {
                const audioURL = URL.createObjectURL(blob);
                const audio = new Audio(audioURL);
    
                audio.onplay = () => {
                    updateSpeakButtonState(true);
                    showFeedbackToast("Speaking...");
                };
    
                audio.onended = () => {
                    updateSpeakButtonState(false);
                    isSpeaking = false;
                    showFeedbackToast("Finished speaking");
                };
    
                audio.onerror = () => {
                    updateSpeakButtonState(false);
                    isSpeaking = false;
                    showFeedbackToast("Error while playing audio");
                };
    
                audio.play();
            })
            .catch(err => {
                console.error("TTS error:", err);
                updateSpeakButtonState(false);
                isSpeaking = false;
                showFeedbackToast("Failed to speak");
            });
    
            return true;
        } catch (err) {
            console.error("TTS Exception:", err);
            updateSpeakButtonState(false);
            isSpeaking = false;
            showFeedbackToast("Failed to speak");
            return false;
        }
    }
    
    
}

// === Audio Recorder ===
class AudioRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
    }

    async startRecording() {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this.mediaRecorder = new MediaRecorder(stream);
        this.audioChunks = [];
        this.mediaRecorder.ondataavailable = e => this.audioChunks.push(e.data);
        this.mediaRecorder.onstop = async () => {
            const blob = new Blob(this.audioChunks, { type: 'audio/webm' });
            await this.transcribeAudio(blob);
            stream.getTracks().forEach(track => track.stop());
        };
        this.mediaRecorder.start();
        this.isRecording = true;
    }

    stopRecording() {
        if (this.mediaRecorder) {
            this.mediaRecorder.stop();
            this.isRecording = false;
        }
    }

    async transcribeAudio(blob) {
        const formData = new FormData();
        formData.append('audio', blob);
        const response = await fetch(`${API_URL}/transcribe-audio`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        const transcript = data.transcript || '';
        document.getElementById('outputText').value = transcript;

        const liveTranscriptBox = document.getElementById('liveTranscript');
        if (liveTranscriptBox) {
          if (liveTranscriptBox) liveTranscriptBox.textContent = transcript;
          const overlayTranscript = document.getElementById('overlayTranscript');
          if (overlayTranscript) overlayTranscript.textContent = transcript;

        }

    }
}

// === AAC Interface ===
class AACInterface {
    constructor() {
        this.contextService = new ContextDetectionService();
        this.recorder = new AudioRecorder();
        this.speechService = new SpeechService();

        this.inputField = document.getElementById('user-input');
        this.outputText = document.getElementById('outputText');
        this.speakBtn = document.getElementById('speakBtn');
        this.micBtn = document.getElementById('micBtn');
        this.clearBtn = document.getElementById('clearBtn');
        this.predictionsDiv = document.getElementById('predictions');
        this.suggestionsContainer = document.getElementById('suggestions');

        this.bindEvents();
    }

    bindEvents() {
        this.speakBtn?.addEventListener('click', () => {
            const text = this.outputText?.value?.trim();
            if (text) {
                this.speechService.speakText(text);
            } else {
                showFeedbackToast('No text to speak');
            }
        });

        this.micBtn?.addEventListener('click', () => {
            if (!isRecording) {
                this.startListening();
            } else {
                this.stopListening();
            }
        });

        this.clearBtn?.addEventListener('click', () => {
            this.inputField.value = '';
            this.outputText.value = '';
        });

        document.querySelectorAll('.suggestion-btn')?.forEach(btn => {
            btn.addEventListener('click', () => {
                this.inputField.value = btn.textContent;
            });
        });
    }

    async startListening() {
        if (!window.aacInterface?.speechService) {
            window.aacInterface = new AACInterface();
        }

        if (isRecording) {
            console.log('Already recording, ignoring start request');
            return;
        }

        isRecording = true;
        this.micBtn.classList.add('mic-recording');
        this.micBtn.querySelector('i').classList.replace('ri-mic-line', 'ri-mic-fill');
        document.getElementById('listeningOverlay').classList.add('active');

        // Start speech recognition
        const success = this.speechService.startListening();
        if (success) {
            showFeedbackToast('Listening...');
        } else {
            this.stopListening();
        }
    }

    stopListening() {
        if (!isRecording) {
            console.log('Not recording, ignoring stop request');
            return;
        }

        isRecording = false;
        this.micBtn.classList.remove('mic-recording');
        this.micBtn.querySelector('i').classList.replace('ri-mic-fill', 'ri-mic-line');
        document.getElementById('listeningOverlay').classList.remove('active');

        if (this.speechService) {
            this.speechService.stopListening();
        }

        const overlayTranscript = document.getElementById('overlayTranscript');
        if (overlayTranscript) overlayTranscript.textContent = '';
    }
}

// Initialize the interface when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.aacInterface = new AACInterface();
    console.log('✅ AACInterface initialized');
    
    // Add global speakText function for backward compatibility
    window.speakText = (text) => {
        if (window.aacInterface?.speechService) {
            return window.aacInterface.speechService.speakText(text);
        }
        return false;
    };
});

async function fetchUserLocationName() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return resolve("Unknown");

    navigator.geolocation.getCurrentPosition(async (position) => {
      const { latitude, longitude } = position.coords;

      // First try Foursquare
      const fsqApiKey = "fsq3rX+qLUv4Vt7uYUIkyXVLe3rhd65P4gad/9/7pAr/0Uk=";
      try {
        const fsqResponse = await fetch(
          `https://api.foursquare.com/v3/places/search?ll=${latitude},${longitude}&limit=1`,
          {
            headers: {
              Accept: "application/json",
              Authorization: fsqApiKey,
            },
          }
        );
        const fsqData = await fsqResponse.json();
        const businessName = fsqData.results?.[0]?.name;
        if (businessName) return resolve(businessName);
      } catch (err) {
        console.warn("Foursquare failed, falling back to city");
      }

      // Fallback to city name
      try {
        const response = await fetch(
          `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`
        );
        const data = await response.json();
        const city =
          data.address.city ||
          data.address.town ||
          data.address.village ||
          data.address.hamlet ||
          "Unknown";
        resolve(city);
      } catch (err) {
        console.error("Reverse geocoding error:", err);
        resolve("Unknown");
      }
    }, () => {
      resolve("Unknown");
    });
  });
}


const mockHistory = [
{ text: "Could you please help me with this task?", time: "10:30 AM", context: "Work" },
{ text: "I'm feeling much better today, thank you!", time: "Yesterday", context: "Health" },
{ text: "The weather is beautiful outside", time: "2 days ago", context: "General" },
{ text: "I would like to order a vegetarian pizza with extra cheese", time: "3 days ago", context: "Food" },
{ text: "Can we schedule a meeting for tomorrow afternoon?", time: "4 days ago", context: "Work" },
{ text: "I'm feeling excited about the upcoming concert", time: "5 days ago", context: "Emotions" },
{ text: "Could you please pass me the water?", time: "1 week ago", context: "Food" },
{ text: "I enjoyed our conversation yesterday", time: "1 week ago", context: "Social" }
];
const phraseSuggestions = {
all: [
"How are you?",
"I need help",
"Thank you",
"Yes, please",
"No, thanks",
"Could you repeat that?",
"I don't understand"
],
emotions: [
"I'm feeling happy today",
"I'm a bit sad",
"I'm excited about this",
"I'm feeling anxious",
"I'm frustrated",
"I'm proud of myself",
"I love you"
],
food: [
"I'm hungry",
"I would like some water",
"Can I have coffee please?",
"I'd like to order pizza",
"This tastes delicious",
"I'm thirsty",
"No more, thank you"
],
home: [
"Please turn on the lights",
"Can you close the window?",
"I need help in the bathroom",
"It's too cold in here",
"I'd like to watch TV",
"Please lock the door",
"I need my medication"
],
health: [
"I'm in pain",
"I need my medication",
"I feel dizzy",
"I need to see a doctor",
"I'm feeling better today",
"I need to rest",
"Can you help me stand up?"
],
social: [
"Nice to meet you",
"How was your day?",
"I'd like to go outside",
"Can we talk later?",
"I enjoyed our conversation",
"Please give me some privacy",
"Let's celebrate together"
]
};
let filteredHistory = [...mockHistory];
let currentFilter = 'all';
function updateHistory(filter = 'all') {
const historyList = document.getElementById('historyList');
filteredHistory = filter === 'all' ?
[...mockHistory] :
mockHistory.filter(item => item.context === filter);
historyList.innerHTML = filteredHistory.map(item => `
<div class="history-item flex items-center justify-between p-5 bg-gray-100 rounded-lg transition-all duration-300 mb-4" data-context="${item.context}">
<div>
<p class="text-gray-900 font-medium">${item.text}</p>
<div class="flex items-center space-x-2 mt-2">
<span class="text-sm text-gray-400">${item.time}</span>
<span class="text-sm text-gray-500">•</span>
<span class="text-sm text-gray-500">${item.context}</span>
</div>
</div>
<div class="flex items-center space-x-3">
<button class="history-reuse w-10 h-10 flex items-center justify-center text-gray-400 hover:text-primary hover:bg-gray-200 rounded-full cursor-pointer transition-all duration-300 keyboard-focus" tabindex="0" aria-label="Reuse this phrase">
<i class="ri-restart-line ri-lg"></i>
</button>
<button class="history-speak w-10 h-10 flex items-center justify-center text-gray-400 hover:text-primary hover:bg-gray-200 rounded-full cursor-pointer transition-all duration-300 keyboard-focus" tabindex="0" aria-label="Speak this phrase">
<i class="ri-volume-up-line ri-lg"></i>
</button>
</div>
</div>
`).join('');
// Add event listeners to history buttons
document.querySelectorAll('.history-reuse').forEach((button, index) => {
button.addEventListener('click', () => {
document.getElementById('outputText').value = filteredHistory[index].text;
// Add a visual feedback
button.classList.add('text-primary', 'bg-gray-200');
setTimeout(() => {
button.classList.remove('text-primary', 'bg-gray-200');
}, 300);
});
});
document.querySelectorAll('.history-speak').forEach((button, index) => {
button.addEventListener('click', () => {
const success = speakText(filteredHistory[index].text);
if (success) {
// Add a visual feedback
button.classList.add('text-primary', 'bg-gray-200');
// Update the main speak button state
updateSpeakButtonState(true);
setTimeout(() => {
button.classList.remove('text-primary', 'bg-gray-200');
}, 300);
showFeedbackToast(`Speaking: "${filteredHistory[index].text.substring(0, 30)}${filteredHistory[index].text.length > 30 ? '...' : ''}"`);
}
});
});
}
function showFeedbackToast(message) {
const toast = document.getElementById('feedbackToast');
const messageEl = document.getElementById('feedbackMessage');
messageEl.textContent = message;
toast.classList.add('show');
setTimeout(() => {
toast.classList.remove('show');
}, 3000);
}
// Initialize speech synthesis voices
function initVoices() {
if (typeof speechSynthesis !== 'undefined') {
speechSynthesis.onvoiceschanged = function() {
// Voices are now loaded
console.log('Voices loaded:', speechSynthesis.getVoices().length);
};
}
}

document.addEventListener('DOMContentLoaded', () => {
  const closeOverrideModal = document.getElementById('closeOverrideModal');
  const manualOverrideModal = document.getElementById('manualOverrideModal');

  if (closeOverrideModal && manualOverrideModal) {
    closeOverrideModal.addEventListener('click', () => {
      manualOverrideModal.classList.add('hidden');
    });
  } else {
    console.warn('Missing #closeOverrideModal or #manualOverrideModal');
  }
});
document.addEventListener('DOMContentLoaded', () => {
    updateHistory();
    ensureVoicesLoaded().then((voices) => {
      console.log("✅ Voices loaded:", voices.length);
    });
    
const settingsBtn = document.getElementById('settingsBtn');
const profileBtn = document.getElementById('profileBtn');
const settingsModal = document.getElementById('settingsModal');
const profileModal = document.getElementById('profileModal');
const closeButtons = document.querySelectorAll('.closeModal');
const speakBtn = document.getElementById('speakBtn');
const micBtn = document.getElementById('micBtn');
const outputText = document.getElementById('outputText');
const outputArea = document.getElementById('outputArea');
const suggestionsContainer = document.getElementById('suggestions');
const darkModeToggle = document.getElementById('darkModeToggle');
const categoryTabs = document.querySelectorAll('.category-tab');
const clearBtn = document.getElementById('clearBtn');
const historyFilterBtn = document.getElementById('historyFilterBtn');
const historyFilterDropdown = document.getElementById('historyFilterDropdown');
const feedbackToast = document.getElementById('feedbackToast');
const closeFeedback = document.getElementById('closeFeedback');
const maleVoiceBtn = document.getElementById('maleVoiceBtn');
const femaleVoiceBtn = document.getElementById('femaleVoiceBtn');
const voiceSpeed = document.getElementById('voiceSpeed');
const voicePitch = document.getElementById('voicePitch');
const languageSelector = document.getElementById('languageSelector');
const languageDropdown = document.getElementById('languageDropdown');
const languageOptions = document.querySelectorAll('.language-option');
const addNewPhraseBtn = document.getElementById('addNewPhraseBtn');
const newPhraseModal = document.getElementById('newPhraseModal');
const closeNewPhraseModal = document.getElementById('closeNewPhraseModal');
const newPhraseText = document.getElementById('newPhraseText');
const newPhraseCategory = document.getElementById('newPhraseCategory');
const saveNewPhrase = document.getElementById('saveNewPhrase');
const cancelNewPhrase = document.getElementById('cancelNewPhrase');
const assistantGreeting = document.getElementById('assistantGreeting');
// Update greeting based on time of day
function updateGreeting() {
const userName = "Yujun";
const greeting = `Hi ${userName}, ready when you are.`;
assistantGreeting.innerHTML = `<span class="typing-animation">${greeting}</span>`;
}
// Call the greeting function
updateGreeting();
let isRecording = false;
let currentCategory = 'all';
let selectedVoiceGender = 'male';
let voiceRate = 1;
let savedPhrases = [
"I'm feeling great today!",
"Could you help me with something?",
"I need a break"
];
// Function to update suggestions based on category
function updateSuggestions(category) {
currentCategory = category;
suggestionsContainer.innerHTML = '';
phraseSuggestions[category].forEach(phrase => {
const button = document.createElement('button');
button.className = 'suggestion-btn px-4 py-2 bg-primary bg-opacity-10 text-primary rounded-full whitespace-nowrap text-sm font-medium hover:bg-opacity-20 cursor-pointer keyboard-focus';
button.textContent = phrase;
button.dataset.category = category;
button.setAttribute('tabindex', '0');
button.addEventListener('click', () => {
outputText.value = phrase;
});
suggestionsContainer.appendChild(button);
});
}
// Initialize with default suggestions
updateSuggestions('all');
// History filter dropdown
historyFilterBtn.addEventListener('click', () => {
historyFilterDropdown.classList.toggle('hidden');
});
// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
if (!historyFilterBtn.contains(e.target) && !historyFilterDropdown.contains(e.target)) {
historyFilterDropdown.classList.add('hidden');
}
});
// Filter history items
document.querySelectorAll('#historyFilterDropdown button').forEach(button => {
button.addEventListener('click', () => {
const filter = button.dataset.filter;
currentFilter = filter;
updateHistory(filter);
historyFilterDropdown.classList.add('hidden');
historyFilterBtn.querySelector('span').textContent = filter === 'all' ? 'Filter' : filter;
});
});
// Show tooltip on hover for mic button
micBtn.addEventListener('mouseenter', () => {
document.getElementById('micTooltip').style.opacity = '1';
});
micBtn.addEventListener('mouseleave', () => {
document.getElementById('micTooltip').style.opacity = '0';
});
const listeningOverlay = document.getElementById('listeningOverlay');
const cancelListening = document.getElementById('cancelListening');
document.querySelector('.listening-indicator')?.addEventListener('click', stopListening);
document.getElementById('doneListening')?.addEventListener('click', stopListening);
cancelListening.addEventListener('click', () => {
stopListening();
});
async function startListening() {
    if (!window.aacInterface?.speechService) {
        window.aacInterface = new AACInterface();
    }

    if (isRecording) {
        console.log('Already recording, ignoring start request');
        return;
    }

    isRecording = true;
    micBtn.classList.add('mic-recording');
    micBtn.querySelector('i').classList.replace('ri-mic-line', 'ri-mic-fill');
    listeningOverlay.classList.add('active');

    // Start real speech recognition
    const success = window.aacInterface.speechService.startListening();
    if (success) {
        showFeedbackToast('Listening...');
    }
}

function stopListening() {
    if (!isRecording) {
        console.log('Not recording, ignoring stop request');
        return;
    }

    isRecording = false;
    micBtn.classList.remove('mic-recording');
    micBtn.querySelector('i').classList.replace('ri-mic-fill', 'ri-mic-line');
    listeningOverlay.classList.remove('active');

    if (window.aacInterface?.speechService) {
        window.aacInterface.speechService.stopListening();
    }

    const overlayTranscript = document.getElementById('overlayTranscript');
    if (overlayTranscript) overlayTranscript.textContent = '';
}

micBtn.addEventListener('click', () => {
    if (!isRecording) {
        startListening();
    } else {
        stopListening();
    }
});
darkModeToggle.addEventListener('click', () => {
document.documentElement.classList.toggle('dark');
const icon = darkModeToggle.querySelector('i');
if (document.documentElement.classList.contains('dark')) {
icon.classList.replace('ri-moon-line', 'ri-sun-line');
darkModeToggle.classList.add('bg-primary', 'text-white');
darkModeToggle.classList.remove('bg-gray-100', 'text-gray-600');
// Save preference to localStorage
localStorage.setItem('darkMode', 'enabled');
} else {
icon.classList.replace('ri-sun-line', 'ri-moon-line');
darkModeToggle.classList.remove('bg-primary', 'text-white');
darkModeToggle.classList.add('bg-gray-100', 'text-gray-600');
// Save preference to localStorage
localStorage.setItem('darkMode', 'disabled');
}

// Update toolbar theme
const actionToolbar = document.querySelector('.action-toolbar');
if (document.documentElement.classList.contains('dark')) {
    actionToolbar.classList.add('dark');
} else {
    actionToolbar.classList.remove('dark');
}
});
// Check for saved dark mode preference
const darkModeSetting = localStorage.getItem('darkMode');
if (darkModeSetting === 'enabled') {
darkModeToggle.click(); // Trigger the click event to enable dark mode
}
categoryTabs.forEach(tab => {
tab.addEventListener('click', () => {
const category = tab.dataset.category;
// Update tab styling
categoryTabs.forEach(t => {
t.classList.replace('bg-primary', 'bg-gray-100');
t.classList.replace('text-white', 'text-gray-700');
t.classList.remove('shadow-md');
});
tab.classList.replace('bg-gray-100', 'bg-primary');
tab.classList.replace('text-gray-700', 'text-white');
tab.classList.add('shadow-md');
// Update suggestions based on category
updateSuggestions(category);
});
});
settingsBtn.addEventListener('click', () => {
settingsModal.classList.remove('hidden');
});
profileBtn.addEventListener('click', () => {
profileModal.classList.remove('hidden');
});
closeButtons.forEach(button => {
button.addEventListener('click', () => {
settingsModal.classList.add('hidden');
profileModal.classList.add('hidden');
});
});
closeFeedback.addEventListener('click', () => {
feedbackToast.classList.remove('show');
});
clearBtn.addEventListener('click', () => {
outputText.value = '';
showFeedbackToast('Text cleared');
});

speakBtn.addEventListener('click', () => {
if (outputText.value) {
const success = speakText(outputText.value);
if (success) {
// Update button to show speaking state
updateSpeakButtonState(true);
// Show feedback toast
showFeedbackToast(`Speaking: "${outputText.value.substring(0, 30)}${outputText.value.length > 30 ? '...' : ''}"`);
// Add to history
const now = new Date();
const timeString = now.getHours() + ':' + (now.getMinutes() < 10 ? '0' : '') + now.getMinutes() + ' ' + (now.getHours() >= 12 ? 'PM' : 'AM');
mockHistory.unshift({
text: outputText.value,
time: timeString,
context: currentCategory.charAt(0).toUpperCase() + currentCategory.slice(1)
});
if (mockHistory.length > 10) {
mockHistory.pop();
}
updateHistory(currentFilter);
}
}
});
// Add event listeners for quick category buttons
document.querySelectorAll('.quick-category').forEach(button => {
button.addEventListener('click', () => {
const category = button.dataset.category;
// Add visual feedback
button.classList.add('border-primary', 'shadow-md');
setTimeout(() => {
button.classList.remove('border-primary', 'shadow-md');
// Find and click the corresponding category tab
document.querySelector(`.category-tab[data-category="${category}"]`).click();
}, 200);
});
});
// Add event listener for context mode toggle
const contextModeToggle = document.getElementById('contextModeToggle');
let contextModeEnabled = true; // Default to enabled
let contextListeningInterval = null;
let currentContext = 'all';
// Function to detect context based on time, simulated location and activity

async function detectContext() {
  const now = new Date();
  const hour = now.getHours();
  const day = now.getDay();
  const isWeekend = day === 0 || day === 6;
  const dayContext = isWeekend ? 'Weekend' : 'Weekday';

  let timeContext, locationContext, activityContext, contextCategory, suggestions;

  if (hour >= 5 && hour < 12) {
    timeContext = 'Morning';
  } else if (hour >= 12 && hour < 17) {
    timeContext = 'Afternoon';
  } else if (hour >= 17 && hour < 22) {
    timeContext = 'Evening';
  } else {
    timeContext = 'Night';
  }

  // Fetch dynamic location
  locationContext = await fetchUserLocationName();

  if (hour >= 6 && hour < 10) {
    contextCategory = 'home';
    activityContext = 'morning routine';
    suggestions = ["Good morning", "I'd like some coffee please", "What's the weather today?", "I need help getting dressed", "Time for breakfast"];
  } else if (hour >= 11 && hour < 14) {
    contextCategory = 'food';
    activityContext = 'lunch time';
    suggestions = ["I'm hungry", "What's for lunch?", "Could I have some water?", "This tastes delicious", "I'd like some more please"];
  } else if (hour >= 14 && hour < 17) {
    contextCategory = 'social';
    activityContext = 'afternoon activities';
    suggestions = ["How are you today?", "I'd like to go outside", "Can we watch TV?", "I enjoyed our conversation", "Let's do something together"];
  } else if (hour >= 17 && hour < 20) {
    contextCategory = 'food';
    activityContext = 'dinner time';
    suggestions = ["What's for dinner?", "I'm thirsty", "This is delicious", "I'm full now", "Thank you for the meal"];
  } else if (hour >= 20 && hour < 23) {
    contextCategory = 'home';
    activityContext = 'evening routine';
    suggestions = ["I'd like to watch a movie", "Could you turn down the lights?", "I'm getting tired", "It's been a good day", "I need my medication"];
  } else {
    contextCategory = 'health';
    activityContext = 'night time';
    suggestions = ["I can't sleep", "I need water", "I need help to the bathroom", "I'm not feeling well", "Could you adjust my pillow?"];
  }

  return {
    context: contextCategory,
    activity: activityContext,
    location: locationContext,
    timeContext: timeContext,
    dayContext: dayContext,
    suggestions: suggestions
  };
}



function updateContextDisplay(contextInfo) {
// Find and click the corresponding category tab
const categoryTab = document.querySelector(`.category-tab[data-category="${contextInfo.context}"]`);
if (categoryTab && !categoryTab.classList.contains('bg-primary')) {
categoryTab.click();
}
// Update the context chips
const timeContextEl = document.getElementById('timeContext');
const locationContextEl = document.getElementById('locationContext');
const dayContextEl = document.getElementById('dayContext');
const activeContextInfo = document.getElementById('activeContextInfo');
if (timeContextEl && locationContextEl && dayContextEl) {
timeContextEl.textContent = contextInfo.timeContext;
locationContextEl.textContent = contextInfo.location;
dayContextEl.textContent = contextInfo.dayContext;
activeContextInfo.style.opacity = '1';
}
// Also update the listening overlay context display
const currentTimeContext = document.getElementById('currentTimeContext');
const currentLocationContext = document.getElementById('currentLocationContext');
const currentDayContext = document.getElementById('currentDayContext');
if (currentTimeContext && currentLocationContext && currentDayContext) {
currentTimeContext.textContent = contextInfo.timeContext;
currentLocationContext.textContent = contextInfo.location;
currentDayContext.textContent = contextInfo.dayContext;
}
// Update suggestions with context-specific ones
if (contextInfo.suggestions && contextInfo.suggestions.length > 0) {
const suggestionsContainer = document.getElementById('suggestions');
suggestionsContainer.innerHTML = '';
// Add a context indicator at the beginning
const contextIndicator = document.createElement('div');
contextIndicator.className = 'px-4 py-2 bg-primary text-white rounded-full whitespace-nowrap text-sm font-medium context-active flex items-center space-x-2';
contextIndicator.innerHTML = `
<i class="ri-radar-line"></i>
<span>${contextInfo.activity}</span>
`;
suggestionsContainer.appendChild(contextIndicator);
contextInfo.suggestions.forEach(phrase => {
const button = document.createElement('button');
button.className = 'suggestion-btn px-4 py-2 bg-primary bg-opacity-10 text-primary rounded-full whitespace-nowrap text-sm font-medium hover:bg-opacity-20 cursor-pointer keyboard-focus';
button.textContent = phrase;
button.dataset.category = contextInfo.context;
button.setAttribute('tabindex', '0');
button.addEventListener('click', () => {
document.getElementById('outputText').value = phrase;
});
suggestionsContainer.appendChild(button);
});
}
// Show context information in a toast
showFeedbackToast(`Context detected: ${contextInfo.timeContext} | ${contextInfo.location} | ${contextInfo.dayContext}`);
}
async function startContextListening() {
// Initial context detection
const contextInfo = await detectContext();
currentContext = contextInfo.context;
updateContextDisplay(contextInfo);
// Set up interval to periodically check for context changes (every 30 seconds)
contextListeningInterval = setInterval(() => {
  (async () => {
    const newContextInfo = await detectContext();
    if (newContextInfo.context !== currentContext) {
      currentContext = newContextInfo.context;
      updateContextDisplay(newContextInfo);
    }
  })();
}, 30000);

// Simulate occasional automatic listening based on context
setTimeout(() => {
if (contextModeEnabled && Math.random() > 0.7) {
// 30% chance of auto-listening
startListening();
}
}, 45000);
}
function stopContextListening() {
if (contextListeningInterval) {
clearInterval(contextListeningInterval);
contextListeningInterval = null;
}
}
// Show tooltip on hover for context mode toggle
contextModeToggle.addEventListener('mouseenter', () => {
document.getElementById('contextTooltip').classList.remove('hidden');
});
contextModeToggle.addEventListener('mouseleave', () => {
document.getElementById('contextTooltip').classList.add('hidden');
});
// Initialize context mode (enabled by default)
function initContextMode() {
    if (contextModeEnabled) {
        // Only update context display, don't start listening
        detectContext().then(contextInfo => {
            updateContextDisplay(contextInfo);
        });
        document.getElementById('activeContextInfo').style.opacity = '1';
    }
}
// Call this after DOM is loaded
initContextMode();
contextModeToggle.addEventListener('click', () => {
contextModeEnabled = !contextModeEnabled;
// Update toggle button appearance
if (contextModeEnabled) {
contextModeToggle.classList.remove('bg-gray-100', 'text-gray-700');
contextModeToggle.classList.add('bg-primary', 'text-white');
contextModeToggle.querySelector('i').classList.replace('ri-brain-line', 'ri-radar-line');
contextModeToggle.querySelector('span:first-of-type').textContent = 'Smart Context';
contextModeToggle.querySelector('span:last-of-type').textContent = 'ON';
contextModeToggle.querySelector('span:last-of-type').classList.remove('bg-gray-200', 'text-gray-600');
contextModeToggle.querySelector('span:last-of-type').classList.add('bg-white', 'text-primary');
// Start context detection
startContextListening();
// Show the context info chips
document.getElementById('activeContextInfo').style.opacity = '1';
} else {
contextModeToggle.classList.remove('bg-primary', 'text-white');
contextModeToggle.classList.add('bg-gray-100', 'text-gray-700');
contextModeToggle.querySelector('i').classList.replace('ri-radar-line', 'ri-brain-line');
contextModeToggle.querySelector('span:first-of-type').textContent = 'Smart Context';
contextModeToggle.querySelector('span:last-of-type').textContent = 'OFF';
contextModeToggle.querySelector('span:last-of-type').classList.remove('bg-white', 'text-primary');
contextModeToggle.querySelector('span:last-of-type').classList.add('bg-gray-200', 'text-gray-600');
// Stop context detection
stopContextListening();
// Hide the context info chips
document.getElementById('activeContextInfo').style.opacity = '0';
}
showFeedbackToast(contextModeEnabled ? 'Smart Context Enabled: Suggestions adapt to your environment' : 'Smart Context Disabled: Manual category selection');
});
// Manual override button
const manualOverrideBtn = document.getElementById('manualOverrideBtn');
const manualOverrideModal = document.getElementById('manualOverrideModal');
const closeOverrideModal = document.getElementById('closeOverrideModal');
if (closeOverrideModal) {
  closeOverrideModal.addEventListener('click', () => {
    manualOverrideModal.classList.add('hidden');
  });
} else {
  console.warn('Element #closeOverrideModal not found.');
}
const cancelOverride = document.getElementById('cancelOverride');
const saveOverride = document.getElementById('saveOverride');
const timeContextOverride = document.getElementById('timeContextOverride');
const locationContextOverride = document.getElementById('locationContextOverride');
const dayContextOverride = document.getElementById('dayContextOverride');
manualOverrideBtn.addEventListener('click', async () => {
if (contextModeEnabled) {
// Get current context values
const contextInfo = await detectContext();
timeContextOverride.value = contextInfo.timeContext;
locationContextOverride.value = contextInfo.location;
dayContextOverride.value = contextInfo.dayContext;
manualOverrideModal.classList.remove('hidden');
}
});
closeOverrideModal.addEventListener('click', () => {
manualOverrideModal.classList.add('hidden');
});
cancelOverride.addEventListener('click', () => {
manualOverrideModal.classList.add('hidden');
});
saveOverride.addEventListener('click', () => {
// Get the selected values
const timeContext = timeContextOverride.value;
const locationContext = locationContextOverride.value;
const dayContext = dayContextOverride.value;
// Update the context chips
document.getElementById('timeContext').textContent = timeContext;
document.getElementById('locationContext').textContent = locationContext;
document.getElementById('dayContext').textContent = dayContext;
// Update the context in the listening overlay
document.getElementById('currentTimeContext').textContent = timeContext;
document.getElementById('currentLocationContext').textContent = locationContext;
document.getElementById('currentDayContext').textContent = dayContext;
// Show feedback
showFeedbackToast(`Context manually set to: ${timeContext} | ${locationContext} | ${dayContext}`);
// Close the modal
manualOverrideModal.classList.add('hidden');
});
// Voice settings
maleVoiceBtn.addEventListener('click', () => {
selectedVoiceGender = 'male';
maleVoiceBtn.classList.remove('bg-gray-100', 'text-gray-700');
maleVoiceBtn.classList.add('bg-primary', 'text-white');
femaleVoiceBtn.classList.remove('bg-primary', 'text-white');
femaleVoiceBtn.classList.add('bg-gray-100', 'text-gray-700');
showFeedbackToast('Male voice selected');
});
femaleVoiceBtn.addEventListener('click', () => {
selectedVoiceGender = 'female';
femaleVoiceBtn.classList.remove('bg-gray-100', 'text-gray-700');
femaleVoiceBtn.classList.add('bg-primary', 'text-white');
maleVoiceBtn.classList.remove('bg-primary', 'text-white');
maleVoiceBtn.classList.add('bg-gray-100', 'text-gray-700');
showFeedbackToast('Female voice selected');
});
voiceSpeed.addEventListener('input', () => {
    ttsVoiceRate = parseFloat(voiceSpeed.value);
  });
  voicePitch.addEventListener('input', () => {
    ttsVoicePitch = parseFloat(voicePitch.value);
  });
  
// Language settings
languageSelector.addEventListener('click', () => {
languageDropdown.classList.toggle('hidden');
});
document.addEventListener('click', (e) => {
if (!languageSelector.contains(e.target) && !languageDropdown.contains(e.target)) {
languageDropdown.classList.add('hidden');
}
});
languageOptions.forEach(option => {
option.addEventListener('click', () => {
const lang = option.dataset.lang;
currentLanguage = lang;
document.getElementById('currentLanguage').textContent = option.textContent;
languageDropdown.classList.add('hidden');
showFeedbackToast(`Language changed to ${option.textContent}`);
});
});
// Add new phrase functionality
function updateSavedPhrases() {
const savedPhrasesContainer = document.querySelector('.space-y-2');
savedPhrasesContainer.innerHTML = '';
savedPhrases.forEach(phrase => {
const button = document.createElement('button');
button.className = 'w-full px-4 py-2 bg-gray-100 rounded-lg text-left text-sm text-gray-700 hover:bg-gray-200 cursor-pointer';
button.textContent = phrase;
button.addEventListener('click', () => {
outputText.value = phrase;
profileModal.classList.add('hidden');
});
savedPhrasesContainer.appendChild(button);
});
}
addNewPhraseBtn.addEventListener('click', () => {
newPhraseModal.classList.remove('hidden');
newPhraseText.focus();
});
closeNewPhraseModal.addEventListener('click', () => {
newPhraseModal.classList.add('hidden');
});
cancelNewPhrase.addEventListener('click', () => {
newPhraseModal.classList.add('hidden');
});
saveNewPhrase.addEventListener('click', () => {
const phraseText = newPhraseText.value.trim();
if (phraseText) {
savedPhrases.push(phraseText);
updateSavedPhrases();
newPhraseText.value = '';
newPhraseModal.classList.add('hidden');
showFeedbackToast('New phrase added');
} else {
showFeedbackToast('Please enter a phrase');
}
});
// Keyboard navigation
document.addEventListener('keydown', (e) => {
// Press Enter when focused on a button to click it
if (e.key === 'Enter' && document.activeElement.tagName === 'BUTTON') {
document.activeElement.click();
}
// Press Escape to close modals and stop listening
if (e.key === 'Escape') {
settingsModal.classList.add('hidden');
profileModal.classList.add('hidden');
historyFilterDropdown.classList.add('hidden');
languageDropdown.classList.add('hidden');
newPhraseModal.classList.add('hidden');
feedbackToast.classList.remove('show');
// Also stop listening if active
if (isRecording) {
stopListening();
}
}
// Ctrl+M to toggle mic
if (e.ctrlKey && e.key === 'm') {
e.preventDefault();
micBtn.click();
}
// Ctrl+S to speak
if (e.ctrlKey && e.key === 's') {
e.preventDefault();
speakBtn.click();
}
// Ctrl+L to clear
if (e.ctrlKey && e.key === 'l') {
e.preventDefault();
clearBtn.click();
}
// Space to start/stop listening when overlay is active
if (e.key === ' ' && listeningOverlay.classList.contains('active')) {
e.preventDefault();
stopListening();
}
});
// Initialize saved phrases
updateSavedPhrases();
});