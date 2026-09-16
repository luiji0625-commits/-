会社を作るため

このリポジトリはそのまま Obsidian Vault としても開ける（`vault/` がVault本体）。

## 構成

- `vault/00-Goals/` — 目標ノート（[[vault/Templates/goal-template.md|テンプレート]]の5ステップで整理）
- `vault/01-Decisions/decision-log.md` — 決定ログ
- `vault/02-Notes/` — 調査メモ・アイデア
- `vault/03-Frameworks/` — 再利用する型（[AIオートメーション・フレームワーク](./vault/03-Frameworks/ai-automation-framework.md)など）
- `.claude/skills/company-building/` — 目標相談・計画づくりの固定手順（5ステップ）を実行するスキル
- `.claude/hooks/` — 危険コマンド（`rm -rf`、mainへのforce push、`git reset --hard`）を防ぐ安全フック
