/**
 * lib/audio.ts
 * ============
 * Audio utilities for SMAR Next.js Frontend.
 * Encodes Float32Array microphone stream into standard 16kHz mono WAV format for Gnani STT.
 */

export function encodeWAV(buffers: Float32Array[], sampleRate: number = 16000): Blob {
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

  // RIFF chunk descriptor
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + pcm16.byteLength, true);
  writeString(view, 8, "WAVE");

  // fmt sub-chunk
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // Linear PCM
  view.setUint16(22, 1, true); // Mono channel
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // Byte rate (SampleRate * NumChannels * BitsPerSample/8)
  view.setUint16(32, 2, true); // Block align
  view.setUint16(34, 16, true); // Bits per sample

  // data sub-chunk
  writeString(view, 36, "data");
  view.setUint32(40, pcm16.byteLength, true);

  return new Blob([view, pcm16], { type: "audio/wav" });
}

function writeString(view: DataView, offset: number, string: string): void {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}
