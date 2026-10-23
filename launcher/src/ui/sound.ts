// The alert sound, as in Pulse: the WAV of the settings (sound_path) or the Windows exclamation, at sound_volume.
// A plain browser has no files: a short tone instead.
import type { Config } from "../core/settings/config";
import type { Platform } from "./platform";

const WINDOWS_MEDIA = "C:\\Windows\\Media\\";
const BEEP_FILES = ["Windows Exclamation.wav", "Windows Background.wav", "Windows Ding.wav"]; // watcher/notifier.py

function tone(volume: number): void {
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
    osc.onended = () => audio.close();
  } catch {
    // no audio device: stay silent
  }
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

/** A player for the settings: play() is cheap, the file is read once. */
export function makeSound(files: Platform | null, config: Config): () => void {
  const volume = Math.min(Math.max(config.sound_volume, 0), 100) / 100;
  if (files === null) return () => tone(volume);
  let url: Promise<string | null> | null = null;
  const find = async () => {
    const own = config.sound_path ? await wavUrl(files, config.sound_path) : null;
    if (own || config.sound_path) return own;
    for (const name of BEEP_FILES) {
      const found = await wavUrl(files, WINDOWS_MEDIA + name);
      if (found) return found;
    }
    return null;
  };
  return () => {
    url ??= find();
    url.then((src) => {
      if (src === null) return tone(volume);
      const audio = new Audio(src);
      audio.volume = volume;
      audio.play().catch(() => tone(volume));
    });
  };
}
