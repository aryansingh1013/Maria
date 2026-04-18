'use strict';

// Elements
const startOverlay = document.getElementById('start-overlay');
const startBtn = document.getElementById('start-btn');
const mainContainer = document.getElementById('main-container');

const chatInput = document.querySelector('#chat_input');
const typingIndicator = document.querySelector('#typing');
const sendButton = document.querySelector('#send');
const chatMessages = document.querySelector('#chat_messages');
const chatBoxBody = document.querySelector('#chat_box_body');
const micBtn = document.querySelector('#mic-btn');
const stopAudioBtn = document.querySelector('#stop-audio-btn');
const avatarStatus = document.querySelector('#avatar-status');

const profile = {
  my: { name: 'You', pic: 'https://via.placeholder.com/30?text=U' },
  other: { name: 'Maria', pic: 'https://via.placeholder.com/30/006ae3/ffffff?text=M' },
};

let chatHistory = JSON.parse(localStorage.getItem('chatHistory')) || [];
let viewHistory = JSON.parse(localStorage.getItem('viewHistory')) || [];
localStorage.removeItem('chatHistory');

// ==========================================
// VOICE & SPEECH SYNTHESIS SETUP
// ==========================================
let voices = [];
let selectedVoice = null;
const synth = window.speechSynthesis;
window._currentUtterance = null; // Prevent Chrome GC bug

function loadVoices() {
    voices = synth.getVoices();
    if (voices.length === 0) return;

    // Prioritize softer, more natural voices
    selectedVoice = voices.find(v => v.name.includes('Google US English')) ||
                    voices.find(v => v.name.includes('Microsoft Hazel Desktop')) || // UK Soft voice
                    voices.find(v => v.name.includes('Google UK English Female')) || 
                    voices.find(v => v.name.includes('Microsoft Zira')) ||
                    voices.find(v => v.name.includes('Female')) || 
                    voices.find(v => v.lang.startsWith('en')) || 
                    voices[0];
}

if (synth.onvoiceschanged !== undefined) {
    synth.onvoiceschanged = loadVoices;
}

