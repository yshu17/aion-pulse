"""Read extracted client NPC/trade XML and items ZIP; export sourced services.

Never writes to the game installation. Input is client_extract/bestiary plus
the existing Russian string tables; output is portable JSON and ready icons.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

SERVICE = {
    'merchant': 'Продаёт предметы.', 'coin_merchant': 'Обменивает монеты на предметы.',
    'vendor': 'Услуги торговой лавки.', 'teleport': 'Перемещает персонажа между локациями.',
    'bindstone': 'Позволяет привязать возвращение к кибелиску.',
    'warehouse': 'Предоставляет доступ к складу.', 'stigma_master': 'Помогает устанавливать и снимать стигмы.',
    'postbox': 'Предоставляет доступ к почте.',
}
TRADE = {'trade_info': 'Покупка', 'extra_currency_trade_info': 'Особая валюта',
         'abyss_trade_info': 'Очки Бездны', 'trade_in_trade_info': 'Обмен', 'coupon_trade_info': 'Купоны'}


def strings_from(root: Path) -> dict[str, str]:
    strings = {}
    for path in sorted((root / 'raw/l10n/rus/data/Strings').glob('*.xml')):
        for _, node in ET.iterparse(path, events=('end',)):
            if node.tag == 'string':
                key, body = node.findtext('name', ''), node.findtext('body', '')
                if key and body:
                    strings[key.casefold()] = body.strip()
                node.clear()
    return strings


def build(extract: Path, output: Path) -> dict:
    from PIL import Image
    strings = strings_from(extract)
    def label(key: str) -> str:
        return strings.get(key.casefold(), '').strip('<> \t\r\n')
    raw = extract / 'bestiary'
    goods = {}
    for filename in ('client_npc_goodslist.xml', 'client_npc_trade_in_list.xml'):
        for node in ET.parse(raw / filename).getroot():
            goods[node.findtext('name', '').casefold()] = {
                'title': label(node.findtext('desc', '')),
                'items': [n.text.casefold() for n in node.findall('./goods_list/data/item') if n.text],
            }
    npcs = {}
    wanted = set()
    for _, node in ET.iterparse(raw / 'client_npcs.xml', events=('end',)):
        if node.tag != 'npc_client':
            continue
        npc_id, role = node.findtext('id', ''), node.findtext('npc_function_type', '').casefold()
        title = label(node.findtext('npc_title', ''))
        tabs = []
        for tag, mode in TRADE.items():
            for tab in node.findall(f'./{tag}/tab_list/data/*'):
                key = (tab.text or '').casefold()
                group = goods.get(key)
                if group:
                    tabs.append({'key': key, 'title': group['title'] or mode, 'mode': mode})
                    wanted.update(group['items'])
                elif key:
                    tabs.append({'key': key, 'title': mode, 'mode': mode, 'unresolved': True})
        if title or role or tabs:
            npcs[npc_id] = {'title': title, 'role': role, 'description': SERVICE.get(role, ''), 'tabs': tabs}
        node.clear()
    items = {}
    with zipfile.ZipFile(raw / 'items.zip') as archive:
        files = {name.casefold(): name for name in archive.namelist()}
        with archive.open('client_items.xml') as stream:
            for _, node in ET.iterparse(stream, events=('end',)):
                if node.tag != 'client_item':
                    continue
                key = node.findtext('name', '').casefold()
                if key in wanted:
                    icon = node.findtext('icon_name', '').strip().casefold()
                    items[key] = {'item_id': node.findtext('id', ''),
                                  'name': label(node.findtext('desc', '')) or key,
                                  'rarity': node.findtext('quality', ''), 'level': node.findtext('level', ''),
                                  'icon_asset': f'client/{icon}.png' if icon else ''}
                node.clear()
        icons = {r['icon_asset'] for r in items.values() if r['icon_asset']}
        missing_icons = []
        for asset in sorted(icons):
            icon = Path(asset).stem
            filename = files.get(icon + '.dds')
            if not filename:
                missing_icons.append(icon)
                continue
            target = output / 'icons' / asset
            target.parent.mkdir(parents=True, exist_ok=True)
            original = raw / 'icons' / (icon + '.dds')
            original.parent.mkdir(parents=True, exist_ok=True)
            data = archive.read(filename)
            original.write_bytes(data)
            with Image.open(io.BytesIO(data)) as image:
                image.convert('RGBA').save(target)
    unresolved = set()
    for npc in npcs.values():
        stock = []
        seen = set()
        for tab in npc['tabs']:
            for key in goods.get(tab['key'], {}).get('items', []):
                if key not in items:
                    unresolved.add(key)
                    continue
                item = items[key]
                identity = (item['item_id'], tab['title'], tab['mode'])
                if identity not in seen:
                    seen.add(identity)
                    stock.append({**item, 'group': tab['title'], 'trade_mode': tab['mode']})
        npc['stock'] = stock
        npc['source'] = 'client_npcs.xml + client_npc_goodslist.xml + client_npc_trade_in_list.xml + client_items.xml'
        if stock and not npc['description']:
            npc['description'] = 'Предлагает предметы из торговых списков клиента.'
    payload = {'schema_version': 1, 'npcs': npcs,
               'coverage': {'npcs_with_description': len(npcs), 'merchants_with_stock': sum(bool(n['stock']) for n in npcs.values()),
                            'stock_rows': sum(len(n['stock']) for n in npcs.values()), 'unique_items': len(items),
                            'icons': len(icons) - len(missing_icons), 'missing_icons': missing_icons,
                            'unresolved_items': sorted(unresolved)}}
    output.mkdir(parents=True, exist_ok=True)
    with gzip.open(output / 'services.json.gz', 'wt', encoding='utf-8') as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(',', ':'))
    (raw / 'services-report.json').write_text(json.dumps(payload['coverage'], ensure_ascii=False, indent=2), encoding='utf-8')
    return payload['coverage']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('local/bestiary'))
    args = parser.parse_args()
    print(json.dumps(build(args.extract, args.output), ensure_ascii=False))
