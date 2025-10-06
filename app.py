#!/usr/bin/env python3
"""
Flask Web Application for Gmail Consultation Report Generator

Provides a web interface to process consultation emails and generate Excel reports.
"""

from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime
import logging
import os
import io
from typing import List
import pandas as pd

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


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/process', methods=['POST'])
def process():
    """Process the email consultation request."""
    try:
        # Get form data
        gmail_userid = request.form.get('gmail_userid', '').strip()
        gmail_password = request.form.get('gmail_password', '').strip()
        start_date_str = request.form.get('start_date', '').strip()
        end_date_str = request.form.get('end_date', '').strip()
        
        # Optional parameters
        student_id_length_str = request.form.get('student_id_length', '8').strip()
        keywords_str = request.form.get('keywords', '').strip()
        
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
        
        # Process emails
        logger.info(f"Processing emails for {gmail_userid} from {start_date_str} to {end_date_str}")
        pairs, error = process_emails(
            gmail_userid, 
            gmail_password, 
            start_date, 
            end_date,
            keywords=keywords,
            student_id_length=student_id_length
        )
        
        if error:
            logger.error(f"Error processing emails: {error}")
            return jsonify({'error': error}), 400
        
        # Convert pairs to table data
        table_data = []
        for pair in pairs:
            table_data.append({
                '상담일': pair.get_date(),
                '시작시간': pair.get_start_time(),
                '종료시간': pair.get_end_time(),
                '장소': '연구실',
                '상담요청 내용': pair.get_request_text(),
                '교수 답변': pair.get_response_text()
            })
        
        logger.info(f"Successfully processed {len(pairs)} consultation records")
        
        return jsonify({
            'success': True,
            'count': len(pairs),
            'data': table_data
        })
        
    except Exception as e:
        logger.exception(f"Unexpected error in process: {e}")
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
