/**
 * visualizer.js
 * =============
 * Cybernetic Audio-Reactive Holographic Orb Visualizer for SMAR.
 * Dynamically reacts to user voice frequency (mic input) and assistant speech (TTS audio).
 */

class HolographicOrbVisualizer {
  constructor(orbCanvasId, waveCanvasId) {
    this.orbCanvas = document.getElementById(orbCanvasId);
    this.waveCanvas = document.getElementById(waveCanvasId);
    this.ctx = this.orbCanvas.getContext("2d");
    this.waveCtx = this.waveCanvas.getContext("2d");

    // Resolution handling
    this.dpr = window.devicePixelRatio || 1;
    this.resizeCanvases();

    // Visualizer state: 'IDLE' | 'LISTENING' | 'THINKING' | 'SPEAKING'
    this.state = "IDLE";
    this.audioData = new Uint8Array(64);
    this.smoothAmplitude = 0;
    this.phase = 0;
    this.rotation = 0;

    // Background floating dust particles
    this.particles = [];
    this.initParticles(36);

    // Audio context link
    this.audioContext = null;
    this.analyser = null;

    // Start 60fps render loop
    this.render = this.render.bind(this);
    requestAnimationFrame(this.render);
  }

  resizeCanvases() {
    const orbW = 380, orbH = 380;
    this.orbCanvas.width = orbW * this.dpr;
    this.orbCanvas.height = orbH * this.dpr;
    this.orbCanvas.style.width = `${orbW}px`;
    this.orbCanvas.style.height = `${orbH}px`;
    this.ctx.scale(this.dpr, this.dpr);

    const waveW = 360, waveH = 36;
    this.waveCanvas.width = waveW * this.dpr;
    this.waveCanvas.height = waveH * this.dpr;
    this.waveCanvas.style.width = `${waveW}px`;
    this.waveCanvas.style.height = `${waveH}px`;
    this.waveCtx.scale(this.dpr, this.dpr);
  }

  initParticles(count) {
    this.particles = [];
    for (let i = 0; i < count; i++) {
      this.particles.push({
        x: Math.random() * 380,
        y: Math.random() * 380,
        radius: Math.random() * 1.8 + 0.5,
        speedX: (Math.random() - 0.5) * 0.4,
        speedY: (Math.random() - 0.5) * 0.4,
        alpha: Math.random() * 0.5 + 0.2,
      });
    }
  }

  setState(newState) {
    this.state = newState.toUpperCase();
    const badge = document.getElementById("state-badge");
    const label = document.getElementById("state-text");
    if (!badge || !label) return;

    badge.className = "state-indicator " + this.state.toLowerCase();

    switch (this.state) {
      case "LISTENING":
        label.textContent = "LISTENING (MIC ACTIVE)";
        break;
      case "THINKING":
        label.textContent = "THINKING (EPSILON 7B)";
        break;
      case "SPEAKING":
        label.textContent = "SPEAKING (NALINI TTS)";
        break;
      default:
        label.textContent = "SYSTEM READY";
        this.state = "IDLE";
        break;
    }
  }

