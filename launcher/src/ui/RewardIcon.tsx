// The game's pictures of the two rewards every card shows beside their number: experience («Опыт») and kinah («Кинары»).
// The pictures are the client's own (data/ui/reward: questexpreward.png, coin_merchant.png), so a reward reads the same in
// every tab. Abyss points have no picture in the client's files; their name stays a word.
const rewardIcons = import.meta.glob("../../../data/ui/reward/*.png", { query: "?url", import: "default", eager: true }) as Record<string, string>;

export type RewardKind = "exp" | "kinah";

const SOURCE: Record<RewardKind, string> = { exp: "../../../data/ui/reward/exp.png", kinah: "../../../data/ui/reward/kinah.png" };

/** A reward's picture, square, at the size of a small icon; nothing when the picture is missing. */
export function RewardIcon({ kind, size = 20 }: { kind: RewardKind; size?: number }) {
  const url = rewardIcons[SOURCE[kind]];
  if (!url) return null;
  return <img className="reward-icon" src={url} width={size} height={size} alt="" aria-hidden="true" draggable={false} />;
}

/** The reward name of a card's number: «Опыт» with its picture, the same for the stats line and the rewards. */
export const REWARD_KIND: Record<string, RewardKind> = { exp: "exp", gold: "kinah" };
