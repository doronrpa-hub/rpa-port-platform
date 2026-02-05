with open('main.py', 'r') as f:
    content = f.read()

followup_code = '''
            # === PHASE 2: Multi-Agent Classification Report ===
            docs_with_text = []
            for att in raw_attachments:
                if att.get('@odata.type') == '#microsoft.graph.fileAttachment':
                    text = ""
                    if att.get('name', '').lower().endswith('.pdf') and att.get('contentBytes'):
                        text = extract_text_from_pdf_base64(att.get('contentBytes'))
                    docs_with_text.append({'name': att.get('name'), 'extracted_text': text, 'contentBytes': att.get('contentBytes')})
            
            if any(d.get('extracted_text') for d in docs_with_text):
                print(f"🤖 Running multi-agent classification...")
                main_report, appendix, excel_data = run_multi_agent_classification(docs_with_text, subject, msg.get('body', {}).get('content', '')[:5000])
                
                if main_report:
                    excel_b64 = create_multi_sheet_excel(excel_data) if excel_data else None
                    class_html = build_classification_email(main_report, appendix, from_name)
                    
                    all_attachments = list(raw_attachments)
                    if excel_b64:
                        all_attachments.append({
                            '@odata.type': '#microsoft.graph.fileAttachment',
                            'name': f'Classification_Report_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
                            'contentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                            'contentBytes': excel_b64
                        })
                    
                    if graph_send_email(access_token, rcb_email, from_email, f"📊 דו\"ח סיווג: {subject}", class_html, None, all_attachments):
                        print(f"  ✅ Classification report sent!")
                        db.collection("rcb_logs").add({"message": f"Classification sent: {subject[:40]}", "status": "report_sent", "timestamp": firestore.SERVER_TIMESTAMP})
'''

# Find insertion point after initial reply log
import re
pattern = r'(db\.collection\("rcb_logs"\)\.add\(\{\s*"message": f"Replied to: \{subject\[:50\]\}".*?\}\))'
match = re.search(pattern, content, re.DOTALL)
if match and 'multi-agent' not in content.lower():
    pos = match.end()
    content = content[:pos] + "\n" + followup_code + content[pos:]

with open('main.py', 'w') as f:
    f.write(content)

print("✅ Follow-up trigger added!")