  updateAudioData(dataArray) {
    if (!dataArray) return;
    this.audioData = dataArray;

    // Calculate current average amplitude
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i];
    }
    const currentAmp = sum / (dataArray.length * 255);
    this.smoothAmplitude += (currentAmp - this.smoothAmplitude) * 0.25;
  }

  render() {
    this.phase += 0.035;
    this.rotation += (this.state === "THINKING" ? 0.08 : 0.015);

    this.ctx.clearRect(0, 0, 380, 380);
    this.waveCtx.clearRect(0, 0, 360, 36);

    const cx = 190;
    const cy = 190;

    // 1. Draw drifting background stardust
    this.renderParticles();

    // 2. State-dependent Orb Drawing
    if (this.state === "LISTENING") {
      this.renderListeningOrb(cx, cy);
    } else if (this.state === "THINKING") {
      this.renderThinkingOrb(cx, cy);
    } else if (this.state === "SPEAKING") {
      this.renderSpeakingOrb(cx, cy);
    } else {
      this.renderIdleOrb(cx, cy);
    }

    // 3. Draw live waveform bar visualizer
    this.renderWaveform();

    requestAnimationFrame(this.render);
  }

  renderParticles() {
    for (const p of this.particles) {
      p.x += p.speedX;
      p.y += p.speedY;

      if (p.x < 0) p.x = 380;
      if (p.x > 380) p.x = 0;
      if (p.y < 0) p.y = 380;
      if (p.y > 380) p.y = 0;

      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      this.ctx.fillStyle = `rgba(0, 240, 255, ${p.alpha * 0.4})`;
      this.ctx.fill();
    }
  }

  renderIdleOrb(cx, cy) {
    const baseRadius = 80 + Math.sin(this.phase) * 5;

    // Outer aura
    const gradOuter = this.ctx.createRadialGradient(cx, cy, 20, cx, cy, baseRadius + 40);
    gradOuter.addColorStop(0, "rgba(0, 240, 255, 0.35)");
    gradOuter.addColorStop(0.5, "rgba(168, 85, 247, 0.2)");
    gradOuter.addColorStop(1, "rgba(0, 0, 0, 0)");
    this.ctx.fillStyle = gradOuter;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, baseRadius + 40, 0, Math.PI * 2);
    this.ctx.fill();

    // Inner glossy sphere
    const gradInner = this.ctx.createRadialGradient(cx - 25, cy - 25, 5, cx, cy, baseRadius);
    gradInner.addColorStop(0, "#cffafe");
    gradInner.addColorStop(0.3, "#00f0ff");
    gradInner.addColorStop(0.7, "#6366f1");
    gradInner.addColorStop(1, "#0f172a");

    this.ctx.beginPath();
    this.ctx.arc(cx, cy, baseRadius, 0, Math.PI * 2);
    this.ctx.fillStyle = gradInner;
    this.ctx.shadowColor = "#00f0ff";
    this.ctx.shadowBlur = 24;
    this.ctx.fill();
    this.ctx.shadowBlur = 0;

    // Gyro ring
    this.ctx.save();
    this.ctx.translate(cx, cy);
    this.ctx.rotate(this.rotation);
    this.ctx.beginPath();
    this.ctx.ellipse(0, 0, baseRadius + 18, (baseRadius + 18) * 0.35, Math.PI / 4, 0, Math.PI * 2);
    this.ctx.strokeStyle = "rgba(0, 240, 255, 0.4)";
    this.ctx.lineWidth = 1.5;
    this.ctx.stroke();
    this.ctx.restore();
  }

  renderListeningOrb(cx, cy) {
    const amp = this.smoothAmplitude;
    const baseRadius = 85 + amp * 60 + Math.sin(this.phase * 2) * 3;

    // Reactive spikes / ripples
    this.ctx.beginPath();
    const points = 64;
    for (let i = 0; i < points; i++) {
      const angle = (i / points) * Math.PI * 2;
      const freqIdx = i % this.audioData.length;
      const freqVal = (this.audioData[freqIdx] || 0) / 255;
      const r = baseRadius + freqVal * 35;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      if (i === 0) this.ctx.moveTo(x, y);
      else this.ctx.lineTo(x, y);
    }
    this.ctx.closePath();

    // Electric cyan fill
    const grad = this.ctx.createRadialGradient(cx, cy, 20, cx, cy, baseRadius + 40);
    grad.addColorStop(0, "rgba(255, 255, 255, 0.9)");
    grad.addColorStop(0.4, "rgba(0, 240, 255, 0.7)");
    grad.addColorStop(0.8, "rgba(14, 165, 233, 0.3)");
    grad.addColorStop(1, "rgba(0, 0, 0, 0)");

    this.ctx.fillStyle = grad;
    this.ctx.shadowColor = "#00f0ff";
    this.ctx.shadowBlur = 35;
    this.ctx.fill();
    this.ctx.shadowBlur = 0;

    // Outer shockwave ring
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, baseRadius + 20 + amp * 30, 0, Math.PI * 2);
    this.ctx.strokeStyle = `rgba(0, 240, 255, ${0.4 + amp * 0.5})`;
    this.ctx.lineWidth = 2;
    this.ctx.stroke();
  }

  renderThinkingOrb(cx, cy) {
    const baseRadius = 80;

    // Swirling vortex rings in violet / magenta
    for (let r = 0; r < 3; r++) {
      this.ctx.save();
      this.ctx.translate(cx, cy);
      this.ctx.rotate(this.rotation * (r % 2 === 0 ? 1.5 : -1.2) + r * (Math.PI / 3));

      this.ctx.beginPath();
      this.ctx.ellipse(0, 0, baseRadius + r * 14, (baseRadius + r * 14) * 0.45, 0, 0, Math.PI * 2);
      this.ctx.strokeStyle = r === 0 ? "#c084fc" : (r === 1 ? "#ec4899" : "#818cf8");
      this.ctx.lineWidth = 2.5;
      this.ctx.shadowColor = "#a855f7";
      this.ctx.shadowBlur = 20;
      this.ctx.stroke();
      this.ctx.restore();
    }

    // Core pulsing nucleus
    const pulseRadius = 55 + Math.sin(this.phase * 4) * 8;
    const gradCore = this.ctx.createRadialGradient(cx, cy, 5, cx, cy, pulseRadius);
    gradCore.addColorStop(0, "#ffffff");
    gradCore.addColorStop(0.5, "#a855f7");
    gradCore.addColorStop(1, "#3b0764");

    this.ctx.beginPath();
    this.ctx.arc(cx, cy, pulseRadius, 0, Math.PI * 2);
    this.ctx.fillStyle = gradCore;
    this.ctx.shadowColor = "#d946ef";
    this.ctx.shadowBlur = 30;
    this.ctx.fill();
    this.ctx.shadowBlur = 0;
  }

  renderSpeakingOrb(cx, cy) {
    const amp = this.smoothAmplitude || 0.35;
    const baseRadius = 85 + amp * 45;

    // Glowing warm rose & golden plasma
    const grad = this.ctx.createRadialGradient(cx, cy, 15, cx, cy, baseRadius + 30);
    grad.addColorStop(0, "#fff1f2");
    grad.addColorStop(0.3, "#f43f5e");
    grad.addColorStop(0.7, "#fbbf24");
    grad.addColorStop(1, "rgba(244, 63, 94, 0)");

    this.ctx.beginPath();
    const waveCount = 48;
    for (let i = 0; i < waveCount; i++) {
      const angle = (i / waveCount) * Math.PI * 2;
      const freqIdx = i % this.audioData.length;
      const audioVal = (this.audioData[freqIdx] || 0) / 255;
      const r = baseRadius + Math.sin(angle * 8 + this.phase * 3) * (6 + audioVal * 25);
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      if (i === 0) this.ctx.moveTo(x, y);
      else this.ctx.lineTo(x, y);
    }
    this.ctx.closePath();

    this.ctx.fillStyle = grad;
    this.ctx.shadowColor = "#f43f5e";
    this.ctx.shadowBlur = 35;
    this.ctx.fill();
    this.ctx.shadowBlur = 0;

    // Expanding speech ring
    const ringRadius = baseRadius + 22 + (this.phase * 25) % 40;
    const ringAlpha = 1 - ((this.phase * 25) % 40) / 40;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, ringRadius, 0, Math.PI * 2);
    this.ctx.strokeStyle = `rgba(251, 191, 36, ${ringAlpha * 0.7})`;
    this.ctx.lineWidth = 2;
    this.ctx.stroke();
  }

  renderWaveform() {
    const w = 360;
    const h = 36;
    const bars = 36;
    const barWidth = 6;
    const gap = (w - bars * barWidth) / (bars - 1);

    for (let i = 0; i < bars; i++) {
      const val = (this.audioData[i % this.audioData.length] || 15) / 255;
      const barHeight = Math.max(3, val * (h - 6));
      const x = i * (barWidth + gap);
      const y = h - barHeight;

      let color = "rgba(0, 240, 255, 0.4)";
      if (this.state === "LISTENING") color = "#00f0ff";
      else if (this.state === "THINKING") color = "#c084fc";
      else if (this.state === "SPEAKING") color = "#fb7185";

      this.waveCtx.fillStyle = color;
      this.waveCtx.beginPath();
      this.waveCtx.roundRect(x, y, barWidth, barHeight, [2, 2, 0, 0]);
      this.waveCtx.fill();
    }
  }
}

// Global visualizer instance
window.orbVisualizer = null;
document.addEventListener("DOMContentLoaded", () => {
  window.orbVisualizer = new HolographicOrbVisualizer("orb-canvas", "waveform-canvas");
});
