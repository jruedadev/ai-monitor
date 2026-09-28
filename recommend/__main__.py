"""CLI: python3 -m recommend run --trigger diario|manual (lo usa el timer diario)."""
import argparse
import sys

from recommend import engine


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m recommend", description="Motor de recomendaciones de ai-monitor")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="Ejecuta una corrida completa")
    run_parser.add_argument("--trigger", choices=("diario", "manual"), default="manual")
    args = parser.parse_args(argv)
    try:
        run_id, status = engine.run(args.trigger)
    except engine.EngineBusy:
        print("Ya hay una corrida en curso", file=sys.stderr)
        return 2
    print(f"Corrida {run_id}: {status}")
    return 1 if status == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
