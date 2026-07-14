"""Train a forecasting model for Colombia's spot energy price.

The script consumes XM's public API through the local pydataxm package,
normalizes the hourly wide response into a time series, trains a one-step
ahead model, and iteratively forecasts the next N hours.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from pydataxm.pydataxm import ReadDB


PRICE_METRIC_ID = "PrecBolsNaci"
PRICE_ENTITY = "Sistema"
PRICE_COLUMN = "precio_bolsa_cop_kwh"


@dataclass(frozen=True)
class TrainResult:
    model: Any
    feature_columns: list[str]
    metrics: dict[str, float]
    validation: dict[str, Any]
    test_predictions: pd.DataFrame


def parse_args() -> argparse.Namespace:
    yesterday = date.today() - timedelta(days=1)
    parser = argparse.ArgumentParser(
        description="Entrena un modelo para predecir el Precio de Bolsa Nacional de XM."
    )
    parser.add_argument("--start-date", default="2022-01-01", help="Fecha inicial YYYY-MM-DD.")
    parser.add_argument(
        "--end-date",
        default=yesterday.isoformat(),
        help="Fecha final YYYY-MM-DD. Por defecto usa ayer.",
    )
    parser.add_argument(
        "--forecast-hours",
        type=int,
        default=24,
        help="Horas futuras a pronosticar iterativamente.",
    )
    parser.add_argument(
        "--test-days",
        type=int,
        default=60,
        help="Dias finales reservados para validacion temporal.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/precio_bolsa",
        help="Directorio donde se guardan datos, modelo y predicciones.",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Usa data_hourly.csv si existe en output-dir.",
    )
    parser.add_argument(
        "--backend",
        choices=["sklearn", "xgboost"],
        default="xgboost",
        help="Motor de entrenamiento. xgboost permite usar CUDA.",
    )
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda"],
        default="cuda",
        help="Dispositivo para xgboost. sklearn siempre usa CPU.",
    )
    parser.add_argument(
        "--strict-validation",
        action="store_true",
        help="Falla la ejecucion si el dataset tiene huecos horarios, duplicados o valores invalidos.",
    )
    return parser.parse_args()


def fetch_price_data(start_date: str, end_date: str) -> pd.DataFrame:
    api = ReadDB()
    raw = api.request_data(PRICE_METRIC_ID, PRICE_ENTITY, start_date, end_date)
    if raw.empty:
        raise RuntimeError("La API XM no retorno datos para el rango solicitado.")
    return raw


def hourly_wide_to_long(raw: pd.DataFrame) -> pd.DataFrame:
    hour_columns = sorted(
        [col for col in raw.columns if col.startswith("Values_Hour")],
        key=lambda name: int(name.replace("Values_Hour", "")),
    )
    if not hour_columns:
        raise ValueError("No se encontraron columnas Values_HourXX en la respuesta de XM.")

    long_df = raw.melt(
        id_vars=["Date"],
        value_vars=hour_columns,
        var_name="hour_col",
        value_name=PRICE_COLUMN,
    )
    long_df["hour"] = long_df["hour_col"].str.extract(r"(\d{2})").astype(int) - 1
    long_df["datetime"] = pd.to_datetime(long_df["Date"]) + pd.to_timedelta(
        long_df["hour"], unit="h"
    )
    long_df = long_df[["datetime", PRICE_COLUMN]].sort_values("datetime")
    long_df[PRICE_COLUMN] = pd.to_numeric(long_df[PRICE_COLUMN], errors="coerce")
    return long_df.dropna().drop_duplicates("datetime").reset_index(drop=True)


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    dt = result["datetime"]
    hour = dt.dt.hour
    dayofweek = dt.dt.dayofweek
    month = dt.dt.month

    result["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    result["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    result["dayofweek_sin"] = np.sin(2 * np.pi * dayofweek / 7)
    result["dayofweek_cos"] = np.cos(2 * np.pi * dayofweek / 7)
    result["month_sin"] = np.sin(2 * np.pi * month / 12)
    result["month_cos"] = np.cos(2 * np.pi * month / 12)
    result["is_weekend"] = dayofweek.isin([5, 6]).astype(int)
    return result


def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    result = add_calendar_features(df)
    price = result[PRICE_COLUMN]

    for lag in [1, 2, 3, 24, 48, 72, 168]:
        result[f"lag_{lag}h"] = price.shift(lag)

    shifted = price.shift(1)
    for window in [24, 72, 168]:
        rolling = shifted.rolling(window=window, min_periods=window)
        result[f"rolling_{window}h_mean"] = rolling.mean()
        result[f"rolling_{window}h_std"] = rolling.std()
        result[f"rolling_{window}h_min"] = rolling.min()
        result[f"rolling_{window}h_max"] = rolling.max()

    # Each row represents the hour being predicted. All predictors are shifted,
    # so the target is never present in the feature matrix.
    result["target_price"] = price
    return result


def make_supervised_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    supervised = add_lag_features(df).dropna().reset_index(drop=True)
    excluded = {"datetime", PRICE_COLUMN, "target_price"}
    feature_columns = [col for col in supervised.columns if col not in excluded]
    return supervised, feature_columns


def validate_hourly_dataset(hourly_df: pd.DataFrame) -> dict[str, Any]:
    ordered = hourly_df.sort_values("datetime").reset_index(drop=True)
    expected_range = pd.date_range(
        ordered["datetime"].min(),
        ordered["datetime"].max(),
        freq="h",
    )
    observed_datetimes = pd.DatetimeIndex(ordered["datetime"])
    missing_datetimes = expected_range.difference(observed_datetimes)
    duplicated_rows = int(ordered["datetime"].duplicated().sum())
    null_prices = int(ordered[PRICE_COLUMN].isna().sum())
    invalid_prices = int((ordered[PRICE_COLUMN] < 0).sum())
    price = ordered[PRICE_COLUMN]
    q1 = price.quantile(0.25)
    q3 = price.quantile(0.75)
    iqr = q3 - q1
    upper_outlier_limit = q3 + 3 * iqr
    extreme_high_rows = int((price > upper_outlier_limit).sum())

    return {
        "rows": int(len(ordered)),
        "start": ordered["datetime"].min().isoformat(),
        "end": ordered["datetime"].max().isoformat(),
        "expected_hourly_rows": int(len(expected_range)),
        "missing_hours": int(len(missing_datetimes)),
        "first_missing_hours": [value.isoformat() for value in missing_datetimes[:10]],
        "duplicated_timestamps": duplicated_rows,
        "null_prices": null_prices,
        "negative_prices": invalid_prices,
        "extreme_high_rows_iqr_3x": extreme_high_rows,
        "min_price": float(price.min()),
        "median_price": float(price.median()),
        "mean_price": float(price.mean()),
        "max_price": float(price.max()),
    }


def raise_if_invalid(validation: dict[str, Any]) -> None:
    blockers = []
    if validation["missing_hours"]:
        blockers.append(f"{validation['missing_hours']} horas faltantes")
    if validation["duplicated_timestamps"]:
        blockers.append(f"{validation['duplicated_timestamps']} timestamps duplicados")
    if validation["null_prices"]:
        blockers.append(f"{validation['null_prices']} precios nulos")
    if validation["negative_prices"]:
        blockers.append(f"{validation['negative_prices']} precios negativos")

    if blockers:
        raise ValueError("Validacion de dataset fallida: " + ", ".join(blockers))


def build_model(backend: str, device: str) -> Any:
    if backend == "sklearn":
        return HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_iter=500,
            l2_regularization=0.01,
            random_state=42,
        )

    try:
        from xgboost import XGBRegressor
    except ImportError as exc:
        raise RuntimeError(
            "Para usar --backend xgboost instala xgboost en el entorno."
        ) from exc

    return XGBRegressor(
        n_estimators=700,
        max_depth=6,
        learning_rate=0.03,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        tree_method="hist",
        device=device,
        random_state=42,
        n_jobs=-1,
    )


def train_model(
    hourly_df: pd.DataFrame,
    test_days: int,
    backend: str,
    device: str,
    strict_validation: bool,
) -> TrainResult:
    validation = validate_hourly_dataset(hourly_df)
    if strict_validation:
        raise_if_invalid(validation)

    supervised, feature_columns = make_supervised_frame(hourly_df)
    if supervised.empty:
        raise ValueError("No hay suficientes datos para construir rezagos y entrenar.")

    test_start = supervised["datetime"].max() - pd.Timedelta(days=test_days)
    train_df = supervised[supervised["datetime"] < test_start]
    test_df = supervised[supervised["datetime"] >= test_start]

    if len(train_df) < 500 or len(test_df) < 24:
        split_index = int(len(supervised) * 0.8)
        train_df = supervised.iloc[:split_index]
        test_df = supervised.iloc[split_index:]

    model = build_model(backend, device)
    model.fit(train_df[feature_columns], train_df["target_price"])

    y_true = test_df["target_price"]
    y_pred = model.predict(test_df[feature_columns])
    baseline_pred = test_df["lag_1h"]
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    baseline_rmse = np.sqrt(mean_squared_error(y_true, baseline_pred))
    mape = np.mean(np.abs((y_true - y_pred) / y_true.replace(0, np.nan))) * 100

    metrics = {
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "backend": backend,
        "device": device if backend == "xgboost" else "cpu",
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(rmse),
        "baseline_lag_1h_rmse": float(baseline_rmse),
        "beats_baseline": bool(rmse < baseline_rmse),
        "rmse_improvement_vs_baseline_percent": float(
            (baseline_rmse - rmse) / baseline_rmse * 100
        ),
        "mape_percent": float(mape),
        "r2": float(r2_score(y_true, y_pred)),
        "test_start": test_df["datetime"].min().isoformat(),
        "test_end": test_df["datetime"].max().isoformat(),
        "feature_count": int(len(feature_columns)),
    }

    test_predictions = test_df[["datetime", PRICE_COLUMN, "target_price"]].copy()
    test_predictions["prediction_price"] = y_pred
    test_predictions["baseline_lag_1h"] = baseline_pred.to_numpy()
    return TrainResult(model, feature_columns, metrics, validation, test_predictions)


def _single_feature_row(history: pd.DataFrame, next_datetime: pd.Timestamp) -> pd.DataFrame:
    placeholder = pd.concat(
        [
            history,
            pd.DataFrame({"datetime": [next_datetime], PRICE_COLUMN: [np.nan]}),
        ],
        ignore_index=True,
    )
    features = add_lag_features(placeholder).tail(1)
    return features


def forecast_next_hours(
    model: Any,
    feature_columns: Iterable[str],
    hourly_df: pd.DataFrame,
    forecast_hours: int,
) -> pd.DataFrame:
    history = hourly_df[["datetime", PRICE_COLUMN]].copy().sort_values("datetime")
    predictions: list[dict[str, object]] = []
    feature_columns = list(feature_columns)

    for _ in range(forecast_hours):
        next_datetime = history["datetime"].max() + pd.Timedelta(hours=1)
        feature_row = _single_feature_row(history, next_datetime)
        prediction = float(model.predict(feature_row[feature_columns])[0])
        predictions.append(
            {
                "datetime": next_datetime,
                "predicted_precio_bolsa_cop_kwh": prediction,
            }
        )
        history = pd.concat(
            [
                history,
                pd.DataFrame({"datetime": [next_datetime], PRICE_COLUMN: [prediction]}),
            ],
            ignore_index=True,
        )

    return pd.DataFrame(predictions)


def save_outputs(
    output_dir: Path,
    hourly_df: pd.DataFrame,
    train_result: TrainResult,
    forecast_df: pd.DataFrame,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    hourly_df.to_csv(output_dir / "data_hourly.csv", index=False)
    train_result.test_predictions.to_csv(output_dir / "test_predictions.csv", index=False)
    forecast_df.to_csv(output_dir / "forecast.csv", index=False)

    with (output_dir / "metrics.json").open("w", encoding="utf-8") as file:
        json.dump(train_result.metrics, file, indent=2, ensure_ascii=False)

    with (output_dir / "dataset_validation.json").open("w", encoding="utf-8") as file:
        json.dump(train_result.validation, file, indent=2, ensure_ascii=False)

    joblib.dump(
        {
            "model": train_result.model,
            "feature_columns": train_result.feature_columns,
            "price_column": PRICE_COLUMN,
        },
        output_dir / "model.joblib",
    )


def load_or_fetch_data(args: argparse.Namespace, output_dir: Path) -> pd.DataFrame:
    cache_path = output_dir / "data_hourly.csv"
    if args.use_cache and cache_path.exists():
        cached = pd.read_csv(cache_path, parse_dates=["datetime"])
        return cached.sort_values("datetime").reset_index(drop=True)

    raw = fetch_price_data(args.start_date, args.end_date)
    return hourly_wide_to_long(raw)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    hourly_df = load_or_fetch_data(args, output_dir)
    train_result = train_model(
        hourly_df,
        args.test_days,
        args.backend,
        args.device,
        args.strict_validation,
    )
    forecast_df = forecast_next_hours(
        train_result.model,
        train_result.feature_columns,
        hourly_df,
        args.forecast_hours,
    )
    save_outputs(output_dir, hourly_df, train_result, forecast_df)

    print("Modelo entrenado para Precio de Bolsa Nacional")
    print("Validacion del dataset")
    print(json.dumps(train_result.validation, indent=2, ensure_ascii=False))
    print("Metricas del modelo")
    print(json.dumps(train_result.metrics, indent=2, ensure_ascii=False))
    print(f"Archivos guardados en: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
