# [브랜드명] 콘텐츠 제작 파이프라인

> 용도: 구성안의 5-Step Agent Content Pipeline을 이 저장소의 폴더·에이전트·서식에 대응시킨 운영 흐름. 발행 전에는 사람에서 멈춘다.

## 5-Step과 저장소 대응

| 단계 | 구성안 명칭 | 이 저장소에서 하는 일 | 입력 | 출력 | 담당 |
|---|---|---|---|---|---|
| Step 1 | Ingestion | `raw/` 새 근거 → `01_knowledge/` 반영안 | [자료 유형] | 반영안 (승인 전) | researcher + 사람 승인 |
| Step 2 | Context Retrieval | 브리프 → 관련 필러·승인 표현·제품 사실·VOC 근거 팩 | 캠페인 브리프 | `deliverables/research/` 리포트 | researcher |
| Step 3 | Generation | 근거 팩 → 앵글 3~5 카피 → 확정 카피 → 비주얼 | 근거 팩, 채널 가이드 | `deliverables/content/` | copywriter → visual-director |
| Step 4 | Audit & Critique | 가드레일 3층 판정. FAIL 1회 수정, 2연속 정지 | 초안 | 판정문 | brand-auditor |
| Step 5 | Human Refinement | 검수 체크리스트, 채널 변형, 발행, 승격 | PASS 초안 | 발행본, 승격분 | 사람 |

## 릴레이 흐름

```text
캠페인 브리프 (사람)
   ▼
[researcher]  근거 팩 리포트 → deliverables/research/
   ▼
[copywriter]  앵글 3~5 카피 표 + 근거표 → deliverables/content/
   ▼  (사람이 앵글 선택 → 확정 카피)
[visual-director]  브리프 → 총량 브리핑 → 승인 → 생성
   ▼
[brand-auditor]  PASS / FAIL / 확인 필요
   ▼
★ 사람 검수 → 발행
   └─ 재사용 지식 → 5필터 → 01_knowledge/
```

## 단계 사이의 계약

- 근거 유입 창구는 researcher 하나다
- copywriter → visual-director로는 확정 카피 파일 경로만 넘긴다
- 후보 표(`R-xx`)는 리포트 안에만 둔다
- 크레딧이 드는 생성 전에는 총량 브리핑과 승인이 있다
- 각 에이전트는 본 대화에 5줄 이내 요약과 파일 경로만 보고한다

## 자동 실행 범위

| 자동으로 하는 것 | 사람 몫 |
|---|---|
| 근거 팩, 초안, 검수 판정, 로그 | 앵글 선택, 생성 승인, 채택, 승격, 발행 |

## 실행 방식 (조직이 선택)

| 방식 | 선택 | 근거 |
|---|---|---|
| 로컬 수동 실행 | | |
| Claude Desktop 로컬 예약 | | |
| GitHub Actions | | |
| 클라우드 Routines | | |

## 안전 규칙

1. 검수 FAIL 2연속이면 정지·보고
2. 로그에는 비식별 정보만
3. 실행 전 자가 점검 실패 시 본 작업 없이 종료
