#!/bin/bash
# Run these commands on Cloud Shell to set up GitHub repo

# Step 1: Configure git
git config --global user.email "doronrpa@gmail.com"
git config --global user.name "Doron RPA-PORT"

# Step 2: Initialize repo
cd ~/rpa-port-platform
git init
git add .
git commit -m "Initial commit: RPA-PORT Customs Intelligence Platform"

# Step 3: Create GitHub repo and push
# First, create the repo on github.com, then:
git remote add origin https://github.com/doronrpa/rpa-port-platform.git
git branch -M main
git push -u origin main
