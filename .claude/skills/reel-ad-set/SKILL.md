---
name: reel-ad-set
description: 레퍼런스 릴스 조사(raw/reference-reels/)에 grounding해 제품 하나의 릴스·메타 광고 세트를 기획하고 제작하는 절차. 유형별 반응 천장과 AI 제작 품질로 릴스 유형을 고르고, 레퍼런스에서는 영상 표현 방식만 가져오며, 제목·자막은 자사 원본 카피만 쓴다. 담당 에이전트는 reel-ad-producer. 「레퍼런스 보고 릴스 기획해줘」「릴스랑 메타 광고 세트」「유형별로 뭐가 맞아」 요청에 사용. 릴스 제작 자체는 product-reel, 광고 이미지 출력은 channel-set.
---

# 릴스·메타 광고 세트 (레퍼런스 grounding)

레퍼런스 70편을 읽고 **유형과 영상 표현 방식**을 고른 뒤, 자사 원본 카피로 릴스와 메타 광고 세트를 만든다. 담당 에이전트는 `.claude/agents/reel-ad-producer.md`.

## 절차

| 단계 | 산출물 | 도구 |
|---|---|---|
| 1 레퍼런스 요약 | `01_레퍼런스_근거.md` — 유형별 분포·상위 사례·AI 품질 판정 | `scripts/reference_grounding.py` (읽기 전용) + `references/expression-catalog.md` |
| 2 원본 카피 풀 | `02_원본카피풀.md` — 제품 자산의 문장을 사용 가능 / 조건부 / 불가로 분류 | `deliverables/research/asset-transcripts/<제품>.md`, `01_knowledge/products/<제품>.md`, `negative-list/`, `approved-claims.md` |
| 3 세트 기획 | `00_세트기획.md` — 릴스 N편(유형·원본 카피 제목·표현 방식·클립 수) + 메타 광고(피드 A/B/C·릴스 끝 화면·광고 문구) + 결정 대기 | 1·2단계 결과 |
| 4 사람 결정 | 결정 대기 항목 회신 | 주 대화 |
| 5 릴스 제작 | `reel.yaml` → 첫 프레임 → 생성(승인 후) → 확인 → 편집 MP4 | `../product-reel/scripts/reel.py` |
| 6 광고 출력 | `campaign.yaml` → `import-reel` → `build` → PNG·preview·자동검수 | `../channel-set/scripts/channel_set.py` |
| 7 검수 | `04_검수판정.md` | brand-auditor |

## 세 가지 원칙

1. **레퍼런스는 표현 방식만.** 컷 구성·카메라·편집 리듬·사운드·자막 문법을 가져온다. 소재·스토리·카피·화면은 옮기지 않는다
2. **내용은 원본 카피만.** 제목·자막은 제품 자산의 문장을 그대로 쓰거나 금지 부분만 지운 일부 변형. 새로 쓴 문장 0. 원문이 없는 슬롯은 함량·제품명(`[근거: 제품 정보]`)으로 채운다
3. **AI가 못 만드는 것은 만들지 않는다.** C·E·G형은 생성하지 않고 참여작·실사로 돌린다. 반응 천장이 높아도 품질이 안 나오면 세트에서 뺀다

## 명령

```bash
S=.claude/skills/reel-ad-set/scripts/reference_grounding.py
X=raw/reference-reels/<레퍼런스_조사표>.xlsx
python3 $S $X                                   # 전체 요약
python3 $S $X --type A,B,F --top 5             # 채택 후보 유형만
python3 $S $X --kr-only --out deliverables/content/<건명>/01_레퍼런스_근거.md
```

## 이 스킬이 없는 위키에서

`product-reel`·`channel-set`이 없으면 1~4단계(기획·콘티·프롬프트·campaign.yaml 초안)까지 하고, 5·6단계는 「해당 스킬 없음」으로 보고한다.
