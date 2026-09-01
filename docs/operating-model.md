# 継続報酬アフィリエイト事業のオペレーション定義

2つの役割を、毎朝同じ手順で回せる形に固定したもの。

| 役割 | 実体 | 入力 | 出力 |
| --- | --- | --- | --- |
| リサーチ担当 | `.claude/agents/asp-researcher.md` | ASP4社の案件情報 | `reports/<日付>/screening.md` + `shortlist.csv` |
| 企画担当 | `.claude/agents/offer-planner.md` | ショートリスト＋過去成約データ | `reports/<日付>/proposals.md`（10本） |

## 毎朝の流れ

```
ASP4社の案件情報
   ↓ リサーチ担当が data/offers/offers.csv に整形
python3 scripts/screen_offers.py --input data/offers/offers.csv
   ↓ LTV6,000円以上 / 解約率15%以下 / 承認率60%以上
reports/<日付>/shortlist.csv + screening.md
   ↓
python3 scripts/build_planning_brief.py
   ↓ 過去成約データと突き合わせ
reports/<日付>/brief.md
   ↓ 企画担当が読む
reports/<日付>/proposals.md（10本）
```

## LTVの定義

「LTV6,000円以上」の6,000円は**アフィリエイト報酬ベースのLTV**（1成約あたり
最終的にいくら受け取れるか）であり、広告主のLTVではありません。計算式は
`scripts/screen_offers.py` に固定してあり、案件ごとに変えません。

```
期待継続月数 M = Σ_{m=1..H} (1 - 解約率)^m      H = min(評価期間24ヶ月, 報酬上限月数)
LTV = (初回報酬 + 月額継続報酬 × M) × 承認率
```

**評価期間24ヶ月で必ず頭打ちにします。** 無期限の継続報酬案件を解約率だけで
割ると（LTV = 報酬 ÷ 解約率）LTVが無限に伸び、基準がザルになるためです。

この式が意味するところ:

- 解約率5%・承認率80%・報酬上限なしの案件で、LTV6,000円に届くには
  **月額継続報酬が約560円以上**必要です（期待継続月数は約13.5ヶ月）。
- 解約率15%（基準ぎりぎり）だと期待継続月数は約5.6ヶ月まで落ち、
  月額継続報酬が1,000円あっても初回報酬なしではLTV6,000円に届きません。

つまり「LTV6,000円以上」は実質的に**月額報酬が高い＝顧客単価が高いBtoB SaaS・
士業系・回線・コーチング**に寄る基準です。VODや低単価ツールはこの基準では
ほぼ落ちます。それが意図通りかは四半期ごとに見直してください。

## 解約率の扱い

ASP4社（A8.net / afb / バリューコマース / もしもアフィリエイト）は解約率を
公開していません。よって `churn_source` で出所を必ず区別します。

| `churn_source` | 意味 | 信頼度 | 扱い |
| --- | --- | --- | --- |
| `own_cohort` | 自社の過去コホートで実測 | 高 | 基準をそのまま適用 |
| `merchant_disclosed` | 広告主が開示した数字 | 高 | 基準をそのまま適用 |
| `category_proxy` | 同カテゴリの実績からの推定 | 低 | 基準を20%厳しく適用 |
| `guess` | 根拠なしの当て推量 | 低 | 基準を20%厳しく適用 |

低信頼度の案件には安全マージン（`config/screening.json` の
`low_confidence_margin`）を掛けます。LTV基準は6,000円→7,200円、解約率基準は
15%→12%になります。推定値のまま基準ぎりぎりの案件を通すと、実際の解約率が
少し悪いだけで赤字になるためです。

素の基準は満たすがマージンで落ちた案件は、`screening.md` の
「実データ取得候補」に出ます。ここに載った案件は、広告主に継続率を
問い合わせるか小額テストで実測を取る価値があります。

## データ定義

### `data/offers/offers.csv`（リサーチ担当の出力）

| 列 | 内容 |
| --- | --- |
| `collected_on` | 収集日 (YYYY-MM-DD) |
| `asp` | A8.net / afb / バリューコマース / もしもアフィリエイト |
| `merchant` | 広告主名 |
| `program_id` | ASP上のプログラムID |
| `program_name` | プログラム名 |
| `category` | カテゴリ（過去成約データと同じ語を使う） |
| `customer_price_monthly` | 顧客が払う月額（円） |
| `initial_reward_yen` | 初回成果報酬（円） |
| `recurring_reward_monthly_yen` | 月額継続報酬（円）。0なら単発案件として除外される |
| `recurring_cap_months` | 継続報酬の上限月数。0 = 無期限 |
| `approval_rate` | 承認率 (0-1) |
| `churn_monthly` | 月次解約率 (0-1) |
| `churn_source` | 上表の4値 |
| `landing_url` | 広告主のLP |
| `notes` | 不明点・特記事項 |

### `data/conversions/conversions.csv`（過去の成約データ）

| 列 | 内容 |
| --- | --- |
| `closed_on` | 成約日 |
| `asp` / `merchant` / `program_name` / `category` | 案件情報 |
| `angle` | 切り口（例: インボイス対応比較） |
| `channel` | SEO / YouTube / X / note など |
| `conversions` | 成約数 |
| `retained_m3` | 3ヶ月後も継続していた数 |
| `realized_ltv_yen` | 1成約あたりの実績報酬額 |

`retained_m3 / conversions` が3ヶ月継続率です。この数字が
`churn_source: own_cohort` の根拠になります。

## 自動化できる範囲と、人間が要る範囲

| 工程 | 自動化 |
| --- | --- |
| ASP管理画面からの案件データ取得 | **不可**（要ログイン）。人間がCSVエクスポートして `data/offers/inbox/` に置く |
| 公開情報からの案件探索 | 可（WebSearch） |
| LTV計算・スクリーニング | 可（`screen_offers.py`） |
| 過去実績との突き合わせ | 可（`build_planning_brief.py`） |
| 10本の企画提案 | 半自動（企画担当エージェントが草案、人間が採否） |
| 広告主への継続率問い合わせ | 不可（人間） |
| 提携申請・掲載 | 不可（人間） |

## 基準の見直し

`config/screening.json` の閾値は、四半期ごとに実績で検証してください。
確認する点は3つです。

1. 通過した案件の**実績LTV**が、スクリーニング時の推定LTVと乖離していないか
2. `category_proxy` の推定解約率が、実測後にどれだけずれたか（マージン20%が妥当か）
3. 基準で落とした案件のうち、後から見て取るべきだったものが無いか

## テスト

```bash
python3 scripts/test_pipeline.py
```

LTV計算式とスクリーニング判定の回帰テストです。`config/screening.json` の
閾値を変える前後で必ず流してください。
