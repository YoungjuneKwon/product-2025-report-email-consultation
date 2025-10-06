#!/usr/bin/env python3
"""
Gmail IMAP Email Consultation Report Generator

This script fetches emails from Gmail using IMAP, filters consultation request-response pairs,
and generates an Excel report.
"""

import imaplib
import email
from email.parser import BytesParser
from email.policy import default
from email.utils import parsedate_to_datetime
import os
import sys
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EmailPair:
    """Represents a pair of original request email and its response."""
    
    def __init__(self, request_email: email.message.EmailMessage, 
                 response_email: email.message.EmailMessage):
        self.request = request_email
        self.response = response_email
    
    def get_date(self) -> str:
        """Get response email date in YYYY-MM-DD format."""
        date = parsedate_to_datetime(self.response['Date'])
        return date.strftime('%Y-%m-%d')
    
    def get_start_time(self) -> str:
        """Get response email time in HH:MM format."""
        date = parsedate_to_datetime(self.response['Date'])
        return date.strftime('%H:%M')
    
    def get_end_time(self) -> str:
        """Get response email time + 30 minutes in HH:MM format."""
        date = parsedate_to_datetime(self.response['Date'])
        end_time = date + timedelta(minutes=30)
        return end_time.strftime('%H:%M')
    
    def get_request_text(self) -> str:
        """Extract plain text from request email body."""
        return self._get_email_body(self.request)
    
    def get_response_text(self) -> str:
        """Extract plain text from response email body."""
        return self._get_email_body(self.response)
    
    def _get_email_body(self, msg: email.message.EmailMessage) -> str:
        """Extract plain text body from email message."""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                # Get text/plain parts
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            body += payload.decode(charset, errors='ignore')
                    except Exception as e:
                        logger.warning(f"Error decoding email part: {e}")
        else:
            # Simple non-multipart email
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='ignore')
            except Exception as e:
                logger.warning(f"Error decoding email: {e}")
        
        return body.strip()


