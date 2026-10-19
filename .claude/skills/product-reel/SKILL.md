---
name: product-reel
description: 제품 릴스(9:16, 15초 안팎)를 콘텐츠 에이전트 릴레이와 reel.yaml 한 장으로 만드는 자동화. 위키의 어느 제품이든 원본 이미지에서 패키지 누끼를 뽑아 시작(init --product·sources·cutout). 인터뷰·자막·콘티가 끝난 뒤 패키지가 들어간 Codex 첫 프레임 → Higgsfield image-to-video → 패키지 확인·교체 → 자막·합성·BGM 편집 → MP4까지. 「릴스 자동으로 만들어줘」「제품 릴스 다시 렌더」「reel.yaml」 요청에 사용.
---

# 제품 릴스 자동화

실제 제작에서 검증한 순서를 그대로 재현한다. 기획 판단은 에이전트와 사람이, 반복 작업은 `scripts/reel.py`가 맡는다.

## 전체 흐름

| 단계 | 담당 | 산출물 |
|---|---|---|
| 1 인터뷰 | content-planner (`content-interview`) | 00a·00·00b. 핵심 카피 출처(Q4-a), 영상 생성 방식(Q7-a) 포함 |
| 2 근거 팩 | researcher | 01_근거팩 |
| 3 자막 | copywriter | 02_자막카피 (원본 카피 우선, 표현 범위 넓게, AI 라임 금지) |
| 4 콘티 | visual-director (`references/short-form-video.md`) | 03_콘티. 16컷 안팎 0.5~1.5초 |
| 5 검수 | brand-auditor | 04_검수판정 |
| 6 설정 | visual-director | 캠페인 폴더 `reel.yaml` (02·03을 옮겨 적음) |
| 7 첫 프레임 | 사람(Codex) | `reel.py prompts`가 만든 프롬프트 + **패키지 누끼 첨부** → `<out_dir>/frames/<클립>.png` |
| 8 생성 | 주 대화 + 사람 승인 | `reel.py cost` → 승인 → `reel.py generate --yes` |
| 9 패키지 확인 | 주 대화 | `reel.py check` → `check/패키지확인.md`에 인쇄 · 캡·스파우트·형태 · 얼굴·손·소품 3열 ✅/❌ |
| 10 교체 | 주 대화 + 사람 승인 | ❌ 클립만 `reel.py replace --clips V1,V2 --yes` (Genjutsu) |
| 11 편집 | 스크립트 | `reel.py all reel.yaml v1` → MP4 + 프레임 모음 |
| 12 최종 확인 | brand-auditor + 사람 | 프레임 모음·음량·고지 확인, 발행은 사람 |

## 패키지를 처음부터 반영하는 규칙

1. **첫 프레임은 패키지 이미지를 첨부해 만든 것만 쓴다.** `reel.py prompts`의 프롬프트는 누끼 파일 첨부와 「인쇄 정면이 보이게, 디자인 그대로」를 지시한다. 무지 파우치 첫 프레임은 다시 만든다
2. **text-to-video로 제품 장면을 만들지 않는다.** 제품이 나오는 클립은 모두 image-to-video. 영상 프롬프트에는 「시작 프레임의 패키지 인쇄를 바꾸거나 흐리게 하지 않음」을 넣는다(스크립트가 자동 추가)
3. **생성 뒤 확인하고, 빠진 클립만 교체한다.** 손에 가려 작게 보이는 클립은 교체하지 않아도 된다
4. 패키지 이미지가 목업(「이미지 예」 인쇄)이거나 생성 장면이면 연출 고지(`package.notice`)를 **끝 화면 구석에 작은 글씨**로 둔다(`package.notice_mode: end_small`, 기본). 전 구간 표시가 필요하면 `full`, 없애려면 `none`(발행 전 법무·플랫폼 라벨 확인)
5. **제품은 자막 영역 아래에**: 자막이 화면 위 y 290–630에 고정되므로 첫 프레임에서 파우치를 화면 아래 60%에 둔다(프롬프트 자동 포함). 이미 위에 있는 클립은 컷의 중심y를 작게(예: 1) 주어 위쪽 고정 확대로 내린다
6. **파우치가 돌아 뒷면(무지)이 보이는 구간은 컷에서 뺀다.** 교체(Genjutsu)는 정면 인쇄만 입히므로, 회전 장면은 프레임 모음으로 앞뒷면을 확인하고 인쇄 면 구간으로 in초를 옮긴다
7. **얼굴이 화면 가장자리에 걸리면** 확대 컷으로 잘라낸다. 프레임 모음에서 모서리를 따로 확인
8. 글자 확인: 브랜드 로고·제품명·함량 줄을 확대해 본다. 미세 글자가 뭉개지면 그 컷은 펀치인하지 않는다
9. **캡·스파우트·형태 확인** (사용자 지적 2026-10-14: 따르는 장면에서 떼어낸 캡이 파우치 옆에 붙어 생성됨): 스파우트는 위 중앙 1개, 캡은 「닫힘」 아니면 「화면에 없음」. 옆에 붙은 캡·캡 2개·스파우트 2개·끈·부풂은 `check/패키지확인.md`의 「캡·스파우트·형태」 열에 ❌. 이 오류는 Genjutsu 교체로 고쳐지지 않으므로 그 구간을 컷에서 빼거나 첫 프레임부터 다시 만든다. 예방은 `package.integrity` 문장(스파우트 파우치면 `init --product`가 자동으로 넣음)이 첫 프레임·영상 프롬프트에 들어가고, 개봉 장면 첫 프레임 문구에 「the removed cap is not in the picture」를 쓴다

