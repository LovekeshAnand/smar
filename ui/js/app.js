/**
 * app.js
 * ======
 * Main frontend application controller for SMAR.
 * Handles microphone capture, Web Audio API frequency analysis,
 * REST API communication, live Knowledge Graph updates, and audio playback.
 */

// Audio recording and Web Audio graph state
let audioContext = null;
let micStream = null;
let micSource = null;
let micAnalyser = null;
let isRecording = false;
let audioChunks = [];
let audioProcessor = null;

// TTS playback Web Audio analyser
let ttsAudioSource = null;
let ttsAnalyser = null;

// DOM Elements
let micBtn, chatForm, textInput, transcriptFeed, msgCountEl;
let kgTriplesCountEl, triplesContainer, vectorsContainer, connectorsList;
let ttsPlayer, syncConnectorsBtn, refreshKgBtn, refreshVectorsBtn, refreshConnectorsBtn;

document.addEventListener("DOMContentLoaded", () => {
  // Bind DOM elements
  micBtn = document.getElementById("mic-toggle-btn");
  chatForm = document.getElementById("chat-form");
  textInput = document.getElementById("text-input");
  transcriptFeed = document.getElementById("transcript-feed");
  msgCountEl = document.getElementById("msg-count");
  kgTriplesCountEl = document.getElementById("kg-triples-count");
  triplesContainer = document.getElementById("triples-container");
  vectorsContainer = document.getElementById("vectors-container");
  connectorsList = document.getElementById("connectors-list");
  ttsPlayer = document.getElementById("tts-audio-player");
  syncConnectorsBtn = document.getElementById("sync-connectors-btn");
  refreshKgBtn = document.getElementById("refresh-kg-btn");
  refreshVectorsBtn = document.getElementById("refresh-vectors-btn");
  refreshConnectorsBtn = document.getElementById("refresh-connectors-btn");

  initEventHandlers();
  initTabNavigation();
  fetchSystemStatus();
  refreshMemoryGraph();
  refreshMemoryVectors();
});

function initEventHandlers() {
  // Mic toggle
  micBtn.addEventListener("click", toggleMicrophone);

  // Chat submit
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    handleTextSubmit();
  });

  // Global spacebar to toggle mic (when not typing in an input)
  window.addEventListener("keydown", (e) => {
    if (e.code === "Space" && document.activeElement.tagName !== "INPUT") {
      e.preventDefault();
      toggleMicrophone();
    }
  });

  // Sync connectors button
  syncConnectorsBtn.addEventListener("click", handleSyncConnectors);

  // Refresh buttons
  refreshKgBtn.addEventListener("click", refreshMemoryGraph);
  refreshVectorsBtn.addEventListener("click", refreshMemoryVectors);
  refreshConnectorsBtn.addEventListener("click", fetchSystemStatus);

  // Audio player setup for reactive speech visualizer
  setupTTSVisualizerHook();
}

function initTabNavigation() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));

      tab.classList.add("active");
      const targetId = tab.getAttribute("data-tab");
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add("active");
    });
  });
}

/**
 * Connects HTML5 audio player output to Web Audio Analyser
 * so the orb dynamically dances when Nalini TTS speaks.
 */
function setupTTSVisualizerHook() {
  let isHooked = false;

  const hook = () => {
    if (isHooked) return;
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!audioContext) audioContext = new AudioContextClass();

      ttsAudioSource = audioContext.createMediaElementSource(ttsPlayer);
      ttsAnalyser = audioContext.createAnalyser();
      ttsAnalyser.fftSize = 128;

      ttsAudioSource.connect(ttsAnalyser);
      ttsAnalyser.connect(audioContext.destination);
      isHooked = true;
    } catch (e) {
      console.warn("Could not hook TTS analyser:", e);
    }
  };

  ttsPlayer.addEventListener("play", () => {
    hook();
    if (audioContext && audioContext.state === "suspended") {
      audioContext.resume();
    }
    if (window.orbVisualizer) {
      window.orbVisualizer.setState("SPEAKING");
    }
    startTTSVisualizerLoop();
  });

  ttsPlayer.addEventListener("ended", () => {
    if (window.orbVisualizer) {
      window.orbVisualizer.setState("IDLE");
      window.orbVisualizer.updateAudioData(new Uint8Array(64));
    }
  });

  ttsPlayer.addEventListener("pause", () => {
    if (window.orbVisualizer && window.orbVisualizer.state === "SPEAKING") {
      window.orbVisualizer.setState("IDLE");
    }
  });
}

