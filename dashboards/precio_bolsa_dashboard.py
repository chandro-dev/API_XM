"""Generate a static dashboard for the spot price forecasting model."""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
from pathlib import Path
from typing import Callable

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PRICE_COLUMN = "precio_bolsa_cop_kwh"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un dashboard HTML del modelo de precio de bolsa."
    )
    parser.add_argument(
        "--input-dir",
        default="outputs/precio_bolsa",
        help="Carpeta con los artefactos del entrenamiento.",
    )
    parser.add_argument(
        "--output",
        default="outputs/precio_bolsa/dashboard.html",
        help="Archivo HTML a generar.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def figure_to_base64(plot_fn: Callable[[], None]) -> str:
    plt.close("all")
    plot_fn()
    buffer = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format="png", dpi=140, bbox_inches="tight")
    plt.close("all")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def money(value: float) -> str:
    return f"{value:,.2f}"


def metric_card(label: str, value: object, detail: str = "") -> str:
    return f"""
    <article class="card">
      <span>{html.escape(label)}</span>
      <strong>{html.escape(str(value))}</strong>
      <small>{html.escape(detail)}</small>
    </article>
    """


def plot_history(hourly: pd.DataFrame) -> str:
    def draw() -> None:
        daily = hourly.set_index("datetime")[PRICE_COLUMN].resample("D").mean()
        monthly = hourly.set_index("datetime")[PRICE_COLUMN].resample("ME").mean()
        fig, ax = plt.subplots(figsize=(12, 4.2))
        ax.plot(daily.index, daily.values, color="#4b5563", linewidth=0.9, alpha=0.45, label="Promedio diario")
        ax.plot(monthly.index, monthly.values, color="#0f766e", linewidth=2.1, label="Promedio mensual")
        ax.set_title("Historico del Precio de Bolsa Nacional")
        ax.set_ylabel("COP/kWh")
        ax.grid(True, alpha=0.25)
        ax.legend()
        fig.autofmt_xdate()

    return figure_to_base64(draw)


def plot_history_heatmap(hourly: pd.DataFrame) -> str:
    def draw() -> None:
        data = hourly.copy()
        data["hour"] = data["datetime"].dt.hour
        data["dayofweek"] = data["datetime"].dt.dayofweek
        pivot = data.pivot_table(
            index="dayofweek",
            columns="hour",
            values=PRICE_COLUMN,
            aggfunc="mean",
        )
        fig, ax = plt.subplots(figsize=(12, 3.8))
        image = ax.imshow(pivot.values, aspect="auto", cmap="viridis")
        ax.set_title("Mapa de calor historico: precio promedio por dia y hora")
        ax.set_xlabel("Hora")
        ax.set_ylabel("Dia de semana")
        ax.set_xticks(range(24))
        ax.set_yticks(range(7))
        ax.set_yticklabels(["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"])
        fig.colorbar(image, ax=ax, label="COP/kWh")

    return figure_to_base64(draw)


def plot_predictions(test_predictions: pd.DataFrame) -> str:
    def draw() -> None:
        sample = test_predictions.tail(24 * 14)
        fig, ax = plt.subplots(figsize=(12, 4.2))
        ax.plot(sample["datetime"], sample["target_price"], color="#111827", linewidth=1.6, label="Real")
        ax.plot(sample["datetime"], sample["prediction_price"], color="#2563eb", linewidth=1.4, label="Modelo")
        ax.plot(sample["datetime"], sample["baseline_lag_1h"], color="#dc2626", linewidth=1.0, alpha=0.75, label="Baseline lag 1h")
        ax.set_title("Validacion temporal: ultimos 14 dias del tramo de prueba")
        ax.set_ylabel("COP/kWh")
        ax.grid(True, alpha=0.25)
        ax.legend()
        fig.autofmt_xdate()

    return figure_to_base64(draw)


def plot_error_heatmap(test_predictions: pd.DataFrame) -> str:
    def draw() -> None:
        data = test_predictions.copy()
        data["abs_error"] = (data["target_price"] - data["prediction_price"]).abs()
        data["hour"] = data["datetime"].dt.hour
        data["dayofweek"] = data["datetime"].dt.dayofweek
        pivot = data.pivot_table(
            index="dayofweek",
            columns="hour",
            values="abs_error",
            aggfunc="mean",
        )
        fig, ax = plt.subplots(figsize=(12, 3.8))
        image = ax.imshow(pivot.values, aspect="auto", cmap="magma")
        ax.set_title("Mapa de calor de error medio absoluto por dia y hora")
        ax.set_xlabel("Hora")
        ax.set_ylabel("Dia de semana")
        ax.set_xticks(range(24))
        ax.set_yticks(range(7))
        ax.set_yticklabels(["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"])
        fig.colorbar(image, ax=ax, label="Error COP/kWh")

    return figure_to_base64(draw)


