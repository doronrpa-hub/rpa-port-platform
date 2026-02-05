with open('main.py', 'r') as f:
    content = f.read()

# Fix 1: Call to_hebrew_name for the name
old_name = "name = name.split()[0]  # First name only"
new_name = "name = to_hebrew_name(name.split()[0])  # First name only, convert to Hebrew"
content = content.replace(old_name, new_name)

# Fix 2: Use a working logo (data URI or different host)
# Using the company website or a reliable source
old_logo = 'https://i.ibb.co/YBwMzLXP/rpa-logo.png'
new_logo = 'https://www.rpa-port.co.il/wp-content/uploads/2020/01/logo.png'
content = content.replace(old_logo, new_logo)

with open('main.py', 'w') as f:
    f.write(content)

print("✅ Fixed name conversion and logo!")
