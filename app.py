#!/usr/bin/env python3
"""
Flask Web Application for Gmail Consultation Report Generator

Provides a web interface to process consultation emails and generate Excel reports.
"""

from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context
from datetime import datetime
import logging
import os
import io
from typing import List, Dict
import pandas as pd
import queue
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import uuid

from main import process_emails, EmailPair

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size

# Store for streaming logs
log_queues = {}

# Store for request status tracking
# Format: {request_id: {status, session_id, created_at, updated_at, email_count, result_count, error, result_file}}
request_status = {}

# Directory to store result files
RESULTS_DIR = "results"
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)


class QueueHandler(logging.Handler):
    """Custom logging handler that puts log records into a queue."""
    
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        try:
            msg = self.format(record)
            # Check if this is a progress message and format accordingly
            if 'PROGRESS|' in msg:
                # Extract progress information
                parts = msg.split('PROGRESS|')
                if len(parts) > 1:
                    progress_data = parts[1].strip()
                    # Send both the formatted log and the progress data separately
                    self.log_queue.put(msg)
                    self.log_queue.put(f"__PROGRESS__{progress_data}")
                else:
                    self.log_queue.put(msg)
            else:
                self.log_queue.put(msg)
        except Exception:
            self.handleError(record)


def send_email_via_smtp(gmail_userid: str, gmail_password: str, to_email: str, 
                        subject: str, body: str, attachment_path: str = None) -> bool:
    """
    Send an email via Gmail SMTP.
    
    Args:
        gmail_userid: Gmail account to send from
        gmail_password: Gmail app password
        to_email: Recipient email address
        subject: Email subject
        body: Email body (HTML supported)
        attachment_path: Optional path to file to attach
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = gmail_userid
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Attach body as HTML
        msg.attach(MIMEText(body, 'html', 'utf-8'))
        
        # Attach file if provided
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                filename = os.path.basename(attachment_path)
                part.add_header('Content-Disposition', f'attachment; filename={filename}')
                msg.attach(part)
        
        # Connect to Gmail SMTP server
        logger.info(f"Connecting to Gmail SMTP server to send email to {to_email}")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_userid, gmail_password)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_start_notification(gmail_userid: str, gmail_password: str, 
                           start_date: str, end_date: str, email_count: int, request_id: str = None):
    """
    Send notification email when processing starts.
    
    Args:
        gmail_userid: Gmail account
        gmail_password: Gmail app password
        start_date: Start date string
        end_date: End date string
        email_count: Number of emails to process
        request_id: Request ID for tracking (optional)
    """
    estimated_time = email_count * 2  # 2 seconds per email
    estimated_minutes = estimated_time // 60
    estimated_seconds = estimated_time % 60
    
    request_info = ""
    if request_id:
        request_info = f"<li><strong>요청 ID:</strong> {request_id}</li>"
    
    subject = "이메일 상담 보고서 처리 시작"
    body = f"""
    <html>
    <body>
        <h2>이메일 상담 보고서 처리가 시작되었습니다</h2>
        <p>처리 정보:</p>
        <ul>
            <li><strong>기간:</strong> {start_date} ~ {end_date}</li>
            <li><strong>대상 이메일 수:</strong> {email_count}건</li>
            <li><strong>예상 완료 시간:</strong> 약 {estimated_minutes}분 {estimated_seconds}초</li>
            {request_info}
        </ul>
        <p>처리가 완료되면 결과를 이메일로 보내드리겠습니다.</p>
    </body>
    </html>
    """
    
    send_email_via_smtp(gmail_userid, gmail_password, gmail_userid, subject, body)


def send_completion_notification(gmail_userid: str, gmail_password: str, 
                                 pairs: List[EmailPair], excel_path: str, request_id: str = None):
    """
    Send notification email when processing completes with Excel attachment.
    
    Args:
        gmail_userid: Gmail account
        gmail_password: Gmail app password
        pairs: List of processed email pairs
        excel_path: Path to Excel file to attach
        request_id: Request ID for tracking (optional)
    """
    # Create HTML table from pairs
    table_rows = ""
    for idx, pair in enumerate(pairs, 1):
        table_rows += f"""
        <tr>
            <td>{idx}</td>
            <td>{pair.get_date()}</td>
            <td>{pair.get_start_time()}</td>
            <td>{pair.get_end_time()}</td>
            <td>{pair.get_student_name()}</td>
            <td>{pair.get_student_id()}</td>
            <td>{pair.get_request_subject()}</td>
        </tr>
        """
    
    request_info = ""
    if request_id:
        request_info = f"<p><strong>요청 ID:</strong> {request_id}</p>"
    
    subject = "이메일 상담 보고서 처리 완료"
    body = f"""
    <html>
    <head>
        <style>
            table {{
                border-collapse: collapse;
                width: 100%;
                margin-top: 20px;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: #4CAF50;
                color: white;
            }}
            tr:nth-child(even) {{
                background-color: #f2f2f2;
            }}
        </style>
    </head>
    <body>
        <h2>이메일 상담 보고서 처리가 완료되었습니다</h2>
        <p><strong>총 {len(pairs)}건의 상담 기록이 처리되었습니다.</strong></p>
        {request_info}
        <p>상세 결과는 첨부된 엑셀 파일을 확인해주세요.</p>
        
        <h3>처리 결과 요약</h3>
        <table>
            <tr>
                <th>번호</th>
                <th>상담일</th>
                <th>시작시간</th>
                <th>종료시간</th>
                <th>학생</th>
                <th>학번</th>
                <th>제목</th>
            </tr>
            {table_rows}
        </table>
    </body>
    </html>
    """
    
    send_email_via_smtp(gmail_userid, gmail_password, gmail_userid, subject, body, excel_path)


def process_emails_background(gmail_userid: str, gmail_password: str, 
                              start_date: datetime, end_date: datetime,
                              start_date_str: str, end_date_str: str,
                              keywords: List[str], student_id_length: int,
                              email_count: int,
                              strict_mode: bool = True,
                              session_id: str = None,
                              request_id: str = None):
    """
    Process emails in background thread and send notification emails.
    
    Args:
        gmail_userid: Gmail account
        gmail_password: Gmail app password
        start_date: Start date object
        end_date: End date object
        start_date_str: Start date string for display
        end_date_str: End date string for display
        keywords: Keywords to filter
        student_id_length: Student ID length
        email_count: Number of emails to process (for notification)
        strict_mode: Whether to use strict student ID filtering
        session_id: Optional session ID for logging
        request_id: Optional request ID for tracking
    """
    queue_handler = None
    
    try:
        # Update request status to processing
        if request_id and request_id in request_status:
            request_status[request_id]['status'] = 'processing'
            request_status[request_id]['updated_at'] = datetime.now().isoformat()
        
        # Set up logging to queue if session_id is provided
        if session_id:
            # Ensure queue exists for this session
            log_queue = log_queues.get(session_id, None)

            if log_queue is None:
                log_queue = queue.Queue()
                log_queues[session_id] = log_queue

            queue_handler = QueueHandler(log_queue)
            queue_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            
            # Add handler to root logger and main module logger
            root_logger = logging.getLogger()
            main_logger = logging.getLogger('main')
            app_logger = logging.getLogger(__name__)
            
            # Set the level to INFO to ensure all messages are captured
            queue_handler.setLevel(logging.INFO)
            
            root_logger.addHandler(queue_handler)
            main_logger.addHandler(queue_handler)
            app_logger.addHandler(queue_handler)
            
            # Send initial message to stream
            log_queue.put("백그라운드 처리가 시작되었습니다...")
        
        # Calculate email count if not provided (email_count = 0)
        if email_count == 0:
            logger.info("이메일 수를 계산하고 있습니다...")
            try:
                from main import GmailIMAPClient
                logger.info("Gmail IMAP 클라이언트를 초기화하고 있습니다...")
                client = GmailIMAPClient(gmail_userid, gmail_password)
                logger.info("Gmail 서버에 연결 중입니다...")
                connect_result = client.connect()
                if connect_result is not True:
                    logger.error(f"Gmail 연결 실패: {connect_result}")
                    if request_id and request_id in request_status:
                        request_status[request_id]['status'] = 'failed'
                        request_status[request_id]['error'] = f'Gmail 연결 실패: {connect_result}'
                        request_status[request_id]['updated_at'] = datetime.now().isoformat()
                    return
                logger.info("Gmail에 연결되었습니다. 이메일을 검색하고 있습니다...")
                logger.info(f"검색 기간: {start_date_str} ~ {end_date_str}")
                
                emails = client.fetch_emails(start_date, end_date)
                email_count = len(emails)
                logger.info(f"이메일 검색이 완료되었습니다. 총 {email_count}건의 이메일을 찾았습니다")
                client.close()
                logger.info("Gmail 연결을 종료했습니다")
                
                logger.info(f"처리할 이메일 {email_count}건을 찾았습니다")
                
                # Update request status with email count
                if request_id and request_id in request_status:
                    request_status[request_id]['email_count'] = email_count
                    request_status[request_id]['updated_at'] = datetime.now().isoformat()
                    
            except Exception as e:
                logger.exception(f"이메일 수 계산 중 오류: {e}")
                if request_id and request_id in request_status:
                    request_status[request_id]['status'] = 'failed'
                    request_status[request_id]['error'] = f'이메일 수 계산 실패: {str(e)}'
                    request_status[request_id]['updated_at'] = datetime.now().isoformat()
                return
        
        # Send start notification email
        logger.info("시작 알림 이메일을 전송하고 있습니다...")
        send_start_notification(gmail_userid, gmail_password, start_date_str, end_date_str, email_count, request_id)
        logger.info("시작 알림 이메일이 전송되었습니다")
        
        # Process emails
        logger.info("이메일 처리를 시작합니다: %s ~ %s", start_date_str, end_date_str)
        logger.info("엄격 모드: %s", '활성화' if strict_mode else '비활성화')
        pairs, error = process_emails(
            gmail_userid,
            gmail_password,
            start_date,
            end_date,
            keywords=keywords,
            student_id_length=student_id_length,
            strict_mode=strict_mode
        )
        
        if error:
            logger.error(f"이메일 처리 중 오류가 발생했습니다: {error}")
            # Update request status to failed
            if request_id and request_id in request_status:
                request_status[request_id]['status'] = 'failed'
                request_status[request_id]['error'] = str(error)
                request_status[request_id]['updated_at'] = datetime.now().isoformat()
            return
        
        if not pairs:
            logger.warning("상담 기록을 찾을 수 없습니다")
            # Update request status to completed (but with no results)
            if request_id and request_id in request_status:
                request_status[request_id]['status'] = 'completed'
                request_status[request_id]['result_count'] = 0
                request_status[request_id]['updated_at'] = datetime.now().isoformat()
            return
        
        # Create Excel file
        output_file = f"consultation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        result_file_path = os.path.join(RESULTS_DIR, f"{request_id}_{output_file}" if request_id else output_file)
        logger.info(f"엑셀 보고서를 생성하고 있습니다: {result_file_path}")
        
        # Prepare data for Excel
        logger.info("데이터를 정리하고 있습니다...")
        data = []
        for pair in pairs:
            data.append({
                '상담일': pair.get_date(),
                '시작시간': pair.get_start_time(),
                '종료시간': pair.get_end_time(),
                '장소': '연구실',
                '학생': pair.get_student_name(),
                '학번': pair.get_student_id(),
                '발신자 이메일 주소': pair.get_request_from(),
                '수신자 이메일 주소': pair.get_request_to(),
                '메일의 제목': pair.get_request_subject(),
                '상담요청 내용': pair.get_request_text(),
                '교수 답변': pair.get_response_text()
            })
        
        # Create DataFrame and save to Excel
        logger.info("엑셀 파일을 저장하고 있습니다...")
        df = pd.DataFrame(data)
        df.to_excel(result_file_path, index=False, engine='openpyxl')
        logger.info(f"엑셀 보고서가 생성되었습니다: {result_file_path}")
        
        # Send completion notification email with attachment
        logger.info("완료 알림 이메일을 전송하고 있습니다...")
        send_completion_notification(gmail_userid, gmail_password, pairs, result_file_path, request_id)
        logger.info("완료 알림 이메일이 전송되었습니다")
        
        # Update request status to completed with result file path
        if request_id and request_id in request_status:
            request_status[request_id]['status'] = 'completed'
            request_status[request_id]['result_count'] = len(pairs)
            request_status[request_id]['result_file'] = result_file_path
            request_status[request_id]['updated_at'] = datetime.now().isoformat()
        
        logger.info(f"모든 처리가 완료되었습니다. 총 {len(pairs)}건의 상담 기록을 처리했습니다")
        
        # Note: Don't clean up the Excel file anymore since we want to keep it for download
        
    except Exception as e:
        logger.exception(f"Error in background processing: {e}")
        # Update request status to failed
        if request_id and request_id in request_status:
            request_status[request_id]['status'] = 'failed'
            request_status[request_id]['error'] = str(e)
            request_status[request_id]['updated_at'] = datetime.now().isoformat()
    
    finally:
        # Remove queue handler
        if queue_handler:
            root_logger = logging.getLogger()
            main_logger = logging.getLogger('main')
            app_logger = logging.getLogger(__name__)
            
            try:
                root_logger.removeHandler(queue_handler)
                main_logger.removeHandler(queue_handler)
                app_logger.removeHandler(queue_handler)
            except:
                pass
        
        # Send end signal to stream
        if session_id and session_id in log_queues:
            log_queues[session_id].put(None)


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/stream/<session_id>')
def stream(session_id):
    """Stream logs to the client using Server-Sent Events."""
    
    def generate():        
        # Send initial connection message
        yield f"data: [연결됨] 로그 스트림이 시작되었습니다 (세션: {session_id}, {list(log_queues.keys())})\n\n"
        
        try:
            while True:
                # Wait for log messages
                try:
                    log_queue = log_queues[session_id]
                    if not log_queue:
                        yield f"data: [오류] 로그 큐를 찾을 수 없습니다. log_queues keys: {list(log_queues.keys())}, session_id: {session_id}\n\n"
                        break
                    msg = log_queue.get(timeout=10)
                    if msg is None:  # Sentinel to end the stream
                        yield f"data: [종료] 로그 스트림이 종료되었습니다\n\n"
                        break
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    # Send a heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
        finally:
          pass

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/process', methods=['POST'])
def process():
    """Process the email consultation request in background."""
    try:
        # Get form data
        gmail_userid = request.form.get('gmail_userid', '').strip()
        gmail_password = request.form.get('gmail_password', '').strip()
        start_date_str = request.form.get('start_date', '').strip()
        end_date_str = request.form.get('end_date', '').strip()
        session_id = request.form.get('session_id', '')
        
        # Optional parameters
        student_id_length_str = request.form.get('student_id_length', '8').strip()
        keywords_str = request.form.get('keywords', '').strip()
        strict_mode_str = request.form.get('strict_mode', 'true').strip().lower()
        
        # Validate required fields
        if not gmail_userid:
            return jsonify({'error': '이메일 주소를 입력해주세요'}), 400
        if not gmail_password:
            return jsonify({'error': '비밀번호를 입력해주세요'}), 400
        if not start_date_str:
            return jsonify({'error': '시작일을 선택해주세요'}), 400
        if not end_date_str:
            return jsonify({'error': '종료일을 선택해주세요'}), 400
        
        # Parse dates
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError as e:
            logger.error(f"Date parsing error: {e}")
            return jsonify({'error': '날짜 형식이 올바르지 않습니다'}), 400
        
        # Parse student ID length
        try:
            student_id_length = int(student_id_length_str) if student_id_length_str else 8
            if student_id_length < 0:
                student_id_length = 0
        except ValueError:
            student_id_length = 8
        
        # Parse keywords
        keywords = None
        if keywords_str:
            keywords = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]

        # Set up logging to queue if session_id is provided
        queue_handler = None
        if session_id:
            # Ensure queue exists for this session
            if session_id not in log_queues:
                log_queue = queue.Queue()
                log_queues[session_id] = log_queue
            else:
                log_queue = log_queues[session_id]
            
            queue_handler = QueueHandler(log_queue)
            queue_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            
            # Add handler to root logger and main module logger
            root_logger = logging.getLogger()
            main_logger = logging.getLogger('main')
            root_logger.addHandler(queue_handler)
            main_logger.addHandler(queue_handler)

        # Parse strict mode (default: True)
        strict_mode = strict_mode_str in ('true', '1', 'on', 'yes')

        # Quick Gmail authentication check only (for fast validation)
        logger.info("Gmail 인증을 확인하고 있습니다...")
        
        try:
            from main import GmailIMAPClient
            client = GmailIMAPClient(gmail_userid, gmail_password)
            connect_result = client.connect()
            
            if connect_result is not True:
                # Authentication failed
                if connect_result == "AUTH_FAILED":
                    return jsonify({
                        'error': connect_result,
                        'errorType': 'AUTH_FAILED',
                        'message': 'Gmail 인증에 실패했습니다. 앱 비밀번호를 확인해주세요.'
                    }), 401
                elif connect_result == "CONNECTION_FAILED":
                    return jsonify({
                        'error': connect_result,
                        'errorType': 'AUTH_FAILED',
                        'message': 'Gmail 연결에 실패했습니다. 인증 정보를 확인해주세요.'
                    }), 401
                return jsonify({'error': '연결에 실패했습니다'}), 400
            
            # Close connection immediately after authentication
            client.close()
            logger.info("Gmail 인증이 성공했습니다")
            
        except Exception as e:
            logger.exception(f"인증 확인 중 오류: {e}")
            return jsonify({'error': f'인증 확인 중 오류가 발생했습니다: {str(e)}'}), 500
        
        finally:
            # Remove queue handler if it was added
            if queue_handler:
                root_logger = logging.getLogger()
                main_logger = logging.getLogger('main')
                try:
                    root_logger.removeHandler(queue_handler)
                    main_logger.removeHandler(queue_handler)
                except:
                    pass
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Store initial request status (email_count will be updated in background)
        request_status[request_id] = {
            'status': 'pending',
            'session_id': session_id,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'email_count': 0,  # Will be updated in background
            'result_count': 0,
            'error': None
        }
        
        # Start background processing (email_count = 0 to trigger calculation in background)
        thread = threading.Thread(
            target=process_emails_background,
            args=(gmail_userid, gmail_password, start_date, end_date, 
                  start_date_str, end_date_str, keywords, student_id_length, 
                  0, strict_mode, session_id, request_id),  # email_count = 0
            daemon=True
        )
        thread.start()
        logger.info("Background processing started")
        
        # Return immediate response with request ID
        return jsonify({
            'success': True,
            'message': '처리가 시작되었습니다. 이메일 수 계산 중입니다.',
            'background': True,
            'request_id': request_id
        })
        
    except Exception as e:
        logger.exception(f"Unexpected error in process: {e}")
        
        # Send end signal to stream
        session_id = request.form.get('session_id', '')
        if session_id and session_id in log_queues:
            log_queues[session_id].put(None)
        
        return jsonify({'error': f'서버 오류가 발생했습니다: {str(e)}'}), 500


@app.route('/download', methods=['POST'])
def download():
    """Generate and download Excel file."""
    try:
        # Get table data from request
        data = request.json.get('data', [])
        
        if not data:
            return jsonify({'error': '다운로드할 데이터가 없습니다'}), 400
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='상담기록')
        output.seek(0)
        
        # Generate filename
        filename = f"consultation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        logger.info(f"Generating Excel file: {filename}")
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.exception(f"Error generating Excel file: {e}")
        return jsonify({'error': f'엑셀 파일 생성 중 오류가 발생했습니다: {str(e)}'}), 500


@app.route('/api/request/<request_id>', methods=['GET'])
def get_request_status(request_id):
    """Get status of a specific request by ID."""
    if request_id not in request_status:
        return jsonify({'error': '요청 ID를 찾을 수 없습니다'}), 404
    
    return jsonify({
        'request_id': request_id,
        **request_status[request_id]
    })


@app.route('/api/request/<request_id>/download', methods=['GET'])
def download_result_file(request_id):
    """Download the result Excel file for a completed request."""
    if request_id not in request_status:
        return jsonify({'error': '요청 ID를 찾을 수 없습니다'}), 404
    
    request_info = request_status[request_id]
    
    # Check if request is completed
    if request_info['status'] != 'completed':
        return jsonify({'error': '아직 처리가 완료되지 않았습니다'}), 400
    
    # Check if result file exists
    if 'result_file' not in request_info or not request_info['result_file']:
        return jsonify({'error': '결과 파일이 없습니다'}), 404
    
    result_file_path = request_info['result_file']
    
    # Check if file exists on disk
    if not os.path.exists(result_file_path):
        return jsonify({'error': '결과 파일을 찾을 수 없습니다'}), 404
    
    try:
        # Generate a user-friendly filename
        filename = f"consultation_report_{request_id[:8]}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        logger.info(f"Downloading result file for request {request_id}: {result_file_path}")
        
        return send_file(
            result_file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    except Exception as e:
        logger.exception(f"Error downloading file for request {request_id}: {e}")
        return jsonify({'error': f'파일 다운로드 중 오류가 발생했습니다: {str(e)}'}), 500


@app.route('/api/requests', methods=['GET'])
def list_requests():
    """List all tracked requests."""
    requests_list = [
        {'request_id': req_id, **req_data}
        for req_id, req_data in request_status.items()
    ]
    # Sort by created_at descending (newest first)
    requests_list.sort(key=lambda x: x['created_at'], reverse=True)
    return jsonify({'requests': requests_list})


@app.route('/status')
def status_page():
    """Render the status monitoring page."""
    return render_template('status.html')


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.exception(f"Internal server error: {error}")
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
