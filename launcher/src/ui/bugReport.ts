/**
 * The text of a bug report: what the user sees when the bug button is pressed, copied to the clipboard for the developer.
 * Pure: the caller passes the state; no window or storage is read here.
 */
export interface ReportState {
  tab: string;
  watching: boolean;
  chatLog: string;
  now?: Date;
  agent?: string;
}

export function reportText(state: ReportState): string {
  const when = (state.now ?? new Date()).toISOString();
  const agent = state.agent ?? (typeof navigator === "undefined" ? "" : navigator.userAgent);
  return [
    "Pulse+ bug report",
    `time: ${when}`,
    `tab: ${state.tab}`,
    `watching: ${state.watching ? "yes" : "no"}`,
    `chat log: ${state.chatLog || "-"}`,
    `agent: ${agent}`,
  ].join("\n");
}
