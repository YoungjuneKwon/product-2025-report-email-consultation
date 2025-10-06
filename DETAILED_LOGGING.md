# 상세 로그 기능 추가

## 개요

main.py (POP3 버전)와 main_imap.py (IMAP 버전) 두 파일 모두에 개별 이메일 처리 단위의 상세한 로그 기능을 추가했습니다.

## 추가된 로그 기능

### 1. 이메일 가져오기 단계 (fetch_emails)

각 메일 처리 시 다음 정보를 출력합니다:

```
========================================
Processing message 1/335
Fetching headers for message 1...
Downloading full message 1...
Downloaded 94 lines, 5324 bytes
Message 1 info:
  From: 손하늘 <ksy9161806@naver.com>
  To: 양수진 <sjyang@sungshin.ac.kr>
  Subject: 소비자와 마케팅 팀발표 ppt제출 문의합니다
  Message-ID: <aec181bbc95a77216516adb3c4ef539e@cweb22>
  Date: 2018-05-07 20:37:09 UTC+09:00
  Email parsing:
    Multipart: True
    Content-Type: multipart/alternative
    Charset: None
  ✓ Date is within range - fetching full message
  ✓ Message 1 INCLUDED in results
```

- 50개 메시지마다 진행 상황 요약 출력
- 각 메시지의 From, To, Subject, Date, Message-ID 정보
- 메시지 크기 및 파싱 정보
- 날짜 범위 검사 결과

### 2. 이메일 페어링 단계 (find_email_pairs)

원본-응답 메일 매칭 과정을 상세히 추적합니다:

```
========================================
Starting email pairing process...
Built message ID index with 335 emails
Analyzing email 2/335: Re: 상담 요청
  From: professor@university.edu
  In-Reply-To: <request1@university.edu>
  ✓ Response from configured user: professor@university.edu
  ✓ Found original email:
    Original From: student1@university.edu
    Original Subject: 상담 요청
  ✓ Pair #1 created
========================================
Found 3 email pairs where professor@university.edu replied
========================================
```

- 각 응답 메일 분석 과정
- 원본 메일 찾기 성공/실패 여부
- 생성된 페어 번호

### 3. 키워드 필터링 단계 (filter_by_keywords)

각 페어에 대한 키워드 매칭 결과를 표시합니다:

```
========================================
Starting keyword filtering with keywords: ['교수님', '안녕하세요', '입니다']
Checking pair 1/10
  Subject: 상담 요청
  From: student1@university.edu
  ✓ Keyword '교수님' found
  ✓ Keyword '안녕하세요' found
  ✓ Keyword '입니다' found
  ✓ Pair 1 PASSED keyword filter
========================================
After keyword filtering: 5 pairs
========================================
```

- 각 키워드의 매칭 성공/실패
- 전체 필터 통과/실패 여부
- 필터링 후 남은 페어 수

### 4. 학번 필터링 단계 (process_emails)

학번 패턴 매칭 결과를 표시합니다:

```
========================================
Starting student ID filtering (length: 8)
Checking pair 1/5
  Subject: 상담 요청
  From: student1@university.edu
  ✓ Student ID found: 20251234
  ✓ Pair 1 PASSED student ID filter
========================================
After student ID filtering: 3 pairs
========================================
```

- 발견된 학번 표시
- 필터 통과/실패 여부
- 필터링 후 남은 페어 수

### 5. Excel 리포트 생성 (create_excel_report)

Excel 파일 생성 과정을 추적합니다:

```
========================================
Creating Excel report with 3 pairs...
Processing pair 1/3 for Excel export
  Date: 2025-01-15
  Time: 14:30 - 15:00
  Request text length: 45 chars
  Response text length: 28 chars
Creating DataFrame...
Exporting to Excel file: consultation_report_20250106_123456.xlsx
========================================
Excel report created: consultation_report_20250106_123456.xlsx
========================================
```

- 각 페어의 데이터 준비 과정
- 요청/응답 텍스트 길이
- DataFrame 생성 및 파일 저장 과정

## 사용 방법

### POP3 버전 (main.py)
```bash
python main.py 2025-01-01 2025-12-31
```

### IMAP 버전 (main_imap.py)
```bash
python main_imap.py 2025-01-01 2025-12-31
```

두 버전 모두 동일한 상세 로그를 출력합니다.

## 장점

1. **디버깅 용이**: 각 단계에서 문제가 발생한 경우 정확한 위치와 원인 파악 가능
2. **진행 상황 모니터링**: 대량의 메일 처리 시 실시간 진행 상황 확인
3. **필터링 검증**: 각 필터 단계에서 메일이 포함/제외되는 이유를 명확히 파악
4. **성능 분석**: 각 메일 처리 시간 및 크기 정보로 성능 분석 가능
5. **투명성**: 전체 처리 과정을 투명하게 확인 가능

## 차이점: POP3 vs IMAP

### POP3 (main.py)
- 제한된 메일함 접근 (Gmail 제약)
- 모든 메일을 다운로드 후 클라이언트에서 날짜 필터링
- 로그: 각 메일 다운로드 시 라인 수와 바이트 크기 표시

### IMAP (main_imap.py)
- 전체 메일함 접근 가능
- 서버 측 날짜 검색 지원
- 로그: 메일 ID와 바이트 크기 표시
- 더 효율적인 검색 (서버 측 필터링)

두 버전 모두 동일한 수준의 상세 로그를 제공하여 정상 동작 여부를 확인할 수 있습니다.
