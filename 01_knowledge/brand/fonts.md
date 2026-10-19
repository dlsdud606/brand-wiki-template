# 콘텐츠용 서체

- 등록일: 2026-10-18 · 사용자 지정으로 추가한 제작용 선택 서체 3종
- 출처·파일 해시: [`raw/design/fonts/sources.json`](../../raw/design/fonts/sources.json)
- 저작권·라이선스 원문: `raw/design/fonts/` 및 `assets/fonts/licenses/`
- 기존 브랜드 전용 서체나 공식 BI가 지정되어 있으면 그 기준을 먼저 따른다. 아래 선택지는 브랜드의 과거 자산에서 식별한 서체라는 뜻이 아니다.

## 파일과 권장 용도

| 서체 | 포함 굵기 | 실제 파일 (위키 루트 기준) | 제작 시 권장 용도 |
|---|---|---|---|
| 마루 부리 | SemiBold | `assets/fonts/MaruBuri-SemiBold.ttf` | 원료·산지·브랜드 이야기의 차분한 제목, 짧은 문구 |
| 배민 주아체 | Regular | `assets/fonts/Jua-Regular.ttf` | 캐릭터·레시피·친근한 제목, 짧은 탄성 모션 |
| Gmarket Sans | Bold | `assets/fonts/GmarketSansTTFBold.ttf` | 제품 소개·핵심어·함량 숫자, 빠른 타이포 전환 |

표의 용도는 제작 제안이다. 실제 화면의 글자 크기·배경 대비·가독성을 보고 선택한다. 포함한 굵기 외의 파일은 공식 배포처에서 추가한다.

## 설치와 선택

- PowerPoint·디자인 편집기: 필요한 TTF를 더블클릭해 macOS는 서체 관리자에서 「설치」, Windows는 「설치」를 누른다. 이미 열어 둔 편집기에 보이지 않으면 다시 연다.
- Python·Pillow 렌더: 위키에 포함한 파일을 직접 읽을 수 있어 OS에 설치하지 않아도 된다. 폴더를 다른 컴퓨터로 옮길 때 `assets/fonts/`와 라이선스도 함께 가져간다.
- 설치 목록의 표기는 `MaruBuri`(SemiBold), `Jua`, `Gmarket Sans TTF`(Bold)일 수 있다.

## 릴스 설정 예시

`reel.yaml`의 기존 `captions` 아래에서 서체 항목을 선택한다. 다음 경로는 위키 루트 기준이며 릴스 스크립트가 작업 폴더 밖에서도 찾는다.

```yaml
captions:
  font: assets/fonts/GmarketSansTTFBold.ttf
  font_index: {light: 0, regular: 0, bold: 0}
  # 기존 y·blocks 등의 설정은 그대로 유지
```

- 원료·산지형: `font: assets/fonts/MaruBuri-SemiBold.ttf`
- 캐릭터·레시피형: `font: assets/fonts/Jua-Regular.ttf`
- 제품·숫자형: `font: assets/fonts/GmarketSansTTFBold.ttf`
- 포함 TTF는 파일당 1개 굵기여서 `font_index`는 모두 0이다. 위의 light·regular·bold 키를 바꿔도 별도 굵기가 생기지 않는다.
- 기본 릴스 스크립트는 한 편의 자막에 서체 1개를 적용한다. 컷별 서체·색·모션을 섞는 편집은 별도 편집 구현이 필요하다.

## 사용·재배포 안내

- 포함한 글꼴은 원본 파일 그대로 보관한다. 함께 들어 있는 저작권 안내와 라이선스 원문을 유지한다.
- 서체 파일만 따로 유료 판매하지 않는다. 수정·재배포는 각 라이선스 원문의 조건을 따른다.
- 전체 안내와 확인일은 `raw/design/fonts/sources.json`, 전문은 `assets/fonts/licenses/`에서 확인한다.

## 공식 배포처

| 서체 | 소개·다운로드 | 라이선스 근거 |
|---|---|---|
| 마루 부리 | [네이버 글꼴](https://hangeul.naver.com/fonts/search?f=maru) | [네이버 공식 안내](https://help.naver.com/service/30016/contents/18088?osType=PC&lang=ko), `raw/design/fonts/MaruBuri-LICENSE.txt` |
| 배민 주아체 | [우아한형제들](https://www.woowahan.com/fonts) | [공식 안내](https://www.woowahan.com/fonts/license), [배포 OFL](https://raw.githubusercontent.com/google/fonts/main/ofl/jua/OFL.txt), `raw/design/fonts/Jua-OFL.txt` |
| Gmarket Sans | [디자인 시스템](https://gds.gmarket.co.kr/foundation/typography), [공식 다운로드](https://corp.gmarket.com/fonts/) | TTF name ID 13의 내장 원문, `raw/design/fonts/GmarketSans-LICENSE.txt` |
