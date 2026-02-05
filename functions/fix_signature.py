with open('main.py', 'r') as f:
    content = f.read()

# New professional signature with RPA PORT logo
new_sig = '''        <hr style="border: none; border-top: 1px solid #ddd; margin: 25px 0;">
        <table dir="rtl" cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif;">
            <tr>
                <td style="vertical-align: middle; padding-left: 15px;">
                    <img src="https://i.ibb.co/YBwMzLXP/rpa-logo.png" 
                         alt="R.P.A. PORT LTD" 
                         style="width: 90px; height: auto;">
                </td>
                <td style="vertical-align: middle; padding-right: 15px; border-right: 3px solid #1e3a5f;">
                    <p style="margin: 0; font-size: 12pt; line-height: 1.6;">
                        <strong style="color: #1e3a5f;">🤖 RCB - AI Customs Broker</strong><br>
                        <strong style="color: #1e3a5f;">R.P.A. PORT LTD</strong><br>
                        <span style="color: #666; font-size: 10pt;">Freight Forwarders & Customs Brokers</span><br>
                        <span style="color: #888; font-size: 10pt;">📧 <a href="mailto:rcb@rpa-port.co.il" style="color: #1e3a5f;">rcb@rpa-port.co.il</a></span>
                    </p>
                </td>
            </tr>
        </table>
        <p style="color: #aaa; font-size: 9pt; margin-top: 15px;">
            הודעה זו נשלחה אוטומטית ע״י מערכת AI. לשאלות - השיבו למייל זה.
        </p>
    </div>
    """
    
    return html'''

# Replace old signatures
import re
pattern = r'<hr style="border: none.*?return html'
content = re.sub(pattern, new_sig.strip(), content, flags=re.DOTALL)

with open('main.py', 'w') as f:
    f.write(content)

print("✅ Signature updated!")
