# Read main.py
with open('main.py', 'r') as f:
    content = f.read()

# Add Hebrew name mapping after imports
name_mapping = '''
# Hebrew name translations
HEBREW_NAMES = {
    'doron': 'דורון',
    'amit': 'עמית',
    'yossi': 'יוסי',
    'moshe': 'משה',
    'david': 'דוד',
    'avi': 'אבי',
    'eli': 'אלי',
    'dan': 'דן',
    'oren': 'אורן',
    'guy': 'גיא',
    'tal': 'טל',
    'nir': 'ניר',
    'roy': 'רועי',
    'gal': 'גל',
    'yuval': 'יובל',
    'itay': 'איתי',
    'idan': 'עידן',
    'eyal': 'אייל',
    'ran': 'רן',
    'uri': 'אורי',
    'yair': 'יאיר',
    'alon': 'אלון',
    'chen': 'חן',
    'lior': 'ליאור',
    'omer': 'עומר',
    'noam': 'נועם',
    'shachar': 'שחר',
    'ron': 'רון',
    'matan': 'מתן',
    'nadav': 'נדב',
}

def to_hebrew_name(name):
    """Convert English name to Hebrew if known"""
    if not name:
        return "שלום"
    # Already Hebrew?
    if any('\\u0590' <= c <= '\\u05FF' for c in name):
        return name
    return HEBREW_NAMES.get(name.lower().strip(), name)

'''

# Insert after "import requests" line
if 'HEBREW_NAMES' not in content:
    content = content.replace('import requests\n', 'import requests\n' + name_mapping)

# Update to use Hebrew name conversion
if 'to_hebrew_name(name)' not in content:
    content = content.replace(
        "name = name_parts[0] if name_parts else",
        "name = to_hebrew_name(name_parts[0]) if name_parts else"
    )

# Remove the old "urgent" line if exists
content = content.replace(
    '<p>אם יש משהו דחוף, ניתן לפנות ישירות ל-<a href="mailto:rcb@rpa-port.co.il">rcb@rpa-port.co.il</a></p>',
    ''
)

with open('main.py', 'w') as f:
    f.write(content)

print("✅ Done!")
