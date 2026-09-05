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
      formData.append("files", file);
      const res = await fetch("/api/data/upload", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Upload failed");
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

      const res = await fetch("/api/voice/process", { method: "POST", body: formData });
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
      const res = await fetch("/api/chat", {
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

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans select-none relative">
      {/* Background ambient radial gradients */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[550px] h-[550px] bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 left-1/2 -translate-x-1/2 w-[650px] h-[650px] bg-blue-600/5 rounded-full blur-3xl pointer-events-none" />

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

      {/* Centered Minimalist Stage */}
      <main className="flex-1 flex flex-col items-center justify-between py-2 px-4 relative z-10 overflow-hidden">
        {/* Center: Audio Music Spikes & Minimalist Dialogue */}
        <div className="flex flex-col items-center justify-center gap-2 my-auto w-full max-w-lg">
          <AudioSpikesVisualizer state={visualizerState} audioData={audioData} />
          <ConversationStream messages={messages} onPlayAudio={playAudioBase64} />
        </div>

        {/* Bottom: Voice & Input Controls */}
        <div className="w-full max-w-sm shrink-0 pb-3">
          <VoiceController
            isRecording={isRecording}
            onToggleRecord={toggleMicrophone}
            onSubmitText={handleTextSubmit}
          />
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
