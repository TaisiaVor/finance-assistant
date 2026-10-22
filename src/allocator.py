"""«Свободно сейчас»: сколько реально можно потратить.

Формула:
    свободно = баланс дебета
             + баланс накопительного
             − заморожено под обязательные платежи до следующей зарплаты
             − подушка (safety_cushion)
             − долг по кредиткам (надо вернуть до grace_end)

Заморожено — сумма всех обязательных платежей (кредиты + прочие)
ДО следующей зарплаты. Если зарплата не найдена — берём все платежи
за 30 дней вперёд (упрощение).

Упрощения (в README):
- считаем, что дебет и накопительный — «одна куча» (в реальности — разные);
- зарплата — первый платёж с category="income" в payments;
- подушка — safety_cushion из rules.json.
"""

from datetime import date, timedelta

from src.models import Account, ScheduledPayment, Loan, CreditCard


def next_salary_date(payments, today):
    """Дата следующей зарплаты от today.

    Ищем ScheduledPayment с category="income" и day_of_month > today.day
    в этом месяце; если нет — в следующем.

    Returns:
        date | None — если зарплаты нет в payments.
    """
    for p in payments:
        if p.category != "income":
            continue
        # зарплата в этом месяце, если day_of_month > today.day
        for delta_month in (0, 1):
            year = today.year + (today.month - 1 + delta_month) // 12
            month = (today.month - 1 + delta_month) % 12 + 1
            if month == 12:
                next_first = date(year + 1, 1, 1)
            else:
                next_first = date(year, month + 1, 1)
            last_day = (next_first - timedelta(days=1)).day
            day = min(p.day_of_month, last_day)
            d = date(year, month, day)
            if d > today:
                return d
    return None


def frozen_until(payments, loans, today, until):
    """Сумма всех обязательных платежей в интервале [today, until).

    Считает: платежи (ScheduledPayment) и кредиты (Loan).
    Возвращает положительное число — сколько «заморожено».
    """
    total = 0.0
    for p in payments:
        if p.category == "income":
            continue   # доходы не «замораживаем»
        # берём payment_dates_between из forecast, но чтобы не импортировать
        # циклически — простой перебор по месяцам
        from src.forecast import payment_dates_between
        for d in payment_dates_between(p, today, until - timedelta(days=1)):
            total += abs(p.amount)

    from src.forecast import payment_dates_between
    for loan in loans:
        for d in payment_dates_between(loan, today, until - timedelta(days=1)):
            total += loan.last_payment()

    return total


def free_now(accounts, payments, loans, credit_cards, rules, today):
    """«Свободно сейчас» — сколько реально можно потратить.

    Args:
        accounts: список Account.
        payments: список ScheduledPayment.
        loans: список Loan.
        credit_cards: список CreditCard.
        rules: словарь из load_rules (raw: safety_cushion).
        today: date — «сегодня».

    Returns:
        dict:
            "debit": float,           # баланс дебета
            "savings": float,         # баланс накопительного
            "frozen": float,          # заморожено под обязательные
            "cushion": float,         # подушка
            "credit_card_debt": float,# сумма spent по всем картам
            "free": float,            # итог: свободно
            "until": date | None,     # до какой даты заморожено
    """
    debit = sum(a.balance for a in accounts if a.kind != "savings")
    savings = sum(a.balance for a in accounts if a.kind == "savings")

    until = next_salary_date(payments, today) or (today + timedelta(days=30))
    frozen = frozen_until(payments, loans, today, until)

    cushion = rules["raw"].get("safety_cushion", 0.0)
    credit_card_debt = sum(c.spent for c in credit_cards)

    free = debit + savings - frozen - cushion - credit_card_debt

    return {
        "debit": round(debit, 2),
        "savings": round(savings, 2),
        "frozen": round(frozen, 2),
        "cushion": round(cushion, 2),
        "credit_card_debt": round(credit_card_debt, 2),
        "free": round(free, 2),
        "until": until,
    }
    