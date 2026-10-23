"""Цена покупки (упрощённая): что сдвинется в системе, если купить X за Y.

Не «есть ли Y на счету», а «что сдвинется»:
1. Свободно после покупки (free_now - сумма).
2. Хватит ли на обязательные (свободно_после >= 0).
3. Цена в днях свободных денег (сумма / средний_дневной_прирост).
4. Влияние на цель (сколько дней цели «съедает» покупка).

Полная версия (сдвиг даты закрытия кредита, недополученный %) —
в roadmap: требует пересчёта всего forecast с покупкой.
"""

from datetime import date, timedelta

from src.allocator import free_now


def _daily_growth(payments, loans, today):
    """Средний дневной прирост свободных денег.

    Упрощение: (сумма доходов - сумма обязательных) / 30.
    Если доходы < обязательные — отрицательный прирост (деньги тают).
    """
    income = sum(p.amount for p in payments if p.category == "income")
    mandatory = sum(abs(p.amount) for p in payments if p.category != "income")
    mandatory += sum(loan.last_payment() for loan in loans)
    return (income - mandatory) / 30.0


def check_purchase(amount, accounts, payments, loans, cards, rules, today, goal=None):
    """Проверка покупки: что сдвинется.

    Args:
        amount: float — сумма покупки (положительная).
        accounts, payments, loans, cards: как в free_now.
        rules: словарь из load_rules.
        today: date.
        goal: Goal | None — цель (для «сколько дней съедает»).

    Returns:
        dict:
            "amount": float,
            "free_before": float,
            "free_after": float,
            "can_afford": bool,        # хватает ли на обязательные
            "shortfall": float,        # если не хватает — сколько
            "days_of_free": float,     # сколько дней свободных денег стоит
            "goal_days_shift": float,  # сколько дней цели «съедает»
    """
    if amount <= 0:
        from src.errors import ValidationError
        raise ValidationError("Сумма покупки должна быть положительной", value=amount)

    alloc = free_now(accounts, payments, loans, cards, rules, today)
    free_before = alloc["free"]
    free_after = free_before - amount

    can_afford = free_after >= 0
    shortfall = max(0.0, -free_after)

    growth = _daily_growth(payments, loans, today)
    if growth > 0:
        days_of_free = amount / growth
    else:
        days_of_free = float("inf")   # деньги не прибавляются — «бесконечная» цена

    # влияние на цель
    goal_days_shift = 0.0
    if goal is not None and goal.target_date is not None:
        days_to_goal = (goal.target_date - today).days
        if days_to_goal > 0 and goal.target_amount > 0:
            # сколько в день нужно откладывать, чтобы успеть
            need_per_day = goal.target_amount / days_to_goal
            # покупка «съедает» amount, это amount / need_per_day дней цели
            goal_days_shift = amount / need_per_day

    return {
        "amount": round(amount, 2),
        "free_before": round(free_before, 2),
        "free_after": round(free_after, 2),
        "can_afford": can_afford,
        "shortfall": round(shortfall, 2),
        "days_of_free": round(days_of_free, 1)
        if days_of_free != float("inf")
        else float("inf"),
        "goal_days_shift": round(goal_days_shift, 0),
    }