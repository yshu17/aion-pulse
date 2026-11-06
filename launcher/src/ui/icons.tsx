// Line icons of the interface (24×24 grid, 2 px stroke, round caps), drawn with currentColor at the text size.
import type { CSSProperties, ReactNode } from "react";

// Duotone: an icon with a `tone` is drawn in that colour with a soft fill (`fill`, a path) of the same colour, the colour
// of its meaning (class blue, race red, level amber …). An icon without a tone is a plain line in the text colour. Where
// an icon sits on a filled button, the CSS sets --duo-flat: currentColor on it and the colours give way (kit.css).
const MONO = "var(--duo-flat, var(--duo))";

function Svg({ children, size = 16, tone, fill, fillOpacity = 0.28 }: { children: ReactNode; size?: number; tone?: string; fill?: string; fillOpacity?: number }) {
  const style = tone ? ({ "--duo": tone, stroke: MONO } as CSSProperties) : undefined;
  return (
    <svg className={tone ? "ico duo" : "ico"} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}>
      {tone && fill && <path d={fill} stroke="none" style={{ fill: MONO }} fillOpacity={fillOpacity} />}
      {children}
    </svg>
  );
}

// the colours of meaning
const BLUE = "#5b8def", RED = "#f07a7a", AMBER = "#e6b23a", VIOLET = "#a06bf0", TEAL = "#4fd1b5", GREEN = "#62c26b", ORANGE = "#ff9a3d", CYAN = "#4ea8e8", GREY = "#9aa7bd";

export const IconCheck = () => <Svg><path d="M5 12.5l4.5 4.5L19 7.5" /></Svg>;
export const IconOverlay = () => <Svg tone={CYAN} fill="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"><rect x="3" y="4" width="18" height="14" rx="2" /><rect x="12" y="11" width="7" height="5" rx="1" /></Svg>;
export const IconExpand = () => <Svg size={14}><path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7" /></Svg>;
export const IconStop = () => <Svg size={14}><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" /></Svg>;
export const IconReset = () => <Svg size={14}><path d="M4 4v6h6" /><path d="M20 12a8 8 0 1 0-2.3 5.7" /></Svg>;
export const IconPause = () => <Svg><path d="M9 5v14M15 5v14" /></Svg>;
export const IconPlay = () => <Svg><path d="M7 5l12 7-12 7z" /></Svg>;
export const IconDown = () => <Svg size={14}><path d="M12 5v14M6 13l6 6 6-6" /></Svg>;
export const IconClose = () => <Svg size={14}><path d="M6 6l12 12M18 6L6 18" /></Svg>;
export const IconChevron = ({ open }: { open: boolean }) => (
  <span className={`chev${open ? " open" : ""}`}><Svg size={14}><path d="M9 6l6 6-6 6" /></Svg></span>
);
export const IconSettings = () => (
  <Svg tone={GREY} fill="M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></Svg>
);

// the rows of an NPC's card in the bestiary: side, location, services, kind
// the filter pills of the bestiary's bar and the list head
export const IconSort = () => <Svg size={14} tone={VIOLET}><path d="M8 5v14M4 15l4 4 4-4M16 19V5M12 9l4-4 4 4" /></Svg>;
export const IconStairs = () => <Svg size={14} tone={AMBER} fill="M4 20h4v-4h4v-4h4V8h4v12H4z"><path d="M4 20h4v-4h4v-4h4V8h4V4" /></Svg>;
export const IconFlag = () => <Svg size={14} tone={RED} fill="M5 4h11l-2.5 4L16 12H5z"><path d="M5 21V4M5 4h11l-2.5 4L16 12H5" /></Svg>;
export const IconGroup = () => (
  <Svg size={14} tone={TEAL} fill="M9 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"><circle cx="9" cy="8" r="3" /><path d="M3 20c.6-3.2 3-5 6-5s5.4 1.8 6 5" /><path d="M16 5.3a3 3 0 0 1 0 5.4M18 15.5c1.8.6 2.8 2.2 3 4.5" /></Svg>
);
export const IconRole = () => (
  <Svg size={14} tone={ORANGE} fill="M4 4h8l8 8-8 8-8-8z"><path d="M4 4h8l8 8-8 8-8-8z" /><circle cx="8.5" cy="8.5" r="1.2" /></Svg>
);
export const IconRank = () => <Svg size={14} tone={BLUE} fill="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" /></Svg>;
export const IconShield = () => <Svg size={18} tone={BLUE} fill="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" /></Svg>;
export const IconPin = () => <Svg size={18} tone={GREEN} fill="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"><path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z" /><circle cx="12" cy="10" r="2.3" /></Svg>;
export const IconCart = () => <Svg size={18} tone={ORANGE} fill="M7 7h13.5l-2.2 7.5H7.7z"><path d="M3 4h2.5l2.2 10.5h10.6L20.5 7H7" /><circle cx="9.5" cy="19" r="1.4" /><circle cx="17" cy="19" r="1.4" /></Svg>;
export const IconUser = () => <Svg size={16} tone={BLUE} fill="M12 4.4a3.6 3.6 0 1 0 0 7.2 3.6 3.6 0 0 0 0-7.2z"><circle cx="12" cy="8" r="3.6" /><path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5" /></Svg>;

