// «Усиление → Расходники» (docs/concepts/consumables): one food, one drink and one stat candy, what they give together,
// and the picker of the kind being chosen. The rules are core/gear/consumables.ts.
import { useEffect, useRef, useState } from "react";

import table from "../../../../data/consumables/consumables.json";
import { chosenConsumables, consumableTotals, effectText, filterConsumables, KINDS, putConsumable, statText, timeText, unknownText,
  type Consumable, type ConsumableKind, type SavedConsumables } from "../../core/gear/consumables";
import { RARITY } from "../../core/bestiary/card";
import type { All } from "../../core/db/npcPoints";
import { Icon } from "../Icon";
import { IconSearch } from "../icons";
import { useHoverTip, type TipInfo } from "./HoverTip";

export const CONSUMABLES = (table as unknown as { items: Consumable[] }).items;
const SHOWN = 120;

const cardTip = (x: Consumable, kind: string): TipInfo =>
  ({ name: x.name, kind, icon: x.icon, lines: [], item: { id: String(x.id), icon: x.icon, grade: x.grade, level: x.item_level, kind: RARITY[x.grade] ?? kind } });

export function ConsumablesBox({ saved, all, onChange }: { saved: SavedConsumables | undefined; all: All | null; onChange(next: SavedConsumables): void }) {
  const tip = useHoverTip(all);
  const [open, setOpen] = useState<ConsumableKind | null>(null);
  const [stat, setStat] = useState("");
  const [query, setQuery] = useState("");
  const [same, setSame] = useState(true);
  const [noEvent, setNoEvent] = useState(false);
  const buttons = useRef(new Map<ConsumableKind, HTMLButtonElement>());
  const focusBack = useRef<ConsumableKind | null>(null);
  useEffect(() => { if (focusBack.current) { buttons.current.get(focusBack.current)?.focus(); focusBack.current = null; } });

  const chosen = chosenConsumables(saved, CONSUMABLES);
  const totals = consumableTotals(chosen);
  const lost = [...new Set(chosen.map(unknownText).filter(Boolean))];
  const close = () => { focusBack.current = open; setOpen(null); setQuery(""); };
  const found = open ? filterConsumables(CONSUMABLES, { kind: open, stat, query, noEvent, same }) : null;

  return (
    <div className="gear-amp-group gear-cons" onKeyDown={(e) => { if (e.key === "Escape" && open) { e.stopPropagation(); close(); } }}>
      <h5>Расходники</h5>
      <ul className="gear-cons-slots">
        {KINDS.map(([kind, label]) => {
          const x = chosen.find((c) => c.kind === kind);
          return (
            <li key={kind} className={`${x ? "filled" : ""}${open === kind ? " open" : ""}`}>
              {x ? <span {...tip.bind(cardTip(x, label))} tabIndex={0}><Icon name={x.icon} size={36} /></span> : <span className="icon blank" />}
              <div>
                {x ? <><b className={`g-${x.grade}`}>{x.name}</b><small>{[effectText(x), timeText(x.minutes), unknownText(x)].filter(Boolean).join(" · ")}</small></>
                  : <><b className="none">{label}: не выбрано</b></>}
              </div>
              <span className="acts">
              <button type="button" className={`btn${open === kind ? " primary" : ""}`} aria-expanded={open === kind} aria-label={`${x ? "Сменить" : "Выбрать"}: ${label}`}
                ref={(el) => { if (el) buttons.current.set(kind, el); }}
                onClick={() => { if (open === kind) close(); else { setOpen(kind); setQuery(""); } }}>{x ? "Сменить" : "Выбрать"}</button>
              {x && <button type="button" className="btn" aria-label={`Снять: ${x.name}`} onClick={() => onChange(putConsumable(saved, kind, null))}>Снять</button>}
              </span>
            </li>
          );
        })}
      </ul>

      {found && open && (
        <div className="gear-cons-pick">
          <div className="bst-search"><IconSearch /><input className="field" autoFocus placeholder="Найти по названию…" value={query}
            onChange={(e) => setQuery(e.target.value)} aria-label="Поиск расходника" /></div>
          <div className="gear-cons-chips" role="group" aria-label="Характеристика">
            <button type="button" aria-pressed={!found.stat} onClick={() => setStat("")}>Все<b>{found.total}</b></button>
            {found.stats.map(([name, count]) => <button type="button" key={name} aria-pressed={found.stat === name} onClick={() => setStat(name)}>{name}<b>{count}</b></button>)}
          </div>
          <div className="gear-cons-checks">
            <label><input type="checkbox" checked={same} onChange={(e) => setSame(e.target.checked)} />Одинаковые по действию вместе</label>
            <label><input type="checkbox" checked={noEvent} onChange={(e) => setNoEvent(e.target.checked)} />Без ивентовых</label>
          </div>
          <ul className="gear-cons-list">
            {found.rows.slice(0, SHOWN).map(({ item: x, more }) => (
              <li key={x.id}><button type="button" className={chosen.some((c) => c.id === x.id) ? "on" : ""}
                onClick={() => { onChange(putConsumable(saved, open, x.id)); close(); }}>
                <Icon name={x.icon} size={32} />
                <span className="nm"><b className={`g-${x.grade}`}>{x.name}</b>{more > 0 && <i>+ещё {more} с тем же действием</i>}</span>
                <span className="fx">{effectText(x)}{x.unknown.length > 0 && <em> · {unknownText(x)}</em>}</span>
                <span className="meta">{timeText(x.minutes)}{x.use_level !== null && <><br />с {x.use_level} ур.</>}</span>
              </button></li>
            ))}
            {!found.rows.length && <li className="dbt-note">Ничего не нашлось.</li>}
          </ul>
          <div className="gear-cons-foot">
            <span>Строк: {found.rows.length} (предметов: {found.matched}){found.rows.length > SHOWN ? ` · показаны первые ${SHOWN}, сузь поиск` : ""}</span>
            <button type="button" className="btn" onClick={close}>Закрыть</button>
          </div>
        </div>
      )}

      {totals.length > 0 && (
        <div className="gear-cons-sum">
          <h6>Вместе дают</h6>
          <dl>{totals.map((t) => <div key={`${t[0]}${t[2]}`}><dt>{t[0]}</dt><dd>{statText(t).slice(t[0].length + 1)}</dd></div>)}</dl>
          {lost.length > 0 && <p className="dbt-note">Не посчитано: {lost.join("; ")}</p>}
        </div>
      )}
      <p className="dbt-note">Числа — как в карточке предмета. Игра может умножать их на уровень умения предмета (так считаются свитки), а этого уровня
        в базе нет, поэтому в игре бонус еды может быть больше. Восстановление HP и MP видно только в этой сумме.</p>
      {tip.box}
    </div>
  );
}
