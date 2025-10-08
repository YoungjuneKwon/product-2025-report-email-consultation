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
import argparse
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
        """Get response email time in HH:MM format with adjustments.
        - Minutes rounded down to 5-minute intervals
        - Times before 09:00 converted to 09:05
        """
        date = parsedate_to_datetime(self.response['Date'])
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        
        hour = date.hour
        minute = date.minute
        
        # Round down minutes to 5-minute intervals (0, 5, 10, 15, ..., 55)
        minute = (minute // 5) * 5
        
        # If time is before 09:00, set to 09:05
        if hour < 9:
            hour = 9
            minute = 5
        
        return f"{hour:02d}:{minute:02d}"
    
    def get_end_time(self) -> str:
        """Get start time + 30 minutes in HH:MM format."""
        # Parse start time to add 30 minutes
        start_time = self.get_start_time()
        hour, minute = map(int, start_time.split(':'))
        
        # Add 30 minutes
        minute += 30
        if minute >= 60:
            hour += 1
            minute -= 60
        
        # Handle day overflow (24:00 -> 00:00)
        if hour >= 24:
            hour -= 24
        
        return f"{hour:02d}:{minute:02d}"
    
    def get_request_text(self) -> str:
        """Extract plain text from request email body, remove HTML tags, limit to 490 chars."""
        text = self._get_email_body(self.request)
        text = self._strip_html_tags(text)
        return text[:490] if len(text) > 490 else text
    
    def get_response_text(self) -> str:
        """Extract plain text from response email body, limit to 490 chars."""
        text = self._get_email_body(self.response)
        return text[:490] if len(text) > 490 else text
    
    def get_student_id(self) -> str:
        """Extract student ID from request email body."""
        request_text = self.get_request_text()
        
        # Look for 8-digit student ID pattern
        # Common patterns: "학번 12345678", "12345678 학번", "저는 12345678입니다"
        pattern = re.compile(r'\d{8}')
        match = pattern.search(request_text)
        
        if match:
            return match.group()
        return ""
    
    def get_student_name(self) -> str:
        """Extract student name from request email body."""
        request_text = self.get_request_text()
        
        # Look for Korean name patterns
        # Common patterns: "저는 김철수입니다", "학번 12345678 김철수"
        # Korean names are typically 2-4 characters
        
        # Pattern 1: "저는 <name>입니다" or "저는 <name>이라고 합니다"
        # But NOT "저는 학번 ..." which is not a name
        pattern1 = re.compile(r'저는\s*([가-힣]{2,4})(?:입니다|이라고|라고|입니|이에요)')
        match = pattern1.search(request_text)
        if match:
            name = match.group(1)
            # Filter out common words that are not names
            if name not in ['학번', '이름', '학생', '교수님']:
                return name
        
        # Pattern 2: "학번 <student_id> <name>" followed by common verb endings
        # This pattern looks for names that come after student ID
        # E.g., "학번 12345678 김철수입니다"
        pattern2 = re.compile(r'\d{8}\s+학번\s+([가-힣]{2,4})(?:입니다|이라고|라고|입니|이에요)')
        match = pattern2.search(request_text)
        if match:
            name = match.group(1)
            if name and name not in ['학번', '이름', '학생', '문의사항', '과제', '질문']:
                return name
        
        # Pattern 3: "<student_id> 학번 <name>"
        # E.g., "20251234 학번 박지훈입니다"
        pattern3 = re.compile(r'학번\s+\d{8}\s+([가-힣]{2,4})(?:입니다|이라고|라고|입니|이에요)')
        match = pattern3.search(request_text)
        if match:
            name = match.group(1)
            if name and name not in ['학번', '이름', '학생', '문의사항', '과제', '질문']:
                return name
        
        return ""
    def get_request_from(self) -> str:
        """Get sender email address from request email."""
        return self.request.get('From', '')
    
    def get_request_to(self) -> str:
        """Get recipient email address from request email."""
        return self.request.get('To', '')
    
    def get_request_subject(self) -> str:
        """Get subject from request email."""
        return self.request.get('Subject', '')
    
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
    
    def _strip_html_tags(self, text: str) -> str:
        """Remove HTML tags from text."""
        # Remove HTML tags using regex
        # This pattern matches anything between < and >
        clean_text = re.sub(r'<[^>]+>', '', text)
        return clean_text.strip()


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
            
            logger.info("Successfully connected to Gmail IMAP")
            
            # List available folders for debugging
            self._list_folders()
            
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
    
    def _list_folders(self):
        """List all available IMAP folders for debugging."""
        try:
            logger.info("\n" + "=" * 50)
            logger.info("Available IMAP folders:")
            logger.info("=" * 50)
            
            status, folder_list = self.connection.list()
            if status == 'OK':
                for folder in folder_list:
                    folder_str = folder.decode('utf-8') if isinstance(folder, bytes) else str(folder)
                    logger.info(f"  {folder_str}")
            else:
                logger.warning("Failed to list folders")
                
            logger.info("=" * 50 + "\n")
            
        except Exception as e:
            logger.warning(f"Error listing folders: {e}")
    
    def fetch_emails(self, start_date: datetime, end_date: datetime) -> List[email.message.EmailMessage]:
        """Fetch emails from both INBOX and Sent Mail within the specified date range."""
        if not self.connection:
            logger.error("Not connected to server")
            return []
        
        # Ensure start_date and end_date have timezone info
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        
        all_emails = []
        
        # Find actual folder names
        inbox_folder = self._find_inbox_folder()
        sent_folder = self._find_sent_folder()
        
        folders = [
            (inbox_folder, '받은 메일함'),
            (sent_folder, '보낸 메일함')
        ]
        
        for folder_name, korean_name in folders:
            if not folder_name:
                logger.warning(f"Could not find {korean_name} folder")
                continue
                
            try:
                logger.info(f"\n{'='*50}")
                logger.info(f"Searching {korean_name} ({folder_name})")
                logger.info('='*50)
                
                # Select the folder
                status, messages = self.connection.select(folder_name)
                if status != 'OK':
                    logger.error(f"Failed to select {folder_name}")
                    continue
                
                num_messages = int(messages[0].decode())
                logger.info(f"Total messages in {korean_name}: {num_messages}")
                
                # Format dates for IMAP search (DD-MMM-YYYY format)
                since_date = start_date.strftime('%d-%b-%Y')
                before_date = (end_date + timedelta(days=1)).strftime('%d-%b-%Y')
                
                logger.info(f"Searching for emails from {since_date} to {before_date}")
                
                # Search for emails in date range
                search_criteria = f'(SINCE {since_date} BEFORE {before_date})'
                logger.info(f"IMAP search criteria: {search_criteria}")
                
                status, message_numbers = self.connection.search(None, search_criteria)
                
                if status != 'OK':
                    logger.error(f"Failed to search emails in {folder_name}")
                    continue
                
                # Get list of message IDs
                msg_ids = message_numbers[0].split()
                num_found = len(msg_ids)
                logger.info(f"Found {num_found} messages in {korean_name} within date range")
                
                if num_found == 0:
                    continue
                
                # Fetch messages from this folder
                folder_emails = self._fetch_messages_from_folder(msg_ids, start_date, end_date, korean_name)
                all_emails.extend(folder_emails)
                
            except Exception as e:
                logger.error(f"Error searching {folder_name}: {e}")
                continue
        
        logger.info(f"\n{'='*50}")
        logger.info(f"Total emails fetched from all folders: {len(all_emails)}")
        logger.info('='*50)
        return all_emails
    
    def _find_inbox_folder(self) -> str:
        """Find the INBOX folder name."""
        return "INBOX"  # INBOX is standard
    
    def _find_sent_folder(self) -> str:
        """Find the Sent Mail folder name by checking common variations."""
        try:
            status, folder_list = self.connection.list()
            if status != 'OK':
                logger.warning("Failed to list folders for sent mail detection")
                return '[Gmail]/Sent Mail'  # Default fallback
            
            # Convert folder list to strings
            folders = []
            for folder in folder_list:
                folder_str = folder.decode('utf-8') if isinstance(folder, bytes) else str(folder)
                folders.append(folder_str)
            
            # Common sent mail folder patterns (prioritized)
            sent_patterns = [
                '"[Gmail]/Sent Mail"',
                '[Gmail]/Sent Mail',
                '"[Gmail]/보낸편지함"',
                '[Gmail]/보낸편지함',
                '"Sent"',
                'Sent',
                '"Sent Mail"',
                'Sent Mail',
                '"[Gmail]/Sent"',
                '[Gmail]/Sent'
            ]
            
            logger.info("Searching for Sent Mail folder...")
            for pattern in sent_patterns:
                for folder in folders:
                    # Extract folder name from IMAP response (format: '(\\HasNoChildren) "/" "FolderName"')
                    if pattern in folder:
                        # Extract the actual folder name from the IMAP response
                        parts = folder.split('"')
                        if len(parts) >= 3:
                            actual_folder_name = parts[-2]  # Usually the last quoted part
                            logger.info(f"Found Sent Mail folder: {actual_folder_name}")
                            return actual_folder_name
                        else:
                            # If no quotes, try to extract from the pattern
                            logger.info(f"Found Sent Mail folder: {pattern}")
                            return pattern.strip('"')
            
            logger.warning("Could not find Sent Mail folder, using default")
            logger.info("Available folders:")
            for folder in folders[:10]:  # Show first 10 folders
                logger.info(f"  {folder}")
            
            return '[Gmail]/Sent Mail'  # Default fallback
            
        except Exception as e:
            logger.error(f"Error finding sent folder: {e}")
            return '[Gmail]/Sent Mail'  # Default fallback
    
    def _fetch_messages_from_folder(self, msg_ids: List[bytes], start_date: datetime, 
                                   end_date: datetime, folder_name: str) -> List[email.message.EmailMessage]:
        """Fetch messages from a specific folder."""
        emails = []
        num_messages = len(msg_ids)
        
        # Log initial progress information
        logger.info(f"PROGRESS|TOTAL|{num_messages}")
        
        # Fetch messages
        for idx, msg_id in enumerate(msg_ids, 1):
            try:
                logger.info("=" * 40)
                logger.info(f"Processing {folder_name} message {idx}/{num_messages}")
                logger.info(f"PROGRESS|CURRENT|{idx}|{num_messages}")
                
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
                logger.info(f"  Folder: {folder_name}")
                
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
                
                # Add folder information to the email message
                msg.add_header('X-Folder-Name', folder_name)
                
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
        logger.info(f"Fetched {len(emails)} emails from {folder_name} (out of {num_messages} total)")
        return emails
    
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
        """Find pairs of original emails and their responses by analyzing both inbox and sent mail."""
        logger.info("\n" + "=" * 40)
        logger.info("Starting enhanced email pairing process...")
        logger.info("=" * 40)
        
        # Separate emails by folder
        inbox_emails = []
        sent_emails = []
        
        for msg in emails:
            folder_name = msg.get('X-Folder-Name', '')
            if 'Sent' in folder_name or '보낸' in folder_name:
                sent_emails.append(msg)
            else:
                inbox_emails.append(msg)
        
        logger.info(f"Separated emails: {len(inbox_emails)} from inbox, {len(sent_emails)} from sent folder")
        
        # Build message-ID to email mapping for both folders
        all_emails_by_id = {}
        inbox_by_id = {}
        sent_by_id = {}
        
        # Build subject-based mapping for additional matching
        inbox_by_subject = {}
        sent_by_subject = {}
        
        for msg in emails:
            msg_id = msg.get('Message-ID', '')
            subject = msg.get('Subject', '').strip()
            
            # Normalize subject for matching (remove Re:, Fw:, etc.)
            normalized_subject = self._normalize_subject(subject)
            
            if msg_id:
                all_emails_by_id[msg_id] = msg
                
                folder_name = msg.get('X-Folder-Name', '')
                if 'Sent' in folder_name or '보낸' in folder_name:
                    sent_by_id[msg_id] = msg
                    if normalized_subject:
                        if normalized_subject not in sent_by_subject:
                            sent_by_subject[normalized_subject] = []
                        sent_by_subject[normalized_subject].append(msg)
                else:
                    inbox_by_id[msg_id] = msg
                    if normalized_subject:
                        if normalized_subject not in inbox_by_subject:
                            inbox_by_subject[normalized_subject] = []
                        inbox_by_subject[normalized_subject].append(msg)
        
        logger.info(f"Built message-ID indexes: {len(inbox_by_id)} inbox, {len(sent_by_id)} sent")
        logger.info(f"Built subject indexes: {len(inbox_by_subject)} inbox subjects, {len(sent_by_subject)} sent subjects")
        
        pairs = []
        
        # Strategy 1: Find responses in sent folder that reply to inbox emails
        logger.info("\n--- Strategy 1: Finding responses from user to received emails ---")
        for idx, sent_msg in enumerate(sent_emails, 1):
            in_reply_to = sent_msg.get('In-Reply-To', '')
            references = sent_msg.get('References', '')
            from_addr = sent_msg.get('From', '')
            subject = sent_msg.get('Subject', 'No Subject')
            
            logger.info(f"\nAnalyzing sent email {idx}/{len(sent_emails)}:")
            logger.info(f"  Subject: {subject}")
            logger.info(f"  From: {from_addr}")
            logger.info(f"  In-Reply-To: {in_reply_to or 'None'}")
            
            # Check if sender is the configured user
            if self.userid in from_addr:
                original = None
                match_method = ""
                
                # Method 1: Try Message-ID based matching first
                if in_reply_to and in_reply_to in inbox_by_id:
                    original = inbox_by_id[in_reply_to]
                    match_method = "Message-ID (In-Reply-To)"
                elif references:
                    # Try to find original in references
                    ref_ids = references.split()
                    for ref_id in ref_ids:
                        if ref_id in inbox_by_id:
                            original = inbox_by_id[ref_id]
                            match_method = "Message-ID (References)"
                            break
                
                # Method 2: If Message-ID matching failed, try subject-based matching
                if not original:
                    normalized_subject = self._normalize_subject(subject)
                    if normalized_subject and self._is_reply_subject(subject):
                        logger.info(f"  Trying subject-based matching for: {normalized_subject}")
                        
                        if normalized_subject in inbox_by_subject:
                            # Find the most recent original email with this subject
                            candidates = inbox_by_subject[normalized_subject]
                            sent_date = parsedate_to_datetime(sent_msg.get('Date', ''))
                            
                            best_candidate = None
                            min_time_diff = None
                            
                            for candidate in candidates:
                                candidate_date = parsedate_to_datetime(candidate.get('Date', ''))
                                if candidate_date and sent_date and candidate_date < sent_date:
                                    time_diff = (sent_date - candidate_date).total_seconds()
                                    if min_time_diff is None or time_diff < min_time_diff:
                                        min_time_diff = time_diff
                                        best_candidate = candidate
                            
                            if best_candidate:
                                original = best_candidate
                                match_method = "Subject-based"
                                logger.info(f"  Found original via subject matching (time diff: {min_time_diff/3600:.1f} hours)")
                
                if original:
                    original_from = original.get('From', 'Unknown')
                    original_subject = original.get('Subject', 'No Subject')
                    
                    logger.info(f"  ✓ Found original email via {match_method}:")
                    logger.info(f"    Original From: {original_from}")
                    logger.info(f"    Original Subject: {original_subject}")
                    
                    # Check if original sender is the configured user (GMAIL_USERID)
                    if self.userid in original_from:
                        logger.info(f"  ✗ EXCLUDED - Original sender is GMAIL_USERID ({self.userid})")
                    else:
                        pair = EmailPair(original, sent_msg)
                        pairs.append(pair)
                        logger.info(f"  ✓ PAIR CREATED (Total pairs: {len(pairs)})")
                else:
                    logger.info(f"  ✗ Original email not found (tried both Message-ID and subject matching)")
            else:
                logger.info(f"  ✗ Not from configured user")
        
        # Strategy 2: Find responses in inbox that are replies to sent emails
        logger.info("\n--- Strategy 2: Finding responses to user's sent emails ---")
        for idx, inbox_msg in enumerate(inbox_emails, 1):
            in_reply_to = inbox_msg.get('In-Reply-To', '')
            references = inbox_msg.get('References', '')
            from_addr = inbox_msg.get('From', '')
            to_addr = inbox_msg.get('To', '')
            subject = inbox_msg.get('Subject', 'No Subject')
            
            logger.info(f"\nAnalyzing inbox email {idx}/{len(inbox_emails)}:")
            logger.info(f"  Subject: {subject}")
            logger.info(f"  From: {from_addr}")
            logger.info(f"  To: {to_addr}")
            logger.info(f"  In-Reply-To: {in_reply_to or 'None'}")
            
            # Check if this is a response to user's email
            if self.userid in to_addr and (in_reply_to or references or self._is_reply_subject(subject)):
                original = None
                match_method = ""
                
                # Method 1: Try Message-ID based matching first
                if in_reply_to and in_reply_to in sent_by_id:
                    original = sent_by_id[in_reply_to]
                    match_method = "Message-ID (In-Reply-To)"
                elif references:
                    # Try to find original in references
                    ref_ids = references.split()
                    for ref_id in ref_ids:
                        if ref_id in sent_by_id:
                            original = sent_by_id[ref_id]
                            match_method = "Message-ID (References)"
                            break
                
                # Method 2: If Message-ID matching failed, try subject-based matching
                if not original:
                    normalized_subject = self._normalize_subject(subject)
                    if normalized_subject and self._is_reply_subject(subject):
                        logger.info(f"  Trying subject-based matching for: {normalized_subject}")
                        
                        if normalized_subject in sent_by_subject:
                            # Find the most recent original email with this subject
                            candidates = sent_by_subject[normalized_subject]
                            inbox_date = parsedate_to_datetime(inbox_msg.get('Date', ''))
                            
                            best_candidate = None
                            min_time_diff = None
                            
                            for candidate in candidates:
                                candidate_date = parsedate_to_datetime(candidate.get('Date', ''))
                                if candidate_date and inbox_date and candidate_date < inbox_date:
                                    time_diff = (inbox_date - candidate_date).total_seconds()
                                    if min_time_diff is None or time_diff < min_time_diff:
                                        min_time_diff = time_diff
                                        best_candidate = candidate
                            
                            if best_candidate:
                                original = best_candidate
                                match_method = "Subject-based"
                                logger.info(f"  Found original via subject matching (time diff: {min_time_diff/3600:.1f} hours)")
                
                if original:
                    original_to = original.get('To', 'Unknown')
                    original_from = original.get('From', 'Unknown')
                    original_subject = original.get('Subject', 'No Subject')
                    
                    logger.info(f"  ✓ Found original email via {match_method}:")
                    logger.info(f"    Original From: {original_from}")
                    logger.info(f"    Original To: {original_to}")
                    logger.info(f"    Original Subject: {original_subject}")
                    
                    # Check if original sender is the configured user (GMAIL_USERID)
                    if self.userid in original_from:
                        logger.info(f"  ✗ EXCLUDED - Original sender is GMAIL_USERID ({self.userid})")
                    else:
                        # In this case, the "request" is the sent email and "response" is the inbox email
                        pair = EmailPair(original, inbox_msg)
                        pairs.append(pair)
                        logger.info(f"  ✓ PAIR CREATED (Total pairs: {len(pairs)})")
                else:
                    logger.info(f"  ✗ Original email not found (tried both Message-ID and subject matching)")
            else:
                logger.info(f"  ✗ Not addressed to configured user or no reply indicators")
        
        # Remove duplicates based on message IDs
        unique_pairs = []
        seen_combinations = set()
        
        for pair in pairs:
            request_id = pair.request.get('Message-ID', '')
            response_id = pair.response.get('Message-ID', '')
            combination = (request_id, response_id)
            
            if combination not in seen_combinations:
                unique_pairs.append(pair)
                seen_combinations.add(combination)
            else:
                logger.info(f"Removed duplicate pair: {request_id} -> {response_id}")
        
        logger.info("\n" + "=" * 40)
        logger.info(f"Found {len(unique_pairs)} unique email pairs (removed {len(pairs) - len(unique_pairs)} duplicates)")
        logger.info("=" * 40 + "\n")
        return unique_pairs
    
    def _normalize_subject(self, subject: str) -> str:
        """Normalize email subject by removing reply/forward prefixes."""
        if not subject:
            return ""
        
        # Remove common reply/forward prefixes (case-insensitive)
        prefixes = [
            'Re:', 'RE:', 'Fwd:', 'FWD:', 'Fw:', 'FW:',
            '답변:', '답장:', '전달:', 'Re :', 'RE :', 
            '[External]', '[EXTERNAL]', '[외부]'
        ]
        
        normalized = subject.strip()
        
        # Keep removing prefixes until no more are found
        changed = True
        while changed:
            changed = False
            for prefix in prefixes:
                if normalized.lower().startswith(prefix.lower()):
                    normalized = normalized[len(prefix):].strip()
                    changed = True
                    break
        
        return normalized
    
    def _is_reply_subject(self, subject: str) -> bool:
        """Check if subject indicates this is a reply email."""
        if not subject:
            return False
        
        subject_lower = subject.lower().strip()
        
        # Check for common reply prefixes
        reply_indicators = [
            're:', 're :', '답변:', '답장:', 
            'reply:', 'response:', 'regarding:'
        ]
        
        for indicator in reply_indicators:
            if subject_lower.startswith(indicator):
                return True
        
        return False
    
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
        logger.info(f"  From: {pair.get_request_from()}")
        logger.info(f"  To: {pair.get_request_to()}")
        logger.info(f"  Subject: {pair.get_request_subject()}")
        logger.info(f"  Request length: {len(pair.get_request_text())} characters")
        logger.info(f"  Response length: {len(pair.get_response_text())} characters")
        
        data.append({
            '학번': pair.get_student_id(),
            '성명': pair.get_student_name(),
            '상담형태': 3,
            '상담일': pair.get_date(),
            '상담시작시간': pair.get_start_time(),
            '상담종료시간': pair.get_end_time(),
            '상담유형': 'CF01',
            '장소': '연구실',
            '학생상담신청내용': pair.get_request_text(),
            '교수답변내용': pair.get_response_text(),
            '공개여부': 'N'
        })
    
    # Create DataFrame
    logger.info(f"\nCreating DataFrame with {len(data)} rows...")
    df = pd.DataFrame(data)
    
    # Ensure student ID and name are treated as strings (not numeric)
    # Replace empty strings with actual empty strings for display
    if '학번' in df.columns:
        df['학번'] = df['학번'].fillna('')
    if '성명' in df.columns:
        df['성명'] = df['성명'].fillna('')
    
    # Export to Excel
    logger.info(f"Exporting to Excel file: {output_file}")
    df.to_excel(output_file, index=False, engine='openpyxl')
    
    logger.info("=" * 40)
    logger.info(f"Excel report created: {output_file}")
    logger.info("=" * 40 + "\n")


def process_emails(gmail_userid: str, gmail_password: str, start_date: datetime, end_date: datetime,
                   keywords: List[str] = None, student_id_length: int = 8, strict_mode: bool = True) -> Tuple[List[EmailPair], str]:
    """
    Process emails and return pairs and any error message.
    
    Args:
        gmail_userid: Gmail user ID
        gmail_password: Gmail password
        start_date: Start date for email search
        end_date: End date for email search
        keywords: Optional list of keywords to filter by (default: ["교수님", "안녕하세요", "입니다"])
        student_id_length: Length of student ID to filter by (default: 8)
        strict_mode: When True, only process emails with student ID in subject or body (default: True)
    
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
                request_subject = pair.request.get('Subject', '')
                
                # In strict mode, check both subject and body
                if strict_mode:
                    if pattern.search(request_subject) or pattern.search(request_text):
                        filtered.append(pair)
                else:
                    # Non-strict mode: only check body (legacy behavior)
                    if pattern.search(request_text):
                        filtered.append(pair)
            pairs = filtered
            logger.info(f"After student ID filtering (strict_mode={strict_mode}): {len(pairs)} pairs")
        
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
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Gmail IMAP Email Consultation Report Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process emails from the last 30 days with strict mode (default)
  python main.py
  
  # Process emails for a specific date range with strict mode
  python main.py 2025-01-01 2025-01-31
  
  # Process emails without strict mode (legacy behavior)
  python main.py 2025-01-01 2025-01-31 --no-strict
        """
    )
    parser.add_argument('start_date', nargs='?', help='Start date (YYYY-MM-DD format)')
    parser.add_argument('end_date', nargs='?', help='End date (YYYY-MM-DD format)')
    parser.add_argument('--no-strict', action='store_true', 
                       help='Disable strict mode (only check student ID in body, not subject)')
    
    args = parser.parse_args()
    
    # Get credentials from environment variables
    gmail_userid = os.getenv('GMAIL_USERID')
    gmail_password = os.getenv('GMAIL_PASSWORD')
    
    if not gmail_userid or not gmail_password:
        logger.error("GMAIL_USERID and GMAIL_PASSWORD environment variables must be set")
        sys.exit(1)
    
    # Get date range from command line arguments or use defaults
    if args.start_date and args.end_date:
        try:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        except ValueError:
            logger.error("Date format should be YYYY-MM-DD")
            logger.error("Usage: python main.py <start_date> <end_date> [--no-strict]")
            sys.exit(1)
    else:
        # Default: last 30 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        logger.info(f"No date range specified, using last 30 days")
    
    # Determine strict mode (default is True)
    strict_mode = not args.no_strict
    logger.info(f"Strict mode: {'enabled' if strict_mode else 'disabled'}")
    
    # Process emails
    pairs, error = process_emails(gmail_userid, gmail_password, start_date, end_date, 
                                  strict_mode=strict_mode)
    
    if error:
        logger.error(error)
        sys.exit(1)
    
    # Create Excel report
    output_file = f"consultation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    create_excel_report(pairs, output_file)


if __name__ == "__main__":
    main()