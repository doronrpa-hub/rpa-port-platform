"""
RCB Email Processor
===================
Smart email processing that only checks TODAY's emails,
avoids duplicates, and sends proper acknowledgments and reports.

Author: RCB System
Version: 1.0
"""

import imaplib
import email as email_lib
from email.header import decode_header
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import re


class RCBEmailProcessor:
    """
    Smart email processor for RCB system.
    
    Features:
    - Only checks TODAY's emails (not all)
    - Compares against processed IDs
    - Sends ACK immediately
    - Sends classification report when done
    - Handles errors gracefully
    """
    
    def __init__(
        self,
        email_addr: str,
        email_pass: str,
        imap_server: str = "imap.gmail.com",
        days_back: int = 1,
    ):
        self.email_addr = email_addr
        self.email_pass = email_pass
        self.imap_server = imap_server
        self.days_back = days_back
        self.mail = None
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to email server"""
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server)
            self.mail.login(self.email_addr, self.email_pass)
            self.mail.select("inbox")
            self.connected = True
            print("✅ Gmail connected")
            return True
        except Exception as e:
            print(f"❌ Gmail connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from email server"""
        if self.mail:
            try:
                self.mail.logout()
                print("✅ Gmail disconnected")
            except:
                pass
        self.connected = False
    
    def get_todays_emails(self) -> List[Tuple[str, Any]]:
        """
        Get only emails from today (or last N days).
        Returns list of (email_id, message) tuples.
        """
        if not self.connected:
            return []
        
        # Calculate date for SINCE filter
        since_date = (datetime.utcnow() - timedelta(days=self.days_back)).strftime("%d-%b-%Y")
        
        # Search only recent emails
        try:
            status, messages = self.mail.search(None, f'SINCE {since_date}')
            email_ids = messages[0].split() if messages[0] else []
            print(f"📧 Found {len(email_ids)} emails since {since_date}")
            
            results = []
            for eid in email_ids:
                try:
                    status, msg_data = self.mail.fetch(eid, "(RFC822)")
                    msg = email_lib.message_from_bytes(msg_data[0][1])
                    results.append((eid, msg))
                except Exception as e:
                    print(f"⚠️ Error fetching email {eid}: {e}")
            
            return results
        except Exception as e:
            print(f"❌ Error searching emails: {e}")
            return []
    
    def get_safe_id(self, msg: Any) -> str:
        """Generate a safe document ID from message"""
        msg_id = msg.get("Message-ID", str(id(msg)))
        safe_id = re.sub(r'[/\\\.\[\]\*~]', '_', str(msg_id))[:100]
        return safe_id
    
    def decode_header_value(self, value: str) -> str:
        """Decode email header value"""
        if not value:
            return ""
        try:
            decoded_parts = decode_header(value)
            result = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    result += part.decode(encoding or 'utf-8', errors='replace')
                else:
                    result += part
            return result
        except:
            return str(value)
    
    def extract_body(self, msg: Any) -> str:
        """Extract text body from email message"""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode(charset, errors='replace')
                    except:
                        pass
        else:
            try:
                charset = msg.get_content_charset() or 'utf-8'
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode(charset, errors='replace')
            except:
                pass
        
        return body[:10000]  # Limit size
    
    def extract_attachments(self, msg: Any) -> List[Dict]:
        """Extract attachment info from email"""
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = part.get("Content-Disposition", "")
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        filename = self.decode_header_value(filename)
                        attachments.append({
                            "filename": filename,
                            "size": len(part.get_payload(decode=True) or b""),
                            "type": part.get_content_type(),
                        })
        
        return attachments
    
    def process_emails(
        self,
        processed_ids: set,
        on_new_email: callable = None,
        on_complete: callable = None,
    ) -> Dict[str, Any]:
        """
        Process new emails.
        
        Args:
            processed_ids: Set of already processed email IDs
            on_new_email: Callback for each new email (email_data) -> None
            on_complete: Callback when all done (count) -> None
            
        Returns:
            Dict with processing results
        """
        results = {
            "checked": 0,
            "new": 0,
            "processed": 0,
            "errors": 0,
            "emails": [],
        }
        
        print(f"📋 Already processed: {len(processed_ids)} emails")
        
        emails = self.get_todays_emails()
        results["checked"] = len(emails)
        
        for eid, msg in emails:
            safe_id = self.get_safe_id(msg)
            
            if safe_id in processed_ids:
                continue
            
            results["new"] += 1
            
            try:
                # Extract email data
                email_data = {
                    "id": safe_id,
                    "subject": self.decode_header_value(msg.get("Subject", "")),
                    "from": self.decode_header_value(msg.get("From", "")),
                    "date": msg.get("Date", ""),
                    "body": self.extract_body(msg),
                    "attachments": self.extract_attachments(msg),
                }
                
                results["emails"].append(email_data)
                
                if on_new_email:
                    on_new_email(email_data)
                
                results["processed"] += 1
                
            except Exception as e:
                print(f"❌ Error processing email: {e}")
                results["errors"] += 1
        
        if on_complete:
            on_complete(results["processed"])
        
        return results


