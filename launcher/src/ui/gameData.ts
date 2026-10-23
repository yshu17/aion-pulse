// The game data of Pulse+ for the screens: the files of data/game come with the program (Vite copies them), the drops
// are asked from drops.sqlite through the program. In a plain browser (the dev page) there are no drops.
import { GameData } from "../core/gameData/gameData";
import { platform } from "./platform";

const files = import.meta.glob("../../../data/game/*.json*", { query: "?url", import: "default", eager: false });

async function readFile(file: string): Promise<Uint8Array | null> {
  const load = files[`../../../data/game/${file}`];
  if (!load) return null;
  const response = await fetch((await load()) as string);
  return response.ok ? new Uint8Array(await response.arrayBuffer()) : null;
}

const program = platform;
export const gameData = new GameData(readFile, program === null ? null : {
  ofNpc: (id) => program.gameDrops("npc", id),
  droppers: (id) => program.gameDrops("item", id),
});
