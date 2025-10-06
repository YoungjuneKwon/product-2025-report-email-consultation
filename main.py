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
            
            # Select inbox
            logger.info("Selecting INBOX...")
            status, messages = self.connection.select('INBOX')
            if status != 'OK':
                logger.error("Failed to select INBOX")
                return "CONNECTION_FAILED"
            
            num_messages = int(messages[0].decode())
            logger.info(f"Successfully connected to Gmail IMAP")
            logger.info(f"Total messages in INBOX: {num_messages}")
            
            return True
            
        except imaplib.IMAP4.error as e:
            error_msg = str(e).lower()
            logger.error(f"IMAP authentication failed: {e}")
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
        
        # Ensure start_date and end_date have timezone info
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        
        try:
            # Format dates for IMAP search (DD-MMM-YYYY format)
            since_date = start_date.strftime('%d-%b-%Y')
            before_date = (end_date + timedelta(days=1)).strftime('%d-%b-%Y')
            
            logger.info(f"Searching for emails from {since_date} to {before_date}")
            
            # Search for emails in date range
            search_criteria = f'(SINCE {since_date} BEFORE {before_date})'
            logger.info(f"IMAP search criteria: {search_criteria}")
            
            status, message_numbers = self.connection.search(None, search_criteria)
            
            if status != 'OK':
                logger.error("Failed to search emails")
                return []
            
            # Get list of message IDs
            msg_ids = message_numbers[0].split()
            num_messages = len(msg_ids)
            logger.info(f"Found {num_messages} messages in date range")
            
            if num_messages == 0:
                return []
            
            emails = []
            
            # Fetch messages
            for idx, msg_id in enumerate(msg_ids, 1):
                try:
                    logger.info("=" * 40)
                    logger.info(f"Processing message {idx}/{num_messages}")
                    
                    # First fetch headers only for quick date check
                    logger.info(f"Fetching headers for message {idx}...")
                    status, msg_data = self.connection.fetch(msg_id, '(BODY.PEEK[HEADER])')
                    
                    if status != 'OK':
                        logger.warning(f"Failed to fetch headers for message {msg_id}")
                        continue
                    
                    # Parse headers
                    header_data = msg_data[0][1]
                    header_msg = BytesParser(policy=default).parsebytes(header_data)
                    
                    # Log message info
                    from_addr = header_msg.get('From', 'Unknown')
                    to_addr = header_msg.get('To', 'Unknown')
                    subject = header_msg.get('Subject', 'No Subject')
                    msg_date_str = header_msg.get('Date', '')
                    message_id = header_msg.get('Message-ID', 'Unknown')
                    
                    logger.info(f"Message {idx} info:")
                    logger.info(f"  From: {from_addr}")
                    logger.info(f"  To: {to_addr}")
                    logger.info(f"  Subject: {subject}")
                    logger.info(f"  Message-ID: {message_id}")
                    logger.info(f"  Date: {msg_date_str}")
                    
                    # Parse and check date
                    if msg_date_str:
                        msg_date = parsedate_to_datetime(msg_date_str)
                        
                        # Ensure msg_date has timezone info
                        if msg_date.tzinfo is None:
                            msg_date = msg_date.replace(tzinfo=timezone.utc)
                        
                        # Log date check
                        if start_date <= msg_date <= end_date:
                            logger.info(f"  ✓ Date is within range - fetching full message")
                        else:
                            logger.info(f"  ✗ Date is outside range - skipping")
                            continue
                    else:
                        logger.warning(f"  ⚠ No date header found - fetching anyway")
                    
                    # Fetch full message
                    logger.info(f"Downloading full message {idx}...")
                    status, msg_data = self.connection.fetch(msg_id, '(RFC822)')
                    
                    if status != 'OK':
                        logger.warning(f"Failed to fetch message {msg_id}")
                        continue
                    
                    # Parse full email
                    raw_email = msg_data[0][1]
                    msg = BytesParser(policy=default).parsebytes(raw_email)
                    
                    # Log parsing details
                    logger.info(f"  Email parsing:")
                    logger.info(f"    Multipart: {msg.is_multipart()}")
                    logger.info(f"    Content-Type: {msg.get_content_type()}")
                    logger.info(f"    Charset: {msg.get_content_charset()}")
                    
                    emails.append(msg)
                    logger.info(f"  ✓ Message {idx} INCLUDED in results")
                    
                    # Log progress every 50 messages
                    if idx % 50 == 0:
                        logger.info(f"\n=== Progress: {idx}/{num_messages} messages processed ({len(emails)} included) ===\n")
                        
                except Exception as e:
                    logger.warning(f"Error fetching message {msg_id}: {e}")
                    continue
            
            logger.info("=" * 40)
            logger.info(f"Fetched {len(emails)} emails in date range (out of {num_messages} total)")
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
        logger.info("\n" + "=" * 40)
        logger.info("Starting email pairing process...")
        logger.info("=" * 40)
        
        # Build message-ID to email mapping
        email_by_id = {}
        for msg in emails:
            msg_id = msg.get('Message-ID', '')
            if msg_id:
                email_by_id[msg_id] = msg
        
        logger.info(f"Built message-ID index with {len(email_by_id)} entries")
        
        pairs = []
        
        # Find responses and match with originals
        for idx, msg in enumerate(emails, 1):
            # Check if this is a response (has In-Reply-To or References)
            in_reply_to = msg.get('In-Reply-To', '')
            references = msg.get('References', '')
            from_addr = msg.get('From', '')
            subject = msg.get('Subject', 'No Subject')
            
            logger.info(f"\nAnalyzing email {idx}/{len(emails)}:")
            logger.info(f"  Subject: {subject}")
            logger.info(f"  From: {from_addr}")
            logger.info(f"  In-Reply-To: {in_reply_to or 'None'}")
            logger.info(f"  References: {references or 'None'}")
            
            if in_reply_to or references:
                # This is a response
                logger.info(f"  → This is a RESPONSE email")
                
                # Check if sender is the configured user
                if self.userid in from_addr:
                    logger.info(f"  ✓ Response is from configured user ({self.userid})")
                    
                    # Find the original message
                    original_id = in_reply_to or references.split()[0] if references else None
                    
                    if original_id and original_id in email_by_id:
                        original = email_by_id[original_id]
                        original_from = original.get('From', 'Unknown')
                        original_subject = original.get('Subject', 'No Subject')
                        
                        logger.info(f"  ✓ Found original email:")
                        logger.info(f"    Original From: {original_from}")
                        logger.info(f"    Original Subject: {original_subject}")
                        
                        pair = EmailPair(original, msg)
                        pairs.append(pair)
                        logger.info(f"  ✓ PAIR CREATED (Total pairs: {len(pairs)})")
                    else:
                        logger.info(f"  ✗ Original email not found in mailbox")
                else:
                    logger.info(f"  ✗ Response is not from configured user")
            else:
                logger.info(f"  → This is an ORIGINAL email (not a response)")
        
        logger.info("\n" + "=" * 40)
        logger.info(f"Found {len(pairs)} email pairs where {self.userid} replied")
        logger.info("=" * 40 + "\n")
        return pairs
    
    def filter_by_keywords(self, pairs: List[EmailPair], keywords: List[str]) -> List[EmailPair]:
        """Filter pairs where original email contains all specified keywords."""
        logger.info("\n" + "=" * 40)
        logger.info(f"Filtering by keywords: {keywords}")
        logger.info("=" * 40)
        
        filtered = []
        
        for idx, pair in enumerate(pairs, 1):
            request_text = pair.get_request_text()
            subject = pair.request.get('Subject', 'No Subject')
            
            logger.info(f"\nChecking pair {idx}/{len(pairs)}:")
            logger.info(f"  Subject: {subject}")
            
            # Check if all keywords are present
            found_keywords = []
            missing_keywords = []
            
            for keyword in keywords:
                if keyword in request_text:
                    found_keywords.append(keyword)
                else:
                    missing_keywords.append(keyword)
            
            logger.info(f"  Found keywords: {found_keywords}")
            if missing_keywords:
                logger.info(f"  Missing keywords: {missing_keywords}")
                logger.info(f"  ✗ EXCLUDED - Not all keywords present")
            else:
                logger.info(f"  ✓ INCLUDED - All keywords present")
                filtered.append(pair)
        
        logger.info("\n" + "=" * 40)
        logger.info(f"After keyword filtering: {len(filtered)}/{len(pairs)} pairs")
        logger.info("=" * 40 + "\n")
        return filtered
    
    def filter_by_student_id(self, pairs: List[EmailPair]) -> List[EmailPair]:
        """Filter pairs where original email contains an 8-digit number (student ID)."""
        pattern = re.compile(r'\d{8}')
        
        logger.info("\n" + "=" * 40)
        logger.info("Filtering by student ID (8-digit pattern)")
        logger.info("=" * 40)
        
        filtered = []
        
        for idx, pair in enumerate(pairs, 1):
            request_text = pair.get_request_text()
            subject = pair.request.get('Subject', 'No Subject')
            
            logger.info(f"\nChecking pair {idx}/{len(pairs)}:")
            logger.info(f"  Subject: {subject}")
            
            match = pattern.search(request_text)
            if match:
                logger.info(f"  ✓ Found student ID: {match.group()}")
                logger.info(f"  ✓ INCLUDED")
                filtered.append(pair)
            else:
                logger.info(f"  ✗ No student ID found")
                logger.info(f"  ✗ EXCLUDED")
        
        logger.info("\n" + "=" * 40)
        logger.info(f"After student ID filtering: {len(filtered)}/{len(pairs)} pairs")
        logger.info("=" * 40 + "\n")
        return filtered


