# Progress Bar Implementation

## Overview
이 문서는 웹 인터페이스에 추가된 실시간 프로그래스 바 기능에 대한 설명입니다.

## 주요 기능

### 1. 실시간 진행 상황 표시
- **전체 메일 수**: 검색된 총 메일 개수
- **현재 처리중인 메일**: 현재 처리 중인 메일 번호
- **진행률**: 퍼센트로 표시되는 시각적 프로그래스 바

### 2. 구현 세부 사항

#### Backend (main.py)
메일 처리 중 진행 상황을 로깅하는 구조화된 메시지 추가:

```python
# 전체 메일 수 로깅
logger.info(f"PROGRESS|TOTAL|{num_messages}")

# 현재 처리중인 메일 로깅
logger.info(f"PROGRESS|CURRENT|{idx}|{num_messages}")
```

#### Server (app.py)
QueueHandler를 확장하여 프로그래스 메시지를 감지하고 별도로 전달:

```python
if 'PROGRESS|' in msg:
    parts = msg.split('PROGRESS|')
    if len(parts) > 1:
        progress_data = parts[1].strip()
        self.log_queue.put(msg)  # 일반 로그
        self.log_queue.put(f"__PROGRESS__{progress_data}")  # 프로그래스 데이터
```

#### Frontend (templates/index.html)
프로그래스 바 UI 컴포넌트와 업데이트 로직 추가:

**HTML 구조:**
```html
<div class="progress-bar-container">
    <div class="progress-stats">
        <div class="progress-stat-item">
            <div class="progress-stat-label">전체 메일 수</div>
            <div class="progress-stat-value" id="totalEmails">0</div>
        </div>
        <div class="progress-stat-item">
            <div class="progress-stat-label">처리중인 메일</div>
            <div class="progress-stat-value" id="currentEmail">0</div>
        </div>
    </div>
    <div class="progress-bar-wrapper">
        <div class="progress-bar" id="progressBar"></div>
        <div class="progress-percentage" id="progressPercentage">0%</div>
    </div>
</div>
```

**JavaScript 로직:**
```javascript
function updateProgress(progressData) {
    const parts = progressData.split('|');
    
    if (parts[0] === 'TOTAL') {
        const total = parseInt(parts[1]);
        document.getElementById('totalEmails').textContent = total;
        document.getElementById('progressBarContainer').style.display = 'block';
    } else if (parts[0] === 'CURRENT') {
        const current = parseInt(parts[1]);
        const total = parseInt(parts[2]);
        
        document.getElementById('currentEmail').textContent = current;
        document.getElementById('totalEmails').textContent = total;
        
        const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
        document.getElementById('progressBar').style.width = percentage + '%';
        document.getElementById('progressPercentage').textContent = percentage + '%';
    }
}
```

## 데이터 흐름

1. **Backend**: `main.py`에서 메일 처리 시 `PROGRESS|` 포맷의 로그 생성
2. **Server**: `app.py`의 QueueHandler가 프로그래스 메시지를 감지하고 `__PROGRESS__` 접두사를 추가하여 별도 전송
3. **Transport**: Server-Sent Events (SSE)를 통해 클라이언트로 실시간 전송
4. **Frontend**: JavaScript가 `__PROGRESS__` 메시지를 파싱하고 UI 업데이트

## 메시지 포맷

### PROGRESS|TOTAL
전체 메일 수를 설정
```
PROGRESS|TOTAL|{total_count}
```

### PROGRESS|CURRENT
현재 진행 상황 업데이트
```
PROGRESS|CURRENT|{current_index}|{total_count}
```

## 사용자 경험

1. 사용자가 "이메일 처리 시작" 버튼 클릭
2. 프로그래스 컨테이너가 표시됨
3. 첫 메일이 검색되면 "전체 메일 수"가 표시됨
4. 각 메일 처리 시마다:
   - "처리중인 메일" 숫자 증가
   - 프로그래스 바 채워짐
   - 퍼센트 업데이트
5. 모든 메일 처리 완료 시 100% 표시

## 스타일링

프로그래스 바는 다음과 같은 디자인 특징을 가집니다:
- 그라데이션 배경 (#667eea → #764ba2)
- 부드러운 애니메이션 전환 (0.3s ease)
- 반응형 레이아웃
- 명확한 숫자 표시와 퍼센트 표시

## 테스트

구현을 테스트하려면:
1. Flask 앱 실행: `python3 app.py`
2. 브라우저에서 http://localhost:5000 접속
3. Gmail 인증 정보 입력
4. "이메일 처리 시작" 클릭
5. 프로그래스 바가 실시간으로 업데이트되는지 확인

## 향후 개선 사항

- [ ] 예상 완료 시간 표시
- [ ] 처리 속도 (메일/초) 표시
- [ ] 에러 발생 시 프로그래스 바 색상 변경
- [ ] 취소 버튼 추가
