import gzip
import json
import zipfile

from tools.build_bestiary_services import build


def test_client_trade_links_use_localized_items_and_report_missing(tmp_path):
    raw = tmp_path / 'bestiary'
    raw.mkdir()
    strings = tmp_path / 'raw/l10n/rus/data/Strings'
    strings.mkdir(parents=True)
    (strings / 'names.xml').write_text('''<strings>
      <string><name>TITLE</name><body>&lt;Кузнец&gt;</body></string>
      <string><name>ITEM</name><body>Туника</body></string>
      <string><name>GROUP</name><body>Одежда</body></string>
    </strings>''', encoding='utf-8')
    (raw / 'client_npcs.xml').write_text('''<npc_clients><npc_client><id>1</id>
      <npc_function_type>Merchant</npc_function_type><npc_title>TITLE</npc_title>
      <trade_info><tab_list><data><tab>SALE_ARMOR</tab></data></tab_list></trade_info>
    </npc_client></npc_clients>''', encoding='utf-8')
    (raw / 'client_npc_goodslist.xml').write_text('''<lists><list><name>sale_armor</name><desc>GROUP</desc>
      <goods_list><data><item>ARMOR</item></data><data><item>missing</item></data></goods_list>
    </list></lists>''', encoding='utf-8')
    (raw / 'client_npc_trade_in_list.xml').write_text('<lists/>')
    with zipfile.ZipFile(raw / 'items.zip', 'w') as archive:
        archive.writestr('client_items.xml', '''<items><client_item><id>100</id><name>armor</name>
        <desc>ITEM</desc><quality>rare</quality><level>10</level></client_item></items>''')
    output = tmp_path / 'out'
    report = build(tmp_path, output)
    assert report['merchants_with_stock'] == 1
    assert report['unresolved_items'] == ['missing']
    with gzip.open(output / 'services.json.gz', 'rt', encoding='utf-8') as stream:
        npc = json.load(stream)['npcs']['1']
    assert npc['title'] == 'Кузнец'
    assert npc['stock'][0]['name'] == 'Туника'
    assert npc['stock'][0]['group'] == 'Одежда'
    assert npc['stock'][0]['item_id'] == '100'
