// The alert sounds, as in Pulse: a WAV of the settings (sound_path for a match, notify_sound_path for the other
// notifications) or the Windows exclamation, at sound_volume.
// A plain browser has no files: a short tone instead.
import type { Platform } from "./platform";

const WINDOWS_MEDIA = "C:\\Windows\\Media\\";
const BEEP_FILES = ["Windows Exclamation.wav", "Windows Background.wav", "Windows Ding.wav"]; // watcher/notifier.py

function tone(volume: number): Promise<void> {
  return new Promise((done) => {
  try {
    const audio = new AudioContext();
    const osc = audio.createOscillator();
    const gain = audio.createGain();
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.25 * volume, audio.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.35);
    osc.connect(gain).connect(audio.destination);
    osc.start();
    osc.stop(audio.currentTime + 0.35);
    osc.onended = () => { audio.close(); done(); };
  } catch {
    done(); // no audio device: stay silent
  }
  });
}

async function wavUrl(files: Platform, path: string): Promise<string | null> {
  try {
    const size = await files.fileSize(path);
    if (size <= 0 || size > 20 * 1024 * 1024) return null;
    const bytes = await files.readRange(path, 0, size);
    return URL.createObjectURL(new Blob([bytes.slice()], { type: "audio/wav" }));
  } catch {
    return null;
  }
}

/** A player for the settings: play() is cheap, the file is read once; it resolves when the sound is over. */
export function makeSound(files: Platform | null, path: string, volumePercent: number): (halt?: AbortSignal) => Promise<void> {
  const volume = Math.min(Math.max(volumePercent, 0), 100) / 100;
  if (files === null) return () => tone(volume);
  let url: Promise<string | null> | null = null;
  const find = async () => {
    const own = path ? await wavUrl(files, path) : null;
    if (own || path) return own;
    for (const name of BEEP_FILES) {
      const found = await wavUrl(files, WINDOWS_MEDIA + name);
      if (found) return found;
    }
    return null;
  };
  return async (halt) => {
    url ??= find();
    const src = await url;
    if (halt?.aborted) return;
    if (src === null) return tone(volume);
    const audio = new Audio(src);
    halt?.addEventListener("abort", () => { audio.pause(); audio.dispatchEvent(new Event("ended")); });
    audio.volume = volume;
    try {
      await audio.play();
    } catch {
      return tone(volume);
    }
    await new Promise<void>((done) => { audio.onended = () => done(); audio.onerror = () => done(); });
  };
}
