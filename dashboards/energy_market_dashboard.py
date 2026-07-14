"""Build the executive, self-contained Colombia Energy Intelligence dashboard.

The dashboard intentionally reads only curated analytical outputs. This keeps the
BI layer decoupled from extraction and model training and makes the artifact easy
to publish as a single HTML file.
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


NAVY = "#081c2c"
BLUE = "#00a6d6"
GREEN = "#2dd4a8"
ORANGE = "#ffb547"
MUTED = "#64748b"
PRICE_COLUMN = "precio_bolsa_cop_kwh"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera el dashboard ejecutivo del portafolio.")
    parser.add_argument("--price-dir", default="outputs/precio_bolsa")
    parser.add_argument("--demand-dir", default="outputs/consumo_actores")
    parser.add_argument("--output", default="portfolio/dashboard.html")
    parser.add_argument("--cover", default="portfolio/cover.png")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def figure(
    plotter: Callable[[], None], output: Path | None = None, facecolor: str = "white"
) -> str:
    plt.close("all")
    plotter()
    buffer = io.BytesIO()
    if facecolor == "white":
        plt.tight_layout()
    plt.savefig(buffer, format="png", dpi=150, bbox_inches="tight", facecolor=facecolor)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(buffer.getvalue())
    plt.close("all")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def style_axis(ax: plt.Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#dbe3ec")
    ax.grid(axis="y", alpha=0.16)
    ax.tick_params(colors=MUTED, labelsize=9)


def plot_price_forecast(history: pd.DataFrame, forecast: pd.DataFrame) -> str:
    def draw() -> None:
        recent = history.tail(24 * 21)
        fig, ax = plt.subplots(figsize=(12, 4.2))
        ax.plot(recent.datetime, recent[PRICE_COLUMN], color=NAVY, lw=1.2, label="Real")
        ax.plot(
            forecast.datetime,
            forecast.predicted_precio_bolsa_cop_kwh,
            color=GREEN,
            lw=2.5,
            label="Forecast 24 h",
        )
        ax.axvline(forecast.datetime.min(), color=ORANGE, ls="--", lw=1)
        ax.set_title("Precio de bolsa: histórico reciente y siguiente horizonte", loc="left", weight="bold")
        ax.set_ylabel("COP/kWh")
        ax.legend(frameon=False, ncol=2)
        style_axis(ax)

    return figure(draw)


def plot_model_validation(predictions: pd.DataFrame) -> str:
    def draw() -> None:
        sample = predictions.tail(24 * 10)
        fig, ax = plt.subplots(figsize=(12, 4.2))
        ax.plot(sample.datetime, sample.target_price, color=NAVY, lw=1.5, label="Real")
        ax.plot(sample.datetime, sample.prediction_price, color=BLUE, lw=1.5, label="XGBoost")
        ax.set_title("Backtesting temporal: real vs. predicción", loc="left", weight="bold")
        ax.set_ylabel("COP/kWh")
        ax.legend(frameon=False, ncol=2)
        style_axis(ax)

    return figure(draw)


def plot_ranking(ranking: pd.DataFrame) -> str:
    def draw() -> None:
        top = ranking.head(10).sort_values("share_percent")
        labels = top.agent_name.str.slice(0, 31)
        fig, ax = plt.subplots(figsize=(10, 5.1))
        bars = ax.barh(labels, top.share_percent, color=BLUE)
        ax.bar_label(bars, fmt="%.1f%%", padding=4, color=NAVY, fontsize=9)
        ax.set_title("Participación de la demanda comercial — Top 10", loc="left", weight="bold")
        ax.set_xlabel("Participación sobre la demanda analizada")
        style_axis(ax)

    return figure(draw)


def plot_monthly(monthly: pd.DataFrame, ranking: pd.DataFrame) -> str:
    def draw() -> None:
        codes = ranking.head(5).agent_code
        subset = monthly[monthly.agent_code.isin(codes)].copy()
        pivot = subset.pivot(index="month", columns="agent_name", values="demanda_comercial_kwh")
        indexed = pivot.div(pivot.iloc[0]).mul(100)
        fig, ax = plt.subplots(figsize=(12, 4.5))
        for column in indexed:
            ax.plot(indexed.index, indexed[column], lw=1.7, label=str(column)[:22])
        ax.axhline(100, color="#cbd5e1", lw=1, ls="--")
        ax.set_title("Evolución mensual del Top 5 (índice: primer mes = 100)", loc="left", weight="bold")
        ax.set_ylabel("Índice de demanda")
        ax.legend(frameon=False, fontsize=8, ncol=2)
        style_axis(ax)

    return figure(draw)


def plot_cover(metrics: dict, validation: dict, ranking: pd.DataFrame, output: Path) -> str:
    def draw() -> None:
        fig = plt.figure(figsize=(12, 6.28))
        fig.patch.set_facecolor(NAVY)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor(NAVY)
        ax.axis("off")
        ax.text(.07, .82, "COLOMBIA ENERGY", color="white", fontsize=30, weight="bold")
        ax.text(.07, .72, "INTELLIGENCE", color=GREEN, fontsize=30, weight="bold")
        ax.text(.07, .61, "Data Engineering · Machine Learning · Business Intelligence", color="#b8c8d8", fontsize=14)
        cards = [
            ("39K+", "registros horarios validados"),
            (f"{metrics['r2']:.2f}", "R² en backtesting temporal"),
            (f"{metrics['rmse_improvement_vs_baseline_percent']:.1f}%", "mejora vs. baseline"),
            (f"{ranking.head(5).share_percent.sum():.1f}%", "participación del Top 5"),
        ]
        for index, (value, label) in enumerate(cards):
            x = .07 + index * .225
            ax.text(x, .39, value, color="white", fontsize=23, weight="bold")
            ax.text(x, .31, label, color="#9fb2c4", fontsize=9.5, wrap=True)
        ax.text(.07, .12, f"Fuente: API pública XM  |  Datos: {validation['start'][:10]} — {validation['end'][:10]}", color="#70869a", fontsize=10)
        ax.add_patch(plt.Rectangle((.07, .52), .18, .008, color=ORANGE, transform=ax.transAxes))

    return figure(draw, output, facecolor=NAVY)


def save_slide(fig: plt.Figure, path: Path) -> None:
    """Save an exact 16:9 social card without browser-dependent rendering."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, facecolor=fig.get_facecolor(), bbox_inches=None)
    plt.close(fig)


