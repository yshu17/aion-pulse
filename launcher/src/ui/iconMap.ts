// The address of every picture of data/icons (items at the top, skills/ and pets/): one module, loaded on the first picture.
// The pictures stay files (vite.config.ts: assetsInlineLimit 0): inlined as text they would make this module tens of MB.
export const ICONS = import.meta.glob(["../../../data/icons/*.png", "../../../data/icons/skills/*.png", "../../../data/icons/pets/*.png"],
  { query: "?url", import: "default", eager: true }) as Record<string, string>;
