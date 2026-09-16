#!/usr/bin/env bash
# PreToolUse hook (Bash): blocks a short list of high-risk commands.
# Best-effort guardrail, not a security boundary.
input=$(cat)
cmd=$(echo "$input" | jq -r '.tool_input.command // empty')

deny() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}' "$1"
  exit 0
}

if echo "$cmd" | grep -Eq '(^|[^a-zA-Z])rm([[:space:]]+-[a-zA-Z]+)*[[:space:]]+-[a-zA-Z]*[rf][a-zA-Z]*[rf][a-zA-Z]*'; then
  deny "危険コマンド(rm -rf相当)をブロックしました: $cmd"
fi

if echo "$cmd" | grep -Eq 'git[[:space:]]+push' \
   && echo "$cmd" | grep -Eq -- '--force(-with-lease)?|(^|[[:space:]])-f([[:space:]]|$)' \
   && echo "$cmd" | grep -Eq '\bmain\b'; then
  deny "mainブランチへのforce pushをブロックしました: $cmd"
fi

if echo "$cmd" | grep -Eq 'git[[:space:]]+reset[[:space:]]+--hard'; then
  deny "git reset --hardをブロックしました: $cmd"
fi

exit 0
