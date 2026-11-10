"""Valida a coleta e confere a revisão servida nos dois endereços do Radar."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

DATA_DIR = Path(__file__).resolve().parents[1] / "docs" / "data"
TIMEZONE = ZoneInfo("America/Sao_Paulo")
ORIGINS = (
    "https://italostatonato.github.io/stock-screener-automation",
    "https://radar-semanal-italo.italo-st.chatgpt.site",
)
MARKER = "publication.json"


def latest_snapshot(data_dir: Path) -> tuple[date, dict]:
    index = json.loads((data_dir / "index.json").read_text(encoding="utf-8"))
    if not isinstance(index, list) or not index or not isinstance(index[0], str):
        raise ValueError("Índice do Radar sem uma data inicial válida.")
    day = date.fromisoformat(index[0])
    if day.isoformat() != index[0]:
        raise ValueError("O índice precisa usar datas no formato AAAA-MM-DD.")
    payload = json.loads((data_dir / f"{day}.json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("data") != day.isoformat():
        raise ValueError(f"Data interna do snapshot divergente de {day}.")
    for key in ("acoes", "fiis"):
        if not isinstance(payload.get(key), list) or not payload[key]:
            raise ValueError(f"Snapshot de {day} sem ranking de {key}.")
    return day, payload


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def collection_required(event: str, today: date, latest: date | None) -> bool:
    if latest is not None and latest > today:
        raise ValueError(f"Snapshot de {latest} é posterior à data da execução {today}.")
    return event != "schedule" or latest is None or latest < monday(today)


def snapshot_digest(payload: dict) -> str:
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def public_json(url: str):
    request = Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "Radar-Publication-Check"})
    with urlopen(request, timeout=12) as response:
        return json.load(response)


def publication_errors(expected: dict, fetch=public_json) -> list[str]:
    snapshot = expected["snapshot"]
    errors = []
    for origin in ORIGINS:
        try:
            data_url = f"{origin}/data"
            served = fetch(f"{data_url}/{MARKER}")
            if served != expected:
                actual = served.get("commit") if isinstance(served, dict) else None
                raise ValueError(f"revisão esperada {expected['commit']}, recebida {actual}")
            index = fetch(f"{data_url}/index.json")
            current = index[0] if isinstance(index, list) and index else None
            if current != snapshot:
                raise ValueError(f"índice ainda aponta para {current}, esperado {snapshot}")
            payload = fetch(f"{data_url}/{snapshot}.json")
            if snapshot_digest(payload) != expected["snapshot_sha256"]:
                raise ValueError(f"conteúdo publicado de {snapshot} diverge do arquivo local")
        except (OSError, ValueError) as exc:
            errors.append(f"{origin}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    subcommands = parser.add_subparsers(dest="command", required=True)

    plan = subcommands.add_parser("plan")
    plan.add_argument("--event", choices=("schedule", "workflow_dispatch"), required=True)
    plan.add_argument("--output", type=Path, required=True)

    validate = subcommands.add_parser("validate")
    validate.add_argument("--minimum-date", type=date.fromisoformat, required=True)

    prepare = subcommands.add_parser("prepare")
    prepare.add_argument("--commit", required=True)
    prepare.add_argument("--scheduled-at", default="")

    verify = subcommands.add_parser("verify")
    verify.add_argument("--timeout", type=int, default=360)

    args = parser.parse_args()
    try:
        if args.command == "plan":
            today = datetime.now(TIMEZONE).date()
            try:
                latest, _ = latest_snapshot(args.data_dir)
            except (OSError, ValueError) as exc:
                print(f"Será feita uma nova coleta. Snapshot atual indisponível: {exc}")
                latest = None
            collect = collection_required(args.event, today, latest)
            print(f"Coleta necessária: {'sim' if collect else 'não'}. Último snapshot: {latest}.")
            with args.output.open("a", encoding="utf-8") as output:
                output.write(f"collect={str(collect).lower()}\nminimum_date={today}\n")
            return 0

        if args.command == "verify":
            expected = json.loads((args.data_dir / MARKER).read_text(encoding="utf-8"))
            deadline = time.monotonic() + args.timeout
            while True:
                errors = publication_errors(expected)
                if not errors:
                    print(f"Snapshot {expected['snapshot']} confirmado nos dois endereços.")
                    return 0
                print("\n".join(errors), file=sys.stderr, flush=True)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return 1
                time.sleep(min(15, remaining))

        day, payload = latest_snapshot(args.data_dir)
        minimum = args.minimum_date if args.command == "validate" else None
        if args.command == "prepare" and args.scheduled_at:
            started = datetime.fromisoformat(args.scheduled_at)
            minimum = monday(started.astimezone(TIMEZONE).date())
        if minimum is not None and day < minimum:
            raise ValueError(f"Snapshot {day} anterior à data esperada {minimum}.")
        if args.command == "prepare":
            marker = {"commit": args.commit, "snapshot": day.isoformat(), "snapshot_sha256": snapshot_digest(payload)}
            (args.data_dir / MARKER).write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
        print(f"Snapshot validado: {day}.")
        return 0
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