def create_excel_report(pairs: List[EmailPair], output_file: str):
    """Create Excel report from email pairs."""
    if not pairs:
        logger.warning("No email pairs to export")
        return
    
    logger.info("\n" + "=" * 40)
    logger.info("Creating Excel report...")
    logger.info("=" * 40)
    
    # Prepare data
    data = []
    for idx, pair in enumerate(pairs, 1):
        logger.info(f"\nProcessing pair {idx}/{len(pairs)} for Excel:")
        logger.info(f"  Date: {pair.get_date()}")
        logger.info(f"  Start Time: {pair.get_start_time()}")
        logger.info(f"  End Time: {pair.get_end_time()}")
        logger.info(f"  Request length: {len(pair.get_request_text())} characters")
        logger.info(f"  Response length: {len(pair.get_response_text())} characters")
        
        data.append({
            '상담일': pair.get_date(),
            '시작시간': pair.get_start_time(),
            '종료시간': pair.get_end_time(),
            '장소': '연구실',
            '상담요청 내용': pair.get_request_text(),
            '교수 답변': pair.get_response_text()
        })
    
    # Create DataFrame
    logger.info(f"\nCreating DataFrame with {len(data)} rows...")
    df = pd.DataFrame(data)
    
    # Export to Excel
    logger.info(f"Exporting to Excel file: {output_file}")
    df.to_excel(output_file, index=False, engine='openpyxl')
    
    logger.info("=" * 40)
    logger.info(f"Excel report created: {output_file}")
    logger.info("=" * 40 + "\n")


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
    client = GmailIMAPClient(gmail_userid, gmail_password)
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