export const IconBug = () => (
  <Svg tone={RED} fill="M12 7a5.5 5.5 0 0 1 5.5 5.5v2a5.5 5.5 0 0 1-11 0v-2A5.5 5.5 0 0 1 12 7z"><path d="M9 7V5.5a3 3 0 0 1 6 0V7" /><rect x="6.5" y="7" width="11" height="13" rx="5.5" /><path d="M12 7v13M3 13h3.5M17.5 13H21M3 19l3.5-2M21 19l-3.5-2M3 7l3.5 2M21 7l-3.5 2" /></Svg>
);

export const IconExternal = () => (
  <Svg size={14}><path d="M14 4h6v6" /><path d="M20 4l-9 9" /><path d="M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4" /></Svg>
);
export const IconLink = () => (
  <Svg size={15} tone={CYAN}><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7" /><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7" /></Svg>
);
export const IconBell = ({ on }: { on: boolean }) => (
  <Svg size={13} tone={on ? AMBER : undefined} fill="M6 17V11a6 6 0 0 1 12 0v6l1.5 2h-15z" fillOpacity={0.6}><path d="M6 17V11a6 6 0 0 1 12 0v6l1.5 2h-15z" /><path d="M10 21h4" /></Svg>
);
export const IconPencil = () => <Svg size={14} tone={AMBER} fill="M4 20l4-1 11-11a2.1 2.1 0 0 0-3-3L5 16z"><path d="M4 20l4-1 11-11a2.1 2.1 0 0 0-3-3L5 16z" /><path d="M14 6l3 3" /></Svg>;
export const IconCopy = () => <Svg size={14} tone={TEAL} fill="M11 9h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-7a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z"><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 0 1 2-2h8" /></Svg>;
export const IconEye = () => <Svg size={15} tone={CYAN} fill="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6z"><path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6z" /><circle cx="12" cy="12" r="2.5" /></Svg>;
export const IconEyeOff = () => <Svg size={14}><path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6z" /><path d="M4 4l16 16" /></Svg>;
export const IconSearch = () => <Svg size={16} tone={TEAL} fill="M11 4.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13z"><circle cx="11" cy="11" r="6.5" /><path d="M20 20l-4.2-4.2" /></Svg>;
export const IconFilter = () => <Svg size={15} tone={ORANGE} fill="M4 5h16l-6 7.5V19l-4-2v-4.5z"><path d="M4 5h16l-6 7.5V19l-4-2v-4.5z" /></Svg>;
export const IconMinus = () => <Svg size={16}><path d="M5 12h14" /></Svg>;
export const IconTarget = () => <Svg size={17} tone={GREEN} fill="M12 5.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13z"><circle cx="12" cy="12" r="6.5" /><circle cx="12" cy="12" r="1.5" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></Svg>;
export const IconFit = () => <Svg size={16}><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></Svg>;
export const IconMessage = () => <Svg size={15} tone={TEAL} fill="M4 5h16v11H9l-5 4z"><path d="M4 5h16v11H9l-5 4z" /></Svg>;
export const IconNavigate = () => <Svg size={16} tone={CYAN} fill="M21 3L3 10.5l7.5 3 3 7.5z"><path d="M21 3L3 10.5l7.5 3 3 7.5z" /></Svg>;
export const IconPlus = () => <Svg size={14}><path d="M12 5v14M5 12h14" /></Svg>;
export const IconLeft = () => <Svg size={16}><path d="M15 6l-6 6 6 6" /></Svg>;
export const IconRight = () => <Svg size={16}><path d="M9 6l6 6-6 6" /></Svg>;
