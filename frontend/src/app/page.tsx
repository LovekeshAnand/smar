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
  ConnectorInfo,
} from "@/components/MemoryInspector";
import { VoiceController } from "@/components/VoiceController";
import { encodeWAV } from "@/lib/audio";

export default function Home() {
  // State
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "init-msg",
      role: "assistant",
      text: "Hello! How can I help you today?",
      timestamp: "Just now",
    },
  ]);
  const [visualizerState, setVisualizerState] = useState<VisualizerState>("IDLE");
  const [audioData, setAudioData] = useState<Uint8Array>(new Uint8Array(64));
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [triples, setTriples] = useState<KGTriple[]>([]);
  const [vectors, setVectors] = useState<VectorMemory[]>([]);
  const [connectors, setConnectors] = useState<Record<string, ConnectorInfo>>({});
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
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

  useEffect(() => {
    fetchSystemStatus();
    fetchMemoryGraph();
    fetchMemoryVectors();

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
            fetchMemoryGraph();
            fetchMemoryVectors();
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
  }, []);

  const fetchSystemStatus = async () => {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) {
        setIsConnected(false);
        return;
      }
      const data = await res.json();
      setConnectors(data.connectors || {});
      setIsConnected(true);
    } catch {
      setIsConnected(false);
    }
  };

  const fetchMemoryGraph = async () => {
    try {
      const res = await fetch("/api/memory/graph");
      if (!res.ok) return;
      const data = await res.json();
      setTriples(data.triples || []);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchMemoryVectors = async () => {
    try {
      const res = await fetch("/api/memory/vectors");
      if (!res.ok) return;
      const data = await res.json();
      setVectors(data.items || []);
    } catch (e) {
      console.error(e);
    }
  };

  const handleSyncAll = async () => {
    setIsSyncing(true);
    try {
      await fetch("/api/connectors/sync", { method: "POST" });
      fetchMemoryGraph();
      fetchMemoryVectors();
      fetchSystemStatus();
    } catch (e: any) {
      console.error(e);
    } finally {
      setIsSyncing(false);
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

      const dataArr = new Uint8Array(64);
      const updateMic = () => {
        if (analyser && micStreamRef.current) {
          analyser.getByteFrequencyData(dataArr);
          setAudioData(new Uint8Array(dataArr));
          requestAnimationFrame(updateMic);
        }
      };
      requestAnimationFrame(updateMic);
    } catch (e: any) {
      console.error("Mic error:", e);
    }
  };

  const stopRecording = () => {
    setIsRecording(false);
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((t) => t.stop());
      micStreamRef.current = null;
    }
    if (audioProcessorRef.current) {
      audioProcessorRef.current.disconnect();
      audioProcessorRef.current = null;
    }

    setVisualizerState("THINKING");

    const wavBlob = encodeWAV(audioChunksRef.current, 16000);
    sendVoiceToBackend(wavBlob);
  };

  const sendVoiceToBackend = async (wavBlob: Blob) => {
    const formData = new FormData();
    formData.append("audio_file", wavBlob, "voice_input.wav");
    formData.append("language", language);

    try {
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

      fetchMemoryGraph();
      fetchMemoryVectors();
      setTimeout(() => {
        fetchMemoryGraph();
        fetchMemoryVectors();
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
        body: JSON.stringify({ text, language }),
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

      fetchMemoryGraph();
      fetchMemoryVectors();
      setTimeout(() => {
        fetchMemoryGraph();
        fetchMemoryVectors();
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
        requestAnimationFrame(updateSpeech);
      })
      .catch(() => {
        setVisualizerState("IDLE");
      });
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#07090e] text-slate-100 overflow-hidden select-none relative font-sans">
      {/* Ambient background bloom */}
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(circle_at_50%_35%,rgba(0,240,255,0.04)_0%,transparent_60%)]" />

      {/* Minimalist Top Bar */}
      <Header
        onToggleMemory={() => setIsMemoryOpen((prev) => !prev)}
        isMemoryOpen={isMemoryOpen}
        isConnected={isConnected}
        language={language}
        onToggleLanguage={() => setLanguage((prev) => (prev === "en-IN" ? "hi-IN" : "en-IN"))}
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


      {/* Slide-over Memory Drawer */}
      <MemoryInspector
        isOpen={isMemoryOpen}
        onClose={() => setIsMemoryOpen(false)}
        triples={triples}
        vectors={vectors}
        connectors={connectors}
        onRefreshGraph={fetchMemoryGraph}
        onRefreshVectors={fetchMemoryVectors}
        onRefreshConnectors={fetchSystemStatus}
        onSyncAll={handleSyncAll}
        isSyncing={isSyncing}
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
