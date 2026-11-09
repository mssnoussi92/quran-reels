#!/usr/bin/env bash
# Commit files of the `state` branch worktree and push them, without ever losing what this run
# wrote: a publication that is not recorded would be published again by the next run.
#
#   save-state.sh "<commit message>" <path>...      (run inside the worktree: state-branch/)
#
# The state branch has several writers (daily, images, prepare, on-demand, a session that reopens
# a slot) and not all of them share the `accounts` concurrency group: the on-demand preview pushes
# its splits while a daily run may be publishing. So when the push is refused, or the network
# fails, the new tip is fetched, this run's commit is replayed on it, and the push is tried again.
# Only a real conflict (two writers changed the same lines) or five failed pushes end in an error.
#
# Exit 0: saved, or nothing to save. Exit 1: not saved, with an annotation on the run
# (SAVE_STATE_LEVEL=warning where losing the files only costs time, as for splits).
set -uo pipefail

message=${1:?usage: save-state.sh "<commit message>" <path>...}
shift

tries=${SAVE_STATE_TRIES:-5}
pause=${SAVE_STATE_PAUSE:-2}          # seconds, doubled after each failed push
level=${SAVE_STATE_LEVEL:-error}

# A worktree of the state branch (its .git is a file); a plain directory has nothing to push.
[ -e .git ] || { echo "save-state: no state worktree here, nothing saved"; exit 0; }

paths=()
for p in "$@"; do
  [ -e "$p" ] && paths+=("$p")
done
[ ${#paths[@]} -gt 0 ] || { echo "save-state: nothing to save ($*)"; exit 0; }

# The identity of the commit, and of its replay: a rebase needs a committer too.
export GIT_AUTHOR_NAME="quran-reels" GIT_COMMITTER_NAME="quran-reels"
export GIT_AUTHOR_EMAIL="41898282+github-actions[bot]@users.noreply.github.com"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

git add -- "${paths[@]}" || exit 1
if git diff --cached --quiet; then
  echo "save-state: no change"
  exit 0
fi
git commit -q -m "$message $(date -u +%Y-%m-%dT%H:%MZ)" || exit 1

for ((i = 1; i <= tries; i++)); do
  if git push -q origin HEAD:state; then
    echo "save-state: pushed ($(git rev-parse --short HEAD), try $i)"
    exit 0
  fi
  [ "$i" -lt "$tries" ] || break
  sleep $((pause * 2 ** (i - 1)))
  # The branch moved, or the network failed. No fetch: the same push is tried again.
  git fetch -q --depth=1 origin state || continue
  if git rev-parse -q --verify HEAD~1 >/dev/null; then
    replay=(git rebase -q --onto FETCH_HEAD HEAD~1)
  else                                # the very first commit of a new state branch
    replay=(git rebase -q --onto FETCH_HEAD --root)
  fi
  if ! "${replay[@]}"; then
    git rebase --abort 2>/dev/null
    echo "::$level::save-state: «$message» conflicts with what another run pushed to the state branch; not saved"
    exit 1
  fi
  echo "save-state: the state branch had moved, commit replayed on $(git rev-parse --short FETCH_HEAD)"
done
echo "::$level::save-state: «$message» not pushed after $tries tries"
exit 1
