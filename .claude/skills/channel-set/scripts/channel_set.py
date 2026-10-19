#!/usr/bin/env python3
"""채널 세트 자동화: campaign.yaml 한 장 → 채널별 이미지·미리보기·자동 검사.

명령
  build       campaign.yaml [--only id,id]   템플릿에 문구·자산을 채워 PNG 출력, 자동 검사, preview.html·manifest.json·자동검수.md
  check       campaign.yaml                  출력 없이 설정만 검사(문구 길이·근거 상태·할인 결정)
  import-reel campaign.yaml reel.yaml        릴스 설정의 패키지 누끼·배경·첫 프레임을 자산 등록부에 추가(이미 있으면 건너뜀)

원본(raw)·위키 지식은 읽기만 한다. 결과는 campaign.yaml이 있는 캠페인 폴더의 out_dir(기본 out/)에만 쓴다.
"""
from pathlib import Path
import argparse, html, json, os, re, shutil, sys

import yaml
from PIL import Image

SKILL = Path(__file__).resolve().parents[1]
TEMPLATES = SKILL / 'templates'

# 채널 규칙 (05_channels 문서 기준, 확인일은 위키 채널 문서에 있음)
CHANNELS = {
    'meta_feed': {'size': (1440, 1800), 'doc': '05_channels/meta-ads.md'},
    'meta_reel': {'size': (1080, 1920), 'doc': '05_channels/meta-ads.md', 'safe': (0.14, 0.35, 0.06)},
    'mobile_main': {'size': (720, 700), 'doc': '05_channels/banner-popup.md', 'no_price': True},
    'insta_card': {'size': (1080, 1350), 'doc': '05_channels/card-news.md'},
    'insta_recruit': {'size': (1080, 1350), 'doc': '05_channels/instagram-feed.md', 'no_price': True, 'no_date': True},
    # 상품 목록 썸네일은 원본 관례상 글자를 넣지 않는다. 목업 표시는 패키지 인쇄의 「이미지 예」로 대신함
    'product_list': {'size': (1000, 1000), 'doc': '05_channels/thumbnail.md', 'no_price': True, 'no_date': True, 'notice_exempt': True},
    'popup': {'size': (400, 476), 'doc': '05_channels/banner-popup.md'},
    # 랜딩(이벤트 페이지)은 섹션마다 높이가 달라 출력별 size로 정하고, stacks로 한 장으로 잇는다
    'landing': {'size': (1000, 1000), 'doc': '05_channels/event-page.md'},
}
AD_COPY_LIMITS = {'primary_feed': 125, 'primary_reel': 44, 'headline': 27}  # 헤드라인은 페이스북 27자에 맞춤
DEFAULT_FORBIDDEN = ['편식', '면역', '무첨가', '첨가물 없', '최고', '1위', '완벽', '치료', '예방', '두뇌', '성장 발달']
# 패키지 위치가 정해진 템플릿: 목록 순서대로 클래스 부여, 이음 문자
POS_CLASSES = {
    'card_cover': (['blue', 'pump', 'apple'], ''),
    'set_overlap': (['blue', 'pump', 'apple'], '\n'),
    'set_steps': (['blue', 'pump', 'apple'], '\n'),
    'set_row': (['p1', 'p2', 'p3'], '\n'),
    'recruit_feed': (['p1', 'p2', 'p3'], ''),
}
NOTICE_ORDER = ['AI 생성 연출', 'AI 생성 배경', '패키지 이미지 예시']

# 패키지가 여러 개일 때 템플릿별 배치 (1개면 템플릿 기본 .pack 그대로)
MULTI_PACK_CSS = {
    'mobile_main_sky': '.pk1{left:140px;top:360px;height:300px;transform:rotate(-6deg)}.pk3{left:400px;top:360px;height:300px;transform:rotate(6deg)}.pk2{left:50%;transform:translateX(-50%);top:330px;height:340px;z-index:2}',
    'mobile_main_table': '.pk1{left:290px;top:340px;height:280px}.pk3{left:490px;top:340px;height:280px}.pk2{left:390px;top:300px;height:320px;z-index:2}',
    'meta_feed_product': '.pk1{left:150px;top:820px;height:780px;transform:rotate(-6deg)}.pk3{left:auto;right:150px;top:820px;height:780px;transform:rotate(6deg)}.pk2{left:50%;transform:translateX(-50%);top:740px;height:900px;z-index:2}',
}

