"""Чтение и запись CSV/JSON.

Числа в файлах могут быть в русском формате: "1 234,56" или "-1200,50".
Функция _parse_float нормализует их: убирает пробелы, заменяет запятую
на точку, потом float(...). Если не получилось — DataError с номером строки.

Даты — в формате "15.10.2026" (день.месяц.год). Поддерживаем и "2026-10-15"
(ISO) на случай, если кто-то экспортировал иначе.
"""

import csv
import json
from datetime import datetime
from pathlib import Path

from src.errors import DataError
from src.models import (
    Account, Loan, CreditCard, ScheduledPayment, CategoryRule, Goal,
)


# ---------- вспомогательные парсеры ----------
def _normalize_row(row):
    """Убирает пробелы из ключей и значений строки CSV.

    Причина: Excel и некоторые редакторы сохраняют CSV с пробелом после
    запятой: "name, balance" → ключ ' balance' (с пробелом). Тогда
    reader.fieldnames = ['name', ' balance'], и наши проверки на
    обязательные колонки падают. Нормализуем: strip() и для ключей, и
    для значений.
    """
    return {k.strip(): (v.strip() if isinstance(v, str) else v)
            for k, v in row.items()}


def _normalize_fieldnames(reader):
    """Убирает пробелы из имён колонок в reader.fieldnames (на месте)."""
    if reader.fieldnames:
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
    return reader

def _parse_date(value, line_no, field_name):
    """Парсит дату из '15.10.2026' или '2026-10-15'. Бросает DataError."""
    text = str(value).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise DataError(
        f"Не удалось разобрать дату: {text!r}",
        line_no=line_no, field=field_name,
    )


def _parse_float(value, line_no, field_name):
    """Парсит число из '1 234,56', '-1200,50' или '1234.56'. Бросает DataError."""
    text = str(value).strip().replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError as err:
        raise DataError(
            f"Не число: {value!r}",
            line_no=line_no, field=field_name,
        ) from err


# ---------- чтение CSV ----------

def load_accounts(path):
    """Читает data/accounts.csv → список Account."""
    file = Path(path)
    if not file.exists():
        raise DataError(f"Файл счетов не найден: {path}")

    accounts = []
    try:
        with file.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            _normalize_fieldnames(reader)
            required = {"account_id", "name", "balance", "kind"}
            if not required.issubset(reader.fieldnames or []):
                raise DataError(
                    f"В {path} нет обязательных колонок: {required}"
                )
            for i, row in enumerate(reader, start=2):
                row = _normalize_row(row)
                balance = _parse_float(row["balance"], i, "balance")
                accounts.append(Account(
                    account_id=row["account_id"].strip(),
                    name=row["name"].strip(),
                    balance=balance,
                    kind=row["kind"].strip(),
                ))
    except FileNotFoundError as err:
        raise DataError(f"Файл счетов не найден: {path}") from err
    return accounts


def load_transactions(path):
    """Читает data/transactions.csv → список Transaction.

    Помечает переводы между своими счетами (is_transfer=True) по слову
    "перевод" в описании — это краевой случай из README: перевод не расход.
    """
    # Локальный импорт: Transaction нужен только здесь.
    from src.models import Transaction

    file = Path(path)
    if not file.exists():
        raise DataError(f"Файл транзакций не найден: {path}")

    txs = []
    try:
        with file.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            _normalize_fieldnames(reader)
            required = {"tx_id", "date", "amount", "description", "account_id"}
            if not required.issubset(reader.fieldnames or []):
                raise DataError(
                    f"В {path} нет обязательных колонок: {required}"
                )
            for i, row in enumerate(reader, start=2):
                tx = Transaction(
                    tx_id=row["tx_id"].strip(),
                    date=_parse_date(row["date"], i, "date"),
                    amount=_parse_float(row["amount"], i, "amount"),
                    description=row["description"].strip(),
                    account_id=row["account_id"].strip(),
                )
                txs.append(tx)
    except FileNotFoundError as err:
        raise DataError(f"Файл транзакций не найден: {path}") from err
    return txs


def load_payments(path):
    """Читает data/payments.csv → список ScheduledPayment."""
    file = Path(path)
    if not file.exists():
        raise DataError(f"Файл платежей не найден: {path}")

    payments = []
    try:
        with file.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            _normalize_fieldnames(reader)
            required = {"payment_id", "name", "amount", "day_of_month", "period_months"}
            if not required.issubset(reader.fieldnames or []):
                raise DataError(
                    f"В {path} нет обязательных колонок: {required}"
                )
            for i, row in enumerate(reader, start=2):
                row = _normalize_row(row)  
                day = int(_parse_float(row["day_of_month"], i, "day_of_month"))
                if not 1 <= day <= 31:
                    raise DataError(
                        f"day_of_month должен быть 1..31, получено {day}",
                        line_no=i, field="day_of_month",
                    )
                period = int(_parse_float(row["period_months"], i, "period_months"))
                payments.append(ScheduledPayment(
                    payment_id=row["payment_id"].strip(),
                    name=row["name"].strip(),
                    amount=_parse_float(row["amount"], i, "amount"),
                    day_of_month=day,
                    period_months=period,
                    category=(row.get("category") or "other").strip(),
                ))
    except FileNotFoundError as err:
        raise DataError(f"Файл платежей не найден: {path}") from err
    return payments