def create_processor(
    email_addr: str,
    email_pass: str,
    days_back: int = 1,
) -> RCBEmailProcessor:
    """Factory function to create email processor"""
    return RCBEmailProcessor(email_addr, email_pass, days_back=days_back)


def build_ack_email(
    sender_name: str,
    attachments: List[Dict],
    subject: str,
    agent_name: str = "מערכת RCB",
) -> str:
    """Build acknowledgment email in Hebrew"""
    lines = [
        f"שלום {sender_name},",
        "",
        "✅ קיבלנו את המסמכים שלך!",
        "",
        f"📌 נושא: {subject}",
        "",
    ]
    
    if attachments:
        lines.append("📎 קבצים שהתקבלו:")
        for att in attachments:
            lines.append(f"  • {att.get('filename', 'קובץ')}")
        lines.append("")
    
    lines.extend([
        "⏳ אנחנו מעבדים את המסמכים ונשלח דוח סיווג בהקדם.",
        "",
        "בברכה,",
        agent_name,
        "ר.פ.א - פורט בע\"מ",
    ])
    
    return "\n".join(lines)


def build_report_email(
    sender_name: str,
    invoice_score: int,
    missing_fields: List[str],
    classifications: List[Dict],
    agent_name: str = "מערכת RCB",
) -> str:
    """Build classification report email in Hebrew"""
    lines = [
        f"שלום {sender_name},",
        "",
        "📋 דוח סיווג מכס",
        "=" * 30,
        "",
    ]
    
    # Invoice validation
    if invoice_score >= 70:
        lines.append(f"✅ חשבון תקין (ציון: {invoice_score}/100)")
    else:
        lines.append(f"⚠️ חשבון לא שלם (ציון: {invoice_score}/100)")
        if missing_fields:
            lines.append("")
            lines.append("📋 שדות חסרים:")
            for field in missing_fields:
                lines.append(f"  ☐ {field}")
    
    lines.append("")
    
    # Classifications
    if classifications:
        lines.append("🏷️ סיווג מכס:")
        for cls in classifications:
            lines.append(f"  • {cls.get('product', 'מוצר')}: {cls.get('hs_code', 'לא סווג')}")
            if cls.get('duty_rate'):
                lines.append(f"    מכס: {cls.get('duty_rate')}")
    
    lines.extend([
        "",
        "לשאלות נוספות - השב למייל זה.",
        "",
        "בברכה,",
        agent_name,
        "ר.פ.א - פורט בע\"מ",
    ])
    
    return "\n".join(lines)


# Test
if __name__ == "__main__":
    print("=" * 60)
    print("RCB Email Processor - Test")
    print("=" * 60)
    
    # Test ACK email
    print("\n📧 Test 1: ACK Email")
    print("-" * 40)
    ack = build_ack_email(
        sender_name="דורון",
        attachments=[
            {"filename": "invoice.pdf"},
            {"filename": "packing_list.xlsx"},
        ],
        subject="מסמכים למשלוח 12345",
    )
    print(ack)
    
    # Test Report email
    print("\n" + "=" * 60)
    print("📧 Test 2: Report Email")
    print("-" * 40)
    report = build_report_email(
        sender_name="דורון",
        invoice_score=85,
        missing_fields=["תעודת מקור"],
        classifications=[
            {"product": "מחשב נייד", "hs_code": "8471.30", "duty_rate": "0%"},
            {"product": "כבלים", "hs_code": "8544.42", "duty_rate": "6%"},
        ],
    )
    print(report)
    
    print("\n" + "=" * 60)
    print("✅ Tests complete!")
