---
name: channel-set
description: 캠페인 하나를 campaign.yaml 한 장으로 채널별 이미지(메타 피드·릴스 끝 화면·자사몰 모바일 메인 등)로 한 번에 만들고 자동 검사하는 자동화. 릴스에서 만든 패키지 누끼·생성 배경·첫 프레임을 자산 등록부로 가져와 다른 채널에 다시 쓴다. 「채널별로 한 번에 만들어줘」「릴스 이미지로 배너도」「campaign.yaml」「채널 세트 다시 출력」 요청에 사용. 인터뷰는 content-interview, 영상은 product-reel.
---

# 채널 세트 자동화

하나의 캠페인 문구·자산을 채널 템플릿에 채워 채널별 이미지를 한 번에 출력한다. 기획 판단은 인터뷰와 사람이, 반복 작업과 규칙 검사는 `scripts/channel_set.py`가 맡는다.

## 흐름

| 단계 | 담당 | 산출물 |
|---|---|---|
| 1 인터뷰 | content-planner (`content-interview`) | 00a·00·00b. 상품·채널·문구 출처(Q4-a)·생성 여부 |
| 2 설정 | visual-director | 캠페인 폴더 `campaign.yaml` (사실·결정·문구 등록부·자산 등록부·출력 목록) |
| 3 릴스 자산 가져오기 | 스크립트 | `channel_set.py import-reel campaign.yaml <reel.yaml>` → 누끼·배경·첫 프레임 등록 |
| 4 출력 | 스크립트 | `channel_set.py build campaign.yaml` → `out/outputs/*.png`, `out/preview.html`, `out/manifest.json`, `out/자동검수.md` |
| 5 검수 | brand-auditor + 사람 | 자동검수에서 FAIL·WARN 확인, 이미지 직접 확인, 발행 결정 |

## campaign.yaml

견본은 `campaign.example.yaml`. 캠페인 폴더에 복사해 사실·결정·문구·자산·출력을 채운다.

- `facts`: 기간·혜택·가격과 상태(확정·제안·미정)
- `decisions`: 사람이 정한 것. 예: `discount_price: {mobile_main: landing}` (할인율 표기를 연결 랜딩에서 충족)
- `copy`: 화면에 들어가는 모든 문구. `text`·`source`(원본 경로 또는 기준 캠페인)·`basis`(제품 정보 또는 C-xx)
- `ad_copy`: 광고 관리자 입력 문구(`primary_feed`·`primary_reel`·`headline`). 길이 자동 검사
- `assets`: `path`·`kind`(cutout·photo·generated)·`notice`(패키지 이미지 예시·AI 생성 배경·AI 생성 연출)·`crops`(채널 크기별 자를 영역)
- `outputs`: `id`·`channel`·`template`·`assets`(`pack`은 1개 또는 목록, `bg`)·`slots`(`@문구키`)·`baseline`(비교할 기존 결과, 선택)

## 템플릿 (templates/)

| 템플릿 | 채널 | 크기 | 슬롯·자산 |
|---|---|---|---|
| meta_feed_product · meta_feed_benefit · meta_feed_info | meta_feed | 1440×1800 | badge·sub·head·under / band·cards. pack |
| reel_endcard | meta_reel | 1080×1920 | badge·sub·head (안전 영역 안). pack |
| mobile_main_sky · mobile_main_table | mobile_main | 720×700 | badge·subl(선택)·head1·head2·chip(선택). pack, bg(table) |
| popup_event | popup | 400×476 | badge·sub·head·benefit·aux·button·legal. pack |
| landing_hero · landing_photo · landing_offer · landing_info | landing | 가로 1000, 높이는 출력 `size` | 히어로 / 글+사진(구성·원료) / 혜택·가격(price_regular·price_sale, 비면 입력란) / 안내 표(info). `stacks`로 한 장 |
| card_cover · card_photo · card_columns · card_storage · card_summary | insta_card | 1080×1350 | 표지 / 사진+배지 / 맛별 비교(columns) / 사진+설명 / 정리(rows). logo, photo, pack |
| set_overlap · set_row · set_steps | product_list | 1000×1000 | 겹침 / 나란히+label / 계단. pack 3개 |
| recruit_feed | insta_recruit | 1080×1350 | badge·head·name·flavors·ask·bar. logo, pack 3개 |

