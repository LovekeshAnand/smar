"use client";

import React, { useState, useEffect, useRef } from "react";
import { Header } from "@/components/Header";
import {
  AudioSpikesVisualizer,
  VisualizerState,
} from "@/components/AudioSpikesVisualizer";
import { ConversationStream, ChatMessage } from "@/components/ConversationStream";
import {
  MemoryInspector,
  KGTriple,
  VectorMemory,
  InventoryStatus,
} from "@/components/MemoryInspector";
import { UserAuthModal, UserProfile } from "@/components/UserAuthModal";
import { VoiceController } from "@/components/VoiceController";
import { encodeWAV } from "@/lib/audio";

export default function Home() {
  // Pre-authenticated default user: lovekesh / lovekesh123
  const [currentUser, setCurrentUser] = useState<UserProfile>({
    username: "lovekesh",
    name: "Lovekesh",
    role: "admin",
  });
  const [isUserModalOpen, setIsUserModalOpen] = useState<boolean>(false);

  // State
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "init-msg",
      role: "assistant",
      text: "Hello Lovekesh! How can I help you today?",
      timestamp: "Just now",
    },
  ]);
  const [visualizerState, setVisualizerState] = useState<VisualizerState>("IDLE");
  const [audioData, setAudioData] = useState<Uint8Array>(new Uint8Array(64));
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [triples, setTriples] = useState<KGTriple[]>([]);
  const [vectors, setVectors] = useState<VectorMemory[]>([]);
  const [inventoryStatus, setInventoryStatus] = useState<InventoryStatus | null>(null);
  const [isMemoryOpen, setIsMemoryOpen] = useState<boolean>(false);
  const [isConnected, setIsConnected] = useState<boolean>(true);
  const [language, setLanguage] = useState<string>("en-IN");

  // Audio References
  const audioContextRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const audioProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const audioChunksRef = useRef<Float32Array[]>([]);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const ttsAnalyserRef = useRef<AnalyserNode | null>(null);
  const isHookedRef = useRef<boolean>(false);
  const recordingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Load stored user or persist lovekesh default
    try {
      const saved = localStorage.getItem("smar_user");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed?.username) setCurrentUser(parsed);
      } else {
        localStorage.setItem("smar_user", JSON.stringify(currentUser));
      }
    } catch {
      // ignore storage error
    }

    fetchSystemStatus();
    fetchMemoryGraph(currentUser.username);
    fetchMemoryVectors(currentUser.username);
    fetchInventoryStatus();

    // Setup live WebSocket for automatic real-time memory updates
    let ws: WebSocket | null = null;
    try {
      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsHost = window.location.port === "3000" ? `${window.location.hostname}:5000` : window.location.host;
      ws = new WebSocket(`${wsProtocol}//${wsHost}/ws/live`);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "MEMORY_UPDATED" || msg.type === "MEMORY_SYNCED") {
            fetchMemoryGraph(currentUser.username);
            fetchMemoryVectors(currentUser.username);
            fetchInventoryStatus();
          }
        } catch {
          // ignore non-json messages
        }
      };
    } catch (e) {
      console.warn("WebSocket connection not available:", e);
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && (e.target as HTMLElement).tagName !== "INPUT") {
        e.preventDefault();
        toggleMicrophone();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (ws) ws.close();
    };
  }, [currentUser.username]);

  const fetchSystemStatus = async () => {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) {
        setIsConnected(false);
        return;
      }
      setIsConnected(true);
    } catch {
      setIsConnected(false);
    }
  };

  const fetchMemoryGraph = async (uid?: string) => {
    try {
      const targetUid = uid || currentUser.username;
      const res = await fetch(`/api/memory/graph?user_id=${encodeURIComponent(targetUid)}`);
      if (!res.ok) return;
      const data = await res.json();
      setTriples(data.triples || []);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchMemoryVectors = async (uid?: string) => {
    try {
      const targetUid = uid || currentUser.username;
      const res = await fetch(`/api/memory/vectors?user_id=${encodeURIComponent(targetUid)}`);
      if (!res.ok) return;
      const data = await res.json();
      setVectors(data.items || []);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchInventoryStatus = async () => {
    try {
      const res = await fetch("/api/inventory/status");
      if (!res.ok) return;
      const data = await res.json();
      setInventoryStatus(data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleUploadFile = async (file: File) => {
    try {
      const formData = new FormData();
      const uploadUrl = typeof window !== "undefined" && window.location.port === "3000"
        ? `http://${window.location.hostname}:5000/api/data/upload`
        : "/api/data/upload";
      const res = await fetch(uploadUrl, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText || "Upload failed");
      }
      await fetchInventoryStatus();
      await fetchMemoryGraph(currentUser.username);
      await fetchMemoryVectors(currentUser.username);
    } catch (e) {
      console.error("Error uploading data file:", e);
      alert("Failed to load and index file.");
    }
  };

  const toggleMicrophone = async () => {
    if (isRecording) {
      stopRecording();
    } else {
      await startRecording();
    }
  };

  const startRecording = async () => {
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioCtx({ sampleRate: 16000 });
      }
      if (audioContextRef.current.state === "suspended") {
        await audioContextRef.current.resume();
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true },
      });
      micStreamRef.current = stream;

      const source = audioContextRef.current.createMediaStreamSource(stream);
      const analyser = audioContextRef.current.createAnalyser();
      analyser.fftSize = 128;
      source.connect(analyser);

      const bufferSize = 4096;
      const processor = audioContextRef.current.createScriptProcessor(bufferSize, 1, 1);
      audioChunksRef.current = [];

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        audioChunksRef.current.push(new Float32Array(inputData));
      };

      source.connect(processor);
      processor.connect(audioContextRef.current.destination);
      audioProcessorRef.current = processor;

      setIsRecording(true);
      setVisualizerState("LISTENING");

      // Auto-stop recording at 25 seconds to respect Gnani STT limits
      if (recordingTimeoutRef.current) clearTimeout(recordingTimeoutRef.current);
      recordingTimeoutRef.current = setTimeout(() => {
        if (isRecording) stopRecording();
      }, 25000);

      // Animation frame update for live audio spikes
      const dataArr = new Uint8Array(64);
      const updateSpikes = () => {
        if (analyser && micStreamRef.current && micStreamRef.current.active) {
          analyser.getByteFrequencyData(dataArr);
          setAudioData(new Uint8Array(dataArr));
          requestAnimationFrame(updateSpikes);
        }
      };
      updateSpikes();
    } catch (err) {
      console.error("Mic Access Error:", err);
      setVisualizerState("IDLE");
      alert("Microphone permission required for voice communication.");
    }
  };

  const stopRecording = async () => {
    if (recordingTimeoutRef.current) {
      clearTimeout(recordingTimeoutRef.current);
      recordingTimeoutRef.current = null;
    }

    if (!isRecording) return;
    setIsRecording(false);
    setVisualizerState("THINKING");

    if (audioProcessorRef.current) {
      audioProcessorRef.current.disconnect();
      audioProcessorRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((t) => t.stop());
      micStreamRef.current = null;
    }

    try {
      const wavBlob = encodeWAV(audioChunksRef.current, 16000);
      const formData = new FormData();
      formData.append("audio_file", wavBlob, "input.wav");
      formData.append("language", language);
      formData.append("user_id", currentUser.username);

      const voiceUrl = typeof window !== "undefined" && window.location.port === "3000"
        ? `http://${window.location.hostname}:5000/api/voice/process`
        : "/api/voice/process";

      const res = await fetch(voiceUrl, { method: "POST", body: formData });
      if (!res.ok) throw new Error("Voice pipeline failed");
      const data = await res.json();

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        text: data.transcription,
        timestamp: "Now",
      };

      const asstMsg: ChatMessage = {
        id: `asst-${Date.now()}`,
        role: "assistant",
        text: data.reply,
        timestamp: "Now",
        audioBase64: data.audio_base64,
        operationDetails: data.operation_details || data.smart_data?.operation_details || null,
        tableData: data.table_data || data.smart_data?.table_data || null,
        visualChart: data.visual_chart || data.smart_data?.visual_chart || null,
      };

      setMessages((prev) => [...prev, userMsg, asstMsg]);

      if (data.audio_base64) {
        playAudioBase64(data.audio_base64);
      } else {
        setVisualizerState("IDLE");
      }

      fetchMemoryGraph(currentUser.username);
      fetchMemoryVectors(currentUser.username);
      setTimeout(() => {
        fetchMemoryGraph(currentUser.username);
        fetchMemoryVectors(currentUser.username);
      }, 1500);
    } catch {
      setVisualizerState("IDLE");
    }
  };

  const handleTextSubmit = async (text: string) => {
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text,
      timestamp: "Now",
    };
    setMessages((prev) => [...prev, userMsg]);
    setVisualizerState("THINKING");

    try {
      const chatUrl = typeof window !== "undefined" && window.location.port === "3000"
        ? `http://${window.location.hostname}:5000/api/chat`
        : "/api/chat";

      const res = await fetch(chatUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          language,
          user_id: currentUser.username,
        }),
      });
      if (!res.ok) throw new Error("Chat failed");
      const data = await res.json();

      const asstMsg: ChatMessage = {
        id: `asst-${Date.now()}`,
        role: "assistant",
        text: data.reply,
        timestamp: "Now",
        audioBase64: data.audio_base64,
        operationDetails: data.operation_details || data.smart_data?.operation_details || null,
        tableData: data.table_data || data.smart_data?.table_data || null,
        visualChart: data.visual_chart || data.smart_data?.visual_chart || null,
      };

      setMessages((prev) => [...prev, asstMsg]);

      if (data.audio_base64) {
        playAudioBase64(data.audio_base64);
      } else {
        setVisualizerState("IDLE");
      }

      fetchMemoryGraph(currentUser.username);
      fetchMemoryVectors(currentUser.username);
      setTimeout(() => {
        fetchMemoryGraph(currentUser.username);
        fetchMemoryVectors(currentUser.username);
      }, 1500);
    } catch {
      setVisualizerState("IDLE");
    }
  };

  const playAudioBase64 = (b64: string) => {
    const player = audioPlayerRef.current;
    if (!player) return;

    if (!isHookedRef.current) {
      try {
        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
        if (!audioContextRef.current) audioContextRef.current = new AudioCtx();

        const src = audioContextRef.current.createMediaElementSource(player);
        const analyser = audioContextRef.current.createAnalyser();
        analyser.fftSize = 128;
        src.connect(analyser);
        analyser.connect(audioContextRef.current.destination);
        ttsAnalyserRef.current = analyser;
        isHookedRef.current = true;
      } catch (err) {
        console.warn("Could not hook analyser:", err);
      }
    }

    player.src = `data:audio/wav;base64,${b64}`;
    player
      .play()
      .then(() => {
        setVisualizerState("SPEAKING");
        const dataArr = new Uint8Array(64);
        const updateSpeech = () => {
          if (player && !player.paused && !player.ended) {
            if (ttsAnalyserRef.current) {
              ttsAnalyserRef.current.getByteFrequencyData(dataArr);
              setAudioData(new Uint8Array(dataArr));
            }
            requestAnimationFrame(updateSpeech);
          }
        };
        updateSpeech();
      })
      .catch((err) => {
        console.warn("Speech playback error:", err);
        setVisualizerState("IDLE");
      });
  };

  const handleUserChange = (newUser: UserProfile) => {
    setCurrentUser(newUser);
    try {
      localStorage.setItem("smar_user", JSON.stringify(newUser));
    } catch {
      // ignore
    }
    // Update welcome message
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        role: "assistant",
        text: `Welcome, ${newUser.name}! Active user is now @${newUser.username}. How can I help you today?`,
        timestamp: "Just now",
      },
    ]);
    fetchMemoryGraph(newUser.username);
    fetchMemoryVectors(newUser.username);
  };

  const [rightInputText, setRightInputText] = useState("");

  const hasStarted = messages.some((m) => m.role === "user");

  const handleResetSession = () => {
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        role: "assistant",
        text: `Hello ${currentUser.name}! How can I help you today?`,
        timestamp: "Just now",
      },
    ]);
    setVisualizerState("IDLE");
  };

  const handleRightSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!rightInputText.trim()) return;
    handleTextSubmit(rightInputText.trim());
    setRightInputText("");
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans select-none relative">
      {/* Background ambient radial gradients */}
      <div className="absolute top-1/4 left-1/3 -translate-x-1/2 w-[550px] h-[550px] bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-[650px] h-[650px] bg-blue-600/5 rounded-full blur-3xl pointer-events-none" />

      {/* Header with User Badge, Language toggle, and Memory Drawer */}
      <Header
        onToggleMemory={() => setIsMemoryOpen((prev) => !prev)}
        isMemoryOpen={isMemoryOpen}
        isConnected={isConnected}
        language={language}
        onToggleLanguage={() => setLanguage((prev) => (prev === "en-IN" ? "hi-IN" : "en-IN"))}
        currentUser={currentUser}
        onOpenUserModal={() => setIsUserModalOpen(true)}
        onToggleDataUpload={() => setIsMemoryOpen(true)}
        isDataReady={inventoryStatus?.ready_to_answer ?? true}
      />

      {/* Main Stage with Cinematic Split Animation */}
      <main className="flex-1 w-full h-[calc(100vh-80px)] overflow-hidden relative z-10 px-3 sm:px-6 pb-4 pt-2">
        <div
          className={`w-full h-full flex flex-col lg:flex-row gap-5 items-stretch transition-all duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] ${
            hasStarted ? "justify-between" : "justify-center items-center"
          }`}
        >
          {/* ========================================================================= */}
          {/* ORB / VOICE HUB PANEL: Centered Initially -> Smoothly Glides to Left Pane */}
          {/* ========================================================================= */}
          <div
            className={`transition-all duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] flex flex-col items-center ${
              hasStarted
                ? "w-full lg:w-[380px] xl:w-[410px] shrink-0 h-full bg-slate-900/60 backdrop-blur-xl border border-slate-800/90 rounded-3xl p-5 shadow-2xl justify-between overflow-y-auto custom-scrollbar animate-in fade-in slide-in-from-left-6"
                : "w-full max-w-xl mx-auto my-auto justify-center"
            }`}
          >
            {/* Top State Badge when in Split Mode */}
            {hasStarted && (
              <div className="w-full flex items-center justify-between pb-2 mb-2 border-b border-slate-800/70 shrink-0">
                <div className="flex items-center gap-2">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      visualizerState === "LISTENING"
                        ? "bg-cyan-400 animate-ping"
                        : visualizerState === "THINKING"
                        ? "bg-purple-400 animate-pulse"
                        : visualizerState === "SPEAKING"
                        ? "bg-rose-400 animate-bounce"
                        : "bg-emerald-400"
                    }`}
                  />
                  <span className="text-[11px] font-mono tracking-wider text-slate-300 font-semibold uppercase">
                    {visualizerState === "LISTENING"
                      ? "Listening..."
                      : visualizerState === "THINKING"
                      ? "Thinking..."
                      : visualizerState === "SPEAKING"
                      ? "Speaking..."
                      : "Voice Standby"}
                  </span>
                </div>

                <span className="text-[10px] font-mono text-cyan-400/80 bg-cyan-950/40 border border-cyan-800/30 px-2 py-0.5 rounded-full">
                  {language === "en-IN" ? "English (IN)" : "Hindi (IN)"}
                </span>
              </div>
            )}

            {/* Spike Orb Visualizer */}
            <div className="shrink-0 flex flex-col items-center justify-center my-1 relative">
              <AudioSpikesVisualizer state={visualizerState} audioData={audioData} />
            </div>

            {/* INITIAL CENTERED VIEW CONTENT (Hidden once hasStarted is true) */}
            {!hasStarted && (
              <div className="w-full flex flex-col items-center text-center mt-2 space-y-6 animate-in fade-in duration-500">
                <div>
                  <h1 className="text-2xl sm:text-3xl font-light text-slate-100 tracking-tight">
                    Hello, <span className="font-semibold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">{currentUser.name}</span>
                  </h1>
                  <p className="text-xs sm:text-sm text-slate-400 font-light mt-1 max-w-md">
                    Voice-driven cognitive intelligence & operations engine
                  </p>
                </div>

                {/* Centered Voice Controller & Input */}
                <div className="w-full max-w-md pt-2">
                  <VoiceController
                    isRecording={isRecording}
                    onToggleRecord={toggleMicrophone}
                    onSubmitText={handleTextSubmit}
                  />
                  <p className="text-[11px] font-mono text-slate-500 mt-2">
                    Press Space to talk or type query
                  </p>
                </div>
              </div>
            )}

            {/* SPLIT STAGE LEFT PANEL CONTROLS (Shown when hasStarted is true) */}
            {hasStarted && (
              <div className="w-full flex flex-col items-center gap-4 mt-2 shrink-0">
                {/* Voice Push-To-Talk Button */}
                <div className="flex flex-col items-center gap-1.5">
                  <button
                    onClick={toggleMicrophone}
                    className={`relative w-16 h-16 rounded-full flex items-center justify-center group focus:outline-none transition-transform active:scale-95 ${
                      isRecording ? "shadow-[0_0_35px_rgba(0,240,255,0.8)]" : ""
                    }`}
                    title="Click or press Spacebar to speak"
                  >
                    {isRecording && (
                      <span className="absolute inset-0 rounded-full border border-cyan-400/80 animate-ping pointer-events-none" />
                    )}
                    <div
                      className={`w-14 h-14 rounded-full flex items-center justify-center transition-all duration-300 ${
                        isRecording
                          ? "bg-gradient-to-r from-cyan-400 to-blue-500 text-black shadow-lg"
                          : "bg-slate-800/90 hover:bg-slate-800 text-slate-200 border border-slate-700/80 shadow-md hover:border-cyan-500/40"
                      }`}
                    >
                      <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                        <line x1="12" y1="19" x2="12" y2="23" />
                        <line x1="8" y1="23" x2="16" y2="23" />
                      </svg>
                    </div>
                  </button>
                  <span className="text-[11px] font-mono text-slate-400">
                    {isRecording ? "Listening now... Click to send" : "Tap mic or hold Space"}
                  </span>
                </div>

                {/* System & Telemetry Card */}
                <div className="w-full bg-slate-950/60 border border-slate-800/80 rounded-2xl p-3 text-left space-y-2">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      Warehouse DB
                    </span>
                    <span className="text-cyan-400 font-medium">1.59M rows ready</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                      Inference Engine
                    </span>
                    <span className="text-slate-200">Qwen 2.5 7B</span>
                  </div>
                  <button
                    onClick={() => setIsMemoryOpen(true)}
                    className="w-full mt-1 py-1.5 px-2.5 rounded-xl bg-white/[0.04] hover:bg-cyan-950/40 border border-white/10 hover:border-cyan-500/40 text-[11px] font-mono text-cyan-300 flex items-center justify-center gap-1.5 transition-all"
                  >
                    <span>Inspect Knowledge Memory</span>
                    <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* ========================================================================= */}
          {/* RIGHT CHAT & OPERATIONS CANVAS: Slides In & Expands on First Question     */}
          {/* ========================================================================= */}
          <div
            className={`transition-all duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] flex flex-col bg-slate-900/40 backdrop-blur-xl border border-slate-800/80 rounded-3xl shadow-2xl overflow-hidden ${
              hasStarted
                ? "flex-1 min-w-0 h-full opacity-100 translate-x-0 p-4 sm:p-5"
                : "w-0 h-0 p-0 opacity-0 translate-x-12 pointer-events-none overflow-hidden hidden lg:flex"
            }`}
          >
            {hasStarted && (
              <>
                {/* Chat & Canvas Header */}
                <div className="flex items-center justify-between pb-3 mb-2 border-b border-slate-800/70 shrink-0">
                  <div className="flex items-center gap-2.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-sm shadow-cyan-400" />
                    <h2 className="text-sm font-semibold font-mono tracking-wide text-slate-100">
                      Operations & Chat Stream
                    </h2>
                    <span className="text-[10px] font-mono text-slate-400 bg-slate-800/80 border border-slate-700/60 px-2 py-0.5 rounded-full">
                      {messages.length} messages
                    </span>
                  </div>

                  {/* Reset to Centered View Button */}
                  <button
                    onClick={handleResetSession}
                    className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-400 hover:text-slate-200 bg-slate-800/40 hover:bg-slate-800/80 border border-slate-700/60 hover:border-slate-600 px-2.5 py-1 rounded-xl transition-all"
                    title="Return to centered hero view"
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                      <path d="M3 3v5h5" />
                    </svg>
                    <span>Center View</span>
                  </button>
                </div>

                {/* Scrollable Conversation Stream */}
                <div className="flex-1 w-full min-h-0 overflow-hidden flex flex-col">
                  <ConversationStream
                    messages={messages}
                    onPlayAudio={playAudioBase64}
                    className="flex-1 w-full overflow-y-auto px-1 sm:px-2 py-2 space-y-4 custom-scrollbar"
                  />
                </div>

                {/* Bottom Follow-up Input Bar */}
                <form onSubmit={handleRightSubmit} className="mt-1 shrink-0">
                  <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-700/60 focus-within:border-cyan-400/60 rounded-2xl px-3 py-2 transition-all shadow-inner">
                    <button
                      type="button"
                      onClick={toggleMicrophone}
                      className={`p-2 rounded-xl transition-all ${
                        isRecording
                          ? "bg-cyan-500 text-black animate-pulse"
                          : "text-slate-400 hover:text-cyan-400 hover:bg-white/5"
                      }`}
                      title={isRecording ? "Stop recording" : "Record voice (or Space)"}
                    >
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                        <line x1="12" y1="19" x2="12" y2="23" />
                        <line x1="8" y1="23" x2="16" y2="23" />
                      </svg>
                    </button>

                    <input
                      type="text"
                      value={rightInputText}
                      onChange={(e) => setRightInputText(e.target.value)}
                      placeholder="Ask follow-up query or execute complex aggregation..."
                      className="flex-1 bg-transparent border-none outline-none text-slate-100 placeholder:text-slate-500 text-xs sm:text-sm font-sans"
                    />

                    <button
                      type="submit"
                      disabled={!rightInputText.trim()}
                      className="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-semibold text-xs tracking-wide transition-all disabled:opacity-30 disabled:pointer-events-none flex items-center gap-1.5 shadow-md shadow-cyan-500/20"
                    >
                      <span>Send</span>
                      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <line x1="22" y1="2" x2="11" y2="13" />
                        <polygon points="22 2 15 22 11 13 2 9 22 2" />
                      </svg>
                    </button>
                  </div>
                </form>
              </>
            )}
          </div>
        </div>
      </main>

      {/* Multi-User Login & Switcher Modal */}
      <UserAuthModal
        isOpen={isUserModalOpen}
        onClose={() => setIsUserModalOpen(false)}
        currentUser={currentUser}
        onUserChange={handleUserChange}
      />

      {/* Slide-over Cognitive & Surprise Data Inspector */}
      <MemoryInspector
        isOpen={isMemoryOpen}
        onClose={() => setIsMemoryOpen(false)}
        triples={triples}
        vectors={vectors}
        inventoryStatus={inventoryStatus}
        onRefreshGraph={() => fetchMemoryGraph(currentUser.username)}
        onRefreshVectors={() => fetchMemoryVectors(currentUser.username)}
        onRefreshInventory={fetchInventoryStatus}
        onUploadFile={handleUploadFile}
        currentUsername={currentUser.username}
      />

      {/* Hidden audio element for speech playback */}
      <audio
        ref={audioPlayerRef}
        onEnded={() => {
          setVisualizerState("IDLE");
          setAudioData(new Uint8Array(64));
        }}
        className="hidden"
      />
    </div>
  );
}
