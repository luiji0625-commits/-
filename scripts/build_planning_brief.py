#!/usr/bin/env python3
"""企画担当への入力ブリーフを作る。

当日のショートリスト（screen_offers.py の出力）と、
過去の成約データ（data/conversions/conversions.csv）を突き合わせ、
「どのカテゴリ・どの切り口が実際に継続したか」を数字で出す。

企画担当が10本提案する時に、記憶や勘ではなくこのブリーフを根拠にする。
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys
from collections import defaultdict


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def aggregate(rows, key):
    """key 別に 成約数 / 3ヶ月継続率 / 実績LTV加重平均 / 粗利貢献 を集計。"""
    acc = defaultdict(lambda: {"conversions": 0, "retained": 0, "revenue": 0.0})
    for row in rows:
        conversions = int(float(row["conversions"]))
        bucket = acc[row[key]]
        bucket["conversions"] += conversions
        bucket["retained"] += int(float(row["retained_m3"]))
        bucket["revenue"] += conversions * float(row["realized_ltv_yen"])

    out = []
    for name, bucket in acc.items():
        conversions = bucket["conversions"]
        out.append({
            "name": name,
            "conversions": conversions,
            "retention_m3": bucket["retained"] / conversions if conversions else 0.0,
            "avg_ltv": bucket["revenue"] / conversions if conversions else 0.0,
            "revenue": bucket["revenue"],
        })
    return sorted(out, key=lambda r: -r["revenue"])


def table(rows, label):
    lines = [
        "| %s | 成約数 | 3ヶ月継続率 | 実績LTV | 粗利貢献 |" % label,
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append("| %s | %d | %.0f%% | %s円 | %s円 |" % (
            r["name"], r["conversions"], r["retention_m3"] * 100,
            f"{round(r['avg_ltv']):,}", f"{round(r['revenue']):,}"))
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description="企画担当向けブリーフ生成")
    parser.add_argument("--shortlist", default=None, help="既定: reports/<今日の日付>/shortlist.csv")
    parser.add_argument("--history", default="data/conversions/conversions.sample.csv")
    parser.add_argument("--outdir", default=None, help="既定: reports/<今日の日付>")
    args = parser.parse_args(argv)

    today = dt.date.today().isoformat()
    outdir = args.outdir or os.path.join("reports", today)
    shortlist_path = args.shortlist or os.path.join(outdir, "shortlist.csv")
    if not os.path.exists(shortlist_path):
        raise SystemExit("ショートリストがありません: %s（先に screen_offers.py を実行）" % shortlist_path)

    shortlist = read_csv(shortlist_path)
    history = read_csv(args.history)

    by_category = aggregate(history, "category")
    by_angle = aggregate(history, "angle")
    by_channel = aggregate(history, "channel")

    history_categories = {r["name"]: r for r in by_category}
    shortlist_categories = {r["category"] for r in shortlist}

    proven = [r for r in shortlist if r["category"] in history_categories]
    unproven = [r for r in shortlist if r["category"] not in history_categories]
    # 実績はあるが今日の候補に無いカテゴリ = 案件を探しに行くべき空白
    gaps = [r for r in by_category if r["name"] not in shortlist_categories and r["retention_m3"] >= 0.6]

    lines = [
        "# 企画ブリーフ %s" % today,
        "",
        "本日のショートリスト %d件 / 過去成約データ %d行から生成。" % (len(shortlist), len(history)),
        "企画担当はこのブリーフを根拠に継続報酬型サービスと切り口を10本提案する。",
        "",
        "## 1. 過去実績：カテゴリ別",
        "",
    ]
    lines += table(by_category, "カテゴリ")
    lines += ["", "## 2. 過去実績：切り口別", ""]
    lines += table(by_angle, "切り口")
    lines += ["", "## 3. 過去実績：チャネル別", ""]
    lines += table(by_channel, "チャネル")

    lines += ["", "## 4. 本日の候補 × 実績の突き合わせ", "", "### 実績カテゴリと一致（横展開候補）", ""]
    if proven:
        for r in proven:
            hist = history_categories[r["category"]]
            lines.append(
                "- **%s**（%s / %s）: 推定LTV %s円・解約率 %.1f%% ／ 同カテゴリ過去実績 成約%d件・3ヶ月継続率%.0f%%・実績LTV %s円"
                % (r["program_name"], r["asp"], r["category"], f"{int(r['ltv_yen']):,}",
                   float(r["churn_monthly"]) * 100, hist["conversions"],
                   hist["retention_m3"] * 100, f"{round(hist['avg_ltv']):,}"))
    else:
        lines.append("なし。")

    lines += ["", "### 実績なし（新規開拓・検証枠）", ""]
    if unproven:
        for r in unproven:
            lines.append("- **%s**（%s / %s）: 推定LTV %s円・解約率 %.1f%% ／ 自社実績なし、小額テストから"
                         % (r["program_name"], r["asp"], r["category"], f"{int(r['ltv_yen']):,}",
                            float(r["churn_monthly"]) * 100))
    else:
        lines.append("なし。")

    lines += ["", "## 5. 空白地帯（実績が良いのに本日の候補が無いカテゴリ）", ""]
    if gaps:
        for r in gaps:
            lines.append("- **%s**: 3ヶ月継続率%.0f%%・実績LTV %s円。リサーチ担当に該当ASPの再探索を依頼。"
                         % (r["name"], r["retention_m3"] * 100, f"{round(r['avg_ltv']):,}"))
    else:
        lines.append("なし。")
    lines.append("")

    os.makedirs(outdir, exist_ok=True)
    brief_path = os.path.join(outdir, "brief.md")
    with open(brief_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("ブリーフ生成: %s" % brief_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
