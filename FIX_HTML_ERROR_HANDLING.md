# HTML Error Handling Fix

## Problem Statement

When the server returned HTML error pages (404 or 500) instead of JSON responses, the web interface displayed confusing error messages with raw HTML fragments:

```
❌ 서버와 통신 중 오류가 발생했습니다: Unexpected token '<', "<html> <h"... is not valid JSON
```

This occurred because:
1. Flask error handlers returned HTML error pages with `Content-Type: text/html`
2. JavaScript tried to parse these HTML responses as JSON using `response.json()`
3. The JSON parser threw a SyntaxError with the HTML fragment in the message
4. This confusing error was displayed to the user

## Solution

Added content-type checking before attempting to parse responses as JSON in the web interface.

### Changes Made

**File: `templates/index.html`**

#### 1. Process Endpoint Error Handling

**Before:**
```javascript
const response = await fetch('/process', {
    method: 'POST',
    body: formData
});

const data = await response.json();  // ❌ Fails if response is HTML

// Close the event source
if (eventSource) {
    eventSource.close();
    eventSource = null;
}
```

**After:**
```javascript
const response = await fetch('/process', {
    method: 'POST',
    body: formData
});

// Close the event source
if (eventSource) {
    eventSource.close();
    eventSource = null;
}

// ✅ Check if response is JSON before parsing
const contentType = response.headers.get('content-type');
if (!contentType || !contentType.includes('application/json')) {
    // Server returned non-JSON response (likely HTML error page)
    throw new Error('서버에서 예상치 못한 응답을 받았습니다. 서버 오류가 발생했을 수 있습니다.');
}

const data = await response.json();
```

#### 2. Download Endpoint Error Handling

**Before:**
```javascript
if (response.ok) {
    // Handle successful download
} else {
    const data = await response.json();  // ❌ Fails if response is HTML
    showError(data.error || '다운로드 중 오류가 발생했습니다');
}
```

**After:**
```javascript
if (response.ok) {
    // Handle successful download
} else {
    // ✅ Check if response is JSON before parsing
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
        const data = await response.json();
        showError(data.error || '다운로드 중 오류가 발생했습니다');
    } else {
        // Server returned non-JSON response (likely HTML error page)
        showError('다운로드 중 서버 오류가 발생했습니다');
    }
}
```

## Error Message Comparison

### Before Fix
```
❌ 서버와 통신 중 오류가 발생했습니다: Unexpected token '<', "<html> <h"... is not valid JSON
```
- Exposes raw HTML fragments
- Confusing for end users
- Technical error message not suitable for users

### After Fix
```
❌ 서버와 통신 중 오류가 발생했습니다: 서버에서 예상치 못한 응답을 받았습니다. 서버 오류가 발생했을 수 있습니다.
```
- Clean, user-friendly message
- No HTML fragments exposed
- Clearly indicates server error

## Technical Details

### Content-Type Headers

- **JSON Response**: `application/json`
- **HTML Error Pages**: `text/html; charset=utf-8`

The fix checks the `Content-Type` header before attempting JSON parsing:
- If `application/json` → Parse as JSON and show detailed error
- If `text/html` or missing → Show generic server error message

### Error Flow

```
Server Error (500/404)
    ↓
Returns HTML Error Page
    ↓
Content-Type: text/html
    ↓
JavaScript checks content-type ✅
    ↓
Detects non-JSON response
    ↓
Throws user-friendly error
    ↓
"서버에서 예상치 못한 응답을 받았습니다..."
```

## Testing

1. **Valid JSON responses** - Still work correctly
2. **HTML error pages (404/500)** - Now show user-friendly messages
3. **Network errors** - Still caught by catch block
4. **JSON error responses** - Still parsed and displayed correctly

## Benefits

1. ✅ Better user experience with clear error messages
2. ✅ No exposure of technical HTML parsing errors
3. ✅ Maintains backward compatibility with JSON responses
4. ✅ Handles both `/process` and `/download` endpoints
5. ✅ Minimal code changes (surgical fix)
