# 판교 점심 메뉴 알림 봇 — 기획서 & 구현 프롬프트

> 네이버 카페 "판교라이프"의 오늘의 밥집 메뉴 게시글을 매일 자동 수집해서,
> 구독한 식당의 메뉴 사진 + AI 추출 텍스트를 슬랙으로 받아보는 개인용 봇.

---

## 1. 문제 정의

- 판교 직장인/우테코 크루는 점심마다 한식뷔페 메뉴를 확인하고 싶어 한다.
- 메뉴 정보는 네이버 카페 게시판에 사진으로만 올라오며, 매일 카페 접속 → 게시판 진입 → 글 클릭 → 사진 확대라는 4단계를 거쳐야 한다.
- 식당별로 글 올라오는 시간이 제각각(07시~10시)이라 여러 번 들어가 확인하게 된다.

**목표:** 오전 10시 전후, 내가 구독한 식당의 오늘 메뉴가 슬랙 DM으로 도착한다. 끝.

## 2. 범위 (스코프를 좁게 유지할 것)

### v0 — 나만 쓰는 봇 (이번에 만들 것)
- 사용자: 나 1명
- 구독 관리: `config.yaml` 파일 직접 수정 (UI 없음)
- 수집: GitHub Actions cron, 평일 10:00 / 10:40 KST 2회 실행
- 발송: 슬랙 Incoming Webhook (메뉴 사진 + AI 추출 텍스트)
- 저장: 처리한 글 ID를 JSON 파일로 관리 (DB 없음, 저장소에 커밋)

### v1 — 나중에 (이번엔 안 함)
- 카카오 "나에게 보내기" 채널 추가
- 메뉴 히스토리 / "오늘 제육 나오는 집" 검색
- 웹 구독 UI, 다중 사용자

### 명시적 비범위 (non-goals)
- 다수 사용자 대상 공개 서비스 ❌ (카페 이미지 재배포 = 저작권/약관 문제)
- 실시간 알림 ❌ (cron 2회면 충분)
- 메뉴 평가/리뷰 기능 ❌

## 3. 제약 및 리스크 (설계에 반영됨)

| 리스크 | 대응 |
|---|---|
| 네이버 카페 읽기 API 없음 | Playwright 헤드리스 브라우저로 크롤링 |
| 글 열람에 로그인 필요 가능성 | 네이버 계정 쿠키를 GitHub Secrets에 저장, 만료 시 재발급 절차 문서화 |
| 자동화 수집은 약관 회색지대 | 개인 사용 한정, 하루 2회 실행, 요청 간 딜레이 2초 이상, 목록 1페이지만 조회 |
| 봇 탐지/캡차 | 실패 시 조용히 종료 + 슬랙으로 "수집 실패" 알림. 재시도 폭주 금지 |
| 메뉴판 사진 OCR 품질 | Tesseract 대신 Claude Vision API로 구조화 추출 |
| 제목 표기가 들쭉날쭉 ("6월11일" vs "6월 11일", 식당명 따옴표 유무) | 정규식이 아닌 키워드 포함 매칭 + 날짜 정규화 함수 |

## 4. 동작 흐름

```
[GitHub Actions cron 10:00, 10:40 KST]
        │
        ▼
1. Playwright로 카페 로그인 세션 복원 (저장된 쿠키 주입)
        │
        ▼
2. "Today 밥집 메뉴" 게시판 목록 1페이지 파싱
   → (글ID, 제목, 작성시각) 리스트
        │
        ▼
3. 필터링
   a. 제목에서 날짜 추출 → 오늘 날짜인 글만
   b. 제목에 구독 식당 키워드가 포함된 글만
   c. seen.json에 없는 글만 (중복 발송 방지)
        │
        ▼
4. 각 글 본문 진입 → 이미지 URL 수집 → 다운로드
        │
        ▼
5. Claude Vision API 호출
   입력: 메뉴판 사진
   출력: { "restaurant": "...", "date": "...", "menus": ["제육볶음", ...], "price": "...", "uncertain": [...] }
   → 사진이 메뉴판이 아니거나 판독 불가면 menus: [] + 사진만 발송
        │
        ▼
6. 슬랙 웹훅 발송 (식당별 1메시지)
   - 식당명, 메뉴 리스트, 원본 글 링크, 사진 첨부(이미지 URL block)
        │
        ▼
7. seen.json 갱신 → 저장소에 커밋 푸시
```

## 5. 데이터 설계

### config.yaml (구독 설정)
```yaml
subscriptions:
  - name: "엄니한식뷔페"
    keywords: ["엄니한식", "엄니 한식"]   # 제목 매칭용, 표기 변형 흡수
  - name: "해담가"
    keywords: ["해담가"]
  - name: "정겨운맛풍경"
    keywords: ["정겨운맛풍경", "정겨운 맛풍경"]
slack_webhook_env: "SLACK_WEBHOOK_URL"
cafe:
  board_url: "https://cafe.naver.com/f-e/cafes/30487307/menus/0?viewType=L"
```

### seen.json (처리 이력)
```json
{
  "2026-06-11": ["글ID1", "글ID2"],
  "retention_days": 7
}
```
- 7일 지난 키는 실행 시 자동 정리.

