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
- 필터링 된 메일 중 8자리 숫자, 즉 정규식으로 [0-9]{8} 형태, 를 포함하는 메일을 필터링

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

### 환경 변수 설정

Gmail 계정 정보를 환경 변수로 설정:

```bash
export GMAIL_USERID="your-email@gmail.com"
export GMAIL_PASSWORD="your-app-password"
```

**중요:** Gmail에서 2단계 인증을 활성화하고 앱 비밀번호를 생성해야 합니다.
1. Google 계정 설정 → 보안 → 2단계 인증 활성화
2. 앱 비밀번호 생성 (https://myaccount.google.com/apppasswords)
3. Gmail 설정에서 POP 활성화

### 스크립트 실행

```bash
# 날짜 범위를 지정하여 실행
python main.py 2025-01-01 2025-01-31

# 날짜 범위를 지정하지 않으면 최근 30일 데이터 처리
python main.py
```

### 출력

- Excel 파일이 `consultation_report_YYYYMMDD_HHMMSS.xlsx` 형식으로 생성됩니다.
- 파일에는 필터링된 상담 메일 쌍들이 포함됩니다.

## 파일 구조

- `main.py`: 메인 스크립트
- `requirements.txt`: Python 의존성
- `.gitignore`: Git 제외 파일 목록