## 다른 제품으로 시작하기 (위키 원본 이미지 사용)

```bash
S=.claude/skills/product-reel/scripts/reel.py
python3 $S init --product <제품명>            # 01_knowledge/products/<제품>.md의 제목·근거 raw 폴더 → deliverables/content/<제품>_릴스_<날짜>/reel.yaml + 원본 이미지 모음
python3 $S cutout deliverables/content/<건명>/reel.yaml --src 1     # sources 1번(단독 제품 컷 점수 1위)에서 패키지 누끼 → assets/package_cutout.png
```

- 제품 이름은 `01_knowledge/products/` 문서 파일명과 같게 쓴다. 문서 머리의 근거 raw 폴더에서 제품 사진을 찾아 누끼를 뜬다
- `sources`: `영상_auto/check/sources.png`(번호·점수)와 `sources.json`. 흰·단색 배경의 단독 제품 컷이 위로 정렬됨(묶음·상세페이지 긴 이미지는 아래). 최종 선택은 사람·visual-director가 그림을 보고 함
- `cutout`: GrabCut + 흰 단색 배경이면 배경색과 같은 픽셀만 제외해 흰 캡까지 살림. `영상_auto/check/cutout_preview.png`(체크무늬·끝 화면 색)로 가장자리 확인. 다른 물건이 붙으면 `--box x,y,w,h`. 기존 누끼는 `--force` 없이 덮지 않음(덮을 때 `*_이전.png` 보관)
- 원본(raw)은 읽기만 함. 원본 패키지에 「이미지 예」 인쇄가 있으면 목업이므로 연출 고지 유지
- init이 만든 reel.yaml의 `[ ]` 칸(패키지 묘사, 클립 구도·동작, 자막)은 인터뷰·02 자막·03 콘티 확정 뒤 채움. 끝 화면 색(`endcard.color`)은 `01_knowledge/brand/visual-guidelines.md`의 제품 색으로 바꿈

## 비용과 승인

- `generate`·`replace`는 `--yes` 없이는 비용만 출력하고 멈춘다. `budget.max_credits`를 넘으면 `--yes`여도 중단
- 승인 받을 때 브리핑: 모델·해상도·클립 수·클립당 크레딧·재시도 한도·잔액 (참고 2026-10-14 조회값: Kling v3.0 pro 5초 7.5, Seedance 2.5 1080p 60, Genjutsu 1080p 66 / 720p 42)
- Higgsfield CLI(`higgsfield`) 로그인이 필요하다. 결과 다운로드는 스크립트가 직접 한다

## BGM·내레이션

- 기본은 로컬 합성 원곡(120BPM, 블록 전환에 강조음). 발행 때는 플랫폼 음악 라이브러리 곡으로 바꾸는 것을 권장
- 라이선스 음원이 있으면 `bgm.file`에 지정
- 내레이션은 기본 없음(자막이 메시지를 전함). 넣을 때는 도구·비용을 따로 승인받는다(프로젝트 규칙상 Higgsfield 음성 생성은 기본 금지)

## 명령 요약

```bash
S=.claude/skills/product-reel/scripts/reel.py
python3 $S init deliverables/content/<건명>          # reel.yaml 견본 복사 → 02·03 기준으로 수정
python3 $S prompts deliverables/content/<건명>/reel.yaml
python3 $S cost    deliverables/content/<건명>/reel.yaml
python3 $S generate deliverables/content/<건명>/reel.yaml --yes
python3 $S check   deliverables/content/<건명>/reel.yaml
python3 $S replace deliverables/content/<건명>/reel.yaml --clips V1,V2 --yes
python3 $S all     deliverables/content/<건명>/reel.yaml v1
```

견본: `reel.example.yaml` (자리표시자만 든 설정). 캠페인 폴더에 복사해 02_자막카피·03_콘티를 옮겨 적는다

## 포함 서체 선택

위키 루트의 `assets/fonts/`에 마루 부리 SemiBold·배민 주아체·Gmarket Sans Bold가 있다. `01_knowledge/brand/fonts.md`에서 용도와 라이선스를 확인한 뒤 `captions.font`에 위키 루트 기준 경로를 적는다. TTF 파일은 `font_index: {light: 0, regular: 0, bold: 0}`로 지정하며 각 키가 별도 굵기를 만드는 것은 아니다. 기존 TTC 설정은 원래 인덱스를 유지한다. 서체 1개 선택은 기본 스크립트에서 지원하며 컷별 서체·모션 조합은 별도 편집 구현이 필요하다.
