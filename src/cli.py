"""Точка входа: разбор sys.argv, вызов нужного модуля.

Команды:
    python3 main.py                            — отчёт (по умолчанию)
    python3 main.py check-purchase --amount N  — цена покупки N
    python3 main.py add "2026-10-15 -1200 наушники"  — добавить транзакцию

Без argparse (его не было в курсе) — свой разбор sys.argv.
Ошибки — в stderr, код возврата != 0.
"""

import sys
from datetime import date

from src.errors import DataError, ValidationError
from src.storage import (
    load_accounts, load_transactions, load_payments, load_loans,
    load_credit_cards, load_rules, load_state, save_state,
)
from src.categorizer import mark_transfers, categorize
from src.reports import build_report
from src.purchases import check_purchase
from src.models import Transaction


# пути по умолчанию (относительно корня проекта)
DEFAULT_ACCOUNTS = "data/accounts.csv"
DEFAULT_TRANSACTIONS = "data/transactions.csv"
DEFAULT_PAYMENTS = "data/payments.csv"
DEFAULT_LOANS = "data/loans.csv"
DEFAULT_CARDS = "data/credit_cards.csv"
DEFAULT_RULES = "data/rules.json"
DEFAULT_STATE = "data/state.json"


def _load_all():
    """Загружает все данные. Бросает DataError, если что-то не так."""
    accounts = load_accounts(DEFAULT_ACCOUNTS)
    transactions = load_transactions(DEFAULT_TRANSACTIONS)
    payments = load_payments(DEFAULT_PAYMENTS)
    loans = load_loans(DEFAULT_LOANS)
    cards = load_credit_cards(DEFAULT_CARDS)
    rules = load_rules(DEFAULT_RULES)
    state = load_state(DEFAULT_STATE)
    return accounts, transactions, payments, loans, cards, rules, state


def cmd_report(args):
    """Отчёт (по умолчанию, без аргументов)."""
    accounts, txs, payments, loans, cards, rules, state = _load_all()

    # категоризация и пометка переводов
    mark_transfers(txs)
    categorize(txs, rules["rules"])

    # обновляем state: какие tx_id уже обработаны
    seen = set(state.get("seen_tx_ids", []))
    new_ids = [tx.tx_id for tx in txs if tx.tx_id not in seen]
    state["seen_tx_ids"] = sorted(seen | set(new_ids))
    save_state(DEFAULT_STATE, state)

    today = date.today()
    print(build_report(accounts, payments, loans, cards, rules, today))
    return 0


def cmd_check_purchase(args):
    """Цена покупки. Ожидает --amount N."""
    amount = None
    i = 0
    while i < len(args):
        if args[i] == "--amount" and i + 1 < len(args):
            try:
                amount = float(args[i + 1])
            except ValueError as err:
                print(f"--amount: не число: {args[i+1]!r}", file=sys.stderr)
                return 2
            i += 2
        else:
            i += 1

    if amount is None:
        print("Использование: python3 main.py check-purchase --amount N", file=sys.stderr)
        return 2

    accounts, txs, payments, loans, cards, rules, state = _load_all()
    today = date.today()
    goal = rules["goal"]
    result = check_purchase(amount, accounts, payments, loans, cards, rules, today, goal)

    print(f"=== Проверка покупки на {amount:.2f} RUB ===")
    print(f"  Свободно до:      {result['free_before']:.2f} RUB")
    print(f"  Свободно после:   {result['free_after']:.2f} RUB")
    if result["can_afford"]:
        print("  ✓ хватает на обязательные")
    else:
        print(f"  ⚠ НЕ хватает {result['shortfall']:.2f} RUB")
    print(f"  Цена в днях свободных: {result['days_of_free']}")
    print(f"  Сдвиг цели:       {result['goal_days_shift']:.0f} дней")
    return 0


def cmd_add(args):
    """Добавить транзакцию из строки: 'YYYY-MM-DD amount description'."""
    if not args:
        print("Использование: python3 main.py add \"2026-10-15 -1200 наушники\"", file=sys.stderr)
        return 2

    raw = args[0]
    parts = raw.split(maxsplit=2)
    if len(parts) < 3:
        print(f"Не понял: {raw!r}. Формат: YYYY-MM-DD amount description", file=sys.stderr)
        return 2

    date_str, amount_str, description = parts
    try:
        d = date.fromisoformat(date_str)
    except ValueError as err:
        print(f"Не дата: {date_str!r}", file=sys.stderr)
        return 2

    try:
        amount = float(amount_str.replace(",", "."))
    except ValueError as err:
        print(f"Не число: {amount_str!r}", file=sys.stderr)
        return 2

    # создаём Transaction и «дописываем» в transactions.csv
    # (упрощение: пишем в конец файла)
    tx_id = f"tx_{d.strftime('%Y%m%d%H%M%S')}"
    tx = Transaction(tx_id=tx_id, date=d, amount=amount,
                     description=description, account_id="acc_debit")

    # дописываем строку в CSV
    from pathlib import Path
    path = Path(DEFAULT_TRANSACTIONS)
    if not path.exists():
        print(f"Файл не найден: {DEFAULT_TRANSACTIONS}", file=sys.stderr)
        return 2
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{tx_id},{d.strftime('%d.%m.%Y')},{amount:.2f},{description},acc_debit\n")

    print(f"✓ добавлено: {tx}")
    return 0


def main(argv=None):
    """Точка входа. argv — список аргументов без имени программы."""
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        return cmd_report([])

    command = argv[0]
    rest = argv[1:]

    try:
        if command == "report":
            return cmd_report(rest)
        elif command == "check-purchase":
            return cmd_check_purchase(rest)
        elif command == "add":
            return cmd_add(rest)
        else:
            print(f"Неизвестная команда: {command}", file=sys.stderr)
            print("Доступно: report, check-purchase, add", file=sys.stderr)
            return 2
    except DataError as err:
        print(f"Ошибка данных: {err}", file=sys.stderr)
        return 2
    except ValidationError as err:
        print(f"Ошибка валидации: {err}", file=sys.stderr)
        return 2