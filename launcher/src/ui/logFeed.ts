// Chat.log reading for the screens: the core's tailer is synchronous, files from Tauri are not. This feed asks the
// file for the bytes the tailer will need first, then lets the tailer run on them.
import { LogReader, LogTailer } from "../core/chat/tailer";

export interface AsyncFile {
  size(): Promise<number>;
  read(position: number, length: number): Promise<Uint8Array>;
}

const HISTORY_BYTES = 4 * 1024 * 1024; // the history of the last hour is far smaller; older bytes are not fetched

/** A reader over what has been fetched: the size, and the bytes of the ranges asked for. */
class FetchedReader implements LogReader {
  length = 0;
  private blocks: [number, Uint8Array][] = [];

  load(length: number, blocks: [number, Uint8Array][]): void {
    this.length = length;
    this.blocks = blocks;
  }

  size(): number {
    return this.length;
  }

  read(position: number, length: number): Uint8Array {
    const out = new Uint8Array(length);
    let filled = 0;
    for (const [start, data] of this.blocks) {
      const from = Math.max(start, position);
      const to = Math.min(start + data.length, position + length);
      if (from >= to) continue;
      out.set(data.subarray(from - start, to - start), from - position);
      filled = Math.max(filled, to - position);
    }
    // bytes before the fetched block read as nothing: the tailer then sees a shorter, partial first line
    const first = Math.max(0, Math.min(...this.blocks.map(([start]) => start), position + length) - position);
    return out.subarray(first, Math.max(first, filled));
  }
}

/** Like LogFeed of the core: the first poll gives the history of the last `historyMin` minutes, then only new lines. */
export class AsyncLogFeed {
  private tailer: LogTailer | null = null;
  private reader = new FetchedReader();
  private pos = 0;
  private historyPending: boolean;

  constructor(private file: AsyncFile, public historyMin = 0, private clock: () => number) {
    this.historyPending = historyMin > 0;
  }

  /** [history lines or null, new lines]. A missing file rejects with code ENOENT, and the next poll starts over. */
  async poll(): Promise<[string[] | null, string[]]> {
    try {
      const size = await this.file.size();
      let history: string[] | null = null;
      if (this.tailer === null) {
        this.reader.load(size, []);
        const tailer = new LogTailer(this.reader);
        tailer.startAtEnd();
        if (this.historyPending) {
          const start = Math.max(0, size - HISTORY_BYTES);
          this.reader.load(size, [[start, await this.file.read(start, size - start)]]);
          history = tailer.readBacklog(this.clock() - this.historyMin * 60_000);
          this.historyPending = false;
        }
        this.tailer = tailer;
        this.pos = size;
        return [history, []];
      }
      const from = size < this.pos ? 0 : this.pos; // a shorter file was recreated
      this.reader.load(size, size > from ? [[from, await this.file.read(from, size - from)]] : []);
      const lines = this.tailer.readNewLines();
      this.pos = size;
      return [null, lines];
    } catch (error) {
      if ((error as { code?: string }).code === "ENOENT") this.tailer = null;
      throw error;
    }
  }
}
