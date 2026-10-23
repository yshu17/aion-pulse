import { useCallback, useEffect, useRef, useState } from "react";

import { Config, chatLogPath, readConfig, serializeConfig } from "../core/settings/config";
import { platform, Platform } from "./platform";

export interface Boot {
  ready: boolean;
  /** null in a plain browser: no files, demo data. */
  platform: Platform | null;
  config: Config;
  /** What config.json said about itself (broken file, wrong values); empty when all is well. */
  notice: string;
  chatLog: string;
  /** Merge fields into the settings and write config.json shortly after (changes in a row are written once). */
  save(patch: Partial<Config>): void;
}

const SAVE_DELAY_MS = 400;

/** Loads config.json once; keeps it in memory and writes it back when a setting changes. */
export function useBoot(): Boot {
  const [config, setConfig] = useState<Config>(() => readConfig(null).config);
  const [notice, setNotice] = useState("");
  const [ready, setReady] = useState(platform === null);
  const path = useRef("");
  const latest = useRef(config);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    if (platform === null) return;
    (async () => {
      path.current = await platform.configPath();
      const result = readConfig(await platform.readText(path.current), "config.json.broken");
      if (result.action === "backup_and_write") {
        const broken = await platform.readText(path.current);
        if (broken !== null) await platform.writeText(path.current.replace(/config\.json$/, "config.json.broken"), broken);
      }
      if (result.action !== null) await platform.writeText(path.current, serializeConfig(result.config));
      latest.current = result.config;
      setConfig(result.config);
      setNotice(result.notice);
      setReady(true);
    })().catch((error) => { setNotice(`Не удалось прочитать настройки: ${error}`); setReady(true); });
  }, []);

  const save = useCallback((patch: Partial<Config>) => {
    latest.current = { ...latest.current, ...patch };
    setConfig(latest.current);
    const files = platform;
    if (files === null || !path.current) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      files.writeText(path.current, serializeConfig(latest.current)).catch((error) => setNotice(`Не удалось сохранить настройки: ${error}`));
    }, SAVE_DELAY_MS);
  }, []);

  return { ready, platform, config, notice, chatLog: chatLogPath(config), save };
}
