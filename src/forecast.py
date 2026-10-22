"""Прогноз баланса по дням: ядро проекта.

Строим календарь: на каждую дату — приходы (зарплата), расходы
(платежи, кредиты), начисление процентов на накопительном. Идём по
дням, считаем баланс на конец каждого дня. Ищем минимальный баланс —
это точка риска (если < 0 — кассовый разрыв).

Пока без процентов на накопительном — добавим во второй порции.
"""

from datetime import date, timedelta

from src.models import Account, ScheduledPayment, Loan


def _days_in_month(year, month):
    """Сколько дней в месяце (28/29/30/31). Учитывает високосные годы.

    Простой способ: первое число следующего месяца минус 1 день.
    """
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    return (next_first - timedelta(days=1)).day


def payment_dates_between(payment, start, end):
    """Даты платежа в интервале [start, end] с учётом period_months и day_of_month.

    Если day_of_month=31, а в месяце 30 дней — берём 30-е (последний день).
    Если day_of_month=31, а в феврале 28 — берём 28-е. Так банки и делают.

    Args:
        payment: ScheduledPayment или Loan (у обоих есть day_of_month, period_months
                 — у ScheduledPayment; у Loan period_months всегда 1).
        start: date, начало интервала (включительно).
        end: date, конец интервала (включительно).

    Returns:
        Список дат (date), отсортированный по возрастанию.
    """
    period = getattr(payment, "period_months", 1)   # Loan всегда платит раз в месяц
    day = payment.day_of_month
    result = []

    # начинаем с месяца start, идём с шагом period
    year, month = start.year, start.month
    while True:
        last_day = _days_in_month(year, month)
        actual_day = min(day, last_day)
        d = date(year, month, actual_day)
        if d > end:
            break
        if d >= start:
            result.append(d)
        month += period
        while month > 12:
            month -= 12
            year += 1
    return result


def forecast_balance(accounts, payments, loans, start, end):
    """Прогноз баланса по дням. Возвращает список [(date, balance_after_day)].

    Args:
        accounts: список Account (debit + savings) — стартовый баланс = сумма.
        payments: список ScheduledPayment (платежи и доходы).
        loans: список Loan (кредиты — ежемесячные платежи).
        start: date, с какого дня строить.
        end: date, по какой день включительно.

    Returns:
        Список кортежей (date, balance) — баланс на конец каждого дня.
        Баланс может быть отрицательным — это сигнал о кассовом разрыве.
    """
    # стартовый баланс — сумма по всем счетам
    balance = sum(a.balance for a in accounts)

    # заранее соберём все даты платежей в интервале, чтобы не перебирать
    # правила каждый день (это оптимизация, но и логика понятнее)
    daily_delta = {}   # date -> сумма изменений за этот день
    for p in payments:
        for d in payment_dates_between(p, start, end):
            daily_delta[d] = daily_delta.get(d, 0.0) + p.amount
    for loan in loans:
        for d in payment_dates_between(loan, start, end):
            # last_payment() — если остаток меньше месячного платежа
            daily_delta[d] = daily_delta.get(d, 0.0) - loan.last_payment()

    timeline = []
    d = start
    while d <= end:
        balance += daily_delta.get(d, 0.0)
        timeline.append((d, round(balance, 2)))
        d += timedelta(days=1)
    return timeline


def min_balance(timeline):
    """Возвращает (date, min_balance) — точку максимального риска.

    Если timeline пустой — возвращает (None, None).
    """
    if not timeline:
        return (None, None)
    return min(timeline, key=lambda x: x[1])