function startTTSVisualizerLoop() {
  const dataArray = new Uint8Array(64);
  const check = () => {
    if (!ttsPlayer.paused && !ttsPlayer.ended && window.orbVisualizer) {
      if (ttsAnalyser) {
        ttsAnalyser.getByteFrequencyData(dataArray);
        window.orbVisualizer.updateAudioData(dataArray);
      }
      requestAnimationFrame(check);
    }
  };
  requestAnimationFrame(check);
}

/**
 * Microphone Toggle & WAV Recording
 */
async function toggleMicrophone() {
  if (isRecording) {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!audioContext) audioContext = new AudioContextClass({ sampleRate: 16000 });
    if (audioContext.state === "suspended") await audioContext.resume();

    micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: 16000,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });

    micSource = audioContext.createMediaStreamSource(micStream);
    micAnalyser = audioContext.createAnalyser();
    micAnalyser.fftSize = 128;
    micSource.connect(micAnalyser);

    // Audio capture via ScriptProcessor for precise 16kHz PCM WAV
    const bufferSize = 4096;
    audioProcessor = audioContext.createScriptProcessor(bufferSize, 1, 1);
    audioChunks = [];

    audioProcessor.onaudioprocess = (e) => {
      if (!isRecording) return;
      const channelData = e.inputBuffer.getChannelData(0);
      // Clone float array
      audioChunks.push(new Float32Array(channelData));
    };

    micSource.connect(audioProcessor);
    audioProcessor.connect(audioContext.destination);

    isRecording = true;
    micBtn.classList.add("active");
    if (window.orbVisualizer) window.orbVisualizer.setState("LISTENING");

    // Loop for microphone visualizer spectrum
    const micData = new Uint8Array(64);
    const micLoop = () => {
      if (isRecording && window.orbVisualizer) {
        micAnalyser.getByteFrequencyData(micData);
        window.orbVisualizer.updateAudioData(micData);
        requestAnimationFrame(micLoop);
      }
    };
    requestAnimationFrame(micLoop);
  } catch (err) {
    console.error("Microphone access error:", err);
    alert("Microphone access error: " + err.message);
  }
}

function stopRecording() {
  if (!isRecording) return;
  isRecording = false;
  micBtn.classList.remove("active");

  if (micStream) {
    micStream.getTracks().forEach((track) => track.stop());
  }
  if (audioProcessor) {
    audioProcessor.disconnect();
  }

  if (window.orbVisualizer) {
    window.orbVisualizer.setState("THINKING");
  }

  // Encode collected PCM floats into standard 16-bit 16kHz WAV
  const wavBlob = encodeWAV(audioChunks, 16000);
  sendVoiceToBackend(wavBlob);
}

/**
 * Encodes Float32Array PCM buffers into a valid WAV file Blob.
 */
function encodeWAV(buffers, sampleRate) {
  let totalLength = 0;
  for (const b of buffers) totalLength += b.length;

  const merged = new Float32Array(totalLength);
  let offset = 0;
  for (const b of buffers) {
    merged.set(b, offset);
    offset += b.length;
  }

  const pcm16 = new Int16Array(totalLength);
  for (let i = 0; i < totalLength; i++) {
    const s = Math.max(-1, Math.min(1, merged[i]));
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }

  const wavHeader = new ArrayBuffer(44);
  const view = new DataView(wavHeader);

  // RIFF chunk
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + pcm16.byteLength, true);
  writeString(view, 8, "WAVE");

  // fmt sub-chunk
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // Linear PCM
  view.setUint16(22, 1, true); // Mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // Byte rate
  view.setUint16(32, 2, true); // Block align
  view.setUint16(34, 16, true); // Bits per sample

  // data sub-chunk
  writeString(view, 36, "data");
  view.setUint32(40, pcm16.byteLength, true);

  return new Blob([view, pcm16], { type: "audio/wav" });
}

