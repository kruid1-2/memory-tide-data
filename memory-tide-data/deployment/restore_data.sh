#!/usr/bin/env bash
set -euo pipefail
: "${DATA_DIR:?}" "${GITHUB_TOKEN:?}" "${GITHUB_REPOSITORY:?}" "${GITHUB_SERVER_URL:?}"

mkdir -p "$DATA_DIR"
git -C "$DATA_DIR" init --initial-branch=data
git -C "$DATA_DIR" remote add origin "$GITHUB_SERVER_URL/$GITHUB_REPOSITORY.git"
# Credentials are supplied from the runner environment, never persisted in data files.
git -C "$DATA_DIR" config credential.helper '!f() { printf "username=x-access-token\npassword=%s\n" "$GITHUB_TOKEN"; }; f'
git -C "$DATA_DIR" config user.name 'github-actions[bot]'
git -C "$DATA_DIR" config user.email '41898282+github-actions[bot]@users.noreply.github.com'

set +e
git -C "$DATA_DIR" ls-remote --exit-code --heads origin refs/heads/data > "$RUNNER_TEMP/weibo-data-ref"
code=$?
set -e
if [[ "$code" == 0 ]]; then
  git -C "$DATA_DIR" fetch --depth=1 origin data
  git -C "$DATA_DIR" checkout -B data FETCH_HEAD
elif [[ "$code" == 2 ]]; then
  printf '# MEMORY TIDE live observations\n\nAppend-only genuine Weibo snapshots. Code and operating instructions are on the default branch.\n' > "$DATA_DIR/README.md"
  printf '.lock\n' > "$DATA_DIR/.gitignore"
else
  echo 'Could not read the data branch. Refusing to treat an access/network error as empty history.' >&2
  exit "$code"
fi
