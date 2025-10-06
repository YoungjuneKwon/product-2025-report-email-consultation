# product-2025-report-email-consultation

Gmail 상담 메일을 수집하고 Excel 보고서를 생성하는 Python 프로젝트

## 기능

### pop3 를 이용해서 특정 기간 gmail 목록 내려 받음
- 기간은 입력으로 받음
- gmail 아이디와 암호는 GitHub secret 에서 GMAIL_USERID, GMAIL_PASSWORD 으로 가져옴
- 메일 로그인에 실패 시 오류 로그를 출력하고 실행 멈춤

### 메일 목록을 아래 순서로 필터링 하여 필요 메일 추출
- 메일 목록 중에 원본과 답변이 있는 메일만 필터링
- GMAIL_USERID 가 답변한 메일로 필터링
- 필터링된 목록을 원본과 답변의 쌍으로 관리
- 원본 메일 내용 중 ["교수님", "안녕하세요", "입니다"] 단어가 모두 포함된 메일 필터링
- **Strict 모드 (기본값)**: 제목 또는 본문에 학번 패턴이 있는 메일만 필터링
  - 필터링 된 메일 중 제목 또는 본문에서 8자리 숫자 (정규식: [0-9]{8}) 를 포함하는 메일을 필터링
  - `--no-strict` 옵션으로 비활성화 가능 (본문만 검사하는 기존 방식)

### 추출된 메일 쌍에 대해 아래 정보로 정리
- date: 답변 메일을 발송한 날짜
- starttime: 답변 메일을 발송한 시간 (hh:mm 포맷)
- endtime: 답변 메일을 발송한 시간 + 30분 (hh:mm 포맷)
- request: 원본 메일의 본문 전체 텍스트
- response: 답변 메일의 본문 전체 텍스트

### 위 내용을 pandas 를 이용하여 취합한 후, 아래 열을 갖는 xlsx 형태로 출력
- 상담일: date
- 시작시간: starttime
- 종료시간: endtime
- 장소: "연구실" 로 전체 채움
- 상담요청 내용: request
- 교수 답변: response

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

### 웹 인터페이스 (권장)

웹 브라우저를 통해 편리하게 사용할 수 있습니다:

```bash
# 의존성 설치
pip install -r requirements.txt

# 웹 서버 실행
python app.py

# 브라우저에서 접속
# http://localhost:5000
```

웹 인터페이스에서는:
- Gmail 이메일 주소와 앱 비밀번호 입력
- 달력 UI로 기간 선택
- **Strict 모드**: 제목 또는 본문에 학번이 있는 이메일만 처리 (기본: 활성화)
- 선택적으로 학번 길이와 키워드 지정
- **처리 시작 시 이메일로 진행 알림 수신**
- **백그라운드에서 처리되므로 브라우저를 닫아도 됨**
- 결과를 테이블로 확인
- 엑셀 파일 다운로드
- **처리 완료 시 이메일로 결과 수신 (Excel 파일 첨부)**

### CLI 사용 (기존 방식)

#### 환경 변수 설정

Gmail 계정 정보를 환경 변수로 설정:

```bash
export GMAIL_USERID="your-email@gmail.com"
export GMAIL_PASSWORD="your-app-password"
```

**중요:** Gmail에서 2단계 인증을 활성화하고 앱 비밀번호를 생성해야 합니다.
1. Google 계정 설정 → 보안 → 2단계 인증 활성화
2. 앱 비밀번호 생성 (https://myaccount.google.com/apppasswords)
3. Gmail 설정에서 POP 활성화

#### 스크립트 실행

```bash
# 날짜 범위를 지정하여 실행 (strict 모드 - 기본값)
python main.py 2025-01-01 2025-01-31

# strict 모드를 비활성화하여 실행 (본문만 검사)
python main.py 2025-01-01 2025-01-31 --no-strict

# 날짜 범위를 지정하지 않으면 최근 30일 데이터 처리
python main.py

# 도움말 보기
python main.py --help
```

**Strict 모드란?**
- 기본 설정으로, 이메일 제목 또는 본문에 학번 패턴이 있는 경우만 처리합니다
- 더 많은 관련 이메일을 찾을 수 있어 권장됩니다
- `--no-strict` 옵션으로 비활성화 시 본문만 검사합니다 (기존 방식)

#### 출력

- Excel 파일이 `consultation_report_YYYYMMDD_HHMMSS.xlsx` 형식으로 생성됩니다.
- 파일에는 필터링된 상담 메일 쌍들이 포함됩니다.

### Docker 사용

```bash
# Docker 이미지 빌드
docker build -t gmail-consultation-report .

# Docker 컨테이너 실행
docker run -p 5000:5000 gmail-consultation-report

# 또는 Docker Compose 사용
docker-compose up -d
```

자세한 내용은 [DOCKER_WEB_GUIDE.md](DOCKER_WEB_GUIDE.md)를 참조하세요.

## 테스트

Gmail 계정 없이 기능을 테스트하려면 예제 스크립트를 실행하세요:

```bash
python example.py
```

이 스크립트는 샘플 이메일 데이터로 필터링 로직을 테스트하고 `example_report.xlsx` 파일을 생성합니다.

## 파일 구조

- `main.py`: 메인 스크립트 (CLI 및 핵심 로직)
- `app.py`: Flask 웹 애플리케이션
- `wsgi.py`: WSGI 프로덕션 서버 진입점
- `templates/`: HTML 템플릿 디렉토리
  - `index.html`: 메인 웹 인터페이스
  - `404.html`: 404 에러 페이지
  - `500.html`: 500 에러 페이지
- `example.py`: 테스트용 예제 스크립트
- `requirements.txt`: Python 의존성
- `Dockerfile`: Docker 이미지 빌드 설정
- `docker-compose.yml`: Docker Compose 설정
- `DOCKER_WEB_GUIDE.md`: Docker 및 웹 인터페이스 사용 가이드
- `EMAIL_REPORT_IMPLEMENTATION.md`: 이메일 레포트 기능 구현 문서
- `.gitignore`: Git 제외 파일 목록

## 새로운 기능: 이메일 레포트

웹 인터페이스를 통한 요청 시:

1. **시작 알림 이메일**: 처리 시작 시 이메일로 진행 상황 알림
   - 처리 기간
   - 대상 이메일 수
   - 예상 완료 시간 (이메일 1건당 2초)

2. **백그라운드 처리**: 브라우저를 닫아도 서버에서 처리 계속

3. **완료 알림 이메일**: 처리 완료 시 이메일로 결과 전송
   - Excel 파일 첨부
   - 결과 요약 테이블

자세한 내용은 [EMAIL_REPORT_IMPLEMENTATION.md](EMAIL_REPORT_IMPLEMENTATION.md)를 참조하세요.