#!/bin/bash
# ============================================================
# RPA-PORT Platform Deployment Script
# Run this on Cloud Shell to set up everything
# ============================================================

echo "============================================"
echo "  RPA-PORT Platform Deployment"
echo "============================================"

# Step 1: Check prerequisites
echo ""
echo "Step 1: Checking prerequisites..."
gcloud config set project rpa-port-customs 2>/dev/null

if ! command -v firebase &> /dev/null; then
    echo "  Installing Firebase CLI..."
    npm install -g firebase-tools
else
    echo "  Firebase CLI: OK"
fi

if ! command -v python3 &> /dev/null; then
    echo "  ERROR: Python3 not found"
    exit 1
else
    echo "  Python3: OK"
fi

# Step 2: Clone or update repo
echo ""
echo "Step 2: Setting up repository..."
cd ~
if [ -d "rpa-port-platform" ]; then
    echo "  Updating existing repo..."
    cd rpa-port-platform
    git pull 2>/dev/null || echo "  (not a git repo yet, skipping pull)"
else
    echo "  Creating project directory..."
    mkdir -p rpa-port-platform
    cd rpa-port-platform
fi

# Step 3: Firebase login check
echo ""
echo "Step 3: Firebase authentication..."
firebase login --no-localhost 2>/dev/null || echo "  Already logged in"

# Step 4: Initialize Firebase project
echo ""
echo "Step 4: Connecting to Firebase project..."
firebase use rpa-port-customs 2>/dev/null || firebase use --add

# Step 5: Deploy functions
echo ""
echo "Step 5: Deploying Cloud Functions..."
if [ -d "functions" ]; then
    firebase deploy --only functions 2>&1
    echo "  Cloud Functions deployed!"
else
    echo "  No functions directory found - skipping"
fi

# Step 6: Deploy hosting
echo ""
echo "Step 6: Deploying Web App..."
if [ -d "web-app/public" ] && [ -f "web-app/public/index.html" ]; then
    firebase deploy --only hosting 2>&1
    echo "  Web App deployed!"
else
    echo "  No web app found - skipping"
fi

# Step 7: Deploy rules and indexes
echo ""
echo "Step 7: Deploying Firestore rules..."
if [ -f "firestore.rules" ]; then
    firebase deploy --only firestore:rules 2>&1
    echo "  Firestore rules deployed!"
fi
if [ -f "firestore.indexes.json" ]; then
    firebase deploy --only firestore:indexes 2>&1
    echo "  Firestore indexes deployed!"
fi

# Step 8: Verify
echo ""
echo "============================================"
echo "  Deployment Complete!"
echo "============================================"
echo ""
echo "  Firebase Console: https://console.firebase.google.com/project/rpa-port-customs"
echo "  Functions Logs:   firebase functions:log"
echo ""
echo "  Cloud Functions will now run automatically:"
echo "    - check_email: every 5 minutes"
echo "    - enrich_knowledge: every hour"
echo "    - classify_document: on new document"
echo "    - learn_from_correction: on user correction"
echo ""
echo "  No Cloud Shell or browser needed - everything runs serverless!"
echo ""
