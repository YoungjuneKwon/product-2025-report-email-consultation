#!/usr/bin/env python3
"""
Example script demonstrating the email processing functionality.
This can be used for testing the filtering logic without Gmail credentials.
"""

from email.message import EmailMessage
from email.utils import formatdate
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path to import main module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import EmailPair, EmailFilter, create_excel_report


def create_sample_email(subject, from_addr, to_addr, body, msg_id, in_reply_to=None, date=None):
    """Create a sample email message for testing."""
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Message-ID'] = msg_id
    msg['Date'] = formatdate(timeval=(date or datetime.now()).timestamp(), localtime=True)
    
    if in_reply_to:
        msg['In-Reply-To'] = in_reply_to
        msg['References'] = in_reply_to
    
    msg.set_content(body)
    return msg


def main():
    """Demonstrate the filtering and export functionality."""
    print("=== Email Processing Demo ===\n")
    
    # Sample email data
    professor_email = "professor@university.edu"
    
    # Create sample emails
    emails = []
    
    # Valid consultation request and response pair
    request1 = create_sample_email(
        subject="상담 요청",
        from_addr="student1@university.edu",
        to_addr=professor_email,
        body="교수님 안녕하세요. 저는 20251234 학번 김철수입니다. 상담 요청드립니다.",
        msg_id="<request1@university.edu>",
        date=datetime(2025, 1, 15, 10, 0, 0)
    )
    emails.append(request1)
    
    response1 = create_sample_email(
        subject="Re: 상담 요청",
        from_addr=professor_email,
        to_addr="student1@university.edu",
        body="네, 알겠습니다. 연구실로 오세요.",
        msg_id="<response1@university.edu>",
        in_reply_to="<request1@university.edu>",
        date=datetime(2025, 1, 15, 14, 30, 0)
    )
    emails.append(response1)
    
    # Another valid pair
    request2 = create_sample_email(
        subject="질문 있습니다",
        from_addr="student2@university.edu",
        to_addr=professor_email,
        body="교수님 안녕하세요. 저는 학번 20259876입니다. 과제 관련 질문드립니다.",
        msg_id="<request2@university.edu>",
        date=datetime(2025, 1, 16, 9, 0, 0)
    )
    emails.append(request2)
    
    response2 = create_sample_email(
        subject="Re: 질문 있습니다",
        from_addr=professor_email,
        to_addr="student2@university.edu",
        body="답변드립니다. 다음과 같이 진행하시면 됩니다.",
        msg_id="<response2@university.edu>",
        in_reply_to="<request2@university.edu>",
        date=datetime(2025, 1, 16, 15, 0, 0)
    )
    emails.append(response2)
    
    # Invalid: missing keywords
    request3 = create_sample_email(
        subject="문의",
        from_addr="student3@university.edu",
        to_addr=professor_email,
        body="학번 20251111 문의사항 있습니다.",
        msg_id="<request3@university.edu>",
        date=datetime(2025, 1, 17, 10, 0, 0)
    )
    emails.append(request3)
    
    response3 = create_sample_email(
        subject="Re: 문의",
        from_addr=professor_email,
        to_addr="student3@university.edu",
        body="답변드립니다.",
        msg_id="<response3@university.edu>",
        in_reply_to="<request3@university.edu>",
        date=datetime(2025, 1, 17, 11, 0, 0)
    )
    emails.append(response3)
    
    # Invalid: missing student ID
    request4 = create_sample_email(
        subject="상담 문의",
        from_addr="student4@university.edu",
        to_addr=professor_email,
        body="교수님 안녕하세요. 저는 김영희입니다. 상담 받고 싶습니다.",
        msg_id="<request4@university.edu>",
        date=datetime(2025, 1, 18, 10, 0, 0)
    )
    emails.append(request4)
    
    response4 = create_sample_email(
        subject="Re: 상담 문의",
        from_addr=professor_email,
        to_addr="student4@university.edu",
        body="네, 가능합니다.",
        msg_id="<response4@university.edu>",
        in_reply_to="<request4@university.edu>",
        date=datetime(2025, 1, 18, 14, 0, 0)
    )
    emails.append(response4)
    
    print(f"Created {len(emails)} sample emails")
    
    # Process emails
    filter_obj = EmailFilter(professor_email)
    
    print("\n1. Finding email pairs...")
    pairs = filter_obj.find_email_pairs(emails)
    print(f"   Found {len(pairs)} pairs")
    
    print("\n2. Filtering by keywords ['교수님', '안녕하세요', '입니다']...")
    keywords = ["교수님", "안녕하세요", "입니다"]
    pairs = filter_obj.filter_by_keywords(pairs, keywords)
    print(f"   {len(pairs)} pairs remaining")
    
    print("\n3. Filtering by student ID (8-digit number)...")
    pairs = filter_obj.filter_by_student_id(pairs)
    print(f"   {len(pairs)} pairs remaining")
    
    if pairs:
        print("\n4. Creating Excel report...")
        output_file = "example_report.xlsx"
        create_excel_report(pairs, output_file)
        print(f"   Report created: {output_file}")
        
        print("\n=== Sample Data ===")
        for i, pair in enumerate(pairs, 1):
            print(f"\nPair {i}:")
            print(f"  Date: {pair.get_date()}")
            print(f"  Time: {pair.get_start_time()} - {pair.get_end_time()}")
            print(f"  Request preview: {pair.get_request_text()[:50]}...")
            print(f"  Response preview: {pair.get_response_text()[:50]}...")
    else:
        print("\nNo valid email pairs found after filtering.")
    
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
