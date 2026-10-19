#!/usr/bin/env python3
"""제품 릴스 자동화 (reel.yaml 하나로 프롬프트 → 생성 → 패키지 확인·교체 → 편집 → BGM → MP4).

사용:
  python3 reel.py init --product <제품>              # 위키 제품 문서·원본 폴더로 캠페인 폴더와 reel.yaml 생성 + 원본 이미지 모음
  python3 reel.py sources  <reel.yaml>               # 원본 이미지 번호 모음 (패키지 누끼 후보가 위로)
  python3 reel.py cutout   <reel.yaml> --src <번호|raw 경로> [--box x,y,w,h] [--force]   # 원본에서 패키지 누끼(투명 PNG). 기존 누끼는 --force 없이 덮지 않음
  python3 reel.py init     <캠페인폴더>              # (기존) reel.yaml 견본만 복사
  python3 reel.py prompts  <reel.yaml>               # Codex 첫 프레임·배경 프롬프트 파일 작성 (패키지 이미지 첨부 지시 포함)
  python3 reel.py cost     <reel.yaml>               # 생성 예상 크레딧 (크레딧 차감 없음)
  python3 reel.py generate <reel.yaml> --yes         # 첫 프레임 → Higgsfield image-to-video. 예산 초과 시 중단
  python3 reel.py check    <reel.yaml>               # 클립별 프레임 모음 + 패키지 확인표 작성
  python3 reel.py replace  <reel.yaml> --clips V1,V2 --yes   # 패키지가 빠진 클립만 Genjutsu로 교체
  python3 reel.py build    <reel.yaml> [버전]        # 자막·합성 레이어 → BGM → 16컷 편집 → MP4
  python3 reel.py all      <reel.yaml> [버전]        # layers + bgm + build (로컬, 크레딧 0)

규칙
- 생성은 사람 승인 뒤에만: generate·replace는 --yes가 없으면 비용만 보여 주고 끝남. budget.max_credits 초과 시 중단
- 패키지 우선: 첫 프레임은 패키지 이미지를 첨부해 만든 것만 사용. check에서 ❌가 나온 클립만 replace
- 원본(raw)·지식 문서는 건드리지 않음. 산출물은 reel.yaml의 out_dir 아래에만 씀
"""
import json, shutil, subprocess, sys, time, urllib.request, wave
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

HERE = Path(__file__).resolve().parent
EXAMPLE = HERE.parent / "reel.example.yaml"

