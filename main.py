#!/usr/bin/env python3
"""
Gmail POP3 Email Consultation Report Generator

This script fetches emails from Gmail using POP3, filters consultation request-response pairs,
and generates an Excel report.
"""

import poplib
import email
from email.parser import BytesParser
from email.policy import default
from email.utils import parsedate_to_datetime
import os
import sys
import re
import logging
from datetime import datetime, timedelta, timezone
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
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.strftime('%Y-%m-%d')
    
    def get_start_time(self) -> str:
        """Get response email time in HH:MM format."""
        date = parsedate_to_datetime(self.response['Date'])
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.strftime('%H:%M')
    
    def get_end_time(self) -> str:
        """Get response email time + 30 minutes in HH:MM format."""
        date = parsedate_to_datetime(self.response['Date'])
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
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


class GmailPOP3Client:
    """Client for fetching emails from Gmail using POP3."""
    
    def __init__(self, userid: str, password: str):
        self.userid = userid
        self.password = password
        self.connection = None
    
    def connect(self) -> bool:
        """Connect to Gmail POP3 server and authenticate.
        
        Returns:
            True on success, or an error message string on failure
        """
        try:
            logger.info("Connecting to Gmail POP3 server...")
            self.connection = poplib.POP3_SSL('pop.gmail.com', 995)
            
            # Authenticate
            logger.info(f"Authenticating as {self.userid}...")
            self.connection.user(self.userid)
            self.connection.pass_(self.password)
            
            logger.info("Successfully connected to Gmail")
            return True
            
        except poplib.error_proto as e:
            error_msg = str(e).lower()
            logger.error(f"Authentication failed: {e}")
            logger.error("Please check your Gmail credentials and ensure:")
            logger.error("1. 2-Step Verification is enabled")
            logger.error("2. You are using an App Password (not your regular password)")
            logger.error("3. POP is enabled in Gmail settings")
            
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
        
        # Ensure start_date and end_date have timezone info
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        
        try:
            # Get number of messages
            num_messages = len(self.connection.list()[1])
            logger.info(f"Total messages in mailbox: {num_messages}")
            
            emails = []
            
            # Fetch all messages (POP3 doesn't support server-side date filtering)
            for i in range(1, num_messages + 1):
                try:
                    # Fetch message
                    response, lines, octets = self.connection.retr(i)
                    
                    # Parse email
                    msg_data = b'\r\n'.join(lines)
                    msg = BytesParser(policy=default).parsebytes(msg_data)
                    
                    # Check date
                    if 'Date' in msg:
                        msg_date = parsedate_to_datetime(msg['Date'])
                        
                        # Ensure msg_date has timezone info
                        if msg_date.tzinfo is None:
                            msg_date = msg_date.replace(tzinfo=timezone.utc)
                        
                        # Filter by date range
                        if start_date <= msg_date <= end_date:
                            emails.append(msg)
                    
                    # Log progress every 100 messages
                    if i % 100 == 0:
                        logger.info(f"Processed {i}/{num_messages} messages...")
                        
                except Exception as e:
                    logger.warning(f"Error fetching message {i}: {e}")
                    continue
            
            logger.info(f"Fetched {len(emails)} emails in date range")
            return emails
            
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return []
    
    def close(self):
        """Close the POP3 connection."""
        if self.connection:
            try:
                self.connection.quit()
                logger.info("Connection closed")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")


class EmailFilter:
    """Filter emails to find consultation request-response pairs."""
    
    def __init__(self, userid: str):
        self.userid = userid
    
    def find_email_pairs(self, emails: List[email.message.EmailMessage]) -> List[EmailPair]:
        """Find pairs of original emails and their responses."""
        # Build message-ID to email mapping
        email_by_id = {}
        for msg in emails:
            msg_id = msg.get('Message-ID', '')
            if msg_id:
                email_by_id[msg_id] = msg
        
        pairs = []
        
        # Find responses and match with originals
        for msg in emails:
            # Check if this is a response (has In-Reply-To or References)
            in_reply_to = msg.get('In-Reply-To', '')
            references = msg.get('References', '')
            
            if in_reply_to or references:
                # This is a response, check if sender is the configured user
                from_addr = msg.get('From', '')
                
                if self.userid in from_addr:
                    # Find the original message
                    original_id = in_reply_to or references.split()[0] if references else None
                    
                    if original_id and original_id in email_by_id:
                        original = email_by_id[original_id]
                        pair = EmailPair(original, msg)
                        pairs.append(pair)
        
        logger.info(f"Found {len(pairs)} email pairs where {self.userid} replied")
        return pairs
    
    def filter_by_keywords(self, pairs: List[EmailPair], keywords: List[str]) -> List[EmailPair]:
        """Filter pairs where original email contains all specified keywords."""
        filtered = []
        
        for pair in pairs:
            request_text = pair.get_request_text()
            
            # Check if all keywords are present
            if all(keyword in request_text for keyword in keywords):
                filtered.append(pair)
        
        logger.info(f"After keyword filtering: {len(filtered)} pairs")
        return filtered
    
    def filter_by_student_id(self, pairs: List[EmailPair]) -> List[EmailPair]:
        """Filter pairs where original email contains an 8-digit number (student ID)."""
        pattern = re.compile(r'\d{8}')
        filtered = []
        
        for pair in pairs:
            request_text = pair.get_request_text()
            
            if pattern.search(request_text):
                filtered.append(pair)
        
        logger.info(f"After student ID filtering: {len(filtered)} pairs")
        return filtered


def create_excel_report(pairs: List[EmailPair], output_file: str):
    """Create Excel report from email pairs."""
    if not pairs:
        logger.warning("No email pairs to export")
        return
    
    # Prepare data
    data = []
    for pair in pairs:
        data.append({
            '상담일': pair.get_date(),
            '시작시간': pair.get_start_time(),
            '종료시간': pair.get_end_time(),
            '장소': '연구실',
            '상담요청 내용': pair.get_request_text(),
            '교수 답변': pair.get_response_text()
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Export to Excel
    df.to_excel(output_file, index=False, engine='openpyxl')
    logger.info(f"Excel report created: {output_file}")


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
    
    # Make end_date inclusive (end of day) and ensure timezone info
    end_date = end_date.replace(hour=23, minute=59, second=59)
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)
    
    logger.info(f"Fetching emails from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Connect to Gmail
    client = GmailPOP3Client(gmail_userid, gmail_password)
    connect_result = client.connect()
    if connect_result is not True:
        # Return specific error message from connect method
        return [], connect_result if isinstance(connect_result, str) else "Failed to connect to Gmail. Please check credentials and ensure POP is enabled."
    
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
            pattern = re.compile(rf'\d{{{student_id_length}}}')
            filtered = []
            for pair in pairs:
                request_text = pair.get_request_text()
                if pattern.search(request_text):
                    filtered.append(pair)
            pairs = filtered
            logger.info(f"After student ID filtering: {len(pairs)} pairs")
        
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
            logger.error("Usage: python main.py <start_date> <end_date>")
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