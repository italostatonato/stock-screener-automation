"""Migracao ja incorporada; este comando nao modifica codigo ou dados.

Reaplicar substituicoes textuais poderia corromper expressoes do dashboard.
Para recalcular derivados, execute python scripts/rebuild_from_lake.py.
"""


def main() -> None:
    print("ML 7d ja incorporado. Para recalcular: python scripts/rebuild_from_lake.py")


if __name__ == "__main__":
    main()
