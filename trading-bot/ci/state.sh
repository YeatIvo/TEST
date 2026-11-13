#!/usr/bin/env bash
# Bot-Zustand zwischen GitHub-Actions-Läufen speichern/laden.
# Der Zustand (was der Bot besitzt, Logs, Berichte, PAUSE, aktive Regeln) liegt auf dem
# eigenen Branch `bot-state`, damit der Code-Branch sauber bleibt.
#   ci/state.sh load   – vor dem Lauf: Zustand über den Checkout legen
#   ci/state.sh save   – nach dem Lauf: Zustand committen und pushen
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
BR=bot-state
PATHS=(trading-bot/data/live trading-bot/logs trading-bot/reports trading-bot/rules trading-bot/PAUSE)
W="${RUNNER_TEMP:-/tmp}/bot-state"

case "${1:-}" in
  load)
    if git fetch -q --depth 1 origin "$BR" 2>/dev/null; then
      mkdir -p "$W.load"
      git archive FETCH_HEAD | tar -x -C "$W.load"
      rm -f trading-bot/PAUSE
      cp -a "$W.load/trading-bot/." trading-bot/
      echo "Zustand geladen ($(git rev-parse --short FETCH_HEAD))."
    else
      echo "Noch kein Zustand – erster Lauf."
    fi
    ;;
  save)
    git config user.name "trading-bot"
    git config user.email "trading-bot@users.noreply.github.com"
    rm -rf "$W"
    if git fetch -q --depth 1 origin "$BR" 2>/dev/null; then
      git worktree add -q -B "$BR" "$W" FETCH_HEAD
    else
      git worktree add -q --detach "$W"
      git -C "$W" checkout -q --orphan "$BR"
      git -C "$W" rm -rfq . >/dev/null
    fi
    rm -rf "$W/trading-bot"
    for p in "${PATHS[@]}"; do
      if [ -e "$p" ]; then mkdir -p "$W/$(dirname "$p")"; cp -a "$p" "$W/$p"; fi
    done
    # Sicherheitsnetz: niemals Secrets speichern
    find "$W" -name ".env*" -not -name ".env.example" -delete
    git -C "$W" add -A
    if git -C "$W" diff --cached --quiet; then
      echo "Zustand unverändert."
    else
      git -C "$W" commit -q -m "Bot-Zustand $(date -u +%Y-%m-%dT%H:%MZ) (${GITHUB_EVENT_NAME:-manuell})"
      git -C "$W" push -q origin "$BR"
      echo "Zustand gespeichert."
    fi
    ;;
  *) echo "usage: $0 load|save"; exit 2 ;;
esac