function writeString(view, offset, string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}

/**
 * Submits Voice WAV audio to backend
 */
async function sendVoiceToBackend(wavBlob) {
  const formData = new FormData();
  formData.append("audio_file", wavBlob, "voice_input.wav");
  formData.append("language", "hi-IN");

  try {
    const res = await fetch("/api/voice/process", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) throw new Error("Voice pipeline failed: " + res.statusText);
    const data = await res.json();

    // Render user speech transcript
    appendChatCard("user", data.transcription);

    // Render SMAR reply
    appendChatCard("assistant", data.reply, data.audio_base64, data.context_used, data.work_intent);

    // Play TTS audio
    if (data.audio_base64) {
      playAudioBase64(data.audio_base64);
    } else {
      if (window.orbVisualizer) window.orbVisualizer.setState("IDLE");
    }

    // Refresh memory
    refreshMemoryGraph();
    refreshMemoryVectors();
  } catch (err) {
    console.error("Voice processing error:", err);
    appendChatCard("assistant", "Sorry, I had trouble processing the voice stream: " + err.message);
    if (window.orbVisualizer) window.orbVisualizer.setState("IDLE");
  }
}

/**
 * Submits Text Chat to backend
 */
async function handleTextSubmit() {
  const text = textInput.value.trim();
  if (!text) return;

  textInput.value = "";
  appendChatCard("user", text);

  if (window.orbVisualizer) window.orbVisualizer.setState("THINKING");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });

    if (!res.ok) throw new Error("Chat request failed: " + res.statusText);
    const data = await res.json();

    appendChatCard("assistant", data.reply, data.audio_base64, data.context_used, data.work_intent);

    if (data.audio_base64) {
      playAudioBase64(data.audio_base64);
    } else {
      if (window.orbVisualizer) window.orbVisualizer.setState("IDLE");
    }

    refreshMemoryGraph();
    refreshMemoryVectors();
  } catch (err) {
    console.error("Chat error:", err);
    appendChatCard("assistant", "Error: " + err.message);
    if (window.orbVisualizer) window.orbVisualizer.setState("IDLE");
  }
}

function playAudioBase64(b64) {
  ttsPlayer.src = `data:audio/wav;base64,${b64}`;
  ttsPlayer.play().catch((e) => {
    console.warn("Autoplay audio blocked or error:", e);
    if (window.orbVisualizer) window.orbVisualizer.setState("IDLE");
  });
}

/**
 * Appends a message card to the Conversation Stream
 */
function appendChatCard(role, text, audioB64 = null, context = null, workIntent = null) {
  const card = document.createElement("div");
  card.className = `chat-card ${role}-card`;

  const meta = document.createElement("div");
  meta.className = "card-meta";
  const speaker = document.createElement("span");
  speaker.className = "speaker-tag";
  speaker.textContent = role === "user" ? "You" : "SMAR (Nalini)";
  const time = document.createElement("span");
  time.className = "time-tag";
  const now = new Date();
  time.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  meta.appendChild(speaker);
  meta.appendChild(time);

  const body = document.createElement("div");
  body.className = "card-body";
  body.textContent = text;

  card.appendChild(meta);
  card.appendChild(body);

  if (role === "assistant") {
    const actions = document.createElement("div");
    actions.className = "card-actions";

    if (audioB64) {
      const replayBtn = document.createElement("button");
      replayBtn.className = "btn-replay-audio";
      replayBtn.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        <span>Play Audio</span>
      `;
      replayBtn.addEventListener("click", () => playAudioBase64(audioB64));
      actions.appendChild(replayBtn);
    }

    if (context && context.trim()) {
      const pill = document.createElement("span");
      pill.className = "context-pill";
      pill.textContent = "Grounding Context Used";
      pill.title = context;
      actions.appendChild(pill);
    }

    if (actions.children.length > 0) card.appendChild(actions);

    if (workIntent && workIntent.action) {
      const intentBox = document.createElement("div");
      intentBox.className = "intent-badge";
      intentBox.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
        <span>Action Dispatched: <strong>${workIntent.action}</strong> &rarr; ${workIntent.target}</span>
      `;
      card.appendChild(intentBox);
    }
  }

  transcriptFeed.appendChild(card);
  transcriptFeed.scrollTop = transcriptFeed.scrollHeight;

  // Update message count
  const allCards = transcriptFeed.querySelectorAll(".chat-card");
  msgCountEl.textContent = `${allCards.length} messages`;
}

