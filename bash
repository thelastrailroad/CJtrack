#!/usr/bin/env bash
set -e

# 1. Initialize a new Git repository (if not already initialized)
git init

# 2. Add your remote GitHub repository
git remote add origin https://github.com/thelastrailroad/zs-cji-tracker-bot.git

# 3. Stage all current files and commit initial code
git add .
git commit -m "Initial ZS-CJI tracker bot"

# 4. Rename your default branch to main
git branch -M main

# 5. Stage the updated requirements.txt (with JobQueue extra enabled)
git add requirements.txt
git commit -m "Enable job-queue extra for python-telegram-bot"

# 6. Push both commits to GitHub and set upstream
git push --set-upstream origin main
