with open('main.py', 'r') as f:
    lines = f.readlines()

# Functions to remove (they exist in lib/rcb_helpers.py)
funcs_to_remove = ['helper_get_graph_token', 'helper_graph_messages', 'helper_graph_attachments', 
                   'helper_graph_mark_read', 'helper_graph_send', 'to_hebrew_name', 'build_rcb_reply',
                   'HEBREW_NAMES']

new_lines = []
skip_until_next = False
for line in lines:
    # Check if this is a function we want to remove
    if any(f'def {func}(' in line for func in funcs_to_remove):
        skip_until_next = True
        continue
    if 'HEBREW_NAMES = {' in line:
        skip_until_next = True
        continue
    if skip_until_next:
        # Check if we've reached the next function/class/decorator
        if (line.startswith('def ') or line.startswith('@') or line.startswith('# ===')) and not any(f'def {func}(' in line for func in funcs_to_remove):
            skip_until_next = False
            new_lines.append(line)
        continue
    new_lines.append(line)

with open('main.py', 'w') as f:
    f.writelines(new_lines)

print("✅ Removed duplicate functions")