- 목록 슬롯: `cards`·`rows`·`info`는 [라벨, 값], `badges`는 [문구], `columns`는 [패키지 자산, 이름, 열량, [항목]]
- `{{#키}}…{{/키}}`는 값이 있을 때만, `{{^키}}…{{/키}}`는 값이 없을 때만 나온다
- 자산: `crop`(원본 일부를 그대로 잘라 씀), `crops`(채널 크기별로 잘라 맞춤), `out_name`(출력 파일 이름)
- 템플릿은 검수까지 끝낸 결과물 HTML에서 문구만 슬롯으로 바꾼 것이다. 새 채널은 결과물을 먼저 만들고 검수한 뒤 템플릿으로 옮긴다. 채널 규격은 `CHANNELS`, 패키지 위치는 `POS_CLASSES`·`MULTI_PACK_CSS`에 있다

## 자동 검사

| 검사 | 기준 |
|---|---|
| 규격 | 출력 PNG 실제 픽셀 = 채널 크기 |
| 제품 잘림 | 패키지 이미지가 화면 밖으로 나가지 않음 |
| 고지 | 쓴 자산의 고지(목업·생성 배경·생성 연출)가 화면에 있음. 자산 등록부에서 자동으로 채움. 상품 목록 썸네일은 무문구 관례라 예외 |
| 안전 영역 | 릴스: 글자가 위 14%·아래 35%·양옆 6% 안쪽 |
| 가격 표기 | 모바일 메인·상품 목록·체험단 피드: 가격 숫자 없음 |
| 이미지 안 날짜 | 상품 목록·체험단 피드: 날짜 없음(원본 관례) |
| 입력란 | `[…입력…]`이 남아 있으면 WARN → 게시 전 입력 |
| 금지 표현 | 기본 목록(편식·면역·무첨가 등) + `rules.forbidden` |
| 날짜 표기 | 연도가 있는 기간은 YYYY.MM.DD ~ YYYY.MM.DD |
| 할인 표기 | 「N% 할인」이 있으면 `decisions.discount_price`(출력 ID 또는 채널별)가 있어야 함. landing=연결 랜딩에서 병기, in_image=price 슬롯 필수. 없으면 게시 불가 FAIL |
| 근거 상태 결정 | `decisions.approval_pending_publish`에 적은 출력은 승인 대기 표현을 사용자 결정으로 발행(PASS로 기록) |
| 근거 상태 | 문구 basis의 C-xx가 승인 표 「승인 표」 절에 없으면 승인 대기 WARN |
| 기준 대비 | baseline이 있으면 평균 픽셀 차 1 미만 |
| 광고 문구 길이 | primary_feed 125자, primary_reel 44자, headline 27자 |

자동 검사는 brand-auditor 판정과 사람 결정을 대신하지 않는다. 화면 배치의 어색함(글자와 제품 겹침, 빈 공간)은 미리보기로 사람이 본다.

## 생성 이미지 재사용 규칙

1. 다른 채널·상품에 다시 쓰는 생성 배경은 패키지·로고·글자가 없는 것만 등록한다
2. 제품은 항상 실제 패키지 누끼를 위에 올린다. 생성 이미지 속 제품을 제품 사진으로 쓰지 않는다
3. 생성 자산을 쓴 출력에는 고지가 자동으로 붙는다. 고지를 지우지 않는다
4. 릴스 첫 프레임(아이·손 장면)은 재사용 전 얼굴 노출과 연출 고지를 확인한다 (`caution`)
5. 크기가 다른 채널은 `crops`에 자를 영역을 적고, 주제가 잘리지 않는지 미리보기로 확인한다

## 실행

```bash
S=.claude/skills/channel-set/scripts/channel_set.py
python3 $S check deliverables/content/<건명>/campaign.yaml        # 출력 없이 문구 길이·근거 상태·자산 존재 확인
python3 $S import-reel deliverables/content/<건명>/campaign.yaml deliverables/content/<릴스 건명>/reel.yaml
python3 $S build deliverables/content/<건명>/campaign.yaml [--only meta_feed_A,mobile_main_A]
```

필요: Python 3, PyYAML, Pillow, NumPy, Playwright와 Chrome 또는 Chromium(`CHROME_PATH`로 지정 가능). 원본(raw)·위키 지식은 읽기만 하고 결과는 캠페인 폴더의 `out/`에만 쓴다. 게시·광고 집행은 하지 않는다.
