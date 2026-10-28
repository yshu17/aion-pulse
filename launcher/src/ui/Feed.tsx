import { m } from "motion/react";
import { FADE, SPRING } from "./fx";
import { Fragment, useEffect, useLayoutEffect, useRef, useState } from "react";

import { LOUD } from "../core/chat/session";
import { messageSegments } from "../core/chat/segments";
import { CHANNEL_COLORS, channelLabel, FeedMode, FeedRow, shown } from "./chatRows";
import { gradeOf, itemById, specByName } from "./data";
import { Icon } from "./Icon";
import { IconDown } from "./icons";
import type { AlertState } from "./useWatch";

const clock = (sec: number) => `${Math.floor(Math.max(sec, 0) / 60)}:${String(Math.floor(Math.max(sec, 0) % 60)).padStart(2, "0")}`;

interface Alerts {
  reactSec: number;
  state: Record<number, AlertState>;
  remaining: Record<number, number>;
  onAccept(alertId: number): void;
}

function Text({ text, hits }: { text: string; hits: string[] }) {
  return (
    <>
      {messageSegments(text, hits, specByName, gradeOf).map((s, i) => (
        <span key={i} className={`seg-${s.kind}${s.hit ? " hit" : ""}${s.grade ? ` g-${s.grade}` : ""}`}>{s.text}</span>
      ))}
    </>
  );
}

/** A match: a card with the item picture, the countdown and «Принять» while it waits. */
function Match({ row, alerts, channel, fresh }: { row: FeedRow; alerts: Alerts; channel: boolean; fresh: boolean }) {
  const entry = row.entry!;
  const loud = entry.kind === LOUD;
  const id = entry.alert_id;
  const done = id !== null ? alerts.state[id] : undefined;
  const left = id !== null ? alerts.remaining[id] : undefined;
  const item = entry.msg.item_ids.map((x) => itemById[x]).find(Boolean);
  return (
    <m.li className={`msg motion${loud ? " loud" : ""}${row.historic ? " old" : ""}${done ? ` ${done}` : ""}`}
      initial={fresh ? { opacity: 0, x: -14 } : false} animate={{ opacity: 1, x: 0 }} transition={{ ...SPRING, opacity: FADE }}>
      {item && loud && <Icon name={item.icon} size={36} />}
      <div className="body">
        <div className="who">
          <b className="nick">{entry.msg.nick}</b><time>{entry.msg.time.slice(-8)}</time>
          {channel && <span className="chan" style={{ color: CHANNEL_COLORS["Поиск группы"] }}>{channelLabel(row)}</span>}
          <span className="spacer" />
          {done === "accepted" && <span className="badge ok">принято</span>}
          {done === "missed" && <span className="badge bad">пропущено</span>}
          {id !== null && !done && left !== undefined && <span className={`left${left <= 8 ? " urgent" : ""}`}>{clock(left)}</span>}
          {id !== null && !done && <button className="btn mini" onClick={() => alerts.onAccept(id)}>Принять</button>}
        </div>
        <div className="msg-text"><Text text={entry.msg.text} hits={entry.hits} /></div>
      </div>
      {id !== null && !done && left !== undefined && alerts.reactSec > 0 && (
        <span className="drain" aria-hidden="true"><i style={{ width: `${Math.max(0, Math.min(1, left / alerts.reactSec)) * 100}%` }} /></span>
      )}
    </m.li>
  );
}

/** Any other chat line: one compact line with its time and channel, as in the game. */
function Line({ row, fresh }: { row: FeedRow; fresh: boolean }) {
  const label = channelLabel(row);
  const color = row.category ? CHANNEL_COLORS[row.category] : undefined;
  return (
    <m.li className={`line${row.line.nick === null ? " sys" : ""}${row.historic ? " old" : ""}`}
      initial={fresh ? { opacity: 0, y: 6 } : false} animate={{ opacity: 1, y: 0 }} transition={FADE}>
      <time>{row.line.time.slice(-8)}</time>
      <span className="line-text">
        {label && <span className="chan" style={color ? { color } : undefined}>[{label}] </span>}
        {row.line.nick !== null && <b className="nick">{row.line.nick}: </b>}
        <Text text={row.line.text} hits={[]} />
      </span>
    </m.li>
  );
}

interface Props {
  rows: FeedRow[];
  mode: FeedMode;
  system: boolean;
  reactSec: number;
  alerts: Omit<Alerts, "reactSec">;
}

/** The chat as in the game: the newest line at the bottom, the list pressed to the bottom edge, older lines above. */
export function Feed({ rows, mode, system, reactSec, alerts: given }: Props) {
  const alerts: Alerts = { ...given, reactSec };
  const list = useRef<HTMLUListElement>(null);
  const stick = useRef(true);
  const [seen, setSeen] = useState(0); // the last row key the user has seen at the bottom
  const visible = rows.filter((row) => shown(row, mode, system));
  const last = visible.length ? visible[visible.length - 1].key : 0;
  const unseen = stick.current ? 0 : visible.filter((row) => row.key > seen).length;
  const firstNew = visible.findIndex((row) => !row.historic);

  const toBottom = () => {
    const el = list.current;
    if (el) el.scrollTop = el.scrollHeight;
    stick.current = true;
    setSeen(last);
  };

  useLayoutEffect(() => { // new rows keep the bottom in view, unless the user scrolled up to read
    if (stick.current) toBottom();
  }, [last, mode, system]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { // another filter: back to the newest line
    stick.current = true;
    toBottom();
  }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps

  // the lines shown when the feed opened or the filter changed: they stay still, only lines that come later slide in
  const opened = useRef<{ mode: string; keys: Set<number> } | null>(null);
  if (!opened.current || opened.current.mode !== mode) opened.current = { mode, keys: new Set(visible.map((r) => r.key)) };
  const fresh = (key: number) => !opened.current!.keys.has(key);

  return (
    <div className="feed-wrap">
      <ul className={`feed ${mode}`} ref={list} onScroll={(e) => {
        const el = e.currentTarget;
        const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        if (atBottom && !stick.current) setSeen(last);
        stick.current = atBottom;
      }}>
        {visible.length === 0 && (
          <li className="empty">{mode === "matches" ? "Совпадений пока нет — они появятся здесь" : "Здесь появятся сообщения чата"}</li>
        )}
        {visible.map((row, i) => (
          <Fragment key={row.key}>
            {i === firstNew && i > 0 && <li className="divider"><span>выше история, ниже новые сообщения</span></li>}
            {row.entry ? <Match row={row} alerts={alerts} channel={mode === "all"} fresh={fresh(row.key)} /> : <Line row={row} fresh={fresh(row.key)} />}
          </Fragment>
        ))}
      </ul>
      {unseen > 0 && (
        <button className="pill-new" onClick={toBottom}><IconDown />{unseen} {unseen === 1 ? "новое" : "новых"}</button>
      )}
    </div>
  );
}
