# RPA-PORT Platform Setup Guide

## Step 1: GitHub Repository

```bash
# On Cloud Shell
cd ~
git clone https://github.com/YOUR_USERNAME/rpa-port-platform.git
cd rpa-port-platform
```

## Step 2: Firebase CLI Setup

```bash
# Install Firebase CLI
npm install -g firebase-tools

# Login
firebase login

# Connect to project
firebase use rpa-port-customs
```

## Step 3: Deploy Cloud Functions

```bash
# Deploy everything
firebase deploy

# Or deploy just functions
firebase deploy --only functions

# Or deploy just hosting (web app)
firebase deploy --only hosting
```

## Step 4: Configure Email

In Firebase Console → Firestore → config/email document:
```json
{
  "email": "airpaport@gmail.com",
  "app_password": "YOUR_APP_PASSWORD"
}
```

## Step 5: Office PC Agent

On the office Windows PC:
```bash
pip install firebase-admin requests pdfplumber beautifulsoup4
python rpa_agent.py
```

## Monitoring

### Check Cloud Functions logs:
```bash
firebase functions:log
```

### Check from Firebase Console:
https://console.firebase.google.com/project/rpa-port-customs/functions/logs

## Costs (Estimated)

| Service | Free Tier | Our Usage | Monthly Cost |
|---|---|---|---|
| Cloud Functions | 2M invocations | ~9,000 (5min x 24h x 31d) | $0 |
| Firestore | 50K reads/day | ~10K reads/day | $0 |
| Storage | 5GB | ~1GB | $0 |
| Hosting | 10GB/month | ~100MB | $0 |
| **Total** | | | **$0** |

Everything stays within Firebase free tier for a single company.
Multi-tenant (10+ companies) estimated: $5-20/month.