def wiki_root(start):
    for p in [start, *start.parents]:
        if (p / 'CLAUDE.md').exists() and (p / '01_knowledge').exists():
            return p
    return None

def approved_ids(root):
    """승인 표 절의 ID만 승인으로 본다. 등록 대상 절은 승인 전."""
    f = root / '01_knowledge/brand/approved-claims.md' if root else None
    if not f or not f.exists():
        return set()
    text = f.read_text(encoding='utf-8')
    part = text.split('## 승인 표', 1)[-1].split('\n## ', 1)[0]
    return set(re.findall(r'^\|\s*(C-\d+)\s*\|', part, re.M))

def load(path):
    """설정을 읽고, import-reel이 덧붙인 assets_from_reel 절을 자산 등록부에 합친다."""
    path = Path(path).resolve()
    cfg = yaml.safe_load(path.read_text(encoding='utf-8'))
    cfg.setdefault('assets', {}).update(cfg.pop('assets_from_reel', {}) or {})
    return path, cfg

def esc(t):
    return html.escape(str(t)).replace('\n', '<br>')

def fill(tpl, values):
    # {{#key}}...{{/key}} 는 값이 있을 때만 남긴다
    def block(m):
        return m.group(2) if values.get(m.group(1)) else ''
    tpl = re.sub(r'\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}', block, tpl, flags=re.S)
    # {{^key}}...{{/key}} 는 값이 없을 때만 남긴다
    tpl = re.sub(r'\{\{\^(\w+)\}\}(.*?)\{\{/\1\}\}', lambda m: '' if values.get(m.group(1)) else m.group(2), tpl, flags=re.S)
    return re.sub(r'\{\{(\w+)\}\}', lambda m: str(values.get(m.group(1), '')), tpl)

def slot_text(cfg, value):
    """'@키'는 copy 등록부의 문구, 그 밖은 그대로."""
    if isinstance(value, str) and value.startswith('@'):
        key = value[1:]
        if key not in cfg.get('copy', {}):
            raise SystemExit(f'copy에 없는 문구 키: {key}')
        return cfg['copy'][key]['text'], key
    return value, None

def prepare_asset(camp, cfg, aid, out_assets, size=None):
    a = cfg['assets'][aid]
    src = (camp / a['path']).resolve()
    if not src.exists():
        raise SystemExit(f'자산 파일 없음: {aid} → {src}')
    crop = (a.get('crops') or {}).get(f'{size[0]}x{size[1]}') if size else None
    if a.get('crop'):   # 원본 일부를 그대로 잘라 씀(크기 변경 없음). 원본 파일은 읽기만 한다
        name = f'{aid}.png'
        Image.open(src).convert('RGB').crop(tuple(a['crop'])).save(out_assets / name)
    elif crop:
        name = f'{aid}_{size[0]}x{size[1]}.jpg'
        im = Image.open(src).convert('RGB').crop(tuple(crop)).resize(size, Image.LANCZOS)
        im.save(out_assets / name, quality=92)
    else:
        name = a.get('out_name') or src.name
        shutil.copyfile(src, out_assets / name)
    return name

def notice_for(cfg, asset_ids, extra):
    found = set(extra or [])
    for aid in asset_ids:
        n = cfg['assets'][aid].get('notice')
        if n:
            found.update(x.strip() for x in n.split('·'))
    return ' · '.join(sorted(found, key=lambda x: NOTICE_ORDER.index(x) if x in NOTICE_ORDER else 99))

def out_size(o):
    if o.get('size'):
        w, h = str(o['size']).lower().split('x')
        return int(w), int(h)
    return tuple(CHANNELS[o['channel']]['size'])

