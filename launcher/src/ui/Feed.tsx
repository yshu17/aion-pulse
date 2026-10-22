import { Fragment, useEffect, useRef } from "react";

import { Entry, HISTORY, LOUD } from "../core/chat/session";
import { messageSegments } from "../core/chat/segments";
import { gradeOf, itemById, specByName } from "./data";
import { Icon } from "./Icon";

function Message({ entry }: { entry: Entry }) {
  const loud = entry.kind === LOUD;
  const segments = messageSegments(entry.msg.text, entry.hits, specByName, gradeOf);
  const item = entry.msg.item_ids.map((id) => itemById[id]).find(Boolean);
  return (
    <li className={`msg${loud ? " loud" : ""}${entry.kind === HISTORY ? " old" : ""}`}>
      {item && loud && <Icon name={item.icon} size={36} />}
      <div className="body">
        <div className="who"><b className="nick">{entry.msg.nick}</b><time>{entry.msg.time.slice(-8)}</time></div>
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
export function Feed({ entries }: { entries: Entry[] }) {
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
          <Message entry={entry} />
        </Fragment>
      ))}
      <li ref={end} aria-hidden className="end" />
    </ul>
  );
}