def slide_header(fig: plt.Figure, number: str, title: str, subtitle: str) -> None:
    fig.text(.055, .91, f"COLOMBIA ENERGY INTELLIGENCE  ·  {number}", color=BLUE, fontsize=9, weight="bold")
    fig.text(.055, .82, title, color=NAVY, fontsize=25, weight="bold")
    fig.text(.055, .765, subtitle, color=MUTED, fontsize=10.5)


def social_slides(
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    predictions: pd.DataFrame,
    metrics: dict,
    validation: dict,
    ranking: pd.DataFrame,
    output_dir: Path,
) -> list[Path]:
    """Generate high-resolution slides with the strongest portfolio insights."""
    price = history.set_index("datetime")[PRICE_COLUMN]
    forecast_values = forecast["predicted_precio_bolsa_cop_kwh"]
    last_24 = price.tail(24).mean()
    forecast_avg = forecast_values.mean()
    forecast_delta = (forecast_avg / last_24 - 1) * 100
    total_twh = ranking.total_demand_kwh.sum() / 1e9
    top5 = ranking.head(5).share_percent.sum()
    top10 = ranking.head(10).share_percent.sum()
    paths: list[Path] = []

    # 01 — executive overview
    fig = plt.figure(figsize=(12, 6.75), facecolor="#f7fafc")
    slide_header(fig, "01", "Del dato público a una decisión", "Una solución reproducible que une Data Engineering, Machine Learning y BI.")
    cards = [
        ("39.120", "horas de precio", "0 huecos · 0 duplicados"),
        (f"{metrics['r2']:.3f}", "R² temporal", f"MAPE {metrics['mape_percent']:.2f}%"),
        (f"{metrics['rmse_improvement_vs_baseline_percent']:.1f}%", "mejora vs. baseline", "persistencia de 1 hora"),
        (f"{total_twh:.1f} TWh", "demanda analizada", f"{len(ranking)} agentes"),
    ]
    for i, (value, label, detail) in enumerate(cards):
        x = .055 + i * .232
        ax = fig.add_axes([x, .46, .205, .22])
        ax.set_facecolor("white")
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values(): spine.set_color("#e1e9f0")
        ax.text(.07, .68, value, transform=ax.transAxes, color=NAVY, fontsize=22, weight="bold")
        ax.text(.07, .40, label, transform=ax.transAxes, color="#334b5e", fontsize=10, weight="bold")
        ax.text(.07, .17, detail, transform=ax.transAxes, color=MUTED, fontsize=8.5)
    steps = [("API XM", "Ingesta"), ("Pandas", "Transformación"), ("Data Quality", "Confianza"), ("XGBoost", "Predicción"), ("Dashboard", "Decisión")]
    for i, (tech, role) in enumerate(steps):
        x = .06 + i * .185
        fig.text(x, .30, tech, color=NAVY, fontsize=10, weight="bold")
        fig.text(x, .265, role, color=MUTED, fontsize=8)
        if i < 4: fig.text(x + .13, .285, "→", color=GREEN, fontsize=18, weight="bold")
    fig.text(.055, .105, "Fuente: API pública XM  ·  Precio 2022–2026  ·  Demanda 2022–2024", color="#8194a5", fontsize=8.5)
    path = output_dir / "01_resumen_ejecutivo.png"; save_slide(fig, path); paths.append(path)

    # 02 — forecast and honest evaluation
    fig = plt.figure(figsize=(12, 6.75), facecolor="white")
    slide_header(fig, "02", "Forecast horario con evaluación honesta", "El modelo respeta el orden temporal y se compara contra una referencia simple.")
    ax = fig.add_axes([.055, .20, .63, .48])
    recent = price.tail(24 * 10)
    ax.plot(recent.index, recent.values, color=NAVY, lw=1.25, label="Histórico")
    ax.plot(forecast.datetime, forecast_values, color=GREEN, lw=2.5, label="Próximas 24 h")
    ax.axvline(forecast.datetime.min(), color=ORANGE, ls="--", lw=1)
    ax.set_ylabel("COP/kWh", color=MUTED); ax.legend(frameon=False, loc="upper left", ncol=2)
    style_axis(ax)
    side = [
        (f"{forecast_avg:,.1f}", "COP/kWh promedio esperado"),
        (f"{forecast_delta:+.1f}%", "vs. últimas 24 horas"),
        (f"{forecast_values.min():,.1f} — {forecast_values.max():,.1f}", "rango del forecast"),
        (f"{metrics['test_rows']:,}", "horas fuera de muestra"),
    ]
    for i, (value, label) in enumerate(side):
        y = .64 - i * .125
        fig.text(.735, y, value, color=NAVY, fontsize=17, weight="bold")
        fig.text(.735, y - .035, label, color=MUTED, fontsize=8.5)
    fig.text(.055, .09, "Corte del histórico: 18 jun 2026 · Horizonte demostrativo, no recomendación operativa.", color="#8194a5", fontsize=8.5)
    path = output_dir / "02_forecast_precio.png"; save_slide(fig, path); paths.append(path)

    # 03 — demand concentration
    fig = plt.figure(figsize=(12, 6.75), facecolor="#f7fafc")
    slide_header(fig, "03", "¿Quién concentra la demanda comercial?", "241,6 TWh resumidos en una vista ejecutiva de participación.")
    ax = fig.add_axes([.14, .17, .50, .53])
    top = ranking.head(8).sort_values("share_percent")
    short_names = {
        "ENDC": "ENEL Colombia", "EPMC": "EPM", "CMMC": "Caribemar",
        "CSSC": "Air-e", "EPSC": "Celsia Colombia", "ISGC": "Isagen",
        "EMIC": "Emcali", "GECC": "Gecelca",
    }
    labels = [f"{row.agent_code} · {short_names.get(row.agent_code, row.agent_name[:18])}" for row in top.itertuples()]
    bars = ax.barh(labels, top.share_percent, color=[BLUE] * 7 + [GREEN])
    ax.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=8, color=NAVY)
    ax.set_xlabel("Participación", color=MUTED); style_axis(ax)
    fig.text(.70, .63, f"{top5:.1f}%", color=NAVY, fontsize=25, weight="bold")
    fig.text(.70, .585, "concentración Top 5", color=MUTED, fontsize=9)
    fig.text(.70, .46, f"{top10:.1f}%", color=NAVY, fontsize=25, weight="bold")
    fig.text(.70, .415, "concentración Top 10", color=MUTED, fontsize=9)
    fig.text(.70, .29, f"{len(ranking)}", color=NAVY, fontsize=25, weight="bold")
    fig.text(.70, .245, "agentes observados", color=MUTED, fontsize=9)
    fig.text(.055, .08, "Demanda comercial acumulada · Corte: dic 2024 · Participación sobre el universo analizado.", color="#8194a5", fontsize=8.5)
    path = output_dir / "03_demanda_agentes.png"; save_slide(fig, path); paths.append(path)

    return paths


