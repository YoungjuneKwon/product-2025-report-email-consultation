# Request ID Tracking and Status Monitoring Implementation

## Overview

This implementation adds a comprehensive request tracking system to handle long-running email processing tasks. Each request is assigned a unique ID, and users can monitor the progress in real-time through a dedicated status monitoring page.

## Key Features

### 1. Request ID Generation
- **UUID-based**: Each request gets a unique UUID (e.g., `550e8400-e29b-41d4-a716-446655440000`)
- **Automatic**: IDs are generated automatically when processing starts
- **Included in notifications**: Request IDs are sent in both start and completion emails

### 2. Request Status Tracking
Each request maintains the following state information:
- **status**: `pending`, `processing`, `completed`, or `failed`
- **session_id**: Associated SSE session for real-time logs
- **created_at**: Timestamp when request was created
- **updated_at**: Timestamp of last status update
- **email_count**: Number of emails to process
- **result_count**: Number of successfully processed emails
- **error**: Error message (if failed)

### 3. API Endpoints

#### Get Single Request Status
```
GET /api/request/<request_id>
```
Returns detailed status information for a specific request.

**Response:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "session_id": "session_1728218400_abc123",
  "created_at": "2025-10-06T12:00:00",
  "updated_at": "2025-10-06T12:05:00",
  "email_count": 100,
  "result_count": 45,
  "error": null
}
```

#### List All Requests
```
GET /api/requests
```
Returns a list of all tracked requests, sorted by creation time (newest first).

**Response:**
```json
{
  "requests": [
    {
      "request_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      ...
    },
    ...
  ]
}
```

### 4. Status Monitoring Page

A dedicated web interface at `/status` provides:

- **Request ID Management**
  - Add request IDs manually via input field
  - View all saved request IDs from localStorage
  - Delete request IDs from the list
  - UUID format validation

- **Real-time Monitoring**
  - Click "조회" (View) button to connect to request's SSE stream
  - View request details (status, timestamps, counts)
  - Real-time progress bar for email processing
  - Live log streaming from background processing
  - Color-coded status badges (pending, processing, completed, failed)

- **LocalStorage Integration**
  - Request IDs are saved in browser's localStorage
  - Persists across browser sessions
  - Accessible from any page on the same domain

### 5. Frontend Integration

The main page automatically saves request IDs to localStorage when a new processing request is submitted. Users can then visit the status page to monitor progress.

**Success message includes request ID:**
```
처리가 시작되었습니다. 100개의 이메일을 처리 중입니다. 완료되면 이메일로 결과를 보내드립니다. 요청 ID: 550e8400-e29b-41d4-a716-446655440000
```

### 6. Email Notifications

Both start and completion notification emails include the request ID:

**Start Notification:**
```html
<ul>
  <li><strong>기간:</strong> 2025-01-01 ~ 2025-12-31</li>
  <li><strong>대상 이메일 수:</strong> 100건</li>
  <li><strong>예상 완료 시간:</strong> 약 3분 20초</li>
  <li><strong>요청 ID:</strong> 550e8400-e29b-41d4-a716-446655440000</li>
</ul>
```

**Completion Notification:**
```html
<p><strong>총 95건의 상담 기록이 처리되었습니다.</strong></p>
<p><strong>요청 ID:</strong> 550e8400-e29b-41d4-a716-446655440000</p>
```

## Usage Flow

### For Users

1. **Submit Processing Request**
   - Fill in the form on the main page
   - Click "이메일 처리 시작" button
   - Receive immediate response with request ID
   - Request ID is automatically saved to localStorage

2. **Monitor Progress**
   - Click "📊 요청 진행상황 조회" link
   - See list of all your request IDs
   - Click "조회" button to view real-time progress
   - Watch progress bar and live logs

3. **From Email Notification**
   - Receive email with request ID
   - Visit status page
   - Manually enter the request ID to track progress

### For Developers

**Backend - Request Processing:**
```python
# Generate request ID
request_id = str(uuid.uuid4())

# Store initial status
request_status[request_id] = {
    'status': 'pending',
    'session_id': session_id,
    'created_at': datetime.now().isoformat(),
    'updated_at': datetime.now().isoformat(),
    'email_count': email_count,
    'result_count': 0,
    'error': None
}

