# Before and After Comparison

## Excel Column Structure

### BEFORE
```
Column Order:
1. 상담일
2. 시작시간
3. 종료시간
4. 장소
5. 학생
6. 학번
7. 발신자 이메일 주소
8. 수신자 이메일 주소
9. 메일의 제목
10. 상담요청 내용
11. 교수 답변

Example Row:
- 상담일: 2025-01-15
- 시작시간: 14:23
- 종료시간: 14:53
- 장소: 연구실
- 학생: 김철수
- 학번: 20251234
- 발신자 이메일 주소: student@example.com
- 수신자 이메일 주소: professor@example.com
- 메일의 제목: 상담 요청
- 상담요청 내용: <p>교수님 안녕하세요...</p> (full text with HTML)
- 교수 답변: 네, 알겠습니다... (full text)
```

### AFTER
```
Column Order:
1. 학번
2. 성명
3. 상담형태
4. 상담일
5. 상담시작시간
6. 상담종료시간
7. 상담유형
8. 장소
9. 학생상담신청내용
10. 교수답변내용
11. 공개여부

Example Row:
- 학번: 20251234
- 성명: 김철수
- 상담형태: 3
- 상담일: 2025-01-15
- 상담시작시간: 14:20  (rounded down from 14:23)
- 상담종료시간: 14:50  (start + 30min)
- 상담유형: CF01
- 장소: 연구실
- 학생상담신청내용: 교수님 안녕하세요... (HTML removed, max 490 chars)
- 교수답변내용: 네, 알겠습니다... (max 490 chars)
- 공개여부: N
```

## Key Differences

### Columns
- ❌ Removed: 발신자 이메일 주소, 수신자 이메일 주소, 메일의 제목
- ✅ Added: 상담형태, 상담유형, 공개여부 (with fixed values)
- 🔄 Renamed: 학생→성명, 시작시간→상담시작시간, 종료시간→상담종료시간, 상담요청 내용→학생상담신청내용, 교수 답변→교수답변내용

### Time Processing
| Scenario | Before | After |
|----------|--------|-------|
| 14:23 | 14:23 | 14:20 (rounded down to 5-min) |
| 14:27 | 14:27 | 14:25 (rounded down to 5-min) |
| 08:30 | 08:30 | 09:05 (early morning → 09:05) |
| 07:00 | 07:00 | 09:05 (early morning → 09:05) |
| End time | start + 30min | adjusted start + 30min |

### Text Processing
| Aspect | Before | After |
|--------|--------|-------|
| HTML tags | Kept in text | Removed from student requests |
| Character limit | No limit | 490 characters max |
| Example | `<p>교수님 안녕하세요</p>` (1000 chars) | `교수님 안녕하세요` (490 chars max) |

## Example Transformations

### Time Rounding Examples
```
Input: 14:23 → Start: 14:20, End: 14:50
Input: 14:27 → Start: 14:25, End: 14:55
Input: 08:15 → Start: 09:05, End: 09:35
Input: 23:57 → Start: 23:55, End: 00:25
```

### HTML Removal Examples
```
Input:  <p>교수님 안녕하세요</p>
Output: 교수님 안녕하세요

Input:  <div>질문<span>입니다</span></div>
Output: 질문입니다

Input:  <html><body><p>Test</p></body></html>
Output: Test
```

### Character Limit Examples
```
Input (600 chars):  "AAAAAA..." (600 characters)
Output (490 chars): "AAAAAA..." (truncated to 490)
```
