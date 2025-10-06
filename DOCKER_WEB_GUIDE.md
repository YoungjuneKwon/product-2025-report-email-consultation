# Docker 및 웹 인터페이스 사용 가이드

## 웹 인터페이스

### 로컬 실행

1. **의존성 설치**:
```bash
pip install -r requirements.txt
```

2. **Flask 개발 서버 실행**:
```bash
python app.py
```

3. **웹 브라우저에서 접속**:
```
http://localhost:5000
```

### WSGI 프로덕션 서버 실행

Gunicorn을 사용한 프로덕션 배포:

```bash
# 4개의 워커 프로세스로 실행
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 300 wsgi:app

# 더 많은 워커와 로그 설정
gunicorn -w 8 -b 0.0.0.0:8000 --timeout 300 --access-logfile - --error-logfile - wsgi:app
```

## Docker 사용법

### Docker 이미지 빌드

```bash
docker build -t gmail-consultation-report .
```

### Docker 컨테이너 실행

```bash
# 기본 실행 (포트 5000)
docker run -p 5000:5000 gmail-consultation-report

# 포트 변경 (8080으로)
docker run -p 8080:5000 gmail-consultation-report

# 백그라운드 실행
docker run -d -p 5000:5000 --name consultation-report gmail-consultation-report

# 환경 변수 설정 (선택사항)
docker run -p 5000:5000 \
  -e SECRET_KEY=your-secret-key \
  gmail-consultation-report
```

### Docker Compose (선택사항)

`docker-compose.yml` 파일 생성:

```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - SECRET_KEY=change-this-in-production
    restart: unless-stopped
```

실행:
```bash
docker-compose up -d
```

## 웹 인터페이스 사용법

1. **Gmail 계정 정보 입력**
   - Gmail 이메일 주소
   - Gmail 앱 비밀번호 (2단계 인증 필요)

2. **기간 선택**
   - 시작일과 종료일을 달력에서 선택

3. **선택 옵션** (필요시)
   - 학번 길이: 학번 자릿수 지정 (기본값: 8)
   - 포함 단어: 필터링할 키워드 입력 (쉼표로 구분)

4. **처리 시작**
   - "이메일 처리 시작" 버튼 클릭
   - 결과 테이블 확인

5. **엑셀 다운로드**
   - "엑셀 다운로드" 버튼으로 결과 저장

## 주의사항

- Gmail에서 2단계 인증을 활성화하고 앱 비밀번호를 생성해야 합니다
- POP3가 Gmail 설정에서 활성화되어 있어야 합니다
- 처리 시간은 이메일 수에 따라 달라질 수 있습니다
- 프로덕션 환경에서는 반드시 `SECRET_KEY` 환경 변수를 설정하세요
