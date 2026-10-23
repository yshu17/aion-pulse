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
function Match({ row, alerts, channel }: { row: FeedRow; alerts: Alerts; channel: boolean }) {
  const entry = row.entry!;
  const loud = entry.kind === LOUD;
  const id = entry.alert_id;
  const done = id !== null ? alerts.state[id] : undefined;
  const left = id !== null ? alerts.remaining[id] : undefined;
  const item = entry.msg.item_ids.map((x) => itemById[x]).find(Boolean);
  return (
    <li className={`msg${loud ? " loud" : ""}${row.historic ? " old" : ""}${done ? ` ${done}` : ""}`}>
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
    </li>
  );
}

/** Any other chat line: one compact line with its time and channel, as in the game. */
function Line({ row }: { row: FeedRow }) {
  const label = channelLabel(row);
  const color = row.category ? CHANNEL_COLORS[row.category] : undefined;
  return (
    <li className={`line${row.line.nick === null ? " sys" : ""}${row.historic ? " old" : ""}`}>
      <time>{row.line.time.slice(-8)}</time>
      <span className="line-text">
        {label && <span className="chan" style={color ? { color } : undefined}>[{label}] </span>}
        {row.line.nick !== null && <b className="nick">{row.line.nick}: </b>}
        <Text text={row.line.text} hits={[]} />
      </span>
    </li>
  );
}

interface Props {
  rows: FeedRow[];
  mode: FeedMode;
  system: boolean;
  pausedAt: number | null; // while «Пауза» is on: the last row key that is shown
  alerts: Alerts;
}

/** The chat as in the game: the newest line at the bottom, the list pressed to the bottom edge, older lines above. */
export function Feed({ rows, mode, system, pausedAt, alerts }: Props) {
  const list = useRef<HTMLUListElement>(null);
  const stick = useRef(true);
  const [seen, setSeen] = useState(0); // the last row key the user has seen at the bottom
  const visible = rows.filter((row) => shown(row, mode, system) && (pausedAt === null || row.key <= pausedAt));
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
            {row.entry ? <Match row={row} alerts={alerts} channel={mode === "all"} /> : <Line row={row} />}
          </Fragment>
        ))}
      </ul>
      {unseen > 0 && (
        <button className="pill-new" onClick={toBottom}><IconDown />{unseen} {unseen === 1 ? "новое" : "новых"}</button>
      )}
    </div>
  );
}
