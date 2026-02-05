with open('main.py', 'r') as f:
    content = f.read()

# Remove the misplaced decorator before helper functions
content = content.replace(
    '''# FUNCTION 5: RCB API ENDPOINTS
# ============================================================
@https_fn.on_request(cors=options.CorsOptions(cors_origins="*", cors_methods=["GET", "POST"]))
# ============================================================
# RCB HELPER FUNCTIONS''',
    '''# FUNCTION 5: RCB API ENDPOINTS
# ============================================================
# ============================================================
# RCB HELPER FUNCTIONS'''
)

# Add decorator before rcb_api function
content = content.replace(
    'def rcb_api(req: https_fn.Request)',
    '@https_fn.on_request(cors=options.CorsOptions(cors_origins="*", cors_methods=["GET", "POST"]))\ndef rcb_api(req: https_fn.Request)'
)

with open('main.py', 'w') as f:
    f.write(content)

print("✅ Fixed decorator placement!")
