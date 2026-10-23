// Line icons of the interface (24×24 grid, 2 px stroke, round caps), drawn with currentColor at the text size.
import type { ReactNode } from "react";

function Svg({ children, size = 16 }: { children: ReactNode; size?: number }) {
  return (
    <svg className="ico" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>
  );
}

export const IconCheck = () => <Svg><path d="M5 12.5l4.5 4.5L19 7.5" /></Svg>;
export const IconOverlay = () => <Svg><rect x="3" y="4" width="18" height="14" rx="2" /><rect x="12" y="11" width="7" height="5" rx="1" /></Svg>;
export const IconExpand = () => <Svg size={14}><path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7" /></Svg>;
export const IconPause = () => <Svg><path d="M9 5v14M15 5v14" /></Svg>;
export const IconPlay = () => <Svg><path d="M7 5l12 7-12 7z" /></Svg>;
export const IconDown = () => <Svg size={14}><path d="M12 5v14M6 13l6 6 6-6" /></Svg>;
export const IconClose = () => <Svg size={14}><path d="M6 6l12 12M18 6L6 18" /></Svg>;
export const IconChevron = ({ open }: { open: boolean }) => (
  <span className={`chev${open ? " open" : ""}`}><Svg size={14}><path d="M9 6l6 6-6 6" /></Svg></span>
);
export const IconSettings = () => (
  <Svg><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></Svg>
);
