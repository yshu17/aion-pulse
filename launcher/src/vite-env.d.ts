/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** The local time of a local build, "YYYY-MM-DDTHH:MM" (tools/build_pulse_plus.ps1, core/buildStamp.ts). */
  readonly VITE_PULSE_BUILT?: string;
  /** "pc" or "laptop": where the dev build was made. */
  readonly VITE_PULSE_MACHINE?: string;
}
