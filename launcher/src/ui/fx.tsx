// Motion effects shared by the screens (the library is set up in main.tsx: features loaded once, the system «reduce
// motion» setting followed). CSS keeps the small things (hover, press, colours); Motion does what CSS cannot: an
// indicator gliding between options, cards moving to their new place, a number that pops when it changes.
import { m } from "motion/react";

/** One spring for everything that moves to a new place: quick, a little soft, no wobble. */
export const SPRING = { type: "spring", stiffness: 520, damping: 40, mass: 0.8 } as const;
/** For things that come and go. */
export const FADE = { duration: 0.18, ease: [0.2, 0.8, 0.2, 1] } as const;

/**
 * The highlight of the chosen option of a segmented control or of the active tab: rendered inside the chosen button
 * only, it glides from the old one to the new one (`group` names the control, unique on the screen).
 */
export function Glide({ group, className = "seg-pill" }: { group: string; className?: string }) {
  return <m.span layoutId={group} className={className} transition={SPRING} aria-hidden />;
}

/** A number that pops a little each time it changes (the counters). */
export function Pop({ value }: { value: number | string }) {
  return (
    <m.b key={value} initial={{ scale: 1.28, y: -2 }} animate={{ scale: 1, y: 0 }} transition={{ type: "spring", stiffness: 600, damping: 18 }}
      style={{ display: "inline-block", transformOrigin: "left center" }}>
      {value}
    </m.b>
  );
}
