# 継続報酬アフィリエイト事業のオペレーション

月額課金型サービスの**継続報酬**案件だけを扱う事業の、毎朝の運用一式。
役割2つ（リサーチ担当・企画担当）を、同じ手順で毎日回せる形にしてある。

## 毎朝

```bash
# 1. リサーチ担当: 収集した案件をスクリーニング
python3 scripts/screen_offers.py --input data/offers/offers.csv

# 2. 企画担当: ショートリストと過去実績を突き合わせたブリーフを生成
python3 scripts/build_planning_brief.py
```

出力は `reports/<日付>/` に出る。

| ファイル | 中身 |
| --- | --- |
| `screening.md` | 通過案件 / 除外理由 / 実データ取得候補 |
| `shortlist.csv` | 通過案件（LTV降順） |
| `brief.md` | カテゴリ・切り口・チャネル別の過去実績と、本日候補との突き合わせ |
| `proposals.md` | 企画担当が書く10本の提案 |

サンプルデータで動作を確認できる（引数なしで実行するとサンプルを読む）。
実データは `data/offers/offers.csv` と `data/conversions/conversions.csv` に置く。
どちらも `.gitignore` 済み。

## 役割

### リサーチ担当 — `.claude/agents/asp-researcher.md`

A8.net / afb / バリューコマース / もしもアフィリエイト から月額課金型の
継続報酬案件を集め、**LTV6,000円以上・解約率15%以下**だけを抽出する。

抽出はエージェントの判断ではなく `scripts/screen_offers.py` が機械的に行う。
LTVは広告主の自己申告値ではなく、こちらの式で毎回計算し直す:

```
期待継続月数 M = Σ_{m=1..H} (1 - 解約率)^m      H = min(評価期間24ヶ月, 報酬上限月数)
LTV = (初回報酬 + 月額継続報酬 × M) × 承認率
```

### 企画担当 — `.claude/agents/offer-planner.md`

過去の成約データと照らして、次に狙う継続報酬型サービスと切り口を10本提案する。
内訳は固定: **横展開6本 / 隣接展開3本 / 実験枠1本**。
提案1本ごとに、根拠となる過去実績の行・LTV試算・リスク・撤退ラインを書く。

## 前提として押さえておくこと

ASP4社は**解約率を公開していない**。そのため案件ごとに解約率の出所
（`own_cohort` / `merchant_disclosed` / `category_proxy` / `guess`）を記録し、
推定値の案件には基準を20%厳しく適用している（LTV 7,200円 / 解約率 12%）。

ASP管理画面はログインが必要でスクレイピングできない。管理画面の数字は
人間がCSVエクスポートして `data/offers/inbox/` に置く運用にしている。

詳細は [`docs/operating-model.md`](docs/operating-model.md) を参照。

## テスト

```bash
python3 scripts/test_pipeline.py
```
