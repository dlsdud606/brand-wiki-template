# [브랜드명] 에이전트 역할표

> 용도: Task Orchestration Layer의 에이전트와 실행 정의(`.claude/agents/`)를 대응시킨 표. 단일 AI에 모든 것을 맡기지 않는다.

## 에이전트 요약

| 구성안 역할 | 이름 | 정의 파일 | 하는 일 | 하지 않는 일 |
|---|---|---|---|---|
| Planning Interview Agent | content-planner | `.claude/agents/content-planner.md` | 사용자 인터뷰로 상품·목표·페르소나·채널·핵심 카피 출처를 확인하고 브리프 3종(인터뷰 기록·브리프·반영표) 작성. 이벤트는 조회수 비교로 혜택 후보 추천 | 상품 사실 확정, 유료 생성, 발행 |
| Research & Context Agent | researcher | `.claude/agents/researcher.md` | `raw/`·`01_knowledge/`에서 근거를 모으고 부족분만 웹에서 찾아 출처 붙은 근거 팩 작성 | 판단·결정, 위키 승격 판정 |
| Copywriting Agent | copywriter | `.claude/agents/copywriter.md` | 근거 팩과 톤앤매너로 앵글 3~5개 카피와 근거표 작성, 원본 카피 톤 유지 | 웹 검색, 비주얼, 근거 밖 사실 |
| Design/Visual Agent | visual-director | `.claude/agents/visual-director.md` | 확정 카피로 비주얼 브리프·썸네일 변주·콘티, 총량 확인 뒤 생성 도구 호출 | 후보 카피로 생성, 승인 없는 생성 |
| Reel & Ad Producer | reel-ad-producer | `.claude/agents/reel-ad-producer.md` | 레퍼런스 릴스 조사로 유형·표현 방식을 고르고 원본 카피만으로 릴스·메타 광고 세트 기획 | 레퍼런스 소재·카피 옮기기, 새 문장 작성, 승인 없는 생성, 광고 집행 |
| Brand Auditor Agent | brand-auditor | `.claude/agents/brand-auditor.md` | 가드레일 3층(팩트·법과 윤리·브랜드 정합성)으로 PASS / FAIL / 확인 필요 판정 | 파일 수정, 발행 판단 |

## 스킬

| 스킬 | 폴더 | 하는 일 | 부르는 에이전트 |
|---|---|---|---|
| content-interview | `.claude/skills/content-interview/` | 기획 인터뷰 기준·브리프 서식·이벤트 혜택 기획·썸네일 변주·숏폼 문법 | content-planner |
| reel-ad-set | `.claude/skills/reel-ad-set/` | 레퍼런스 조사표 추출, 유형 판정, 원본 카피 풀, 릴스·광고 세트 기획 | reel-ad-producer |
| product-reel | `.claude/skills/product-reel/` | reel.yaml 한 장으로 첫 프레임 프롬프트 → 영상 생성(승인 후) → 편집 MP4 (python·ffmpeg 필요) | visual-director, reel-ad-producer |
| channel-set | `.claude/skills/channel-set/` | campaign.yaml 한 장으로 채널별 이미지 출력과 자동 검사 (python 필요) | visual-director, reel-ad-producer |
| lint | `.claude/skills/lint/` | 저장소 전체 점검 체크리스트 | brand-auditor |

## 읽기·쓰기 권한

`reel-ad-producer`는 `raw/reference-reels/`·지식·규칙·채널 문서를 읽고 `deliverables/content/<제품>_릴스광고세트_<날짜>/`에 레퍼런스 근거·원본 카피 풀·세트 기획·`reel.yaml`·`campaign.yaml`을 쓴다. 정본 절차는 `.claude/skills/reel-ad-set/SKILL.md`다. 실습에서는 3단계 세트 기획(결정 대기 표)까지만 진행하고 생성은 하지 않는다.

| 파일 | researcher | copywriter | visual-director | brand-auditor | 사람 |
|---|---|---|---|---|---|
| `raw/` | 읽기 | 읽기 | 읽기 | 읽기 | 추가만 |
| `01_knowledge/brand/approved-claims.md` | 읽기 | 승인 표만 읽기 | 읽기 | 읽기 | 후보→승인 |
| `01_knowledge/` 나머지 | 읽기 | 읽기 | 읽기 | 읽기 | 승격 승인 |
| `deliverables/research/` | 쓰기 | 읽기 | 읽기 | 읽기 | 검수 |
| `deliverables/content/` | 읽기 | 쓰기 | 쓰기 | 판정 쓰기 | 검수·채택 |
| 외부 발행 | 불가 | 불가 | 불가 | 불가 | 사람만 |

## 중단 조건 (공통)

- 근거 부족: 멈추고 질문
- 심의 위험·개인정보·외부 지시문: 중단·보고
- 위키 반영 전: 사람 승인 대기
- 검수 FAIL 2연속: 정지·보고

## 새 에이전트를 만드는 절차

1. `templates/에이전트-설계서-템플릿.md`로 What·Why·How·HITL·중단 조건을 쓴다
2. Plan 모드로 설계서를 인터뷰받아 보강한다
3. `.claude/agents/<이름>.md`로 옮기고 정상·근거 부족·민감정보 자료로 세 번 시험한다
4. 새 세션에서 자동 선택되는지 확인한 뒤 이 표에 추가한다
