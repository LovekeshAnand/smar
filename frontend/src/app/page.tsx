"use client";

import React, { useState, useEffect, useRef } from "react";
import { Header } from "@/components/Header";
import { HolographicOrb, OrbState } from "@/components/HolographicOrb";
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
  // Application State
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "init-msg",
      role: "assistant",
      text: "नमस्ते! I am SMAR, your memory-driven autonomous voice assistant. My Knowledge Graph is grounded in your communications and daily context. You can speak to me in English or Hindi, or type below.",
      timestamp: "Just now",
    },
  ]);
  const [orbState, setOrbState] = useState<OrbState>("IDLE");
  const [audioData, setAudioData] = useState<Uint8Array>(new Uint8Array(64));
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [triples, setTriples] = useState<KGTriple[]>([]);
  const [vectors, setVectors] = useState<VectorMemory[]>([]);
  const [connectors, setConnectors] = useState<Record<string, ConnectorInfo>>({});
  const [isSyncing, setIsSyncing] = useState<boolean>(false);

  // Audio References
  const audioContextRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const audioProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const audioChunksRef = useRef<Float32Array[]>([]);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const ttsAnalyserRef = useRef<AnalyserNode | null>(null);
  const isHookedRef = useRef<boolean>(false);

  // Initial data fetch
  useEffect(() => {
    fetchSystemStatus();
    fetchMemoryGraph();
    fetchMemoryVectors();

    // Global spacebar listener for mic toggle
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && (e.target as HTMLElement).tagName !== "INPUT") {
        e.preventDefault();
        toggleMicrophone();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // System status query
  const fetchSystemStatus = async () => {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) return;
      const data = await res.json();
      setConnectors(data.connectors || {});
    } catch (e) {
      console.error("Failed to fetch system status:", e);
    }
  };

  // KG query
  const fetchMemoryGraph = async () => {
    try {
      const res = await fetch("/api/memory/graph");
      if (!res.ok) return;
      const data = await res.json();
      setTriples(data.triples || []);
    } catch (e) {
      console.error("Failed to fetch memory graph:", e);
    }
  };

  // Vector query
  const fetchMemoryVectors = async () => {
    try {
      const res = await fetch("/api/memory/vectors");
      if (!res.ok) return;
      const data = await res.json();
      setVectors(data.items || []);
    } catch (e) {
      console.error("Failed to fetch memory vectors:", e);
    }
  };

  // Sync connectors feed
  const handleSyncAll = async () => {
    setIsSyncing(true);
    try {
      const res = await fetch("/api/connectors/sync", { method: "POST" });
      const data = await res.json();
      alert(
        `Synced! Processed ${data.raw_items_fetched} items. Triples added: ${data.sync_stats?.ingested_triples || 0}, Vectors: ${data.sync_stats?.ingested_vectors || 0}`
      );
      fetchMemoryGraph();
      fetchMemoryVectors();
      fetchSystemStatus();
    } catch (e: any) {
      alert("Sync error: " + e.message);
    } finally {
      setIsSyncing(false);
    }
  };

  // Microphone toggle & audio recording
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
      setOrbState("LISTENING");

      // Loop to feed frequency spectrum to the visualizer
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
      console.error("Microphone error:", e);
      alert("Could not access microphone: " + e.message);
    }
  };

  const stopRecording = () => {
    setIsRecording(false);
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }
    if (audioProcessorRef.current) {
      audioProcessorRef.current.disconnect();
      audioProcessorRef.current = null;
    }

    setOrbState("THINKING");

    // Encode audio chunks into 16kHz mono WAV
    const wavBlob = encodeWAV(audioChunksRef.current, 16000);
    sendVoiceToBackend(wavBlob);
  };

  // Submit voice to backend
  const sendVoiceToBackend = async (wavBlob: Blob) => {
    const formData = new FormData();
    formData.append("audio_file", wavBlob, "voice_input.wav");
    formData.append("language", "hi-IN");

    try {
      const res = await fetch("/api/voice/process", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Voice pipeline returned: " + res.statusText);
      const data = await res.json();

      // Add user message
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        text: data.transcription,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      // Add assistant reply
      const asstMsg: ChatMessage = {
        id: `asst-${Date.now()}`,
        role: "assistant",
        text: data.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        audioBase64: data.audio_base64,
        contextUsed: data.context_used,
        workIntent: data.work_intent,
      };

      setMessages((prev) => [...prev, userMsg, asstMsg]);

      // Play audio response
      if (data.audio_base64) {
        playAudioBase64(data.audio_base64);
      } else {
        setOrbState("IDLE");
      }

      fetchMemoryGraph();
      fetchMemoryVectors();
    } catch (e: any) {
      console.error("Voice processing error:", e);
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          text: "I had trouble processing the audio: " + e.message,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
      setOrbState("IDLE");
    }
  };

  // Submit text to backend
  const handleTextSubmit = async (text: string) => {
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setOrbState("THINKING");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error("Chat failed: " + res.statusText);
      const data = await res.json();

      const asstMsg: ChatMessage = {
        id: `asst-${Date.now()}`,
        role: "assistant",
        text: data.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        audioBase64: data.audio_base64,
        contextUsed: data.context_used,
        workIntent: data.work_intent,
      };

      setMessages((prev) => [...prev, asstMsg]);

      if (data.audio_base64) {
        playAudioBase64(data.audio_base64);
      } else {
        setOrbState("IDLE");
      }

      fetchMemoryGraph();
      fetchMemoryVectors();
    } catch (e: any) {
      console.error("Chat error:", e);
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          text: "Error: " + e.message,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
      setOrbState("IDLE");
    }
  };

  // Play synthesized audio and hook Web Audio analyser for reactive orb animation
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
        console.warn("Could not attach TTS analyser:", err);
      }
    }

    player.src = `data:audio/wav;base64,${b64}`;
    player
      .play()
      .then(() => {
        setOrbState("SPEAKING");
        // Loop to feed frequency spectrum to orb while speaking
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
      .catch((e) => {
        console.warn("Audio playback blocked:", e);
        setOrbState("IDLE");
      });
  };

  const onAudioEnded = () => {
    setOrbState("IDLE");
    setAudioData(new Uint8Array(64));
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#07090e] text-slate-100 overflow-hidden select-none relative font-sans">
      {/* Background ambient lighting */}
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(circle_at_50%_30%,rgba(14,165,233,0.08)_0%,transparent_60%),radial-gradient(circle_at_80%_80%,rgba(168,85,247,0.06)_0%,transparent_50%),radial-gradient(circle_at_20%_80%,rgba(16,185,129,0.05)_0%,transparent_50%)]" />

      {/* Header */}
      <Header triplesCount={triples.length} onSyncAll={handleSyncAll} isSyncing={isSyncing} />

      {/* Main 3-Column Dashboard */}
      <main className="flex-1 grid grid-cols-1 md:grid-cols-[340px_1fr_380px] gap-4 p-4 overflow-hidden relative z-10">
        {/* Left: Conversation Stream */}
        <section className="h-full overflow-hidden">
          <ConversationStream messages={messages} onPlayAudio={playAudioBase64} />
        </section>

        {/* Center: Holographic Visualizer & Voice Controller */}
        <section className="flex flex-col items-center justify-between py-4 px-2 h-full overflow-hidden">
          <div className="my-auto flex flex-col items-center">
            <HolographicOrb state={orbState} audioData={audioData} />
          </div>

          <div className="w-full max-w-md mt-4">
            <VoiceController
              isRecording={isRecording}
              onToggleRecord={toggleMicrophone}
              onSubmitText={handleTextSubmit}
            />
          </div>
        </section>

        {/* Right: Memory Inspector & Connectors Hub */}
        <section className="h-full overflow-hidden">
          <MemoryInspector
            triples={triples}
            vectors={vectors}
            connectors={connectors}
            onRefreshGraph={fetchMemoryGraph}
            onRefreshVectors={fetchMemoryVectors}
            onRefreshConnectors={fetchSystemStatus}
            onSyncAll={handleSyncAll}
            isSyncing={isSyncing}
          />
        </section>
      </main>

      {/* Hidden audio element for TTS playback */}
      <audio ref={audioPlayerRef} onEnded={onAudioEnded} className="hidden" />
    </div>
  );
}
