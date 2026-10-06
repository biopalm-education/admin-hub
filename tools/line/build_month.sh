#!/bin/sh
# Rebuild admin-hub with one LINE month added/replaced. Run from the repo root after secret.txt is in place.
#   sh tools/line/build_month.sh out/line_2026-09.json.gz [line_2026-09_raw.json.gz ...]
# Raw bundles after the first argument also refresh the "ติดแท็ก / ใส่โน้ต ให้ครบ" list (agg.tnfu) —
# pass the raw bundle of every pull in this round, oldest first. Without them the list stays as it was.
set -e
python3 unpack.py > /dev/null
cp src/agg.json /tmp/agg_before_line.json
python3 mk_line.py "$1"
python3 tools/line/keep_legacy.py /tmp/agg_before_line.json
python3 build_v4.py > /tmp/build_v4.log
python3 build_v5.py > /tmp/build_v5.log
python3 post_v5_speed.py > /tmp/post_v5.log
shift
if [ $# -gt 0 ]; then python3 tools/line/tn_update.py src "$@" > /tmp/tn_update.log && tail -1 /tmp/tn_update.log
else echo "WARN: no raw bundle given — tag/note list (agg.tnfu) NOT refreshed"; fi
python3 build.py | tail -3
echo BUILD_OK
