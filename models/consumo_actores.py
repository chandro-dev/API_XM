"""Extract and rank Colombian energy demand by market actor.

The script uses XM's public API through pydataxm and focuses on
`DemaCome` / `Agente`, which represents commercial demand by agent.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from pydataxm.pydataxm import ReadDB


DEMAND_METRIC_ID = "DemaCome"
DEMAND_ENTITY = "Agente"
AGENTS_METRIC_ID = "ListadoAgentes"
AGENTS_ENTITY = "Sistema"
DEMAND_COLUMN = "demanda_comercial_kwh"


def parse_args() -> argparse.Namespace:
    yesterday = date.today() - timedelta(days=1)
    parser = argparse.ArgumentParser(
        description="Consulta y rankea los agentes con mayor demanda comercial."
    )
    parser.add_argument("--start-date", default="2022-01-01", help="Fecha inicial YYYY-MM-DD.")
    parser.add_argument(
        "--end-date",
        default=yesterday.isoformat(),
        help="Fecha final YYYY-MM-DD. Por defecto usa ayer.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Numero de agentes a incluir en el ranking principal.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/consumo_actores",
        help="Directorio de salida.",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Usa archivos existentes si ya fueron generados.",
    )
    return parser.parse_args()


def hourly_wide_to_long(raw: pd.DataFrame) -> pd.DataFrame:
    hour_columns = sorted(
        [col for col in raw.columns if col.startswith("Values_Hour")],
        key=lambda name: int(name.replace("Values_Hour", "")),
    )
    if not hour_columns:
        raise ValueError("No se encontraron columnas Values_HourXX en la respuesta de XM.")

    long_df = raw.melt(
        id_vars=["Date", "Values_code"],
        value_vars=hour_columns,
        var_name="hour_col",
        value_name=DEMAND_COLUMN,
    )
    long_df["hour"] = long_df["hour_col"].str.extract(r"(\d{2})").astype(int) - 1
    long_df["datetime"] = pd.to_datetime(long_df["Date"]) + pd.to_timedelta(
        long_df["hour"], unit="h"
    )
    long_df = long_df.rename(columns={"Values_code": "agent_code"})
    long_df[DEMAND_COLUMN] = pd.to_numeric(long_df[DEMAND_COLUMN], errors="coerce")
    return (
        long_df[["datetime", "agent_code", DEMAND_COLUMN]]
        .dropna()
        .sort_values(["datetime", "agent_code"])
        .reset_index(drop=True)
    )


def fetch_demand(start_date: str, end_date: str) -> pd.DataFrame:
    api = ReadDB()
    raw = api.request_data(DEMAND_METRIC_ID, DEMAND_ENTITY, start_date, end_date)
    if raw.empty:
        raise RuntimeError("La API XM no retorno demanda comercial por agente.")
    return hourly_wide_to_long(raw)


def fetch_agents() -> pd.DataFrame:
    api = ReadDB()
    raw = api.request_data(AGENTS_METRIC_ID, AGENTS_ENTITY, date.today().isoformat(), date.today().isoformat())
    if raw.empty:
        return pd.DataFrame(columns=["agent_code", "agent_name", "activity", "state"])
    agents = raw.rename(
        columns={
            "Values_Code": "agent_code",
            "Values_Name": "agent_name",
            "Values_Activity": "activity",
            "Values_State": "state",
            "Values_OperStartdate": "operation_start_date",
        }
    )
    columns = ["agent_code", "agent_name", "activity", "state", "operation_start_date"]
    return agents[[col for col in columns if col in agents.columns]].drop_duplicates("agent_code")


def build_outputs(demand: pd.DataFrame, agents: pd.DataFrame, top_n: int) -> dict[str, pd.DataFrame]:
    demand = demand.merge(agents, on="agent_code", how="left")
    demand["agent_name"] = demand["agent_name"].fillna(demand["agent_code"])
    demand["date"] = demand["datetime"].dt.date
    demand["month"] = demand["datetime"].dt.to_period("M").dt.to_timestamp()
    demand["hour"] = demand["datetime"].dt.hour
    demand["dayofweek"] = demand["datetime"].dt.dayofweek

    ranking = (
        demand.groupby(["agent_code", "agent_name"], as_index=False)
        .agg(
            total_demand_kwh=(DEMAND_COLUMN, "sum"),
            avg_hourly_demand_kwh=(DEMAND_COLUMN, "mean"),
            max_hourly_demand_kwh=(DEMAND_COLUMN, "max"),
            records=(DEMAND_COLUMN, "size"),
        )
        .sort_values("total_demand_kwh", ascending=False)
    )
    total = ranking["total_demand_kwh"].sum()
    ranking["share_percent"] = ranking["total_demand_kwh"] / total * 100
    top_codes = ranking.head(top_n)["agent_code"].tolist()

    monthly = (
        demand[demand["agent_code"].isin(top_codes)]
        .groupby(["month", "agent_code", "agent_name"], as_index=False)[DEMAND_COLUMN]
        .sum()
        .sort_values(["month", DEMAND_COLUMN], ascending=[True, False])
    )
    heatmap = (
        demand[demand["agent_code"].isin(top_codes)]
        .groupby(["agent_code", "agent_name", "dayofweek", "hour"], as_index=False)[DEMAND_COLUMN]
        .mean()
    )

    return {
        "consumo_hourly": demand,
        "top_consumidores": ranking,
        "consumo_mensual_top": monthly,
        "heatmap_top": heatmap,
    }


def load_or_build(args: argparse.Namespace, output_dir: Path) -> dict[str, pd.DataFrame]:
    hourly_path = output_dir / "consumo_hourly.csv"
    agents_path = output_dir / "agentes.csv"
    if args.use_cache and hourly_path.exists():
        # Persisted hourly data is already enriched. Rebuild from the canonical
        # fact columns to keep repeated cached runs idempotent.
        demand = pd.read_csv(hourly_path, parse_dates=["datetime"])[
            ["datetime", "agent_code", DEMAND_COLUMN]
        ]
        agents = pd.read_csv(agents_path) if agents_path.exists() else pd.DataFrame()
    else:
        demand = fetch_demand(args.start_date, args.end_date)
        agents = fetch_agents()
    return build_outputs(demand, agents, args.top_n)


def save_outputs(output_dir: Path, outputs: dict[str, pd.DataFrame]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs["consumo_hourly"].to_csv(output_dir / "consumo_hourly.csv", index=False)
    outputs["top_consumidores"].to_csv(output_dir / "top_consumidores.csv", index=False)
    outputs["consumo_mensual_top"].to_csv(output_dir / "consumo_mensual_top.csv", index=False)
    outputs["heatmap_top"].to_csv(output_dir / "heatmap_top.csv", index=False)
    agent_columns = ["agent_code", "agent_name", "activity", "state", "operation_start_date"]
    agents = outputs["consumo_hourly"][[col for col in agent_columns if col in outputs["consumo_hourly"].columns]]
    agents.drop_duplicates("agent_code").to_csv(output_dir / "agentes.csv", index=False)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    outputs = load_or_build(args, output_dir)
    save_outputs(output_dir, outputs)

    ranking = outputs["top_consumidores"].head(args.top_n)
    print(f"Archivos guardados en: {output_dir.resolve()}")
    print("Top consumidores por demanda comercial total")
    print(ranking[["agent_code", "agent_name", "total_demand_kwh", "share_percent"]].to_string(index=False))


if __name__ == "__main__":
    main()