def card(label: str, value: str, detail: str) -> str:
    return f"<article class='card'><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong><small>{html.escape(detail)}</small></article>"


def build_dashboard(price_dir: Path, demand_dir: Path, output: Path, cover: Path) -> None:
    history = pd.read_csv(price_dir / "data_hourly.csv", parse_dates=["datetime"])
    forecast = pd.read_csv(price_dir / "forecast.csv", parse_dates=["datetime"])
    predictions = pd.read_csv(price_dir / "test_predictions.csv", parse_dates=["datetime"])
    metrics = load_json(price_dir / "metrics.json")
    validation = load_json(price_dir / "dataset_validation.json")
    ranking = pd.read_csv(demand_dir / "top_consumidores.csv")
    monthly = pd.read_csv(demand_dir / "consumo_mensual_top.csv", parse_dates=["month"])

    top5_share = ranking.head(5).share_percent.sum()
    hhi = float(np.square(ranking.share_percent).sum())
    cards = "".join([
        card("Calidad de datos", "100%", f"{validation['rows']:,} horas · 0 huecos"),
        card("R² temporal", f"{metrics['r2']:.3f}", f"{metrics['test_rows']:,} observaciones de test"),
        card("Mejora vs. baseline", f"{metrics['rmse_improvement_vs_baseline_percent']:.1f}%", "RMSE contra persistencia"),
        card("MAPE", f"{metrics['mape_percent']:.1f}%", "Error porcentual medio"),
        card("Concentración Top 5", f"{top5_share:.1f}%", "Demanda comercial acumulada"),
        card("Índice HHI", f"{hhi:,.0f}", "Concentración del mercado analizado"),
    ])
    images = {
        "price": plot_price_forecast(history, forecast),
        "validation": plot_model_validation(predictions),
        "ranking": plot_ranking(ranking),
        "monthly": plot_monthly(monthly, ranking),
    }
    plot_cover(metrics, validation, ranking, cover)
    slides = social_slides(history, forecast, predictions, metrics, validation, ranking, output.parent / "screenshots")
    slide_images = [base64.b64encode(path.read_bytes()).decode("ascii") for path in slides]

    document = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><title>Colombia Energy Intelligence</title>
