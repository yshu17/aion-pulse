import { Fragment, useEffect, useRef } from "react";

import { Entry, HISTORY, LOUD } from "../core/chat/session";
import { messageSegments } from "../core/chat/segments";
import { gradeOf, itemById, specByName } from "./data";
import { Icon } from "./Icon";
import type { AlertState } from "./useWatch";

const clock = (sec: number) => `${Math.floor(Math.max(sec, 0) / 60)}:${String(Math.floor(Math.max(sec, 0) % 60)).padStart(2, "0")}`;

interface Alerts {
  state: Record<number, AlertState>;
  remaining: Record<number, number>;
  onAccept(alertId: number): void;
}

function Message({ entry, alerts }: { entry: Entry; alerts: Alerts }) {
  const loud = entry.kind === LOUD;
  const segments = messageSegments(entry.msg.text, entry.hits, specByName, gradeOf);
  const item = entry.msg.item_ids.map((id) => itemById[id]).find(Boolean);
  const id = entry.alert_id;
  const done = id !== null ? alerts.state[id] : undefined;
  const left = id !== null ? alerts.remaining[id] : undefined;
  return (
    <li className={`msg${loud ? " loud" : ""}${entry.kind === HISTORY ? " old" : ""}${done ? ` ${done}` : ""}`}>
      {item && loud && <Icon name={item.icon} size={36} />}
      <div className="body">
        <div className="who"><b className="nick">{entry.msg.nick}</b><time>{entry.msg.time.slice(-8)}</time>
          <span className="spacer" />
          {done === "accepted" && <span className="badge ok">принято</span>}
          {done === "missed" && <span className="badge bad">пропущено</span>}
          {id !== null && !done && left !== undefined && (
            <span className={`left${left <= 8 ? " urgent" : ""}`}>{clock(left)}</span>)}
          {id !== null && !done && <button className="btn mini" onClick={() => alerts.onAccept(id)}>Принять</button>}
        </div>
        <div className="msg-text">
          {segments.map((s, i) => (
            <span key={i} className={`seg-${s.kind}${s.hit ? " hit" : ""}${s.grade ? ` g-${s.grade}` : ""}`}>{s.text}</span>
          ))}
        </div>
      </div>
    </li>
  );
}

/** The feed as in the game: the newest line at the bottom, the list pressed to the bottom edge, older lines above. */
export function Feed({ entries, alerts }: { entries: Entry[]; alerts: Alerts }) {
  const end = useRef<HTMLLIElement>(null);
  const stick = useRef(true);
  useEffect(() => {
    if (stick.current) end.current?.scrollIntoView({ block: "end" });
  }, [entries]);
  const firstNew = entries.findIndex((e) => e.kind !== HISTORY);
  return (
    <ul className="feed" onScroll={(e) => {
      const el = e.currentTarget;
      stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40; // scrolled up: the feed stays where it is
    }}>
      {entries.length === 0 && <li className="empty">Пока ничего не найдено</li>}
      {entries.map((entry, i) => (
        <Fragment key={i}>
          {i === firstNew && i > 0 && <li className="divider"><span>выше история за 60 мин, ниже новые сообщения</span></li>}
          <Message entry={entry} alerts={alerts} />
        </Fragment>
      ))}
      <li ref={end} aria-hidden className="end" />
    </ul>
  );
}
