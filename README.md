# 판교 점심 메뉴 알림 봇 (Pangyo Lunch Bot)

네이버 카페 "판교라이프"의 오늘의 밥집 메뉴 게시판에서 매일 구독한 식당의 메뉴 정보를 수집하여 Gemini Vision API로 텍스트화한 뒤 슬랙(Slack) Incoming Webhook으로 발송하는 개인용 봇 프로젝트입니다.

---

## 🛠️ 기술 스택
- **Python**: 3.12+
- **크롤링**: Playwright (Headless Chromium)
- **AI (OCR)**: Google Gemini API (`gemini-1.5-flash` 무료 티어 권장)
- **스케줄러**: GitHub Actions (`cron` 평일 매일 실행)
- **알림**: Slack Incoming Webhook (Block Kit)

---

## 📁 프로젝트 구조
- `main.py`: 파이프라인 제어 및 실행 엔트리포인트.
- `crawler.py`: Playwright 기반 게시판 크롤러 및 게시글 날짜/식당 필터링.
- `menu_extractor.py`: Gemini API 연동 (이미지 OCR 및 구조화 JSON 추출).
- `notifier.py`: 슬랙 Webhook 발송 (Block Kit 구성).
- `state.py`: `seen.json`을 통한 중복 발송 방지 및 7일 보관 히스토리 정리.
- `config.yaml`: 구독할 식당 및 검색 키워드 설정.
- `seen.json`: 발송 완료된 글 ID 관리 데이터 (자동 생성 및 Git Commit 관리).

---

## 🚀 로컬 환경 구축 및 실행 방법

### 1. Python 가상환경 생성 및 패키지 설치
```bash
# 가상환경 생성
python -m venv .venv

# 가상환경 활성화 (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# 가상환경 활성화 (macOS / Linux)
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium
```

### 2. 환경변수 설정
프로젝트를 실행하려면 다음 환경변수들이 필요합니다.
- `GEMINI_API_KEY`: Google AI Studio에서 발급받은 API 키 (무료 티어 사용 가능)
- `SLACK_WEBHOOK_URL`: Slack Incoming Webhook URL
- `NAVER_COOKIES` (선택): 카페가 비공개/멤버 전용으로 변경될 경우 네이버 로그인 세션 유지를 위한 쿠키 JSON 문자열.

#### 로컬에서 환경변수 설정 예시 (PowerShell):
```powershell
$env:GEMINI_API_KEY="AIzaSy..."
$env:SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

### 3. 로컬 테스트 실행

- **Mock 모드로 테스트 (API 호출 및 크롤링 생략)**:
  ```bash
  python main.py --mock
  ```
  *환경변수가 설정되지 않은 경우 자동으로 Mock 모드로 실행됩니다.*

- **실제 연동 실행**:
  ```bash
  python main.py
  ```

- **특정 날짜 수동 수집 (테스트용)**:
  ```bash
  python main.py --date 2026-06-11
  ```

- **누락 검사 실행 테스트 (10:40) 실행**:
  ```bash
  python main.py --time 10:40
  ```

---

## 🔒 네이버 로그인 쿠키 획득 방법 (선택사항)
카페가 비공개로 바뀌거나 접근에 로그인이 필수적일 경우에만 필요합니다.

1. 브라우저에서 네이버 로그인 후 대상 카페로 접속합니다.
2. 개발자 도구(F12) -> **Application** -> **Cookies** -> `https://cafe.naver.com` 항목을 선택합니다.
3. 전체 쿠키 데이터를 복사하여 JSON 포맷 파일로 변환하거나, [EditThisCookie] 같은 크롬 확장 도구를 통해 JSON 포맷으로 Export합니다.
4. 해당 JSON 문자열을 `NAVER_COOKIES` 환경변수 또는 GitHub Secrets에 등록합니다.

---

## 🤖 GitHub Actions 설정 (Private 저장소 전용)

1. 이 프로젝트를 **반드시 Private 저장소**로 생성하여 GitHub에 업로드합니다. (API 키 및 쿠키 정보 보호 목적)
2. GitHub 저장소의 **Settings** -> **Secrets and variables** -> **Actions**로 이동하여 다음 Repository Secrets를 등록합니다:
   - `GEMINI_API_KEY`
   - `SLACK_WEBHOOK_URL`
   - `NAVER_COOKIES` (필요 시 등록)
3. 워크플로우에 의해 `seen.json` 파일이 업데이트되면 자동으로 `github-actions[bot]`이 저장소에 변경사항을 커밋하고 푸시합니다.