# Update status during processing
request_status[request_id]['status'] = 'processing'
request_status[request_id]['updated_at'] = datetime.now().isoformat()

# Mark as completed
request_status[request_id]['status'] = 'completed'
request_status[request_id]['result_count'] = len(pairs)
```

**Frontend - LocalStorage:**
```javascript
// Save request ID
function saveRequestId(requestId) {
    const requestIds = getRequestIds();
    if (!requestIds.includes(requestId)) {
        requestIds.unshift(requestId);
        localStorage.setItem('requestIds', JSON.stringify(requestIds));
    }
}

// Get all request IDs
function getRequestIds() {
    const stored = localStorage.getItem('requestIds');
    return stored ? JSON.parse(stored) : [];
}

// Delete request ID
function deleteRequestId(requestId) {
    const requestIds = getRequestIds();
    const filtered = requestIds.filter(id => id !== requestId);
    localStorage.setItem('requestIds', JSON.stringify(filtered));
}
```

## Architecture

### Request Lifecycle

```
1. User submits form
   ↓
2. Generate UUID request ID
   ↓
3. Store status = 'pending'
   ↓
4. Start background thread
   ↓
5. Return response with request_id
   ↓
6. Frontend saves to localStorage
   ↓
7. Background thread updates status = 'processing'
   ↓
8. Process emails...
   ↓
9. Update status = 'completed' or 'failed'
   ↓
10. Send completion notification
```

### Data Flow

```
Main Page (/):
  - Submit form → Generate request_id → Save to localStorage
  
Status Page (/status):
  - Load from localStorage → Display list
  - Click request → Fetch status via API
  - Connect to SSE stream → Show live logs
  
Backend (app.py):
  - Store request_status in memory dictionary
  - Update status during processing
  - Serve via API endpoints
```

## File Changes

### Backend (`app.py`)
- Added `uuid` import
- Added `request_status` dictionary for tracking
- Modified `send_start_notification()` to include request_id
- Modified `send_completion_notification()` to include request_id
- Modified `process_emails_background()` to update request status
- Modified `/process` endpoint to generate and return request_id
- Added `/api/request/<request_id>` endpoint
- Added `/api/requests` endpoint
- Added `/status` route for status page

### Frontend (`templates/index.html`)
- Added navigation link to status page
- Added localStorage management functions
- Modified success message to show request_id
- Auto-save request_id on successful submission

### New File (`templates/status.html`)
- Complete status monitoring interface
- Request ID input and validation
- Request list with status badges
- Real-time progress monitoring
- SSE stream integration
- LocalStorage integration

## Benefits

1. **User Experience**
   - Users can track long-running requests
   - No need to wait on the page
   - Can check progress from email notifications
   - Multiple requests can be tracked simultaneously

2. **Reliability**
   - Users know if their request is still processing
   - Can identify failed requests
   - Transparent status information

3. **Debugging**
   - Developers can track request lifecycle
   - Error messages are preserved
   - Status history is available

4. **Scalability**
   - Multiple concurrent requests supported
   - Each request tracked independently
   - No blocking on long operations

## Future Enhancements

Possible improvements for future versions:

1. **Persistent Storage**: Store request status in database instead of memory
2. **Request History**: Keep historical records of all requests
3. **User Authentication**: Link requests to specific users
4. **Email Subscription**: Allow users to subscribe to status updates via email
5. **Webhook Support**: Send status updates to external systems
6. **Request Cancellation**: Allow users to cancel in-progress requests
7. **Batch Requests**: Support submitting multiple requests at once
8. **Advanced Filtering**: Filter request list by status, date, etc.

## Screenshots

### Main Page with Status Link
![Main Page](https://github.com/user-attachments/assets/879049c6-9e66-48d5-883b-07d2208be310)

### Status Monitoring Page - Empty State
![Status Page](https://github.com/user-attachments/assets/6d3d0cae-1be8-4973-8f7a-1094c08ccdbf)

### Status Monitoring Page - With Request
![Status Page with Request](https://github.com/user-attachments/assets/0b906d8c-02da-445f-b5a2-e50b1b954877)
