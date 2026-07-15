"""One-command orchestrator for the portfolio's cached or full pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys


def run(*parts: str) -> None:
    command = [sys.executable, *parts]
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecuta Colombia Energy Intelligence end-to-end.")
    parser.add_argument("--refresh", action="store_true", help="Consulta nuevamente la API XM.")
    parser.add_argument("--backend", choices=["sklearn", "xgboost"], default="xgboost")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    args = parser.parse_args()
    cache = [] if args.refresh else ["--use-cache"]

    run("models/precio_bolsa_model.py", *cache, "--backend", args.backend, "--device", args.device, "--strict-validation")
    run("models/consumo_actores.py", *cache)
    run("models/caribe_policy_analysis.py")
    run("dashboards/energy_market_dashboard.py")
    print("\nProyecto listo: abre portfolio/dashboard.html")


if __name__ == "__main__":
    main()