// Clean text for TTS (remove markdown artifacts)
function cleanTextForSpeech(text) {
    return text
        .replace(/### \ud83d\udcc4 Source[\s\S]*/g, '') // remove source section
        .replace(/[#*`_]/g, '')                     // strip markdown symbols
        .replace(/📄 From LPU Documents/g, '')     // strip UI tags
        .replace(/🤖 General AI Response/g, '');   // strip UI tags
}

function stopSpeaking() {
    if (synth.speaking) {
        synth.cancel();
    }
    window.avatarState = 'idle';
    if(avatarStatus) avatarStatus.innerText = '';
}

function speak(text) {
    stopSpeaking(); // stop current if any
    
    // Safety check if voices didn't load yet
    if (!selectedVoice && voices.length === 0) {
        loadVoices();
    }

    if (text.trim() === '') return;

    const utterance = new SpeechSynthesisUtterance(cleanTextForSpeech(text));
    if (selectedVoice) utterance.voice = selectedVoice;
    
    // Soften the tone
    utterance.rate = 0.95; 
    utterance.pitch = 1.0;

    utterance.onstart = () => {
        window.avatarState = 'speaking';
        if(avatarStatus) avatarStatus.innerText = 'Maria is speaking...';
    };

    utterance.onend = () => {
        window.avatarState = 'idle';
        if(avatarStatus) avatarStatus.innerText = '';
        
        // Auto-resume microphone if hands-free is enabled
        if (isMicToggledOn && recognition && !isRecording) {
            try { recognition.start(); } catch(e){}
        }
    };

    utterance.onerror = () => {
        window.avatarState = 'idle';
        if(avatarStatus) avatarStatus.innerText = '';
    };

    // Save to global to prevent Chrome garbage collection cutoff
    window._currentUtterance = utterance;
    synth.speak(utterance);
}

stopAudioBtn.addEventListener('click', stopSpeaking);


// ==========================================
// SPEECH RECOGNITION (Voice to Text)
// ==========================================
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let isRecording = false;
let isMicToggledOn = false; // Hands-free mode tracker

if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        isRecording = true;
        micBtn.classList.add('active');
        if(avatarStatus) avatarStatus.innerText = 'Listening...';
        chatInput.placeholder = "Listening...";
    };

    recognition.onresult = async (event) => {
        const transcript = event.results[event.results.length - 1][0].transcript;
        const lower = transcript.toLowerCase();

        // 1. If Maria is currently busy (echo rejection & interrupt logic)
        if (window.avatarState === 'speaking' || window.avatarState === 'thinking' || synth.speaking) {
            if (/stop|shut up|cancel/i.test(lower)) {
                // User yelled stop, interrupt her!
                stopSpeaking();
                appendMessage('other', '*(Speech interrupted)*\n\nOkay, I am listening.');
                setTimeout(() => speak("Okay, I am listening."), 200);
            }
            // Ignore everything else (like her own speech echoing back)
            return;
        }

        // 2. Normal Conversation Flow
        chatInput.value = transcript;
        await submitCurrentMessage();
    };

    recognition.onend = () => {
        isRecording = false;
        
        if (!isMicToggledOn) {
            micBtn.classList.remove('active');
            chatInput.placeholder = "Type or speak to Maria...";
            if (window.avatarState !== 'speaking' && window.avatarState !== 'thinking') {
                if(avatarStatus) avatarStatus.innerText = '';
            }
        } else {
            // Continuous hands-free: always restart immediately to allow interruptions!
            try { recognition.start(); } catch(e){}
        }
    };

    micBtn.addEventListener('click', () => {
        isMicToggledOn = !isMicToggledOn;
        if (isMicToggledOn) {
            micBtn.classList.add('active');
            if (!isRecording) {
                try { recognition.start(); } catch(e){}
            }
        } else {
            micBtn.classList.remove('active');
            isRecording = false;
            try { recognition.stop(); } catch(e){}
            chatInput.placeholder = "Type or speak to Maria...";
            if(avatarStatus) avatarStatus.innerText = '';
        }
    });
} else {
    micBtn.style.display = 'none'; // hide if not supported
}


// ==========================================
// FLOW CONTROLS
// ==========================================
startBtn.addEventListener('click', () => {
    // Hide overlay, transition main UI
    startOverlay.style.opacity = '0';
    setTimeout(() => {
        startOverlay.classList.add('hidden');
        mainContainer.classList.remove('hidden');
        
        // Timeout to allow DOM layout
        setTimeout(() => {
            mainContainer.classList.add('visible');
            // Trigger 3D canvas resize now that it's visible
            window.dispatchEvent(new Event('resize')); 
            
            // Greeter text
            const greeting = "Hello, I am Maria, your LPU Placement Assistant. I can help you with placement rules, eligibility, and career guidance. How can I help you today?";
            appendMessage('other', greeting);
            saveMessage('other', greeting);
            speak(greeting);
        }, 100);
    }, 1000); // Wait for CSS fade out
});

// ==========================================
// CHAT UI UTILITIES
// ==========================================
function escapeHtml(value) {
    return value
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function formatInline(text) {
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    return text;
}

function parseMarkdown(text) {
    let html = '';
    const lines = text.split('\n');
    let inList = false;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        if (line.startsWith('### ')) {
            if (inList) { html += '</ul>'; inList = false; }
            html += `<h4>${formatInline(escapeHtml(line.substring(4)))}</h4>`;
            continue;
        }

        if (/^\s*[-*]\s+/.test(line)) {
            if (!inList) { html += '<ul>'; inList = true; }
            const itemText = line.replace(/^\s*[-*]\s+/, '');
            html += `<li>${formatInline(escapeHtml(itemText))}</li>`;
            continue;
        }

        if (inList) { html += '</ul>'; inList = false; }
        const trimmed = line.trim();
        if (trimmed) {
            html += `<p>${formatInline(escapeHtml(trimmed))}</p>`;
        }
    }

    if (inList) html += '</ul>';
    return html;
}

function saveChatHistory() {
    localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
}

function saveToViewHistory() {
    const timestamp = new Date().toLocaleString();
    viewHistory.push({ timestamp, chatHistory });
    localStorage.setItem('viewHistory', JSON.stringify(viewHistory));
}

function clearChatHistory() {
    localStorage.removeItem('chatHistory');
    chatHistory = [];
}

function renderProfile(profileType) {
    return `
      <div class="profile ${profileType}-profile">
        <span>${profile[profileType].name}</span>
      </div>`;
}

function renderMessage(profileType, message) {
    if (profileType === 'other') {
        return `<div class="message ${profileType}-message"><div class="other-message-content">${parseMarkdown(message)}</div></div>`;
    }
    return `<div class="message ${profileType}-message">${renderProfile(profileType)}<p>${escapeHtml(message).replaceAll('\n', '<br>')}</p></div>`;
}

function appendMessage(profileType, message) {
    const profileHtml = profileType === 'other' ? renderProfile(profileType) : ''; 
    const messageHtml = renderMessage(profileType, message);
    chatMessages.insertAdjacentHTML('beforeend', profileHtml + messageHtml);
    chatBoxBody.scrollTop = chatBoxBody.scrollHeight;
}

function saveMessage(profileType, message) {
    chatHistory.push({ sender: profileType === 'my' ? 'You' : 'Maria', message });
    saveChatHistory();
}

function sendMessage(profileType, text) {
    if (!text.trim()) return false;
    appendMessage(profileType, text);
    saveMessage(profileType, text);
    chatInput.value = '';
    return true;
}

// ==========================================
// RAG & BOT LOGIC
// ==========================================
async function fetchRagResponse(userInput) {
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: userInput }),
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || `Request failed with status ${response.status}`);
        }

        return data;
    } catch (error) {
        console.error(error);
        return {
            answer: 'Sorry, there was an error connecting to the backend.',
            sources: [],
        };
    }
}

