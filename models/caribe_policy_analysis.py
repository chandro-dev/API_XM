"""Build a policy-oriented analytical mart for Colombia's Caribbean region.

XM demand is used to size the commercial agents and construct a transparent
spot-price exposure proxy. Official financial balances are kept in a separate
reference table because demand, user arrears, tariff-option balances, subsidy
receivables and wholesale-market obligations are different concepts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


OPERATOR_MAP = {
    "CMMC": "Afinia / Caribemar",
    "CSSC": "Air-e",
    "CSIC": "Air-e",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Construye el mart analítico del reto Caribe.")
    parser.add_argument("--demand-dir", default="outputs/consumo_actores")
    parser.add_argument("--price-dir", default="outputs/precio_bolsa")
    parser.add_argument("--reference", default="data/reference/caribe_policy_indicators.csv")
    parser.add_argument("--output-dir", default="outputs/caribe")
    return parser.parse_args()


def build_caribe_marts(
    ranking: pd.DataFrame,
    monthly: pd.DataFrame,
    hourly_price: pd.DataFrame,
    policy: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    selected = ranking[ranking.agent_code.isin(OPERATOR_MAP)].copy()
    selected["operator"] = selected.agent_code.map(OPERATOR_MAP)
    summary = (
        selected.groupby("operator", as_index=False)
        .agg(total_demand_kwh=("total_demand_kwh", "sum"), share_percent=("share_percent", "sum"))
        .sort_values("total_demand_kwh", ascending=False)
    )
    summary["total_demand_twh"] = summary.total_demand_kwh / 1e9

    caribe_monthly = monthly[monthly.agent_code.isin(OPERATOR_MAP)].copy()
    caribe_monthly["operator"] = caribe_monthly.agent_code.map(OPERATOR_MAP)
    caribe_monthly = (
        caribe_monthly.groupby(["month", "operator"], as_index=False).demanda_comercial_kwh.sum()
    )
    caribe_monthly["demand_twh"] = caribe_monthly.demanda_comercial_kwh / 1e9

    price = hourly_price.copy()
    price["month"] = price.datetime.dt.to_period("M").dt.to_timestamp()
    monthly_price = price.groupby("month", as_index=False).precio_bolsa_cop_kwh.mean()
    proxy = caribe_monthly.merge(monthly_price, on="month", how="inner")
    proxy["spot_value_100pct_proxy_cop_billions"] = (
        proxy.demanda_comercial_kwh * proxy.precio_bolsa_cop_kwh / 1e9
    )
    proxy["warning"] = "Counterfactual at 100% spot exposure; not actual procurement cost or debt"

    option = policy[(policy.debt_type == "option_tariff") & (policy.indicator == "option_tariff_balance")]
    national_balance = float(option.loc[option.entity == "National", "value"].iloc[0])
    caribe_balance = float(option.loc[option.entity.isin(["Caribemar-Afinia", "Air-e"]), "value"].sum())
    combined_demand = float(summary.total_demand_kwh.sum())
    result = {
        "xm_window": {
            "start": caribe_monthly.month.min().date().isoformat(),
            "end": caribe_monthly.month.max().date().isoformat(),
        },
        "caribe_commercial_demand_twh": combined_demand / 1e9,
        "caribe_share_of_xm_universe_percent": float(summary.share_percent.sum()),
        "operators": summary[["operator", "total_demand_twh", "share_percent"]].to_dict("records"),
        "option_tariff_balance_cutoff": "2024-12-31",
        "caribe_option_tariff_balance_cop": caribe_balance,
        "national_option_tariff_balance_cop": national_balance,
        "caribe_share_of_option_balance_percent": caribe_balance / national_balance * 100,
        "interpretation_limits": [
            "DemaCome is commercial demand by market agent, not household billing or geocoded municipal consumption.",
            "The spot-value proxy assumes 100% spot exposure and is not an actual energy purchase cost.",
            "User arrears, option-tariff balances, MEM obligations and subsidy receivables must remain separate.",
        ],
    }
    return summary, caribe_monthly, proxy, result


def main() -> None:
    args = parse_args()
    demand_dir, price_dir = Path(args.demand_dir), Path(args.price_dir)
    ranking = pd.read_csv(demand_dir / "top_consumidores.csv")
    monthly = pd.read_csv(demand_dir / "consumo_mensual_top.csv", parse_dates=["month"])
    price = pd.read_csv(price_dir / "data_hourly.csv", parse_dates=["datetime"])
    policy = pd.read_csv(args.reference)
    summary, monthly_mart, proxy, result = build_caribe_marts(ranking, monthly, price, policy)

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output / "caribe_agent_summary.csv", index=False)
    monthly_mart.to_csv(output / "caribe_monthly_demand.csv", index=False)
    proxy.to_csv(output / "caribe_spot_exposure_proxy.csv", index=False)
    policy.to_csv(output / "policy_indicators_sourced.csv", index=False)
    (output / "analysis_summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