def plot_forecast(hourly: pd.DataFrame, forecast: pd.DataFrame) -> str:
    def draw() -> None:
        recent = hourly.tail(24 * 10)
        fig, ax = plt.subplots(figsize=(12, 4.2))
        ax.plot(recent["datetime"], recent[PRICE_COLUMN], color="#374151", linewidth=1.5, label="Historico reciente")
        ax.plot(
            forecast["datetime"],
            forecast["predicted_precio_bolsa_cop_kwh"],
            color="#16a34a",
            linewidth=2.0,
            marker="o",
            markersize=2.5,
            label="Pronostico",
        )
        ax.set_title("Pronostico generado por el modelo")
        ax.set_ylabel("COP/kWh")
        ax.grid(True, alpha=0.25)
        ax.legend()
        fig.autofmt_xdate()

    return figure_to_base64(draw)


def model_importance_frame(model_bundle: dict) -> pd.DataFrame:
    model = model_bundle["model"]
    feature_columns = model_bundle["feature_columns"]
    if hasattr(model, "feature_importances_"):
        importance = np.asarray(model.feature_importances_, dtype=float)
    else:
        importance = np.zeros(len(feature_columns), dtype=float)

    frame = pd.DataFrame({"feature": feature_columns, "importance": importance})
    total = frame["importance"].sum()
    if total > 0:
        frame["importance_percent"] = frame["importance"] / total * 100
    else:
        frame["importance_percent"] = 0.0

    def category(feature: str) -> str:
        if feature.startswith("lag_"):
            return "Rezagos"
        if feature.startswith("rolling_"):
            return "Ventanas moviles"
        if feature in {"hour_sin", "hour_cos"}:
            return "Hora"
        if feature.startswith("dayofweek") or feature == "is_weekend":
            return "Semana"
        if feature.startswith("month"):
            return "Mes"
        return "Otros"

    frame["category"] = frame["feature"].map(category)
    return frame.sort_values("importance_percent", ascending=False)


def plot_feature_importance(importance: pd.DataFrame) -> str:
    def draw() -> None:
        top = importance.head(15).sort_values("importance_percent")
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.barh(top["feature"], top["importance_percent"], color="#2563eb")
        ax.set_title("Variables mas usadas por el modelo")
        ax.set_xlabel("Importancia relativa (%)")
        ax.grid(True, axis="x", alpha=0.25)

    return figure_to_base64(draw)


def plot_learning_heatmap(importance: pd.DataFrame) -> str:
    def draw() -> None:
        categories = ["Rezagos", "Ventanas moviles", "Hora", "Semana", "Mes", "Otros"]
        grouped = (
            importance.groupby("category")["importance_percent"]
            .sum()
            .reindex(categories)
            .fillna(0.0)
        )
        matrix = grouped.to_numpy().reshape(1, -1)
        fig, ax = plt.subplots(figsize=(10, 2.2))
        image = ax.imshow(matrix, aspect="auto", cmap="Blues")
        ax.set_title("Mapa de calor: que tipo de senales aprendio el modelo")
        ax.set_xticks(range(len(categories)))
        ax.set_xticklabels(categories, rotation=25, ha="right")
        ax.set_yticks([0])
        ax.set_yticklabels(["Importancia"])
        for idx, value in enumerate(grouped.values):
            ax.text(idx, 0, f"{value:.1f}%", ha="center", va="center", color="#111827")
        fig.colorbar(image, ax=ax, label="Importancia %")

    return figure_to_base64(draw)


def build_interpretation(metrics: dict, validation: dict, importance: pd.DataFrame) -> str:
    top_features = importance.head(5)
    category_summary = importance.groupby("category")["importance_percent"].sum().sort_values(ascending=False)
    top_feature_text = ", ".join(
        f"{row.feature} ({row.importance_percent:.1f}%)" for row in top_features.itertuples()
    )
    top_category = category_summary.index[0] if len(category_summary) else "N/A"
    top_category_value = category_summary.iloc[0] if len(category_summary) else 0.0

    baseline_state = (
        "El modelo esta superando el baseline de la hora anterior."
        if metrics.get("beats_baseline")
        else "El modelo NO esta superando el baseline de la hora anterior."
    )
    data_state = (
        "El historico no tiene huecos, duplicados, nulos ni precios negativos."
        if validation.get("missing_hours", 0) == 0
        and validation.get("duplicated_timestamps", 0) == 0
        and validation.get("null_prices", 0) == 0
        and validation.get("negative_prices", 0) == 0
        else "El historico tiene alertas de calidad que deben revisarse."
    )

    return f"""
    <section class="panel">
      <h2>Que esta pasando con el modelo</h2>
      <p>{html.escape(data_state)}</p>
      <p>{html.escape(baseline_state)} La mejora de RMSE frente al baseline es de
      <strong>{metrics.get("rmse_improvement_vs_baseline_percent", 0):.2f}%</strong>.</p>
      <p>La senal dominante que esta aprendiendo es <strong>{html.escape(top_category)}</strong>
      con <strong>{top_category_value:.1f}%</strong> de la importancia total.</p>
      <p>Variables mas influyentes: {html.escape(top_feature_text)}.</p>
      <p>Esto indica si el modelo esta dependiendo mas de memoria reciente del precio,
      patrones calendario o estadisticas moviles del historico.</p>
    </section>
    """