### Claude Vision 출력 스키마
```json
{
  "is_menu_board": true,
  "restaurant_name_on_image": "해담가",
  "date_on_image": "6월 11일",
  "menus": ["차돌된장찌개", "제육볶음", "계란찜"],
  "price": "9,000원",
  "uncertain_items": ["흐릿한 항목은 여기"],
  "notes": "휴무 공지 등 특이사항"
}
```

## 6. 엣지 케이스 처리 규칙

1. **오늘 글이 아직 안 올라옴** → 10:00 실행에서 못 찾으면 패스, 10:40 재시도. 그래도 없으면 "오늘 {식당} 메뉴 글이 아직 없어요" 1회 알림.
2. **사진이 여러 장** → 전부 Vision에 넣되, `is_menu_board=true`인 것만 텍스트화. 나머지는 무시.
3. **휴무 공지 글** → Vision의 notes로 감지되면 "오늘 휴무" 메시지 발송.
4. **로그인 세션 만료** → 크롤링 실패 시 슬랙으로 "쿠키 갱신 필요" 알림 + README의 쿠키 재발급 절차 안내.
5. **같은 식당 글이 2개** (수정 재업로드 등) → 더 늦게 작성된 글 채택.
6. **날짜 파싱**: "6월11일", "6월 11일", "06/11" 모두 흡수하는 normalize 함수. 연도는 작성일 기준.

## 7. 기술 스택

- **언어**: Python 3.12 (v0는 속도가 생명. Spring 연습은 v1에서 수집기를 유지한 채 발송/구독 서버만 Spring으로 떼어내는 식으로)
- **크롤링**: Playwright (headless chromium)
- **AI**: Anthropic API — claude vision (이미지 → 구조화 JSON)
- **스케줄링**: GitHub Actions `schedule` (cron은 UTC 기준이므로 KST 10:00 = UTC 01:00)
- **발송**: Slack Incoming Webhook
- **시크릿**: GitHub Secrets — `NAVER_COOKIES`, `ANTHROPIC_API_KEY`, `SLACK_WEBHOOK_URL`

### 비용 추정
- Vision 호출: 식당 3곳 × 사진 2장 × 평일 = 일 6회 호출, 월 수백 원 수준.
- GitHub Actions: 퍼블릭 저장소면 무료. (단, 쿠키가 들어가므로 **반드시 프라이빗 저장소** → 월 2,000분 무료로 충분)

---

## 8. Claude Code 구현 프롬프트 (아래 전체를 복사해서 사용)

