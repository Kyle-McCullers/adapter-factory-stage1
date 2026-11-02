#!/bin/zsh
# Usage: run_one.sh <source: houston|atlanta|ct> <model id> <run number>
# Builds a fresh sandbox, runs one headless Claude Code session in it, saves the full
# event log and the final result. Never prints the API key.
set -u
SRC=$1; MODEL=$2; N=$3
P=/Users/Shared/orgsci-rebuild-pilot
case $MODEL in
  *opus*) SHORT=opus;; *sonnet*) SHORT=sonnet;; *haiku*) SHORT=haiku;; *fable*) SHORT=fable;; *) SHORT=$MODEL;;
esac
NAME=${SRC}_${SHORT}_${N}
RUN=$P/runs/$NAME
if [ -e "$RUN" ]; then echo "exists: $RUN"; exit 1; fi
mkdir -p "$RUN/raw"
cp $P/materials/adapter_base.py $P/materials/INSTRUCTIONS.md "$RUN/"
cp $P/materials/SOURCE_$SRC.md "$RUN/SOURCE.md"
case $SRC in
  houston) cp $P/materials/raw/houston_directory_2026-06-14.csv "$RUN/raw/";;
  atlanta) cp $P/materials/raw/atlanta_directory_2026-06-14.xls "$RUN/raw/";;
  ct)      cp $P/materials/raw/ct_das_y4ub-e4dd_2026-10-15.csv "$RUN/raw/";;
esac
KEY=$(tr -d '\n\r' < ~/.config/orgsci-pilot/key)
WS=$(tr -d '\n\r' < ~/.config/orgsci-pilot/workspace)
cd "$RUN"
date -u +%Y-%m-%dT%H:%M:%SZ > "$RUN/.started"
env -u CLAUDECODE -u CLAUDE_CODE_CHILD_SESSION -u CLAUDE_CODE_SESSION_ID \
  ANTHROPIC_API_KEY="$KEY" ANTHROPIC_CUSTOM_HEADERS="anthropic-workspace-id: $WS" \
  claude -p "$(cat INSTRUCTIONS.md)" --model "$MODEL" \
  --output-format stream-json --verbose --dangerously-skip-permissions \
  --setting-sources project --disallowedTools WebFetch WebSearch \
  --max-turns 100 --max-budget-usd 15 \
  < /dev/null > "$P/logs/$NAME.jsonl" 2> "$P/logs/$NAME.err"
RC=$?
date -u +%Y-%m-%dT%H:%M:%SZ > "$RUN/.finished"
grep '"type":"result"' "$P/logs/$NAME.jsonl" | tail -1 > "$RUN/result.json"
echo "$NAME exit=$RC"
python3 -I -c "
import json,sys
try:
    r=json.load(open('$RUN/result.json'))
except Exception as e:
    print('no result json', e); sys.exit()
u=r.get('usage',{})
print('cost_usd',round(r.get('total_cost_usd',0),3),'turns',r.get('num_turns'),'duration_s',round(r.get('duration_ms',0)/1000),
      'in',u.get('input_tokens'),'cache_read',u.get('cache_read_input_tokens'),'cache_create',u.get('cache_creation_input_tokens'),'out',u.get('output_tokens'),
      'is_error',r.get('is_error'),'subtype',r.get('subtype'))
"
ls "$RUN"