# ───────────────────────── 공통 ─────────────────────────
def load(cfg_path):
    cfg_path = Path(cfg_path).resolve()
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    base = cfg_path.parent                                   # 캠페인 폴더
    out = (base / cfg.get("out_dir", "영상")).resolve()
    for sub in ("clips", "frames", "layers", "audio", "check", "tmp"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    cfg["_base"], cfg["_out"] = base, out
    return cfg

def P(cfg, rel):                                             # 캠페인 폴더 기준 경로
    return (cfg["_base"] / rel).resolve()

def run(args, **kw):
    return subprocess.run(args, check=True, **kw)

def ff(args):
    run(["ffmpeg", "-v", "error", "-y", *args])

def hf(args):
    r = subprocess.run(["higgsfield", *args, "--json"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return json.loads(r.stdout)

def download(url, dest):
    with urllib.request.urlopen(url) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)

# ───────────────────────── init / prompts ─────────────────────────
WIKI = HERE.parents[3]                                       # 위키 루트 (.claude/skills/<스킬>/scripts 기준)
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
# 스파우트 파우치 물리 정합 문장 (첫 프레임·영상 프롬프트에 자동 포함). 2026-10-14 사용자 지적: 따를 때 떼어낸 캡이 파우치 옆에 붙어 생성됨
SPOUT_INTEGRITY = ("Package integrity: the pouch has exactly one spout at the top center. The white screw cap is either screwed "
                   "onto that spout (sealed) or completely removed and out of the picture. Never draw a cap attached to the side "
                   "or body of the pouch, no second cap, no second spout, no tether or string, no straw. The pouch keeps its flat "
                   "spout-pouch shape with one top spout.")
CHECKLIST = """## 점검 항목 (프레임 5장 모두)

- 패키지 인쇄: 로고·제품명·캐릭터·색이 누끼와 같은가. 무지 파우치·바뀐 글자·흐려진 인쇄 → ❌ (replace 대상)
- 캡·스파우트·형태: 스파우트는 위 중앙 1개뿐인가. 캡은 「스파우트에 닫힘」 또는 「화면에 없음」 둘 중 하나인가.
  떼어낸 캡이 파우치 옆·몸통에 붙어 있음, 캡 2개, 스파우트 2개, 끈·빨대, 부풀거나 구겨짐·찢김 → ❌
- 얼굴·손·소품: 얼굴·옆얼굴·입·귀 노출, 손가락 수·형태 이상, 파우치 여러 개, 브리프에 없는 과일·소품 → ❌
- ❌ 구간은 `cuts`의 in초를 옮겨 피하고, 피할 수 없으면 첫 프레임을 고쳐 다시 생성한다 (`03` 6절에 기록)
"""

def cmd_init(folder):
    dest = Path(folder) / "reel.yaml"
    if dest.exists():
        sys.exit(f"이미 있음: {dest}")
    shutil.copy(EXAMPLE, dest)
    print("작성:", dest, "→ 브리프·자막·콘티에 맞게 고친 뒤 prompts 실행")

def product_info(product):
    """01_knowledge/products/<제품>.md 첫 줄 제목과 「근거」 줄의 raw 폴더를 읽음"""
    doc = WIKI / "01_knowledge" / "products" / f"{product}.md"
    if not doc.exists():
        names = sorted(p.stem for p in doc.parent.glob("*.md") if p.stem != "README")
        sys.exit(f"제품 문서 없음: {doc.name}. 가능한 제품: {', '.join(names)}")
    text = doc.read_text(encoding="utf-8")
    title = text.splitlines()[0].lstrip("# ").replace(" 제품 사실", "").strip()
    import re
    folders = []
    for m in re.findall(r"`(raw/products/[^`]+)`", text.split("\n\n")[1] if "\n\n" in text else text):
        p = WIKI / m
        if p.is_dir(): folders.append(m.rstrip("/"))
    return title, folders, doc

def cmd_init_product(product, name=None):
    import datetime
    title, folders, doc = product_info(product)
    camp = WIKI / "deliverables" / "content" / (name or f"{product}_릴스_{datetime.date.today().isoformat()}")
    dest = camp / "reel.yaml"
    if dest.exists():
        sys.exit(f"이미 있음: {dest}")
    (camp / "assets").mkdir(parents=True, exist_ok=True)
    y = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    y["name"] = f"{product}_릴스_15초"
    y["product"] = {"title": title, "doc": str(doc.relative_to(WIKI)), "raw_folders": folders}
    y["package"].update({"cutout": "assets/package_cutout.png",
                         "describe": f"[visual-director가 assets/package_cutout.png를 보고 패키지 모양·색·로고·캐릭터·제품명 위치를 영어로 적음] {title}",
                         "source": None,
                         "integrity": SPOUT_INTEGRITY if "스파우트" in doc.read_text(encoding="utf-8") else
                                      "[포장 형태에 맞게 적음: 부품 수·위치, 떼어낸 부품 처리, 모양 유지]"})
    y["clips"] = {k: {"frame": f"[콘티 {k} 첫 화면 구도]", "motion": f"[콘티 {k} 동작]"} for k in ("V1", "V2", "V3", "V4")}
    y["background"]["image"] = "assets/bg_table.png"
    y["captions"]["blocks"] = [
        {"start": 0, "end": 3, "lead": "[원본 리드]", "head": title},
        {"start": 3, "end": 6, "lead": "[원본 리드]", "head": title, "body": "[원본 본문]"},
        {"start": 6, "end": 9, "head": "[원본 헤드]"},
        {"start": 9, "end": 12, "head": "[원본 헤드]", "body": "[원본 본문]"},
        {"start": 12, "end": 13, "head": title},
        {"start": 13, "end": 15, "head": title, "panel": False}]
    header = (f"# {title} 릴스 설정 (reel.py init --product {product}, {datetime.date.today().isoformat()})\n"
              "# [ ] 칸은 인터뷰·02 자막·03 콘티 확정 뒤 채움. cuts는 생성 클립을 보고 in초·확대를 다시 잡음\n"
              "# 원본 폴더는 읽기만 함(raw 불변). 누끼는 sources → cutout으로 assets/에 만듦\n")
    dest.write_text(header + yaml.safe_dump(y, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
    print("작성:", dest)
    print("제품:", title, "| 원본 폴더:", ", ".join(folders) or "없음")
    cmd_sources(dest)

def _sources(cfg):
    folders = cfg.get("product", {}).get("raw_folders") or []
    files = []
    for f in folders:
        files += sorted(p for p in (WIKI / f).iterdir() if p.suffix.lower() in IMG_EXT)
    return files

def _package_score(path):
    """흰·단색 배경의 단독 제품 컷일수록 높음: 테두리 밝기 균일 + 정사각형에 가까움 + 세로로 긴 상세페이지는 감점"""
    im = Image.open(path).convert("RGB"); w, h = im.size
    a = np.asarray(im.resize((200, max(1, round(200 * h / w)))), dtype=np.float32)
    border = np.concatenate([a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3), a[:, :4].reshape(-1, 3), a[:, -4:].reshape(-1, 3)])
    uniform = 1.0 / (1.0 + border.std(axis=0).mean() / 10)
    bright = border.mean() / 255
    shape = 1.0 if h / w < 1.6 else 0.3
    # 배경과 다른 픽셀 덩어리 수: 단독 제품(1개)일수록 높게
    import cv2
    bg = np.median(border, axis=0)
    fg = (np.abs(a - bg).sum(axis=2) > 40).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    ys, xs = np.where(fg > 0)
    wr = (xs.max() - xs.min()) / fg.shape[1] if len(xs) else 1.0      # 제품이 차지하는 가로 비율
    single = 1.0 if wr < 0.7 else (0.6 if wr < 0.85 else 0.2)          # 묶음·여러 제품은 가로를 꽉 채움
    return round(float(uniform * 0.45 + bright * 0.15 + shape * 0.15 + single * 0.25), 3), (w, h)

def cmd_sources(cfg_path):
    cfg = load(cfg_path); files = _sources(cfg)
    if not files: sys.exit("reel.yaml product.raw_folders에 원본 폴더가 없음")
    rows = sorted(((*_package_score(f), f) for f in files), key=lambda r: -r[0])
    listing = [{"no": i + 1, "score": sc, "size": f"{wh[0]}x{wh[1]}", "path": str(f.relative_to(WIKI))} for i, (sc, wh, f) in enumerate(rows)]
    (cfg["_out"] / "check" / "sources.json").write_text(json.dumps(listing, ensure_ascii=False, indent=1), encoding="utf-8")
    tw, th = 220, 260; cols = 6
    sheet = Image.new("RGB", (tw * cols, th * ((len(rows) + cols - 1) // cols)), "white"); d = ImageDraw.Draw(sheet)
    for i, (sc, wh, f) in enumerate(rows):
        im = Image.open(f).convert("RGB"); im.thumbnail((tw - 10, th - 40))
        x, y = (i % cols) * tw, (i // cols) * th
        sheet.paste(im, (x + (tw - im.width) // 2, y + 5))
        d.text((x + 5, y + th - 32), f"#{i+1} 점수 {sc}", fill=(200, 0, 0), font=font_plain(14))
        d.text((x + 5, y + th - 16), f.name[:28], fill=(60, 60, 60), font=font_plain(12))
    out = cfg["_out"] / "check" / "sources.png"; sheet.save(out)
    print("원본 모음:", out, "| 목록:", cfg["_out"] / "check" / "sources.json")
    for r in listing[:5]: print(f"  #{r['no']} 점수 {r['score']} {r['size']} {r['path']}")

def font_plain(size):
    try: return ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", size)
    except Exception: return ImageFont.load_default()

def cmd_cutout(cfg_path, src, box=None, force=False):
    """원본에서 패키지를 오려 투명 PNG로. GrabCut + (흰 단색 배경이면) 배경색 제외로 흰 캡까지 살림"""
    import cv2
    cfg = load(cfg_path)
    if P(cfg, cfg["package"]["cutout"]).exists() and not force:
        sys.exit(f"이미 누끼가 있음: {cfg['package']['cutout']} → 덮어쓰려면 --force (기존 파일은 *_이전.png로 보관됨)")
    if P(cfg, cfg["package"]["cutout"]).exists():
        old = P(cfg, cfg["package"]["cutout"]); shutil.copy(old, old.with_name(old.stem + "_이전.png"))
    if src.isdigit():
        lst = json.loads((cfg["_out"] / "check" / "sources.json").read_text(encoding="utf-8"))
        src = lst[int(src) - 1]["path"]
    path = WIKI / src if not Path(src).is_absolute() else Path(src)
    img = cv2.imread(str(path)); h, w = img.shape[:2]
    border = np.concatenate([img[:3].reshape(-1, 3), img[-3:].reshape(-1, 3), img[:, :3].reshape(-1, 3), img[:, -3:].reshape(-1, 3)])
    plain_bg = border.std(axis=0).mean() < 6 and border.mean() > 200
    if box:
        x, y, bw, bh = [int(v) for v in box.split(",")]
    else:
        x, y, bw, bh = int(w * 0.02), int(h * 0.02), int(w * 0.96), int(h * 0.96)
    mask = np.zeros((h, w), np.uint8); bgd = np.zeros((1, 65), np.float64); fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(img, mask, (x, y, bw, bh), bgd, fgd, 6, cv2.GC_INIT_WITH_RECT)
    m = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    method = "GrabCut"
    if plain_bg:
        # 흰 단색 배경: 배경색과 거의 같은 색만(고정 범위) 테두리에서 채워 '확실한 배경'을 구함
        # → GrabCut이 놓친 흰 캡 같은 부분을 되살림 (확실한 배경이 아니면 제품으로 봄)
        bgc = np.median(border, axis=0)
        near = (np.abs(img.astype(np.int16) - bgc).max(axis=2) <= 4).astype(np.uint8)
        n2, lab2 = cv2.connectedComponents(near)
        edge_labels = set(np.unique(np.concatenate([lab2[0], lab2[-1], lab2[:, 0], lab2[:, -1]]))) - {0}
        sure_bg = np.isin(lab2, list(edge_labels))
        not_bg = np.where(sure_bg, 0, 255).astype(np.uint8)
        not_bg = cv2.morphologyEx(not_bg, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))   # 얇은 압축 노이즈 테두리 제거
        m = cv2.bitwise_or(m, not_bg); method = "GrabCut + 배경색 제외"
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)                 # 가장 큰 덩어리만 (글자·소품 조각 제거)
    if n > 1:
        k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA])); m = np.where(lab == k, 255, 0).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        m = np.zeros_like(m); cv2.drawContours(m, cnts, -1, 255, -1)    # 안쪽 구멍 메움
    m = cv2.erode(m, np.ones((3, 3), np.uint8), iterations=1)            # 가장자리 흰 테두리 1px 제거
    m = cv2.GaussianBlur(m, (3, 3), 0)
    rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA); rgba[:, :, 3] = m
    ys, xs = np.where(m > 10)
    rgba = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    out = P(cfg, cfg["package"]["cutout"]); out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), rgba)
    cut = Image.open(out).convert("RGBA"); pw = 360; ph = round(cut.height * pw / cut.width)
    prev = Image.new("RGB", (pw * 2 + 30, ph + 20), "white")
    chk = Image.new("RGBA", (pw, ph), (200, 200, 200, 255)); d = ImageDraw.Draw(chk)
    for yy in range(0, ph, 20):
        for xx in range(0, pw, 20):
            if (xx // 20 + yy // 20) % 2: d.rectangle((xx, yy, xx + 19, yy + 19), fill=(240, 240, 240, 255))
    small = cut.resize((pw, ph), Image.LANCZOS); chk.alpha_composite(small)
    sky = Image.new("RGBA", (pw, ph), tuple(int(cfg["endcard"]["color"][i:i + 2], 16) for i in (1, 3, 5)) + (255,)); sky.alpha_composite(small)
    prev.paste(chk.convert("RGB"), (10, 10)); prev.paste(sky.convert("RGB"), (pw + 20, 10))
    pv = cfg["_out"] / "check" / "cutout_preview.png"; prev.save(pv)
    cfg_text = Path(cfg_path).read_text(encoding="utf-8")
    if "source: null" in cfg_text:
        Path(cfg_path).write_text(cfg_text.replace("source: null", f"source: {src}", 1), encoding="utf-8")
    print(f"누끼({method}):", out, f"({cut.width}x{cut.height}) | 확인:", pv, "| 원본:", src)
    print("  가장자리·글자를 확인. 다른 물건이 붙었으면 --box x,y,w,h로 영역을 좁혀 다시 실행")

NO_PACKAGE = "No product package of any kind appears in the frame: no pouch, bottle, box, carton, label or printed text."

def frame_prompt(cfg, clip):
    s, pk = cfg["style"], cfg["package"]
    if cfg["clips"][clip].get("package", True) is False:      # 제품이 나오지 않는 클립(밭·원물·캐릭터만, 2026-10-17 추가): 첨부·패키지 문장 없음
        return "\n".join([
            f"[저장] {cfg['out_dir']}/frames/{clip}.png  (세로 9:16, 1080x1920)",
            "[첨부] 없음 (제품이 나오지 않는 장면. 패키지 이미지를 첨부하지 않음)",
            "", s["preamble_frame"], s["person"], NO_PACKAGE, cfg["clips"][clip]["frame"],
            "", "Avoid: " + s["avoid"]])
    return "\n".join([
        f"[저장] {cfg['out_dir']}/frames/{clip}.png  (세로 9:16, 1080x1920)",
        f"[첨부] 패키지 이미지 {pk['cutout']} 를 반드시 함께 첨부",
        "",
        s["preamble_frame"],
        s["person"],
        f"The pouch must be exactly the product in the attached package image: {pk['describe']} "
        "Keep the printed front design, logo, character, colors and layout identical to the attachment, "
        "with the printed front facing the camera and clearly visible. Do not invent new graphics or text. "
        "Place the pouch in the lower 60% of the frame; keep the top 35% of the frame free of the pouch because captions sit there.",
        *([pk["integrity"]] if pk.get("integrity") and not str(pk["integrity"]).startswith("[") else []),
        cfg["clips"][clip]["frame"],
        "",
        "Avoid: " + cfg["style"]["avoid"],
    ])

def cmd_prompts(cfg_path):
    cfg = load(cfg_path)
    blocks = ["# Codex 첫 프레임 프롬프트 (패키지 이미지를 첨부해 생성)\n"]
    for clip in cfg["clips"]:
        blocks.append(f"\n────────── {clip} ──────────\n" + frame_prompt(cfg, clip))
    bg = cfg.get("background")
    if bg and bg.get("prompt"):
        blocks.append(f"\n────────── 배경 ──────────\n[저장] {bg['image']}\n\n{cfg['style']['preamble_frame']}\n{bg['prompt']}")
    out = cfg["_out"] / "Codex_프롬프트.txt"
    out.write_text("\n".join(blocks), encoding="utf-8")
    print("작성:", out)

# ───────────────────────── 생성 ─────────────────────────
def video_args(cfg, clip, frame):
    c = cfg["clips"][clip]; g = cfg["generate"]
    integ = cfg["package"].get("integrity", "")
    integ = "" if str(integ).startswith("[") else integ
    keep = (f"Keep the printed package design on the pouch exactly as in the start image; do not change or blur its lettering or graphics. {integ}"
            if c.get("package", True) is not False else f"{NO_PACKAGE} Do not add one.")
    prompt = (f"Continue from the start image. {c['motion']} {keep} {cfg['style']['preamble_video']} "
              f"Avoid: {cfg['style']['avoid']}")
    return [c.get("model", g["model"]), "--prompt", prompt, "--start-image", str(frame),
            "--aspect_ratio", "9:16", "--duration", str(c.get("duration", g["duration"])),
            "--mode", g.get("mode", "pro"), "--sound", "off"]

def pending_clips(cfg):
    out = []
    for clip in cfg["clips"]:
        frame = cfg["_out"] / "frames" / f"{clip}.png"
        if not frame.exists():
            print(f"  {clip}: 첫 프레임 없음 ({frame.name}) → 건너뜀"); continue
        if (cfg["_out"] / "clips" / f"{clip}.mp4").exists():
            print(f"  {clip}: 이미 생성됨 → 건너뜀"); continue
        pend = cfg["_out"] / "clips" / "pending.json"
        if pend.exists() and f"{clip}.mp4" in json.loads(pend.read_text()):
            print(f"  {clip}: 진행 중 작업 있음 → 이어받기만 함 (추가 비용 없음)"); out.append((clip, frame, True)); continue
        out.append((clip, frame, False))
    return out

def estimate(cfg, jobs, builder):
    total = 0.0
    for job in jobs:
        clip, src = job[0], job[1]
        if len(job) > 2 and job[2]: continue                # 이어받는 작업은 비용 없음
        c = hf(["generate", "cost", *builder(cfg, clip, src)])["credits"]
        print(f"  {clip}: {c} 크레딧"); total += c
    return total

def gate(cfg, total, yes):
    cap = cfg["budget"]["max_credits"]
    bal = hf(["account", "status"]).get("credits")
    print(f"예상 {total} 크레딧 / 예산 {cap} / 잔액 {bal}")
    if total > cap:
        sys.exit("예산 초과 → 중단. reel.yaml budget.max_credits를 사람 승인 뒤 조정")
    if not yes:
        sys.exit("비용 확인만 함. 승인 뒤 --yes로 다시 실행")

def _job_id(res):
    """CLI 응답에서 작업 ID 추출. 문자열·문자열 목록·객체·객체 목록 모두 처리"""
    item = res[0] if isinstance(res, list) and res else res
    if isinstance(item, str): return item, None
    if isinstance(item, dict): return item.get("id") or item.get("job_id"), item.get("preset_recommendation")
    return None, None

def submit_and_fetch(args, dest, log):
    pend = dest.parent / "pending.json"                     # 중단 뒤 재실행 시 중복 생성 방지
    pending = json.loads(pend.read_text()) if pend.exists() else {}
    jid = pending.get(dest.name)
    if jid:
        print(f"  {dest.name}: 진행 중 작업 {jid} 이어받음")
    else:
        jid, preset = _job_id(hf(["generate", "create", *args]))
        if not jid and preset:                              # 무관한 프리셋 추천이면 거절하고 그대로 생성
            jid, _ = _job_id(hf(["generate", "create", *args, "--declined_preset_id", preset["preset_id"]]))
        if not jid:
            raise RuntimeError("작업 ID를 읽지 못함. `higgsfield generate list`로 생성 여부를 먼저 확인할 것")
        pending[dest.name] = jid; pend.write_text(json.dumps(pending, indent=1))
    log.append({"job": jid, "dest": dest.name})
    while True:
        st = hf(["generate", "get", jid])
        if st["status"] == "completed":
            download(st["result_url"], dest); print("  받음:", dest.name)
            pending.pop(dest.name, None); pend.write_text(json.dumps(pending, indent=1)); return st
        if st["status"] in ("failed", "nsfw", "canceled"):
            pending.pop(dest.name, None); pend.write_text(json.dumps(pending, indent=1))
            raise RuntimeError(f"{jid} {st['status']}")
        time.sleep(8)

def cmd_cost(cfg_path):
    cfg = load(cfg_path)
    print("예상 합계:", estimate(cfg, pending_clips(cfg), video_args), "크레딧")

def cmd_generate(cfg_path, yes):
    cfg = load(cfg_path); jobs = pending_clips(cfg)
    if not jobs: return print("생성할 클립 없음")
    gate(cfg, estimate(cfg, jobs, video_args), yes)
    log = []
    for clip, frame, _ in jobs:
        submit_and_fetch(video_args(cfg, clip, frame), cfg["_out"] / "clips" / f"{clip}.mp4", log)
    (cfg["_out"] / "clips" / "jobs.json").write_text(json.dumps(log, ensure_ascii=False, indent=1))

# ───────────────────────── 패키지 확인·교체 ─────────────────────────
def cmd_check(cfg_path):
    cfg = load(cfg_path); rows = ["| 클립 | 패키지 인쇄 보임 (✅/❌) | 캡·스파우트·형태 정상 (✅/❌) | 얼굴·손·소품 정상 (✅/❌) | 메모 |", "|---|---|---|---|---|"]
    for clip in cfg["clips"]:
        src = best_clip(cfg, clip)
        if not src.exists(): continue
        ims = []
        for t in (0.2, 1.2, 2.2, 3.2, 4.2):
            f = cfg["_out"] / "tmp" / f"chk_{clip}_{t}.png"
            ff(["-ss", str(t), "-i", str(src), "-frames:v", "1", "-vf", "scale=240:-1", str(f)]); ims.append(Image.open(f))
        sheet = Image.new("RGB", (240 * len(ims), ims[0].height), "white")
        for i, im in enumerate(ims): sheet.paste(im, (i * 240, 0))
        sheet.save(cfg["_out"] / "check" / f"{clip}_frames.png")
        rows.append(f"| {clip} ({src.name}) |  |  |  |  |")
    (cfg["_out"] / "check" / "패키지확인.md").write_text(
        "# 패키지 확인\n\n`check/<클립>_frames.png`(0.2·1.2·2.2·3.2·4.2초)를 열어 아래 항목을 클립마다 표시. "
        "인쇄 ❌만 replace 대상이고, 캡·형태·얼굴·손 ❌는 교체로 고쳐지지 않으므로 그 구간을 컷에서 빼거나 첫 프레임부터 다시 만든다\n\n"
        + "\n".join(rows) + "\n\n" + CHECKLIST, encoding="utf-8")
    print("작성:", cfg["_out"] / "check")

def flat_cutout(cfg):
    p = Image.open(P(cfg, cfg["package"]["cutout"])).convert("RGBA")
    bg = Image.new("RGBA", p.size, (255, 255, 255, 255)); bg.alpha_composite(p)
    f = cfg["_out"] / "tmp" / "package_flat.jpg"; bg.convert("RGB").save(f, quality=95); return f

def replace_args(cfg, clip, src):
    return ["hf_mult_replace_object", "--resolution", cfg["generate"].get("replace_resolution", "1080p"),
            "--prompt", "Replace the plain spout pouch in the video with the printed pouch from the reference image, "
                        "keeping its position, hand grip, motion, size and lighting. Keep everything else unchanged. One pouch only.",
            "--video-references", str(src), "--image-references", str(flat_cutout(cfg))]

def cmd_replace(cfg_path, clips, yes):
    cfg = load(cfg_path)
    jobs = [(c, cfg["_out"] / "clips" / f"{c}.mp4") for c in clips if not (cfg["_out"] / "clips" / f"{c}_pkg.mp4").exists()]
    if not jobs: return print("교체할 클립 없음")
    gate(cfg, estimate(cfg, jobs, replace_args), yes)
    log = []
    for clip, src in jobs:
        submit_and_fetch(replace_args(cfg, clip, src), cfg["_out"] / "clips" / f"{clip}_pkg.mp4", log)

def best_clip(cfg, clip):
    pkg = cfg["_out"] / "clips" / f"{clip}_pkg.mp4"
    return pkg if pkg.exists() else cfg["_out"] / "clips" / f"{clip}.mp4"

# ───────────────────────── 레이어 ─────────────────────────
def font(cfg, size, weight):
    c = cfg["captions"]
    path = Path(c["font"]).expanduser()
    if not path.is_absolute():
        candidates = [cfg["_base"] / path, WIKI / path, Path.cwd() / path]
        path = next((p for p in candidates if p.is_file()), candidates[0])
    # Bundled TTF files have one face; existing TTC configurations keep their indices.
    index = c.get("font_index", {}).get(weight, 0)
    return ImageFont.truetype(str(path), size, index=index)

def cmd_layers(cfg):
    W, H = cfg["size"]; c = cfg["captions"]; L = cfg["_out"] / "layers"; y = c["y"]
    notice = cfg["package"]["notice"]

    mode = cfg["package"].get("notice_mode", "end_small")     # end_small(기본) | full | none

    def overlay(name, blk, panel=True, notice_on=False):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        y = {**c["y"], **(blk.get("y") or {})}                 # 블록별 위치 덮어쓰기 (예: 마시기 컷은 자막을 파우치 아래로)
        if panel:
            top = y["lead"] - 20 if blk.get("lead") else y["head"] - 30
            bot = y["body"] + 60 if blk.get("body") else y["head"] + 95
            m = Image.new("L", (W, H), 0); ImageDraw.Draw(m).rectangle((0, top, W, bot), fill=150)
            wl = Image.new("RGBA", (W, H), (255, 255, 255, 255)); wl.putalpha(m.filter(ImageFilter.GaussianBlur(28)))
            img.alpha_composite(wl)
        d = ImageDraw.Draw(img)
        if mode == "full":                                   # 전 구간 캡슐 고지
            f = font(cfg, 28, "regular"); tw = d.textlength(notice, font=f)
            d.rounded_rectangle((65, 290, round(65 + tw + 32), 334), radius=22, fill=(0x38, 0x38, 0x38, 204))
            d.text((81, 312), notice, fill=(255, 255, 255), font=f, anchor="lm")
        elif mode == "end_small" and notice_on:             # 끝 화면 오른쪽 아래 작은 글씨 (안전 영역 안)
            d.text((W - 65, 1240), notice, fill=(110, 110, 110), font=font(cfg, 22, "regular"), anchor="rb")
        for key, size, wt in (("lead", 58, "light"), ("head", 72, "bold"), ("body", 43, "regular")):
            if blk.get(key):
                d.text((W // 2, y[key]), blk[key], fill=(0, 0, 0), font=font(cfg, size, wt), anchor="mt")
        img.save(L / f"{name}.png")

    for i, blk in enumerate(c["blocks"]):
        overlay(f"cap_{i}", blk, panel=blk.get("panel", True), notice_on=(i == len(c["blocks"]) - 1))

    pouch = Image.open(P(cfg, cfg["package"]["cutout"])).convert("RGBA")
    pouch = pouch.crop(pouch.getchannel("A").point(lambda v: 255 if v > 0 else 0).getbbox())
    base_y = cfg["package"].get("base_y", 1240)

    def place(canvas, h, sw, st):
        w = round(pouch.width * h / pouch.height)
        p = pouch.convert("RGBa").resize((w, h), Image.LANCZOS).convert("RGBA")
        sh = Image.new("L", (W, H), 0)
        ImageDraw.Draw(sh).ellipse((W // 2 - int(w * sw) // 2, base_y - 18, W // 2 + int(w * sw) // 2, base_y + 10), fill=st)
        k = Image.new("RGBA", (W, H), (0, 0, 0, 255)); k.putalpha(sh.filter(ImageFilter.GaussianBlur(14))); canvas.alpha_composite(k)
        canvas.alpha_composite(p, (W // 2 - w // 2, base_y - h))

    bg = cfg.get("background")
    if bg and P(cfg, bg["image"]).exists():
        im = Image.open(P(cfg, bg["image"])).convert("RGB"); s = bg.get("scale", 1.0)
        big = im.resize((round(W * s), round(H * s)), Image.LANCZOS)
        x0 = (big.width - W) // 2; y0 = max(0, min(big.height - H, round(bg.get("table_y", 0) * s) - bg.get("target_y", 0)))
        canvas = big.crop((x0, y0, x0 + W, y0 + H)).convert("RGBA"); place(canvas, bg.get("pouch_h", 480), 0.95, 120)
        canvas.convert("RGB").save(L / "still_bg.png")
    e = cfg["endcard"]; col = tuple(int(e["color"][i:i + 2], 16) for i in (1, 3, 5))
    if e.get("cutout"):                                      # 끝 화면만 다른 누끼 (예: 3종 묶음 실물 누끼, 2026-10-17 추가)
        pouch = Image.open(P(cfg, e["cutout"])).convert("RGBA")
        pouch = pouch.crop(pouch.getchannel("A").point(lambda v: 255 if v > 0 else 0).getbbox())
    base_y = e.get("base_y", base_y)                         # 가로로 넓은 누끼가 고지(y 1240)와 겹치면 끝 화면 바닥선만 올림
    end = Image.new("RGBA", (W, H), col + (255,)); place(end, e.get("pouch_h", 620), 0.9, 70)
    end.convert("RGB").save(L / "still_end.png")
    print("레이어:", L)

# ───────────────────────── BGM ─────────────────────────
def cmd_bgm(cfg):
    b = cfg["bgm"]
    if b.get("file"):
        shutil.copy(P(cfg, b["file"]), cfg["_out"] / "audio" / "bgm.wav"); return print("BGM: 지정 음원 사용")
    SR, DUR, BEAT = 48000, float(cfg["duration"]), 60 / b.get("bpm", 120)
    N = int(SR * DUR); rng = np.random.default_rng(7); LR = np.zeros((N, 2))
    midi = lambda m: 440.0 * 2 ** ((m - 69) / 12)

    def add(sig, t, gl, gr):
        i = int(t * SR); j = min(N, i + len(sig))
        if i < N: LR[i:j, 0] += sig[: j - i] * gl; LR[i:j, 1] += sig[: j - i] * gr

    def pluck(f, dur):
        n = int(SR * dur); p = max(2, int(SR / f)); ring = rng.uniform(-1, 1, p); out = np.empty(n)
        for k in range(n):
            out[k] = ring[k % p]; ring[k % p] = 0.996 * 0.5 * (ring[k % p] + ring[(k + 1) % p])
        return out * np.linspace(1, 0, n) ** 0.6

    t = np.arange(int(SR * 0.25)) / SR; kick = np.sin(2 * np.pi * (55 + 70 * np.exp(-t * 30)) * t) * np.exp(-t * 14)
    t2 = np.arange(int(SR * 0.08)) / SR; snap = rng.normal(0, 1, len(t2)) * np.exp(-t2 * 60) * 0.6
    chords = {"C": [60, 64, 67, 72], "G": [55, 59, 62, 67], "Am": [57, 60, 64, 69], "F": [53, 57, 60, 65]}
    prog = b.get("progression", ["C", "G", "Am", "F"]); arp = [0, 1, 2, 3, 2, 1, 2, 3]
    bar = 0
    while bar * 4 * BEAT < DUR:
        notes = chords[prog[bar % len(prog)]]; t0 = bar * 4 * BEAT
        add(pluck(midi(notes[0] - 12), 1.8), t0, 0.35, 0.35)
        for k, idx in enumerate(arp):
            tt = t0 + k * BEAT / 2
            if tt < DUR: add(pluck(midi(notes[idx]), 0.8), tt, 0.28 * (0.65 - 0.3 * (k % 2)), 0.28 * (0.35 + 0.3 * (k % 2)))
        bar += 1
    for i in range(int(DUR / BEAT)):
        add(kick if i % 2 == 0 else snap, i * BEAT, 0.5 if i % 2 == 0 else 0.22, 0.5 if i % 2 == 0 else 0.25)
    for tt in b.get("accents", []):
        g = np.arange(int(SR * 1.2)) / SR; f0 = midi(84)
        add((np.sin(2 * np.pi * f0 * g) + 0.3 * np.sin(2 * np.pi * 2.76 * f0 * g)) * np.exp(-g * 4), tt, 0.12, 0.14)
    mix = np.tanh(LR * 1.2); mix *= 0.89 / np.max(np.abs(mix))
    with wave.open(str(cfg["_out"] / "audio" / "bgm.wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    print("BGM: 로컬 원곡 합성 (발행 때 플랫폼 음악으로 교체 권장)")

# ───────────────────────── 편집 ─────────────────────────
def cmd_build(cfg, ver):
    W, H = cfg["size"]; FPS = cfg["fps"]; O = cfg["_out"]; L, T = O / "layers", O / "tmp"
    enc = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18", "-r", str(FPS)]
    ax, ay = W // 2, cfg["package"].get("base_y", 1240)
    parts = []
    for cut in cfg["cuts"]:
        name, dur, src = cut[0], cut[1], cut[2]; out = T / f"{name}.mp4"
        if str(src).startswith("still:"):
            img = L / f"still_{src.split(':')[1]}.png"; zend = cut[4]; n = round(dur * FPS)
            vf = (f"scale={W*2}:{H*2},zoompan=z='1+({zend}-1)*on/{n-1}':x='{ax*2}-{ax*2}/zoom':y='{ay*2}-{ay*2}/zoom'"
                  f":d={n}:s={W}x{H}:fps={FPS}")
            ff(["-loop", "1", "-i", str(img), "-vf", vf, "-frames:v", str(n), *enc, str(out)])
        else:
            t0, z, cx, cy = cut[3], cut[4], cut[5], cut[6]
            cw, ch = round(W / z / 2) * 2, round(H / z / 2) * 2
            x = min(max(cx - cw // 2, 0), W - cw); y = min(max(cy - ch // 2, 0), H - ch)
            vf = f"crop={cw}:{ch}:{x}:{y},scale={W}:{H}:flags=lanczos,setsar=1,fps={FPS}"
            ff(["-ss", str(t0), "-t", str(dur), "-i", str(best_clip(cfg, src)), "-vf", vf, "-an", *enc, str(out)])
        parts.append(out)
    lst = T / "list.txt"; lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    base = T / "base.mp4"; ff(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(base)])
    blocks = cfg["captions"]["blocks"]; inputs = ["-i", str(base)]
    for i in range(len(blocks)): inputs += ["-i", str(L / f"cap_{i}.png")]
    chain, prev = [], "[0:v]"
    for i, blk in enumerate(blocks, 1):
        chain.append(f"{prev}[{i}:v]overlay=0:0:enable='between(t,{blk['start']},{blk['end'] - 0.001})'[v{i}]"); prev = f"[v{i}]"
    bgm = O / "audio" / "bgm.wav"
    if bgm.exists():
        inputs += ["-i", str(bgm)]
        chain.append(f"[{len(blocks)+1}:a]volume=3dB,alimiter=limit=0.5:attack=1:release=30:level=false,aresample=48000[a]"); amap = "[a]"
    else:
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]; amap = f"{len(blocks)+1}:a"
    out = O / f"{cfg['name']}_{ver}.mp4"
    ff([*inputs, "-filter_complex", ";".join(chain), "-map", prev, "-map", amap, *enc,
        "-c:a", "aac", "-b:a", "192k", "-t", str(cfg["duration"]), "-movflags", "+faststart", str(out)])
    # 검수용 프레임 모음
    ims = []
    for i, cut in enumerate(cfg["cuts"]):
        t = sum(c[1] for c in cfg["cuts"][:i]) + cut[1] / 2; f = T / f"k{i}.png"
        ff(["-ss", f"{t:.2f}", "-i", str(out), "-frames:v", "1", "-vf", "scale=216:-1", str(f)]); ims.append(Image.open(f))
    cols = 8; sheet = Image.new("RGB", (216 * cols, ims[0].height * ((len(ims) + cols - 1) // cols)), "white")
    for i, im in enumerate(ims): sheet.paste(im, ((i % cols) * 216, (i // cols) * im.height))
    sheet.save(O / "check" / f"contact_{ver}.png")
    print("완성:", out, "| 프레임 모음:", O / "check" / f"contact_{ver}.png")

# ───────────────────────── main ─────────────────────────
if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    cmd, rest = a[0], a[1:]
    yes = "--yes" in rest; rest = [x for x in rest if x != "--yes"]
    if cmd == "init":
        if "--product" in rest:
            i = rest.index("--product"); nm = rest[rest.index("--name") + 1] if "--name" in rest else None
            cmd_init_product(rest[i + 1], nm)
        else: cmd_init(rest[0])
    elif cmd == "sources": cmd_sources(rest[0])
    elif cmd == "cutout":
        box = rest[rest.index("--box") + 1] if "--box" in rest else None
        cmd_cutout(rest[0], rest[rest.index("--src") + 1], box, force="--force" in rest)
    elif cmd == "prompts": cmd_prompts(rest[0])
    elif cmd == "cost": cmd_cost(rest[0])
    elif cmd == "generate": cmd_generate(rest[0], yes)
    elif cmd == "check": cmd_check(rest[0])
    elif cmd == "replace":
        clips = rest[rest.index("--clips") + 1].split(",") if "--clips" in rest else []
        cmd_replace(rest[0], clips, yes)
    elif cmd in ("layers", "bgm", "build", "all"):
        cfg = load(rest[0]); ver = rest[1] if len(rest) > 1 else "v1"
        if cmd in ("layers", "all"): cmd_layers(cfg)
        if cmd in ("bgm", "all"): cmd_bgm(cfg)
        if cmd in ("build", "all"): cmd_build(cfg, ver)
    else: sys.exit(__doc__)