def load_loans(path):
    """Читает data/loans.csv → список Loan."""
    file = Path(path)
    if not file.exists():
        raise DataError(f"Файл кредитов не найден: {path}")

    loans = []
    try:
        with file.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            _normalize_fieldnames(reader)
            required = {"loan_id", "name", "balance", "rate",
                        "monthly_payment", "day_of_month"}
            if not required.issubset(reader.fieldnames or []):
                raise DataError(
                    f"В {path} нет обязательных колонок: {required}"
                )
            for i, row in enumerate(reader, start=2):
                row = _normalize_row(row)  
                day = int(_parse_float(row["day_of_month"], i, "day_of_month"))
                if not 1 <= day <= 31:
                    raise DataError(
                        f"day_of_month должен быть 1..31, получено {day}",
                        line_no=i, field="day_of_month",
                    )
                target_raw = (row.get("target_date") or "").strip()
                target = _parse_date(target_raw, i, "target_date") if target_raw else None
                loans.append(Loan(
                    loan_id=row["loan_id"].strip(),
                    name=row["name"].strip(),
                    balance=_parse_float(row["balance"], i, "balance"),
                    rate=_parse_float(row["rate"], i, "rate"),
                    monthly_payment=_parse_float(row["monthly_payment"], i, "monthly_payment"),
                    day_of_month=day,
                    target_date=target,
                ))
    except FileNotFoundError as err:
        raise DataError(f"Файл кредитов не найден: {path}") from err
    return loans


def load_credit_cards(path):
    """Читает data/credit_cards.csv → список CreditCard."""
    file = Path(path)
    if not file.exists():
        raise DataError(f"Файл кредиток не найден: {path}")

    cards = []
    try:
        with file.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            _normalize_fieldnames(reader)
            required = {"card_id", "name", "spent", "grace_start",
                        "grace_days", "rate_after"}
            if not required.issubset(reader.fieldnames or []):
                raise DataError(
                    f"В {path} нет обязательных колонок: {required}"
                )
            for i, row in enumerate(reader, start=2):
                row = _normalize_row(row)  
                cards.append(CreditCard(
                    card_id=row["card_id"].strip(),
                    name=row["name"].strip(),
                    spent=_parse_float(row["spent"], i, "spent"),
                    grace_start=_parse_date(row["grace_start"], i, "grace_start"),
                    grace_days=int(_parse_float(row["grace_days"], i, "grace_days")),
                    rate_after=_parse_float(row["rate_after"], i, "rate_after"),
                ))
    except FileNotFoundError as err:
        raise DataError(f"Файл кредиток не найден: {path}") from err
    return cards


  

# ---------- чтение/запись JSON ----------

def load_rules(path):
    """Читает data/rules.json → словарь с ключами rules, limits, goal, savings.

    Ожидаемая структура (см. data/rules.json):
        {
          "savings_rates": [...],
          "safety_cushion": 5000.0,
          "category_rules": [...],
          "goal": {...},
          ...
        }

    Возвращает словарь:
        {
          "rules": [CategoryRule, ...],
          "goal": Goal | None,
          "raw": исходный dict (на будущее),
        }
    """
    file = Path(path)
    if not file.exists():
        raise DataError(f"Файл правил не найден: {path}")

    try:
        with file.open(encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as err:
        raise DataError(
            f"Битый JSON в {path}: {err.msg} (позиция {err.pos})"
        ) from err
    except FileNotFoundError as err:
        raise DataError(f"Файл правил не найден: {path}") from err

    # правил категоризации может не быть — тогда пустой список
    rules = []
    for i, item in enumerate(raw.get("category_rules", []), start=1):
        try:
            rules.append(CategoryRule(
                category=item["category"],
                keywords=list(item["keywords"]),
                priority=int(item.get("priority", 0)),
            ))
        except KeyError as err:
            raise DataError(
                f"В правиле №{i} нет поля {err}",
                line_no=i, field=str(err),
            ) from err

    # цель может отсутствовать
    goal = None
    if "goal" in raw:
        g = raw["goal"]
        try:
            goal = Goal(
                name=g["name"],
                target_amount=float(g["target_amount"]),
                target_date=_parse_date(g["target_date"], 0, "goal.target_date")
                if g.get("target_date") else None,
                loan_id=g.get("loan_id"),
            )
        except KeyError as err:
            raise DataError(f"В goal нет поля {err}", field=str(err)) from err

    return {"rules": rules, "goal": goal, "raw": raw}


def load_state(path):
    """Читает data/state.json. Если файла нет — пустое состояние.

    Состояние между запусками: какие tx_id уже обработаны,
    какие платежи отмечены как оплаченные.
    """
    file = Path(path)
    if not file.exists():
        return {"seen_tx_ids": [], "paid_payment_ids": []}

    try:
        with file.open(encoding="utf-8") as f:
            state = json.load(f)
    except json.JSONDecodeError as err:
        raise DataError(
            f"Битый JSON состояния {path}: {err.msg} (позиция {err.pos})"
        ) from err

    # гарантируем обязательные ключи — даже если в файле их нет
    state.setdefault("seen_tx_ids", [])
    state.setdefault("paid_payment_ids", [])
    return state


def save_state(path, state):
    """Записывает состояние в data/state.json. Создаёт папку, если её нет."""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)

    # множества → списки, чтобы JSON-сериализация сработала
    serializable = {
        "seen_tx_ids": sorted(state.get("seen_tx_ids", [])),
        "paid_payment_ids": sorted(state.get("paid_payment_ids", [])),
    }

    try:
        with file.open("w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
    except OSError as err:
        raise DataError(f"Не удалось сохранить состояние в {path}: {err}") from err  