```
판교 점심 메뉴 알림 봇을 만들어줘. Python 3.12 프로젝트야.

## 목적
네이버 카페 "판교라이프"의 오늘의 밥집 메뉴 게시판에서 내가 구독한 식당의
오늘자 메뉴 글을 찾아, 메뉴판 사진을 Claude Vision으로 텍스트화한 뒤
슬랙 웹훅으로 보내는 개인용 봇. GitHub Actions cron으로 평일 하루 2회 실행된다.

## 프로젝트 구조
pangyo-lunch-bot/
├── main.py                 # 엔트리포인트: 전체 파이프라인 오케스트레이션
├── crawler.py              # Playwright 기반 카페 크롤러
├── menu_extractor.py       # Claude Vision 호출 및 JSON 파싱
├── notifier.py             # 슬랙 웹훅 발송
├── state.py                # seen.json 읽기/쓰기/7일 정리
├── config.yaml             # 구독 식당 설정
├── seen.json               # 처리한 글 ID 이력 (커밋으로 관리)
├── requirements.txt
├── README.md               # 셋업 절차 (특히 네이버 쿠키 발급 방법)
└── .github/workflows/lunch.yml

## 상세 요구사항

### crawler.py
- Playwright headless chromium 사용.
- 환경변수 NAVER_COOKIES에 JSON 배열로 저장된 쿠키를 context에 주입해 로그인 세션 복원.
- 게시판 목록 URL: https://cafe.naver.com/f-e/cafes/30487307/menus/0?viewType=L
- 네이버 카페는 iframe(cafe_main) 안에 본문이 렌더링될 수 있으니 frame 전환 처리를 포함할 것.
  단, 신형 카페 UI(f-e 경로)는 iframe이 아닐 수 있으므로, 페이지 로드 후 두 구조 모두 시도하는
  방어적 셀렉터 전략을 써줘. 셀렉터는 상수로 분리해서 깨졌을 때 한 곳만 고치면 되게.
- 목록 1페이지에서 (글ID, 제목, 작성시각, 링크)를 추출.
- 요청 사이 2초 sleep. 목록 → 본문 진입은 매칭된 글만(최대 5개).
- 본문에서 <img> 태그의 원본 이미지 URL을 수집해 임시 디렉토리에 다운로드.
- 실패(로그인 풀림, 셀렉터 미스, 타임아웃)는 예외로 올리지 말고
  CrawlResult(status, reason) 형태로 반환해서 main에서 슬랙 에러 알림을 보내게 할 것.

### 제목 파싱 (crawler.py 내 함수)
- parse_title(title: str) -> {date: date | None, matched_restaurant: str | None}
- 날짜 패턴: "6월11일", "6월 11일", "06/11", "6/11" 모두 지원. 연도는 오늘 기준.
- 식당 매칭: config.yaml의 keywords 중 하나라도 제목에 포함되면 매칭.
- 단위 테스트 필수: 실제 제목 샘플로 작성
  - '6월11일 판교아이스퀘어 107호 "해담가" 오늘 메뉴'
  - '6월 11일 경기기업성장센터 2층 "정겨운맛풍경" 오늘 메뉴'
  - '6월11일 판교아이스퀘어 B1 "엄니한식뷔페" 오늘 메뉴'
  - '6월10일 목요일 런치포유 점심메뉴 글로벌비즈센터 B동 110호' (구독 안 한 식당 → None)

### menu_extractor.py
- anthropic 라이브러리로 Claude API 호출 (모델: claude-sonnet-4-6, 환경변수 ANTHROPIC_API_KEY).
- 이미지를 base64로 넣고, 아래 JSON 스키마로만 응답하게 시스템 프롬프트 작성:
  {is_menu_board, restaurant_name_on_image, date_on_image, menus[], price, uncertain_items[], notes}
- 응답에서 마크다운 펜스 제거 후 json.loads. 파싱 실패 시 is_menu_board=false로 폴백.
- 사진 여러 장이면 각각 호출하고 is_menu_board=true인 첫 결과를 채택.

### notifier.py
- 슬랙 Block Kit 사용. 메시지 구성:
  - 헤더: "🍚 {식당명} — {날짜} 메뉴"
  - 메뉴 리스트 (불릿), 가격, notes가 있으면 표시
  - 원본 글 링크 버튼
  - 이미지 block (원본 이미지 URL이 외부 접근 불가하면 텍스트만)
- 에러 알림용 send_error(message) 함수도 별도 제공.

### state.py
- seen.json 로드/저장. 날짜 키 기준 7일 지난 항목 자동 삭제.
- 글 ID 중복 체크 함수 is_seen(post_id), mark_seen(date, post_id).

### main.py 파이프라인
1. config 로드 → 2. 크롤링 → 3. 오늘 날짜 + 구독 매칭 + 미발송 필터
→ 4. 이미지 다운로드 → 5. Vision 추출 → 6. 슬랙 발송 → 7. seen 갱신
- 10:40 실행에서도 구독 식당 글이 하나도 없으면 "아직 안 올라왔다" 알림 1회
  (이미 보냈는지도 seen.json에 기록해 중복 방지).

### .github/workflows/lunch.yml
- schedule: cron "0 1 * * 1-5" 와 "40 1 * * 1-5" (KST 10:00, 10:40)
- workflow_dispatch로 수동 실행 가능하게.
- 스텝: checkout → python 셋업 → pip install → playwright install chromium
  → python main.py → seen.json 변경 시 git commit & push (github-actions bot 계정).
- Secrets: NAVER_COOKIES, ANTHROPIC_API_KEY, SLACK_WEBHOOK_URL

### README.md
- 네이버 쿠키 발급 절차를 단계별로:
  브라우저에서 네이버 로그인 → 개발자도구 → Application → Cookies →
  NID_AUT, NID_SES 등 전체를 JSON 배열로 추출하는 방법 (북마클릿 또는 확장 추천)
- 슬랙 웹훅 생성 절차, GitHub Secrets 등록 절차.
- "개인 사용 목적, 요청 최소화" 원칙 명시.

## 품질 기준
- 외부 I/O(크롤링, API, 슬랙)는 전부 모듈 경계로 분리해서 mock 테스트 가능하게.
- parse_title, state는 pytest 단위 테스트 작성.
- 셀렉터/URL/모델명 같은 변동 가능 값은 상수 또는 config로 분리.
- 로그는 print 대신 logging, 실행 1회의 전 과정이 Actions 로그에서 추적 가능하게.

먼저 프로젝트 뼈대와 parse_title + 테스트부터 만들고, 그다음 크롤러를 구현해줘.
크롤러는 실제 셀렉터를 내가 카페 HTML을 확인하고 알려줄 때까지 placeholder 상수로 두고,
나머지 파이프라인이 mock 데이터로 end-to-end 동작하는 것을 먼저 보여줘.
```

---

## 9. 셋업 체크리스트 (코드 받은 후 네가 할 일)

- [ ] 프라이빗 GitHub 저장소 생성 (쿠키 들어가니까 반드시 private)
- [ ] 슬랙 워크스페이스에 Incoming Webhook 생성
- [ ] 네이버 로그인 쿠키 추출 → `NAVER_COOKIES` Secret 등록
- [ ] Anthropic API 키 발급 → `ANTHROPIC_API_KEY` Secret 등록
- [ ] 카페 게시판/본문의 실제 HTML 구조 확인 → 크롤러 셀렉터 채우기
- [ ] `workflow_dispatch`로 수동 실행 → 슬랙 수신 확인
- [ ] 이틀 정도 cron 모니터링 (쿠키 만료 주기 파악)
