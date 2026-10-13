#!/usr/bin/env bash
set -euo pipefail
: "${DATA_DIR:?}" "${GITHUB_RUN_ID:?}" "${GITHUB_RUN_ATTEMPT:?}"
test -f "$DATA_DIR/observations/status.json"
git -C "$DATA_DIR" add -- README.md .gitignore observations/
if git -C "$DATA_DIR" diff --cached --quiet; then
  echo 'No new observations or attempts to persist.'
  exit 0
fi
git -C "$DATA_DIR" commit -m "Record Weibo attempt $GITHUB_RUN_ID/$GITHUB_RUN_ATTEMPT"
for push_attempt in 1 2 3; do
  if git -C "$DATA_DIR" push origin HEAD:refs/heads/data; then
    echo 'Persistent data branch updated.'
    exit 0
  fi
  if [[ "$push_attempt" == 3 ]]; then break; fi
  # Non-fast-forward pushes are never forced. Refuse unresolved pointer conflicts.
  git -C "$DATA_DIR" fetch --depth=50 origin data
  if ! git -C "$DATA_DIR" rebase origin/data; then
    git -C "$DATA_DIR" rebase --abort
    echo 'Concurrent data update could not be safely reconciled; retain the outbox artifact.' >&2
    exit 1
  fi
done
echo 'Push failed after three attempts; recover the outbox artifact before its retention expires.' >&2
exit 1
