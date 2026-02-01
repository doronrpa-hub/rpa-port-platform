import re
# Fix the path line in main.py
with open("main.py", "r") as f:
    content = f.read()
old = '    path = req.path.replace("/api/", "")'
new = '    path = req.path.strip("/").replace("api/", "")\n'
old2 = '    if path == "stats" and method == "GET":'
new2 = '    if path in ("stats", "") and method == "GET":'
content = content.replace(old, new)
content = content.replace(old2, new2)
with open("main.py", "w") as f:
    f.write(content)
print("Fixed!")