def image_section(title: str, image_base64: str) -> str:
    return f"""
    <section class="panel">
      <h2>{html.escape(title)}</h2>
      <img src="data:image/png;base64,{image_base64}" alt="{html.escape(title)}">
    </section>
    """


def generate_dashboard(input_dir: Path, output_path: Path) -> None:
    hourly = pd.read_csv(input_dir / "data_hourly.csv", parse_dates=["datetime"])
    test_predictions = pd.read_csv(input_dir / "test_predictions.csv", parse_dates=["datetime"])
    forecast = pd.read_csv(input_dir / "forecast.csv", parse_dates=["datetime"])
    metrics = load_json(input_dir / "metrics.json")
    validation = load_json(input_dir / "dataset_validation.json")
    model_bundle = joblib.load(input_dir / "model.joblib")
    importance = model_importance_frame(model_bundle)

    cards = "\n".join(
        [
            metric_card("Periodo historico", f"{validation['start'][:10]} a {validation['end'][:10]}", f"{validation['rows']:,} horas"),
            metric_card("RMSE modelo", money(metrics["rmse"]), "Menor es mejor"),
            metric_card("RMSE baseline", money(metrics["baseline_lag_1h_rmse"]), "Precio hora anterior"),
            metric_card("Mejora vs baseline", f"{metrics['rmse_improvement_vs_baseline_percent']:.2f}%", f"beats_baseline={metrics['beats_baseline']}"),
            metric_card("MAPE", f"{metrics['mape_percent']:.2f}%", "Error porcentual medio"),
            metric_card("R2", f"{metrics['r2']:.3f}", f"{metrics['backend']} / {metrics['device']}"),
            metric_card("Calidad dataset", "OK" if validation["missing_hours"] == 0 and validation["null_prices"] == 0 else "Revisar", f"{validation['missing_hours']} huecos, {validation['null_prices']} nulos"),
            metric_card("Valores extremos", validation["extreme_high_rows_iqr_3x"], "Regla IQR 3x"),
        ]
    )

    sections = [
        build_interpretation(metrics, validation, importance),
        image_section("Historico", plot_history(hourly)),
        image_section("Mapa de calor historico", plot_history_heatmap(hourly)),
        image_section("Validacion del modelo", plot_predictions(test_predictions)),
        image_section("Mapa de calor de errores", plot_error_heatmap(test_predictions)),
        image_section("Pronostico", plot_forecast(hourly, forecast)),
        image_section("Importancia de variables", plot_feature_importance(importance)),
        image_section("Mapa de calor de aprendizaje", plot_learning_heatmap(importance)),
    ]

    html_doc = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dashboard Precio de Bolsa</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --ink: #111827;
      --muted: #6b7280;
      --line: #d7dde8;
      --accent: #0f766e;
    }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    header {{
      padding: 28px 32px 18px;
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }}
    header h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      letter-spacing: 0;
    }}
    header p {{
      margin: 0;
      color: var(--muted);
    }}
    main {{
      max-width: 1220px;
      margin: 0 auto;
      padding: 24px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .card, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
    }}
    .card {{
      padding: 14px 16px;
    }}
    .card span, .card small {{
      display: block;
      color: var(--muted);
      font-size: 13px;
    }}
    .card strong {{
      display: block;
      margin: 6px 0;
      font-size: 22px;
    }}
    .panel {{
      padding: 18px;
      margin-bottom: 18px;
    }}
    .panel h2 {{
      margin: 0 0 12px;
      font-size: 19px;
    }}
    .panel p {{
      max-width: 920px;
      line-height: 1.48;
      color: #374151;
    }}
    img {{
      width: 100%;
      height: auto;
      display: block;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Dashboard Precio de Bolsa Nacional</h1>
    <p>Historico, validacion temporal, pronostico y lectura del aprendizaje del modelo.</p>
  </header>
  <main>
    <section class="cards">
      {cards}
    </section>
    {''.join(sections)}
  </main>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_doc, encoding="utf-8")


def main() -> None:
    args = parse_args()
    generate_dashboard(Path(args.input_dir), Path(args.output))
    print(f"Dashboard generado en: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