def build_html(camp, cfg, o, out_assets):
    tpl = (TEMPLATES / f"{o['template']}.html").read_text(encoding='utf-8')
    tpl = re.sub(r'^<!--.*?-->\n', '', tpl, count=1, flags=re.S)  # 템플릿 설명 주석 제거
    size = out_size(o)
    values = {'id': o['id'], 'w': size[0], 'h': size[1]}
    used_copy, asset_ids = [], []

    def txt(v):
        t, key = slot_text(cfg, v)
        if key:
            used_copy.append(key)
        return esc(t) if t else ''

    def asset(aid, sz=None):
        asset_ids.append(aid)
        return prepare_asset(camp, cfg, aid, out_assets, sz)

    for k, v in (o.get('slots') or {}).items():
        if k == 'cards':      # [라벨, 값]
            values['cards_html'] = ''.join(f'<div class="card"><b>{txt(a)}</b><span>{txt(b)}</span></div>' for a, b in v)
        elif k == 'caution':  # [문구] 유의사항 블록
            values['caution_html'] = ''.join(f'<div>· {txt(a)}</div>' for a in v)
        elif k == 'badges':   # [문구]
            values['badges_html'] = ''.join(f'<span>{txt(a)}</span>' for a in v)
        elif k == 'info':     # [라벨, 값] 안내 표
            values['info_html'] = ''.join(f'<div><b>{txt(a)}</b><span>{txt(b)}</span></div>' for a, b in v)
        elif k == 'rows':     # [제목, 설명]
            values['rows_html'] = ''.join(f'<div class="row"><i>{i+1}</i><div><b>{txt(a)}</b><span>{txt(b)}</span></div></div>\n' for i, (a, b) in enumerate(v))
        elif k == 'columns':  # [패키지 자산, 이름, 열량, [항목]]
            values['columns_html'] = ''.join(
                f'<div class="col c{i+1}"><img src="../assets/{asset(pk)}"><b>{txt(nm)}</b><div class="kcal">{txt(kc)}</div><ul>'
                + ''.join(f'<li>{txt(it)}</li>' for it in items) + '</ul></div>\n' for i, (pk, nm, kc, items) in enumerate(v))
        else:
            values[k] = txt(v)
    for key, aid in (o.get('assets') or {}).items():
        if key == 'pack':
            packs = aid if isinstance(aid, list) else [aid]
            names = [asset(p) for p in packs]
            if o['template'] in POS_CLASSES:
                cls, sep = POS_CLASSES[o['template']]
                values['packs_html'] = sep.join(f'<img class="pack {c}" src="../assets/{n}">' for c, n in zip(cls, names))
                values['packs_css'] = ''
            elif len(names) == 1:
                values['packs_html'] = f'<img class="pack" src="../assets/{names[0]}">'
                values['packs_css'] = ''
            else:
                values['packs_html'] = ''.join(f'<img class="pack pk{i+1}" src="../assets/{n}">' for i, n in enumerate(names))
                values['packs_css'] = MULTI_PACK_CSS.get(o['template'], '')
        elif key == 'bg':
            values['asset_bg'] = asset(aid, size)
        else:
            values[f'asset_{key}'] = asset(aid)
    values['notice'] = esc(notice_for(cfg, asset_ids, o.get('notice_extra')))
    return fill(tpl, values), asset_ids, used_copy

def text_checks(cfg, o, text, used_copy, approved):
    res = []
    forbidden = DEFAULT_FORBIDDEN + list((cfg.get('rules') or {}).get('forbidden', []))
    hits = [w for w in forbidden if w in text]
    res.append(('금지 표현', 'FAIL' if hits else 'PASS', ', '.join(hits) or '없음'))
    bad_dates = [d for d in re.findall(r'\d{4}\.\d{2}\.\d{2}\s*[~\-—]\s*[\d.]+', text)
                 if not re.fullmatch(r'\d{4}\.\d{2}\.\d{2} ~ \d{4}\.\d{2}\.\d{2}', d)]
    res.append(('날짜 표기', 'FAIL' if bad_dates else 'PASS', ', '.join(bad_dates) or 'YYYY.MM.DD ~ YYYY.MM.DD'))
    if re.search(r'\d+\s?%\s?(할인|OFF)', text):
        dec = (cfg.get('decisions') or {}).get('discount_price') or {}
        how = (dec.get(o['id']) or dec.get(o['channel'])) if isinstance(dec, dict) else dec
        if how == 'landing':
            res.append(('할인 표기', 'PASS', '정가·할인가는 연결 랜딩에서 병기 (사람 결정)'))
        elif how == 'in_image' and all((o.get('slots') or {}).get(k) for k in ('price_regular', 'price_sale')):
            res.append(('할인 표기', 'PASS', '이미지 안 정가·할인가'))
        else:
            res.append(('할인 표기', 'FAIL', '할인율이 있는데 정가·할인가 병기 결정 없음 → 게시 불가'))
    pending = []
    for key in used_copy:
        for b in cfg['copy'][key].get('basis', []) or []:
            if re.fullmatch(r'C-\d+', b) and b not in approved:
                pending.append(f'{key}({b})')
    holes = re.findall(r'\[[^\]]*입력[^\]]*\]', text)
    if holes:
        res.append(('입력란', 'WARN', f'{len(holes)}곳 남음 → 게시 전 입력: ' + ', '.join(holes[:3])))
    ok_pending = o['id'] in ((cfg.get('decisions') or {}).get('approval_pending_publish') or [])
    if pending and ok_pending:
        res.append(('근거 상태', 'PASS', '승인 대기 표현을 사용자 결정으로 발행: ' + ', '.join(pending)))
    else:
        res.append(('근거 상태', 'WARN' if pending else 'PASS', ('승인 대기: ' + ', '.join(pending)) if pending else '승인 대기 표현 없음'))
    if CHANNELS[o['channel']].get('no_date'):
        d = re.findall(r'\d{4}\.\d{1,2}\.\d{1,2}|\d{1,2}\.\d{1,2}\s*[~—-]|\d{1,2}월\s*\d{1,2}일', text)
        res.append(('이미지 안 날짜', 'FAIL' if d else 'PASS', ', '.join(d) or '없음 (원본 관례)'))
    return res