<style>
:root{{--navy:{NAVY};--blue:{BLUE};--green:{GREEN};--bg:#f1f5f9;--muted:{MUTED}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:#142536;font-family:Inter,Segoe UI,Arial,sans-serif}}
header{{background:var(--navy);color:white;padding:52px max(6vw,24px)}} header em{{color:var(--green);font-style:normal}} header h1{{font-size:clamp(34px,5vw,62px);margin:8px 0}} header p{{color:#b8c8d8;max-width:750px;font-size:18px;line-height:1.5}}
main{{max-width:1280px;margin:auto;padding:28px}} .eyebrow{{text-transform:uppercase;letter-spacing:2px;color:var(--blue);font-weight:700;font-size:12px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:12px;margin:0 0 22px}} .card,.panel{{background:white;border:1px solid #dce5ed;border-radius:14px;box-shadow:0 4px 18px #0c22320a}}
.card{{padding:19px}} .card span,.card small{{display:block;color:var(--muted);font-size:12px}} .card strong{{display:block;font-size:25px;margin:8px 0;color:var(--navy)}}
.panel{{padding:24px;margin:18px 0}} .panel h2{{margin:0 0 8px;color:var(--navy)}} .panel p{{line-height:1.65;color:#536578}} img{{width:100%;display:block}}
.gallery{{display:grid;gap:18px}} .capture{{padding:0;overflow:hidden;position:relative}} .capture img{{aspect-ratio:16/9;object-fit:cover}} .capture:after{{content:'PNG 16:9';position:absolute;right:14px;top:14px;background:#081c2cdd;color:white;padding:6px 9px;border-radius:6px;font-size:10px;letter-spacing:1px}}
.architecture{{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin-top:22px}} .step{{background:#eef7fa;border-top:4px solid var(--blue);padding:16px;border-radius:8px;font-size:13px}} .step b{{display:block;color:var(--navy);margin-bottom:5px}}
footer{{text-align:center;color:var(--muted);padding:26px}} @media(max-width:760px){{.architecture{{grid-template-columns:1fr}}}}
</style></head><body>
<header><div class='eyebrow'>Proyecto de portafolio end-to-end</div><h1>Colombia Energy <em>Intelligence</em></h1><p>De datos públicos del mercado eléctrico a decisiones: pipeline reproducible, calidad de datos, forecasting horario y una capa ejecutiva de BI.</p></header>
<main><section class='panel'><div class='eyebrow'>Capturas listas para publicar</div><h2>Una historia en tres láminas</h2><p>Cada imagen está renderizada en 16:9 y alta resolución. Puedes abrirla desde <code>portfolio/screenshots</code> o capturarla directamente aquí.</p><div class='gallery'>
<article class='panel capture'><img src='data:image/png;base64,{slide_images[0]}' alt='Resumen ejecutivo'></article>
<article class='panel capture'><img src='data:image/png;base64,{slide_images[1]}' alt='Forecast del precio'></article>
<article class='panel capture'><img src='data:image/png;base64,{slide_images[2]}' alt='Demanda por agentes'></article></div></section>
<section class='cards'>{cards}</section>
<section class='panel'><div class='eyebrow'>Arquitectura</div><h2>Del API al insight, con responsabilidades separadas</h2><div class='architecture'>
<div class='step'><b>1 · Ingesta</b>API pública XM y extracción por ventanas</div><div class='step'><b>2 · Transformación</b>Wide-to-long y estandarización horaria</div><div class='step'><b>3 · Calidad</b>Continuidad, nulos, duplicados y rangos</div><div class='step'><b>4 · Analítica</b>Features temporales, XGBoost y backtesting</div><div class='step'><b>5 · BI</b>Data marts, KPIs y dashboard ejecutivo</div></div></section>
<section class='panel'><div class='eyebrow'>Forecasting</div><h2>¿Qué puede pasar con el precio?</h2><p>El modelo usa rezagos, ventanas móviles y señales cíclicas. La evaluación respeta el orden temporal y compara contra un baseline de persistencia.</p><img src='data:image/png;base64,{images['price']}'></section>
<section class='panel'><img src='data:image/png;base64,{images['validation']}'></section>
<section class='panel'><div class='eyebrow'>Business Intelligence</div><h2>¿Quién concentra la demanda comercial?</h2><p>La capa de BI resume millones de observaciones en indicadores accionables de participación y concentración.</p><img src='data:image/png;base64,{images['ranking']}'></section>
<section class='panel'><img src='data:image/png;base64,{images['monthly']}'></section>
<section class='panel'><div class='eyebrow'>Lectura responsable</div><h2>Alcance</h2><p>Demostración técnica con datos públicos. El forecast no incorpora clima, hidrología, restricciones operativas ni variables exógenas y no constituye recomendación financiera ni operativa. Los resultados reflejan el corte de datos indicado.</p></section></main>
<footer>Python · Pandas · XGBoost · scikit-learn · Matplotlib · Data Quality · BI | Fuente: XM</footer></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")


def main() -> None:
    args = parse_args()
    build_dashboard(Path(args.price_dir), Path(args.demand_dir), Path(args.output), Path(args.cover))
    print(f"Dashboard: {Path(args.output).resolve()}")
    print(f"Portada: {Path(args.cover).resolve()}")


if __name__ == "__main__":
    main()
