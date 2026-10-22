"""Сценарии погашения кредита: по графику vs досрочно.

Для кредита-цели считаем:
- A: платить только monthly_payment, пока не закроется.
- B: платить monthly_payment + досрочный взнос (или весь остаток сразу).

Сравниваем переплату и недополученный % на накопительном.

Упрощения (в README):
- проценты по кредиту — простые (balance * rate / 12 за месяц);
- накопительный — 18% годовых (до 2027) / 14% (после);
- досрочный взнос — из свободных, которые лежат на накопительном.
"""

from datetime import date, timedelta

from src.models import Loan


def _add_months(d, months):
    """Прибавить months месяцев к дате d, сохранив день (или последний в месяце).

    Например: 31 января + 1 месяц = 28/29 февраля.
    """
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    # последний день месяца
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    last_day = (next_first - timedelta(days=1)).day
    day = min(d.day, last_day)
    return date(year, month, day)


def scenario_schedule(loan, start):
    """Сценарий A: платить только monthly_payment, пока не закроется.

    Returns:
        (close_date, total_paid, total_interest) — дата закрытия,
        сколько всего заплатили, сколько из этого проценты.
    """
    balance = loan.balance
    rate_monthly = loan.rate / 12.0
    total_paid = 0.0
    total_interest = 0.0

    current = _add_months(start, 0)   # ближайшая дата платежа
    while balance > 0:
        # проценты за месяц
        interest = balance * rate_monthly
        total_interest += interest
        balance += interest

        # платёж — либо monthly_payment, либо остаток (если меньше)
        payment = min(loan.monthly_payment, balance)
        total_paid += payment
        balance -= payment

        if balance <= 0:
            return (current, total_paid, total_interest)

        # следующая дата платежа — через месяц
        current = _add_months(current, 1)

    return (current, total_paid, total_interest)


def scenario_early(loan, start, extra_payment, savings_rate):
    """Сценарий B: monthly_payment + досрочный extra_payment.

    Args:
        savings_rate: ставка накопительного (0.18 = 18%) — чтобы посчитать
                      недополученный % на деньги, ушедшие на досрочку.

    Returns:
        (close_date, total_paid, total_interest, lost_savings_interest)
    """
    balance = loan.balance
    rate_monthly = loan.rate / 12.0
    total_paid = 0.0
    total_interest = 0.0
    months_early = 0   # сколько месяцев extra_payment лежит «не на накопительном»

    current = start
    while balance > 0:
        interest = balance * rate_monthly
        total_interest += interest
        balance += interest

        payment = min(loan.monthly_payment, balance)
        total_paid += payment
        balance -= payment

        # досрочный взнос — из свободных (которых нет на накопительном)
        if balance > 0 and extra_payment > 0:
            extra = min(extra_payment, balance)
            total_paid += extra
            balance -= extra
            months_early += 1

        if balance <= 0:
            close_date = _add_months(start, months_early) if months_early else start
            # недополученный % на накопительном: extra_payment * savings_rate / 12
            # за каждый месяц, пока деньги не вернулись (упрощение)
            lost = extra_payment * savings_rate / 12.0 * months_early
            return (close_date, total_paid, total_interest, lost)

        current = _add_months(current, 1)

    return (current, total_paid, total_interest,
            extra_payment * savings_rate / 12.0 * months_early)


def compare_scenarios(loan, start, extra_payment, savings_rate):
    """Сравнить сценарии A и B.

    Returns:
        dict:
            "A": {"close_date": ..., "total_paid": ..., "total_interest": ...},
            "B": {"close_date": ..., "total_paid": ..., "total_interest": ...,
                  "lost_savings": ...},
            "conclusion": "early_better" | "schedule_better" | "equal",
            "diff_interest": float,    # переплата A - переплата B
            "diff_savings": float,     # недополученный % в B
            "net_diff": float,         # diff_interest - diff_savings
    """
    close_a, paid_a, interest_a = scenario_schedule(loan, start)
    close_b, paid_b, interest_b, lost_b = scenario_early(
        loan, start, extra_payment, savings_rate
    )

    diff_interest = interest_a - interest_b   # сколько сэкономили на процентах
    diff_savings = lost_b                     # сколько недополучили на накопительном
    net_diff = diff_interest - diff_savings   # чистая выгода (>0 — досрочно выгодно)

    if net_diff > 0:
        conclusion = "early_better"
    elif net_diff < 0:
        conclusion = "schedule_better"
    else:
        conclusion = "equal"

    return {
        "A": {
            "close_date": close_a,
            "total_paid": round(paid_a, 2),
            "total_interest": round(interest_a, 2),
        },
        "B": {
            "close_date": close_b,
            "total_paid": round(paid_b, 2),
            "total_interest": round(interest_b, 2),
            "lost_savings": round(lost_b, 2),
        },
        "conclusion": conclusion,
        "diff_interest": round(diff_interest, 2),
        "diff_savings": round(diff_savings, 2),
        "net_diff": round(net_diff, 2),
    }