def build(camp_yaml, only=None):
    path, cfg = load(camp_yaml)
    camp = path.parent
    out = camp / cfg.get('out_dir', 'out')
    for sub in ('src', 'assets', 'outputs'):
        (out / sub).mkdir(parents=True, exist_ok=True)
    for f in (TEMPLATES / 'static').glob('*'):   # 템플릿 공통 CSS 등
        shutil.copyfile(f, out / 'assets' / f.name)
    root = wiki_root(camp)
    approved = approved_ids(root)
    from playwright.sync_api import sync_playwright
    chrome = os.environ.get('CHROME_PATH') or ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').exists() else None)
    report = {'campaign': cfg.get('name'), 'approved_ids': sorted(approved), 'outputs': [], 'ad_copy': ad_copy_checks(cfg)}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, **({'executable_path': chrome} if chrome else {}))
        for o in cfg['outputs']:
            if only and o['id'] not in only:
                continue
            ch = CHANNELS[o['channel']]
            w, h = out_size(o)
            html_text, asset_ids, used_copy = build_html(camp, cfg, o, out / 'assets')
            src = out / 'src' / f"{o['id']}.html"; src.write_text(html_text, encoding='utf-8')
            png = out / 'outputs' / f"{o['id']}.png"
            page = b.new_page(viewport={'width': w, 'height': h}, device_scale_factor=1)
            page.goto(src.as_uri(), wait_until='load'); page.evaluate('document.fonts.ready')
            page.locator('.c').screenshot(path=str(png))
            text = page.locator('.c').inner_text()
            boxes = page.evaluate('''()=>[...document.querySelectorAll('.c *')].filter(e=>e.childElementCount===0&&e.textContent.trim()).map(e=>{const r=e.getBoundingClientRect();return {t:e.textContent.trim(),x0:r.left,y0:r.top,x1:r.right,y1:r.bottom}})''')
            packs_out = page.evaluate('''()=>{const c=document.querySelector('.c').getBoundingClientRect();return [...document.querySelectorAll('img.pack')].filter(i=>{const r=i.getBoundingClientRect();return r.left<c.left-1||r.right>c.right+1||r.top<c.top-1||r.bottom>c.bottom+1}).map(i=>i.getAttribute('src').split('/').pop())}''')
            page.close()
            checks = []
            real = Image.open(png).size
            checks.append(('규격', 'PASS' if real == (w, h) else 'FAIL', f'{real[0]}×{real[1]}'))
            need = notice_for(cfg, asset_ids, o.get('notice_extra'))
            checks.append(('제품 잘림', 'FAIL' if packs_out else 'PASS', ', '.join(packs_out) or '패키지 모두 화면 안'))
            if ch.get('notice_exempt'):
                checks.append(('고지', 'PASS', '목록 썸네일 무문구 관례, 패키지 인쇄 「이미지 예」로 대신함' if need else '필요 없음'))
            else:
                checks.append(('고지', 'PASS' if (not need or need in text) else 'FAIL', need or '필요 없음'))
            if ch.get('safe'):
                t, bt, s = ch['safe']
                x0, x1, y0, y1 = w * s, w * (1 - s), h * t, h * (1 - bt)
                out_of = [bx['t'][:12] for bx in boxes if bx['x0'] < x0 - 1 or bx['x1'] > x1 + 1 or bx['y0'] < y0 - 1 or bx['y1'] > y1 + 1]
                checks.append(('안전 영역', 'FAIL' if out_of else 'PASS', ', '.join(out_of) or f'글자 {len(boxes)}개 모두 안쪽'))
            if ch.get('no_price') and re.search(r'\d{1,3}(,\d{3})+\s?원', text):
                checks.append(('가격 표기', 'FAIL', '이 채널 원본은 가격을 넣지 않음'))
            checks += text_checks(cfg, o, text, used_copy, approved)
            base = o.get('baseline')
            if base:
                bp = (camp / base).resolve()
                if bp.exists():
                    import numpy as np
                    g = lambda q: np.asarray(Image.open(q).convert('L'), float)
                    diff = float(np.abs(g(png) - g(bp)).mean()) if Image.open(bp).size == real else None
                    checks.append(('기준 대비', 'PASS' if diff is not None and diff < 1 else 'WARN', f'평균 픽셀 차 {diff:.2f}' if diff is not None else '크기 다름'))
            state = 'FAIL' if any(c[1] == 'FAIL' for c in checks) else 'WARN' if any(c[1] == 'WARN' for c in checks) else 'PASS'
            report['outputs'].append({'id': o['id'], 'channel': o['channel'], 'template': o['template'], 'file': f"outputs/{o['id']}.png",
                                      'assets': asset_ids, 'copy': used_copy, 'state': state, 'checks': checks})
            print(o['id'], state, ' · '.join(f'{c[0]} {c[1]}' for c in checks))
        b.close()
    for st in cfg.get('stacks') or []:   # 섹션 이미지를 세로로 이어 한 장으로
        parts = [Image.open(out / 'outputs' / f'{pid}.png').convert('RGB') for pid in st['parts']]
        full = Image.new('RGB', (max(i.width for i in parts), sum(i.height for i in parts)), 'white')
        y = 0
        for im in parts:
            full.paste(im, (0, y)); y += im.height
        full.save(out / 'outputs' / f"{st['id']}.jpg", quality=90)
        states = [o['state'] for o in report['outputs'] if o['id'] in st['parts']]
        report['outputs'].append({'id': st['id'], 'channel': 'stack', 'template': '+'.join(st['parts']), 'file': f"outputs/{st['id']}.jpg",
                                  'assets': [], 'copy': [], 'state': 'FAIL' if 'FAIL' in states else 'WARN' if 'WARN' in states else 'PASS',
                                  'checks': [('이어 붙임', 'PASS', f'{len(parts)}개 섹션, {full.width}×{full.height}')]})
        print(st['id'], f'{full.width}×{full.height}')
    (out / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    write_report(out, cfg, report)
    write_preview(out, cfg, report)
    return report

def ad_copy_checks(cfg):
    res = []
    for k, v in (cfg.get('ad_copy') or {}).items():
        lim = AD_COPY_LIMITS.get(k)
        n = len(v)
        res.append((k, n, lim, 'PASS' if (lim is None or n <= lim) else 'FAIL'))
    return res

def write_report(out, cfg, report):
    L = [f"# 자동 검수 · {cfg.get('name')}", '', '스크립트 검사 결과. brand-auditor 판정과 사람 결정을 대신하지 않는다.', '']
    if report['ad_copy']:
        L += ['## 광고 문구 길이', '', '| 칸 | 글자 수 | 기준 | 결과 |', '|---|---|---|---|']
        L += [f'| {k} | {n} | {lim or "-"} | {r} |' for k, n, lim, r in report['ad_copy']] + ['']
    L += ['## 출력별', '', '| ID | 채널 | 결과 | 검사 |', '|---|---|---|---|']
    for o in report['outputs']:
        L.append(f"| {o['id']} | {o['channel']} | {o['state']} | " + ' / '.join(f'{c[0]} {c[1]} ({c[2]})' for c in o['checks']) + ' |')
    (out / '자동검수.md').write_text('\n'.join(L) + '\n', encoding='utf-8')

def write_preview(out, cfg, report):
    cards = ''.join(f'''<a href="{o['file']}"><img src="{o['file']}" alt="{o['id']}"><span>{o['id']} · {o['channel']} · <b class="s-{o['state']}">{o['state']}</b></span></a>''' for o in report['outputs'])
    page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(cfg.get('name',''))} 채널 세트</title>
