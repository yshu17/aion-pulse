// Motion effects shared by the screens (the library is set up in main.tsx: features loaded once, the system «reduce
// motion» setting followed). CSS keeps the small things (hover, press, colours); Motion does what CSS cannot: an
// indicator gliding between options, cards moving to their new place, a number that pops when it changes.
import { useEffect } from "react";
import { animate, m, useMotionValue, useReducedMotion, useTransform } from "motion/react";

/** One spring for everything that moves to a new place: quick, a little soft, no wobble. */
export const SPRING = { type: "spring", stiffness: 520, damping: 40, mass: 0.8 } as const;
/** For things that come and go. */
export const FADE = { duration: 0.18, ease: [0.2, 0.8, 0.2, 1] } as const;

/** The curve of things that arrive: fast start, long soft landing (the references: Linear, Raycast, Apple's sheets). */
export const EASE = [0.2, 0.8, 0.2, 1] as const;

/**
 * Props of a block that comes in after its neighbours: `step` 0 first, 1 after it, and so on (about 50 ms apart,
 * capped so a long run never waits for its tail). The card of an NPC and its sections use it: they arrive as one
 * rising wave, not all at once.
 */
export const reveal = (step: number, y = 14) => ({
  initial: { opacity: 0, y },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.42, ease: EASE, delay: Math.min(step, 10) * 0.05 },
});

/** The same for the rows of a long list: the first ones arrive one by one, the rest together with the last of them. */
export const row = (index: number, y = 10) => ({
  initial: { opacity: 0, y },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.34, ease: EASE, delay: Math.min(index, 14) * 0.022 },
});

/** A whole number that counts up to its value when it appears or changes (the numbers of a card). */
export function CountUp({ value, format = (n: number) => String(n) }: { value: number; format?(n: number): string }) {
  const shown = useMotionValue(0);
  const text = useTransform(shown, (v) => format(Math.round(v)));
  const reduce = useReducedMotion();
  useEffect(() => {
    if (reduce) { shown.set(value); return; }
    const run = animate(shown, value, { duration: 0.8, ease: EASE });
    return () => run.stop();
  }, [value, reduce]); // eslint-disable-line react-hooks/exhaustive-deps -- `shown` is a stable motion value
  return <m.span>{text}</m.span>;
}

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