function buildBotMessage(answer, sources, sourceType) {
    let message = '';
    if (sourceType === 'general') {
        message += '🤖 **General AI Response**\n\n';
    } else {
        message += '📄 **From LPU Documents**\n\n';
    }
    message += answer;

    if (sources && sources.length > 0) {
        message += '\n\n### \ud83d\udcc4 Source\n' + sources.map((s) => `- ${s}`).join('\n');
    }
    return message;
}

async function handleBotResponse(userInput) {
    // Handle Special Shortcut Commands
    const lowerInput = userInput.toLowerCase().trim();
    
    // Catch variations of "stop" spoken via mic
    if (/^(stop|maria stop|stop maria|shut up|cancel)/.test(lowerInput)) {
        stopSpeaking();
        appendMessage('other', "Okay, I will stop.");
        setTimeout(() => speak("Okay, I will stop."), 200);
        return;
    }
    
    if (lowerInput === 'introduce yourself' || lowerInput === 'who are you') {
        const intro = "Hello! I am Maria, your official LPU Placement Assistant. I am an intelligent hybrid AI system. I can assist you with university rules, placement eligibility criteria, policies, or even offer general career guidance! Feel free to talk to me!";
        appendMessage('other', intro);
        saveMessage('other', intro);
        speak(intro);
        return;
    }

    // Standard RAG flow
    window.avatarState = 'thinking';
    if(avatarStatus) avatarStatus.innerText = 'Maria is thinking...';
    typingIndicator.classList.add('active');
    sendButton.disabled = true;

    const response = await fetchRagResponse(userInput);
    
    window.avatarState = 'idle'; // state immediately changes before speaking
    typingIndicator.classList.remove('active');
    sendButton.disabled = false;
    
    const sourceType = response.source_type || 'rag';
    const botMessage = buildBotMessage(response.answer, response.sources, sourceType);

    appendMessage('other', botMessage);
    saveMessage('other', botMessage);
    
    speak(botMessage);
}

async function submitCurrentMessage() {
    const userInput = chatInput.value;
    const didSend = sendMessage('my', userInput);
    if (!didSend) return;
    await handleBotResponse(userInput);
}

// Event Listeners
chatInput.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        await submitCurrentMessage();
    }
});

sendButton.addEventListener('click', async () => {
    await submitCurrentMessage();
});

window.addEventListener('beforeunload', () => {
    saveChatHistory();
    saveToViewHistory();
    clearChatHistory();
});

// Init available voices
loadVoices();