class GmailIMAPClient:
    """Client for fetching emails from Gmail using IMAP."""
    
    def __init__(self, userid: str, password: str):
        self.userid = userid
        self.password = password
        self.connection = None
    
    def connect(self) -> bool:
        """Connect to Gmail IMAP server and authenticate.
        
        Returns:
            True on success, or an error message string on failure
        """
        try:
            logger.info("Connecting to Gmail IMAP server...")
            self.connection = imaplib.IMAP4_SSL('imap.gmail.com', 993)
            
            # Authenticate
            logger.info(f"Authenticating as {self.userid}...")
            self.connection.login(self.userid, self.password)
            
            logger.info("Successfully connected to Gmail")
            return True
            
        except imaplib.IMAP4.error as e:
            error_msg = str(e).lower()
            logger.error(f"Authentication failed: {e}")
            logger.error("Please check your Gmail credentials and ensure:")
            logger.error("1. 2-Step Verification is enabled")
            logger.error("2. You are using an App Password (not your regular password)")
            logger.error("3. IMAP is enabled in Gmail settings")
            
            # Return specific error type for web interface
            if 'auth' in error_msg or 'password' in error_msg or 'credential' in error_msg:
                return "AUTH_FAILED"
            return "CONNECTION_FAILED"
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return "CONNECTION_FAILED"
    
    def fetch_emails(self, start_date: datetime, end_date: datetime) -> List[email.message.EmailMessage]:
        """Fetch emails within the specified date range."""
        if not self.connection:
            logger.error("Not connected to server")
            return []
        
        try:
            # Select INBOX
            logger.info("Selecting INBOX...")
            status, messages = self.connection.select('INBOX')
            if status != 'OK':
                logger.error(f"Failed to select INBOX: {messages}")
                return []
            
            total_messages = int(messages[0])
            logger.info(f"Total messages in INBOX: {total_messages}")
            
            # Search for emails in date range using IMAP server-side filtering
            # Format dates for IMAP search (DD-Mon-YYYY)
            since_date = start_date.strftime('%d-%b-%Y')
            before_date = (end_date + timedelta(days=1)).strftime('%d-%b-%Y')
            
            logger.info(f"Searching for emails from {since_date} to {before_date}")
            search_criteria = f'(SINCE {since_date} BEFORE {before_date})'
            
            status, message_numbers = self.connection.search(None, search_criteria)
            if status != 'OK':
                logger.error(f"Search failed: {message_numbers}")
                return []
            
            # Get list of message IDs
            message_ids = message_numbers[0].split()
            num_messages = len(message_ids)
            logger.info(f"Found {num_messages} messages in date range")
            
            if num_messages == 0:
                return []
            
            emails = []
            
            # Fetch messages
            for idx, msg_id in enumerate(message_ids, 1):
                try:
                    logger.info("=" * 40)
                    logger.info(f"Processing message {idx}/{num_messages}")
                    logger.info(f"Fetching message ID: {msg_id.decode()}")
                    
                    # Fetch email
                    status, msg_data = self.connection.fetch(msg_id, '(RFC822)')
                    if status != 'OK':
                        logger.warning(f"Failed to fetch message {msg_id}: {msg_data}")
                        continue
                    
                    # Parse email
                    raw_email = msg_data[0][1]
                    logger.info(f"Downloading full message {idx}...")
                    logger.info(f"Downloaded {len(raw_email)} bytes")
                    
                    msg = BytesParser(policy=default).parsebytes(raw_email)
                    
                    # Log message details
                    from_addr = msg.get('From', 'Unknown')
                    to_addr = msg.get('To', 'Unknown')
                    subject = msg.get('Subject', 'No subject')
                    msg_id_header = msg.get('Message-ID', 'No Message-ID')
                    
                    logger.info(f"Message {idx} info:")
                    logger.info(f"  From: {from_addr}")
                    logger.info(f"  To: {to_addr}")
                    logger.info(f"  Subject: {subject}")
                    logger.info(f"  Message-ID: {msg_id_header}")
                    
                    # Log email parsing info
                    is_multipart = msg.is_multipart()
                    content_type = msg.get_content_type()
                    charset = msg.get_content_charset()
                    
                    logger.info(f"  Email parsing:")
                    logger.info(f"    Multipart: {is_multipart}")
                    logger.info(f"    Content-Type: {content_type}")
                    logger.info(f"    Charset: {charset}")
                    
                    # Check and log date
                    if 'Date' in msg:
                        msg_date = parsedate_to_datetime(msg['Date'])
                        logger.info(f"  Date: {msg_date.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
                        
                        # Double-check date is in range (IMAP search should handle this)
                        if start_date <= msg_date <= end_date:
                            logger.info(f"  ✓ Date is within range")
                            emails.append(msg)
                            logger.info(f"  ✓ Message {idx} INCLUDED in results")
                        else:
                            logger.info(f"  ✗ Date is outside range (IMAP search returned it anyway)")
                            logger.info(f"  ✗ Message {idx} EXCLUDED from results")
                    else:
                        logger.warning(f"  ⚠ No date header found - including anyway")
                        emails.append(msg)
                        logger.info(f"  ✓ Message {idx} INCLUDED in results")
                    
                    # Log progress every 50 messages
                    if idx % 50 == 0:
                        logger.info("=" * 40)
                        logger.info(f"Progress: Processed {idx}/{num_messages} messages, {len(emails)} included so far")
                        logger.info("=" * 40)
                        
                except Exception as e:
                    logger.warning(f"Error fetching message {msg_id}: {e}")
                    continue
            
            logger.info("=" * 40)
            logger.info(f"Fetched {len(emails)} emails in date range")
            logger.info("=" * 40)
            return emails
            
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return []
    
    def close(self):
        """Close the IMAP connection."""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
                logger.info("Connection closed")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")


class EmailFilter:
    """Filter emails to find consultation request-response pairs."""
    
    def __init__(self, userid: str):
        self.userid = userid
    
    def find_email_pairs(self, emails: List[email.message.EmailMessage]) -> List[EmailPair]:
        """Find pairs of original emails and their responses."""
        logger.info("=" * 40)
        logger.info("Starting email pairing process...")
        
        # Build message-ID to email mapping
        email_by_id = {}
        for msg in emails:
            msg_id = msg.get('Message-ID', '')
            if msg_id:
                email_by_id[msg_id] = msg
        
        logger.info(f"Built message ID index with {len(email_by_id)} emails")
        
        pairs = []
        
        # Find responses and match with originals
        for idx, msg in enumerate(emails, 1):
            # Check if this is a response (has In-Reply-To or References)
            in_reply_to = msg.get('In-Reply-To', '')
            references = msg.get('References', '')
            from_addr = msg.get('From', '')
            subject = msg.get('Subject', 'No subject')
            
            if in_reply_to or references:
                logger.info(f"Analyzing email {idx}/{len(emails)}: {subject}")
                logger.info(f"  From: {from_addr}")
                logger.info(f"  In-Reply-To: {in_reply_to}")
                
                # This is a response, check if sender is the configured user
                if self.userid in from_addr:
                    logger.info(f"  ✓ Response from configured user: {self.userid}")
                    
                    # Find the original message
                    original_id = in_reply_to or references.split()[0] if references else None
                    
                    if original_id and original_id in email_by_id:
                        original = email_by_id[original_id]
                        original_from = original.get('From', 'Unknown')
                        original_subject = original.get('Subject', 'No subject')
                        
                        logger.info(f"  ✓ Found original email:")
                        logger.info(f"    Original From: {original_from}")
                        logger.info(f"    Original Subject: {original_subject}")
                        
                        pair = EmailPair(original, msg)
                        pairs.append(pair)
                        logger.info(f"  ✓ Pair #{len(pairs)} created")
                    else:
                        logger.info(f"  ✗ Original email not found in current batch")
                else:
                    logger.debug(f"  ✗ Response not from configured user")
        
        logger.info("=" * 40)
        logger.info(f"Found {len(pairs)} email pairs where {self.userid} replied")
        logger.info("=" * 40)
        return pairs
    
    def filter_by_keywords(self, pairs: List[EmailPair], keywords: List[str]) -> List[EmailPair]:
        """Filter pairs where original email contains all specified keywords."""
        logger.info("=" * 40)
        logger.info(f"Starting keyword filtering with keywords: {keywords}")
        
        filtered = []
        
        for idx, pair in enumerate(pairs, 1):
            request_text = pair.get_request_text()
            from_addr = pair.request.get('From', 'Unknown')
            subject = pair.request.get('Subject', 'No subject')
            
            logger.info(f"Checking pair {idx}/{len(pairs)}")
            logger.info(f"  Subject: {subject}")
            logger.info(f"  From: {from_addr}")
            
            # Check if all keywords are present
            matches = []
            for keyword in keywords:
                if keyword in request_text:
                    matches.append(keyword)
                    logger.info(f"  ✓ Keyword '{keyword}' found")
                else:
                    logger.info(f"  ✗ Keyword '{keyword}' NOT found")
            
            if len(matches) == len(keywords):
                filtered.append(pair)
                logger.info(f"  ✓ Pair {idx} PASSED keyword filter")
            else:
                logger.info(f"  ✗ Pair {idx} FAILED keyword filter ({len(matches)}/{len(keywords)} keywords matched)")
        
        logger.info("=" * 40)
        logger.info(f"After keyword filtering: {len(filtered)} pairs")
        logger.info("=" * 40)
        return filtered


def create_excel_report(pairs: List[EmailPair], output_file: str):
    """Create Excel report from email pairs."""
    if not pairs:
        logger.warning("No email pairs to export")
        return
    
    logger.info("=" * 40)
    logger.info(f"Creating Excel report with {len(pairs)} pairs...")
    
    # Prepare data
    data = []
    for idx, pair in enumerate(pairs, 1):
        logger.info(f"Processing pair {idx}/{len(pairs)} for Excel export")
        
        date_str = pair.get_date()
        start_time = pair.get_start_time()
        end_time = pair.get_end_time()
        request_text = pair.get_request_text()
        response_text = pair.get_response_text()
        
        logger.info(f"  Date: {date_str}")
        logger.info(f"  Time: {start_time} - {end_time}")
        logger.info(f"  Request text length: {len(request_text)} chars")
        logger.info(f"  Response text length: {len(response_text)} chars")
        
        data.append({
            '상담일': date_str,
            '시작시간': start_time,
            '종료시간': end_time,
            '장소': '연구실',
            '상담요청 내용': request_text,
            '교수 답변': response_text
        })
    
    # Create DataFrame
    logger.info("Creating DataFrame...")
    df = pd.DataFrame(data)
    
    # Export to Excel
    logger.info(f"Exporting to Excel file: {output_file}")
    df.to_excel(output_file, index=False, engine='openpyxl')
    
    logger.info("=" * 40)
    logger.info(f"Excel report created: {output_file}")
    logger.info("=" * 40)


def process_emails(gmail_userid: str, gmail_password: str, start_date: datetime, end_date: datetime,
                   keywords: List[str] = None, student_id_length: int = 8) -> Tuple[List[EmailPair], str]:
    """
    Process emails and return pairs and any error message.
    
    Args:
        gmail_userid: Gmail user ID
        gmail_password: Gmail password
        start_date: Start date for email search
        end_date: End date for email search
        keywords: Optional list of keywords to filter by (default: ["교수님", "안녕하세요", "입니다"])
        student_id_length: Length of student ID to filter by (default: 8)
    
    Returns:
        Tuple of (list of EmailPair objects, error message or empty string)
    """
    if keywords is None:
        keywords = ["교수님", "안녕하세요", "입니다"]
    
    # Make end_date inclusive (end of day)
    end_date = end_date.replace(hour=23, minute=59, second=59)
    
    logger.info(f"Fetching emails from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Connect to Gmail
    client = GmailIMAPClient(gmail_userid, gmail_password)
    connect_result = client.connect()
    if connect_result is not True:
        # Return specific error message from connect method
        return [], connect_result if isinstance(connect_result, str) else "Failed to connect to Gmail. Please check credentials and ensure IMAP is enabled."
    
    try:
        # Fetch emails
        emails = client.fetch_emails(start_date, end_date)
        
        if not emails:
            return [], "No emails found in the specified date range"
        
        # Filter emails
        filter_obj = EmailFilter(gmail_userid)
        
        # Find request-response pairs
        pairs = filter_obj.find_email_pairs(emails)
        
        if not pairs:
            return [], "No email pairs found"
        
        # Filter by keywords
        pairs = filter_obj.filter_by_keywords(pairs, keywords)
        
        if not pairs:
            return [], "No emails matching keyword criteria"
        
        # Filter by student ID
        if student_id_length > 0:
            logger.info("=" * 40)
            logger.info(f"Starting student ID filtering (length: {student_id_length})")
            
            pattern = re.compile(rf'\d{{{student_id_length}}}')
            filtered = []
            for idx, pair in enumerate(pairs, 1):
                request_text = pair.get_request_text()
                from_addr = pair.request.get('From', 'Unknown')
                subject = pair.request.get('Subject', 'No subject')
                
                logger.info(f"Checking pair {idx}/{len(pairs)}")
                logger.info(f"  Subject: {subject}")
                logger.info(f"  From: {from_addr}")
                
                match = pattern.search(request_text)
                if match:
                    student_id = match.group()
                    logger.info(f"  ✓ Student ID found: {student_id}")
                    filtered.append(pair)
                    logger.info(f"  ✓ Pair {idx} PASSED student ID filter")
                else:
                    logger.info(f"  ✗ No {student_id_length}-digit student ID found")
                    logger.info(f"  ✗ Pair {idx} FAILED student ID filter")
            
            pairs = filtered
            logger.info("=" * 40)
            logger.info(f"After student ID filtering: {len(pairs)} pairs")
            logger.info("=" * 40)
        
        if not pairs:
            return [], "No emails containing student ID"
        
        logger.info(f"Successfully processed {len(pairs)} consultation records")
        return pairs, ""
        
    except Exception as e:
        logger.error(f"Error processing emails: {e}")
        return [], f"Error processing emails: {str(e)}"
    finally:
        client.close()


def main():
    """Main function."""
    # Get credentials from environment variables
    gmail_userid = os.getenv('GMAIL_USERID')
    gmail_password = os.getenv('GMAIL_PASSWORD')
    
    if not gmail_userid or not gmail_password:
        logger.error("GMAIL_USERID and GMAIL_PASSWORD environment variables must be set")
        sys.exit(1)
    
    # Get date range from command line arguments or use defaults
    if len(sys.argv) >= 3:
        try:
            start_date = datetime.strptime(sys.argv[1], '%Y-%m-%d')
            end_date = datetime.strptime(sys.argv[2], '%Y-%m-%d')
        except ValueError:
            logger.error("Date format should be YYYY-MM-DD")
            logger.error("Usage: python main_imap.py <start_date> <end_date>")
            sys.exit(1)
    else:
        # Default: last 30 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        logger.info(f"No date range specified, using last 30 days")
    
    # Process emails
    pairs, error = process_emails(gmail_userid, gmail_password, start_date, end_date)
    
    if error:
        logger.error(error)
        sys.exit(1)
    
    # Create Excel report
    output_file = f"consultation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    create_excel_report(pairs, output_file)


if __name__ == "__main__":
    main()
