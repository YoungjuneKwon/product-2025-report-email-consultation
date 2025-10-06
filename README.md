# product-2025-report-email-consultation


아래 작업을 수행하는 python 프로젝트 작성

# pop3 를 이용해서 특정 기간 gmail 목록 내려 받음
- 기간은 입력으로 받음
- gmail 아이디와 암호는 GitHub secret 에서 GMAIL_USERID, GMAIL_PASSWORD 으로 가져옴
- 메일 로그인에 실패 시 오류 로그를 출력하고 실행 멈춤

# 메일 목록을 아래 순서로 필터링 하여 필요 메일 추출
- 메일 목록 중에 원본과 답변이 있는 메일만 필터링
- GMAIL_USERID 가 답변한 메일로 필터링
- 필터링된 목록을 원본과 답변의 쌍으로 관리
- 원본 메일 내용 중 ["교수님", "안녕하세요", "입니다"] 단어가 모두 포함된 메일 필터링
- 필터링 된 메일 중 8자리 숫자, 즉 정규식으로 [0-9][8] 형태, 를 포함하는 메일을 필터링

# 추출된 메일 쌍에 대해 아래 정보로 정리
- date: 답변 메일을 발송한 날짜
- starttime: 답변 메일을 발송한 시간 (hh:mm 포맷)
- endtime: 답변 메일을 발송한 시간 + 30분 (hh:mm 포맷)
- request:: 원본 메일의 본문 전체 텍스트
- response: 답변 메일의 본문 전체 텍스트

# 위 내용을 pandas 를 이용하여 취함한 후, 아래 열을 갖는 xlsx 형태로 출력
- 상담일: date
- 시작시간: starttime
- 종료시간: endtime
- 장소: "연구실" 로 전체 채움
- 상담요청 내용: request
- 교수 답변: response