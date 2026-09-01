#!/usr/bin/env python3
"""継続報酬案件のスクリーニング。

毎朝リサーチ担当が収集した案件CSVを読み、
「LTV6,000円以上・解約率15%以下」の抽出基準を機械的に適用する。

LTVは広告主が名乗る数字ではなく、こちらの計算式で必ず計算し直す:

    期待継続月数 M = Σ_{m=1..H} (1-c)^m       (H = 評価期間と報酬上限月数の小さい方)
    LTV = (初回報酬 + 月額継続報酬 × M) × 承認率

評価期間(horizon_months)で必ず頭打ちにする。無期限継続報酬を
解約率だけで割ると LTV が発散し、基準が意味をなくなるため。

解約率の出所が推定(category_proxy/guess)の案件には安全マージンを掛ける。
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys

DEFAULT_CONFIG = {
    "horizon_months": 24,
    "ltv_floor_yen": 6000,
    "churn_ceiling_monthly": 0.15,
    "min_approval_rate": 0.6,
    "low_confidence_margin": 0.2,
    "high_confidence_sources": ["own_cohort", "merchant_disclosed"],
}

REQUIRED_COLUMNS = [
    "collected_on", "asp", "merchant", "program_id", "program_name", "category",
    "customer_price_monthly", "initial_reward_yen", "recurring_reward_monthly_yen",
    "recurring_cap_months", "approval_rate", "churn_monthly", "churn_source",
    "landing_url", "notes",
]


def load_config(path):
    config = dict(DEFAULT_CONFIG)
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            config.update(json.load(fh))
    return config


def expected_recurring_months(churn, horizon):
    """解約率 churn の下で horizon ヶ月間に発生する継続報酬の期待回数。"""
    if churn <= 0:
        return float(horizon)
    if churn >= 1:
        return 0.0
    total = 0.0
    survival = 1.0
    for _ in range(horizon):
        survival *= (1.0 - churn)
        total += survival
    return total


def to_float(row, key, default=0.0):
    value = (row.get(key) or "").strip()
    if value == "":
        return default
    return float(value)


def evaluate(row, config):
    """1案件を評価して指標と合否理由を返す。"""
    churn = to_float(row, "churn_monthly")
    approval = to_float(row, "approval_rate", 1.0)
    initial = to_float(row, "initial_reward_yen")
    recurring = to_float(row, "recurring_reward_monthly_yen")
    cap = int(to_float(row, "recurring_cap_months"))
    source = (row.get("churn_source") or "guess").strip()

    horizon = int(config["horizon_months"])
    if cap > 0:
        horizon = min(horizon, cap)

    months = expected_recurring_months(churn, horizon)
    ltv = (initial + recurring * months) * approval

    high_confidence = source in config["high_confidence_sources"]
    margin = 0.0 if high_confidence else float(config["low_confidence_margin"])
    ltv_floor = float(config["ltv_floor_yen"]) * (1.0 + margin)
    churn_ceiling = float(config["churn_ceiling_monthly"]) * (1.0 - margin)

    reasons = []
    if recurring <= 0:
        reasons.append("継続報酬なし（単発報酬のみ）")
    if churn > churn_ceiling:
        reasons.append(
            "解約率 %.1f%% > 基準 %.1f%%%s"
            % (churn * 100, churn_ceiling * 100, "" if high_confidence else "（推定値マージン適用後）")
        )
    if ltv < ltv_floor:
        reasons.append(
            "LTV %.0f円 < 基準 %.0f円%s"
            % (ltv, ltv_floor, "" if high_confidence else "（推定値マージン適用後）")
        )
    if approval < float(config["min_approval_rate"]):
        reasons.append("承認率 %.0f%% < 基準 %.0f%%" % (approval * 100, config["min_approval_rate"] * 100))

    raw_reasons = []
    if recurring <= 0:
        raw_reasons.append("継続報酬なし")
    if churn > float(config["churn_ceiling_monthly"]):
        raw_reasons.append("解約率超過")
    if ltv < float(config["ltv_floor_yen"]):
        raw_reasons.append("LTV不足")
    if approval < float(config["min_approval_rate"]):
        raw_reasons.append("承認率不足")

    return {
        "asp": row.get("asp", ""),
        "merchant": row.get("merchant", ""),
        "program_id": row.get("program_id", ""),
        "program_name": row.get("program_name", ""),
        "category": row.get("category", ""),
        "churn_monthly": churn,
        "churn_source": source,
        "confidence": "高" if high_confidence else "低",
        "expected_months": round(months, 2),
        "evaluated_horizon": horizon,
        "ltv_yen": round(ltv),
        "ltv_floor_applied": round(ltv_floor),
        "churn_ceiling_applied": round(churn_ceiling, 4),
        "approval_rate": approval,
        "landing_url": row.get("landing_url", ""),
        "notes": row.get("notes", ""),
        "verdict": "PASS" if not reasons else "FAIL",
        "verdict_raw": "PASS" if not raw_reasons else "FAIL",
        "reasons": "; ".join(reasons),
    }


def read_offers(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit("入力CSVに必須列がありません: %s" % ", ".join(missing))
        return list(reader)


def write_report(results, outdir, config, source_path):
    os.makedirs(outdir, exist_ok=True)
    passed = sorted([r for r in results if r["verdict"] == "PASS"], key=lambda r: -r["ltv_yen"])
    failed = [r for r in results if r["verdict"] == "FAIL"]

    csv_path = os.path.join(outdir, "shortlist.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(results[0].keys()) if results else ["verdict"])
        writer.writeheader()
        for row in passed:
            writer.writerow(row)

    md_path = os.path.join(outdir, "screening.md")
    lines = [
        "# 継続報酬案件スクリーニング %s" % os.path.basename(outdir),
        "",
        "- 入力: `%s`（%d件）" % (source_path, len(results)),
        "- 抽出基準: LTV %s円以上 / 月次解約率 %.0f%%以下 / 承認率 %.0f%%以上"
        % (config["ltv_floor_yen"], config["churn_ceiling_monthly"] * 100, config["min_approval_rate"] * 100),
        "- LTV評価期間: %sヶ月で頭打ち" % config["horizon_months"],
        "- 解約率が推定値（category_proxy / guess）の案件は基準を%.0f%%厳しく適用"
        % (config["low_confidence_margin"] * 100),
        "",
        "## 通過 %d件" % len(passed),
        "",
    ]
    if passed:
        lines += [
            "| ASP | 案件 | カテゴリ | LTV | 解約率 | 出所信頼度 | 期待継続月数 |",
            "| --- | --- | --- | ---: | ---: | --- | ---: |",
        ]
        for r in passed:
            lines.append(
                "| %s | %s | %s | %s円 | %.1f%% | %s | %.1fヶ月 |"
                % (r["asp"], r["program_name"], r["category"], f"{r['ltv_yen']:,}",
                   r["churn_monthly"] * 100, r["confidence"], r["expected_months"])
            )
    else:
        lines.append("なし。")
    lines += ["", "## 除外 %d件" % len(failed), ""]
    for r in failed:
        lines.append("- **%s**（%s / %s）: %s" % (r["program_name"], r["asp"], r["category"], r["reasons"]))
    borderline = [r for r in failed if r["verdict_raw"] == "PASS"]
    if borderline:
        lines += [
            "",
            "## 実データ取得候補 %d件" % len(borderline),
            "",
            "素の基準（LTV%s円 / 解約率%.0f%%）は満たすが、解約率が推定値のため"
            % (config["ltv_floor_yen"], config["churn_ceiling_monthly"] * 100),
            "マージン適用で除外された案件。広告主に継続率を問い合わせるか、",
            "小額テストで自社コホートを取れば通過する可能性が高い。",
            "",
        ]
        for r in borderline:
            lines.append(
                "- **%s**（%s / %s）: 推定LTV %s円・推定解約率 %.1f%% / 出所 `%s`"
                % (r["program_name"], r["asp"], r["category"], f"{r['ltv_yen']:,}",
                   r["churn_monthly"] * 100, r["churn_source"])
            )
    lines.append("")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return csv_path, md_path, passed, failed


def main(argv=None):
    parser = argparse.ArgumentParser(description="継続報酬案件のスクリーニング")
    parser.add_argument("--input", default="data/offers/offers.sample.csv")
    parser.add_argument("--config", default="config/screening.json")
    parser.add_argument("--outdir", default=None, help="既定: reports/<今日の日付>")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    rows = read_offers(args.input)
    results = [evaluate(row, config) for row in rows]
    outdir = args.outdir or os.path.join("reports", dt.date.today().isoformat())
    csv_path, md_path, passed, failed = write_report(results, outdir, config, args.input)

    print("入力 %d件 → 通過 %d件 / 除外 %d件" % (len(results), len(passed), len(failed)))
    print("  %s" % csv_path)
    print("  %s" % md_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
