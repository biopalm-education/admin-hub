#!/bin/sh
# Rebuild admin-hub with one LINE month added/replaced. Run from the repo root after secret.txt is in place.
#   sh tools/line/build_month.sh out/line_2026-09.json.gz
set -e
python3 unpack.py > /dev/null
cp src/agg.json /tmp/agg_before_line.json
python3 mk_line.py "$1"
python3 tools/line/keep_legacy.py /tmp/agg_before_line.json
python3 build_v4.py > /tmp/build_v4.log
python3 build_v5.py > /tmp/build_v5.log
python3 post_v5_speed.py > /tmp/post_v5.log
python3 build.py | tail -3
echo BUILD_OK