/**
 * Fetch and populate Knowledge Graph
 */
async function refreshMemoryGraph() {
  try {
    const res = await fetch("/api/memory/graph");
    if (!res.ok) return;
    const data = await res.json();

    kgTriplesCountEl.textContent = `KG: ${data.triples_count} FACTS`;
    document.getElementById("kg-total-badge").textContent = `Active Triples: ${data.triples_count}`;

    triplesContainer.innerHTML = "";
    if (data.triples.length === 0) {
      triplesContainer.innerHTML = '<div class="empty-state">No relational facts extracted yet.</div>';
      return;
    }

    data.triples.forEach((t) => {
      const card = document.createElement("div");
      card.className = "triple-card";
      card.innerHTML = `
        <div class="triple-nodes">
          <span class="node-sub">${escapeHtml(t.subject)}</span>
          <span class="pred-link">&mdash;[${escapeHtml(t.predicate)}]&rarr;</span>
          <span class="node-obj">${escapeHtml(t.object)}</span>
        </div>
        <div class="triple-meta">
          <span>Confidence: ${(t.confidence * 100).toFixed(0)}%</span>
          <span>Updated: ${new Date(t.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
        </div>
      `;
      triplesContainer.appendChild(card);
    });
  } catch (err) {
    console.error("Error fetching KG:", err);
  }
}

/**
 * Fetch and populate Vector Memory
 */
async function refreshMemoryVectors() {
  try {
    const res = await fetch("/api/memory/vectors");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("vector-total-badge").textContent = `Semantic Embeddings: ${data.count}`;

    vectorsContainer.innerHTML = "";
    if (data.items.length === 0) {
      vectorsContainer.innerHTML = '<div class="empty-state">No semantic vector chunks recorded yet.</div>';
      return;
    }

    data.items.forEach((item) => {
      const card = document.createElement("div");
      card.className = "vector-card";
      card.innerHTML = `
        <div class="vector-category">${escapeHtml(item.category)}</div>
        <div class="vector-content">${escapeHtml(item.content)}</div>
      `;
      vectorsContainer.appendChild(card);
    });
  } catch (err) {
    console.error("Error fetching vectors:", err);
  }
}

/**
 * Fetch System Status and Connectors
 */
async function fetchSystemStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const data = await res.json();

    // Render connectors
    connectorsList.innerHTML = "";
    const conns = data.connectors || {};
    for (const [key, c] of Object.entries(conns)) {
      const card = document.createElement("div");
      card.className = "connector-card";
      const isOnline = c.connected;
      card.innerHTML = `
        <div class="conn-info">
          <span class="conn-name">${escapeHtml(c.name)}</span>
          <span class="conn-status-tag ${isOnline ? "online" : "offline"}">
            <span class="dot ${isOnline ? "online" : ""}"></span>
            ${isOnline ? "Connected & Active" : "Configured / Standby"}
          </span>
        </div>
      `;
      connectorsList.appendChild(card);
    }
  } catch (err) {
    console.error("Error fetching status:", err);
  }
}

/**
 * Synchronize all external feeds
 */
async function handleSyncConnectors() {
  syncConnectorsBtn.disabled = true;
  syncConnectorsBtn.querySelector("span").textContent = "Syncing...";

  try {
    const res = await fetch("/api/connectors/sync", { method: "POST" });
    const data = await res.json();

    alert(`Synced! Processed ${data.raw_items_fetched} items. Triples added: ${data.sync_stats.ingested_triples}, Vectors: ${data.sync_stats.ingested_vectors}`);

    refreshMemoryGraph();
    refreshMemoryVectors();
    fetchSystemStatus();
  } catch (err) {
    alert("Error syncing connectors: " + err.message);
  } finally {
    syncConnectorsBtn.disabled = false;
    syncConnectorsBtn.querySelector("span").textContent = "Sync Context";
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
