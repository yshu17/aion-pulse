// The build stamp of the developer's local build (tools/build_pulse_plus.ps1 -Variant dev): instead of the version number,
// the date and time of the last build and the machine it was made on, so the developer sees at a glance that a new build runs.
// Data in, text out, no state: the build script passes VITE_PULSE_BUILT (local time "YYYY-MM-DDTHH:MM") and
// VITE_PULSE_MACHINE ("pc" | "laptop", from a battery being present or PULSE_MACHINE set by hand).
// stampText(built, machine) -> "Сборка: 24.11.2026 01:40 · ноутбук", or "" when there is no stamp (dev server, the users' build).
// titleText(version, stamp) -> "Pulse+ 2.3.2 · Сборка: …": the window's title bar shows the stamp (it takes no room in the page).

const MACHINES: Record<string, string> = { pc: "ПК", laptop: "ноутбук" };

/** The line shown in the header of the local build, "" when the build carries no stamp or it is malformed. */
export function stampText(built: string | undefined, machine: string | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(built ?? "");
  if (!m) return "";
  const [, y, mo, d, h, mi] = m;
  const where = MACHINES[(machine ?? "").trim().toLowerCase()] ?? (machine ?? "").trim();
  return `Сборка: ${d}.${mo}.${y} ${h}:${mi}` + (where ? ` · ${where}` : "");
}

/** The main window's title: the version, and the stamp after it when the build has one. */
export function titleText(version: string, stamp: string): string {
  return `Pulse+ ${version}` + (stamp ? ` · ${stamp}` : "");
}