<style>:root{{--bg:#f6f5f2;--card:#fff;--ink:#2b2420;--sub:#6b625b;--line:#e3ded7}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#1b1b1b;--card:#262626;--ink:#eee;--sub:#aaa;--line:#3a3a3a}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:"Apple SD Gothic Neo","Noto Sans KR",sans-serif}}main{{max-width:1200px;margin:0 auto;padding:28px 16px 56px}}
h1{{font-size:24px;margin:0 0 6px}}p{{color:var(--sub);margin:0 0 20px}}.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px;align-items:start}}
.g a{{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;color:inherit;text-decoration:none}}.g img{{display:block;width:100%}}.g span{{display:block;padding:8px 12px;font-size:13px}}
.s-PASS{{color:#2f7d32}}.s-WARN{{color:#b26a00}}.s-FAIL{{color:#c62828}}</style><main>
<h1>{html.escape(cfg.get('name',''))} · 채널 세트</h1><p>campaign.yaml 한 장으로 만든 출력. 검사 내용은 자동검수.md</p><div class="g">{cards}</div></main></html>'''
    (out / 'preview.html').write_text(page, encoding='utf-8')

def check(camp_yaml):
    path, cfg = load(camp_yaml)
    approved = approved_ids(wiki_root(path.parent))
    for k, n, lim, r in ad_copy_checks(cfg):
        print(f'광고 문구 {k}: {n}자 / 기준 {lim} → {r}')
    for k, c in (cfg.get('copy') or {}).items():
        pend = [b for b in c.get('basis', []) or [] if re.fullmatch(r'C-\d+', b) and b not in approved]
        if pend:
            print(f'근거 상태 {k}: 승인 대기 {pend}')
        if not c.get('source'):
            print(f'출처 없음 {k}: {c["text"]}')
    for aid, a in cfg['assets'].items():
        p = (path.parent / a['path'])
        print(f'자산 {aid}: {"있음" if p.exists() else "없음"} · {a.get("kind")} · 고지 {a.get("notice") or "-"}')

def import_reel(camp_yaml, reel_yaml):
    path, cfg = load(camp_yaml)
    rpath = Path(reel_yaml).resolve()
    reel = yaml.safe_load(rpath.read_text(encoding='utf-8'))
    rdir = rpath.parent
    rel = lambda p: os.path.relpath((rdir / p).resolve(), path.parent)
    add = {}
    pkg = reel.get('package') or {}
    if pkg.get('cutout'):
        add['reel_cutout'] = {'path': rel(pkg['cutout']), 'kind': 'cutout', 'notice': '패키지 이미지 예시', 'from': f'{rpath.name} package.cutout'}
    bg = (reel.get('background') or {}).get('image')
    if bg:
        add['reel_background'] = {'path': rel(bg), 'kind': 'generated', 'notice': 'AI 생성 배경', 'from': f'{rpath.name} background.image', 'crops': {}}
    frames = rdir / reel.get('out_dir', '.') / 'frames'
    for f in sorted(frames.glob('*.png')) if frames.exists() else []:
        add[f'reel_frame_{f.stem}'] = {'path': rel(f), 'kind': 'generated', 'notice': 'AI 생성 연출', 'from': f'{rpath.name} 첫 프레임', 'caution': '아이·손이 나오면 재사용 전 연출 고지와 얼굴 노출 확인'}
    cfg.setdefault('assets', {})
    new = {k: v for k, v in add.items() if k not in cfg['assets'] and v['path'] not in [a['path'] for a in cfg['assets'].values()]}
    if not new:
        print('추가할 자산 없음 (이미 등록됨)'); return
    text = path.read_text(encoding='utf-8')
    block = yaml.safe_dump({'assets_from_reel': new}, allow_unicode=True, sort_keys=False)
    # 원본 설정의 주석을 지키기 위해 assets: 절 끝에 덧붙이지 않고, 별도 절로 추가한 뒤 load 시 합친다
    if 'assets_from_reel:' in text:
        raise SystemExit('assets_from_reel 절이 이미 있음. 새 항목만 손으로 옮기거나 절을 지운 뒤 다시 실행')
    path.write_text(text.rstrip() + '\n\n# import-reel 로 추가 (' + rpath.name + ')\n' + block, encoding='utf-8')
    print('추가:', ', '.join(new))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('build'); a.add_argument('campaign'); a.add_argument('--only')
    c = sp.add_parser('check'); c.add_argument('campaign')
    r = sp.add_parser('import-reel'); r.add_argument('campaign'); r.add_argument('reel')
    args = ap.parse_args()
    if args.cmd == 'build':
        rep = build(args.campaign, set(args.only.split(',')) if args.only else None)
        sys.exit(0)
    elif args.cmd == 'check':
        check(args.campaign)
    else:
        import_reel(args.campaign, args.reel)
