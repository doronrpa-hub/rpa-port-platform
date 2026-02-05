import re

# Read current main.py
with open('main.py', 'r') as f:
    content = f.read()

# Fix 1: Update build_rcb_reply function signature to include subject
old_sig = 'def build_rcb_reply(sender_name, attachments, is_first_email=False, include_joke=False):'
new_sig = 'def build_rcb_reply(sender_name, attachments, subject="", is_first_email=False, include_joke=False):'
content = content.replace(old_sig, new_sig)

# Fix 2: Update the call to build_rcb_reply to pass subject
old_call = '''reply_body = build_rcb_reply(
                sender_name=from_name,
                attachments=attachments,
                is_first_email=is_first_email,
                include_joke=is_first_email
            )'''
new_call = '''reply_body = build_rcb_reply(
                sender_name=from_name,
                attachments=attachments,
                subject=subject,
                is_first_email=is_first_email,
                include_joke=is_first_email
            )'''
content = content.replace(old_call, new_call)

# Fix 3: Update build_rcb_reply body to show subject
old_body_start = '''<p>תודה על פנייתך! קיבלתי את המייל שלך ואני מתחילה לעבור על המסמכים.</p>
    """
    
    if attachments:'''

new_body_start = '''<p>תודה על פנייתך! קיבלתי את המסמכים שלך ואני מתחילה לעבור עליהם.</p>
    """
    
    # Show subject
    if subject:
        html += f'<p>📋 <strong>נושא:</strong> {subject}</p>'
    
    if attachments:'''
content = content.replace(old_body_start, new_body_start)

# Fix 4: Update signature with logo
old_sig_block = '''            ר.פ.א - פורט בע"מ | סוכנת מכס ממוחשבת<br>
            מייל זה נשלח אוטומטית. לשאלות: rcb@rpa-port.co.il
        </p>
    </div>
    """
    
    return html'''

new_sig_block = '''</p>
                </td>
            </tr>
        </table>
        <p style="color: #aaa; font-size: 10pt; margin-top: 10px;">
            הודעה זו נשלחה אוטומטית. לשאלות או בירורים - פשוט השיבו למייל זה.
        </p>
    </div>
    """
    
    return html'''

# Actually let's replace the whole signature section more carefully
old_signature = '''        <hr style="border: none; border-top: 1px solid #ccc; margin: 20px 0;">
        <p style="color: #888; font-size: 12px;">
            🤖 <strong>RCB - Robot Customs Broker</strong><br>
            ר.פ.א - פורט בע"מ | סוכנת מכס ממוחשבת<br>
            מייל זה נשלח אוטומטית. לשאלות: rcb@rpa-port.co.il
        </p>
    </div>
    """
    
    return html'''

new_signature = '''        <hr style="border: none; border-top: 1px solid #ccc; margin: 20px 0;">
        <table dir="rtl" style="font-family: Arial, sans-serif; font-size: 12pt;">
            <tr>
                <td style="padding-left: 15px; vertical-align: top;">
                    <img src="https://rpa-port-customs.web.app/rcb-logo.png" 
                         alt="RCB" 
                         style="width: 60px; height: 60px; border-radius: 50%;">
                </td>
                <td style="vertical-align: top;">
                    <p style="margin: 0;">
                        <strong style="color: #2c5aa0;">🤖 RCB - Robot Customs Broker</strong><br>
                        <span style="color: #666;">ר.פ.א - פורט בע״מ | סוכנת מכס ממוחשבת</span><br>
                        <span style="color: #888;">
                            📧 <a href="mailto:rcb@rpa-port.co.il" style="color: #2c5aa0;">rcb@rpa-port.co.il</a>
                        </span>
                    </p>
                </td>
            </tr>
        </table>
        <p style="color: #aaa; font-size: 10pt; margin-top: 10px;">
            הודעה זו נשלחה אוטומטית. לשאלות או בירורים - פשוט השיבו למייל זה.
        </p>
    </div>
    """
    
    return html'''

content = content.replace(old_signature, new_signature)

# Write back
with open('main.py', 'w') as f:
    f.write(content)

print("✅ Patched main.py successfully!")
