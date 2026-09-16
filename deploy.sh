#!/bin/sh
# Rebuild the published site from src/ and push it to GitHub Pages.
#   ./deploy.sh "ข้อความ commit"
# ต้องมีไฟล์ gh_token.txt (GitHub fine-grained token, สิทธิ์ Contents: Read and write
# บน repo biopalm-education/admin-hub) วางไว้ในโฟลเดอร์เดียวกับสคริปต์นี้
set -e
HUB=$(cd "$(dirname "$0")" && pwd)
REPO=$HOME/.admin-hub-deploy
SLUG=biopalm-education/admin-hub

[ -f "$HUB/gh_token.txt" ] || { echo "ไม่พบ gh_token.txt ใน $HUB"; exit 1; }
TOKEN=$(tr -d ' \r\n' < "$HUB/gh_token.txt")

rm -rf "$REPO"
git clone -q --depth 1 "https://github.com/$SLUG.git" "$REPO"
git -C "$REPO" config user.name  "biopalm-education"
git -C "$REPO" config user.email "mkt.biopalm@gmail.com"

cd "$HUB" && python3 build.py "$REPO"
# keep the pipeline in the repo in sync with the local copies
for f in app.html build.py deploy.sh extract.py unpack.py mk_line.py; do [ -f "$HUB/$f" ] && cp "$HUB/$f" "$REPO/$f"; done

cd "$REPO"
git add -A
if git diff --cached --quiet; then echo "ไม่มีอะไรเปลี่ยน — ไม่ต้อง push"; exit 0; fi
git commit -q -m "${1:-Update dashboard data}"
git push -q "https://x-access-token:$TOKEN@github.com/$SLUG.git" HEAD:main
echo "pushed · https://biopalm-education.github.io/admin-hub/"
