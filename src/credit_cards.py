"""Анализ кредиток: когда закрывать, хватит ли денег, сколько нужно отложить.

Для каждой кредитки:
1. Дата окончания льготного периода (grace_end).
2. Сколько дней осталось от today.
3. Хватит ли savings_balance к grace_end, чтобы закрыть spent.
4. Если не хватает — сколько ещё отложить (нужно / дни до).
5. Недополученный % накопительного (spent * rate * дни / 365).

Упрощения (в README):
- считаем, что spent закрывается ровно в grace_end (в реальности — за пару дней);
- savings не пополняется (в реальности — вы откладываете с зарплаты);
- ставка накопительного — берём текущую (первую из savings_rates).
"""

from datetime import date

from src.models import CreditCard


def analyze_card(card, savings_balance, today, savings_rate):
    """Анализ одной кредитки.

    Args:
        card: CreditCard.
        savings_balance: сколько сейчас на накопительном.
        today: date — «сегодня».
        savings_rate: ставка накопительного (0.18 = 18%).

    Returns:
        dict с ключами:
            "card": CreditCard,
            "grace_end": date,
            "days_left": int,
            "spent": float,
            "enough": bool,           # хватает ли savings_balance
            "shortfall": float,       # сколько не хватает (0 если хватает)
            "need_per_day": float,    # сколько откладывать в день (если не хватает)
            "lost_interest": float,   # недополученный % накопительного
    """
    grace_end = card.grace_end
    days_left = (grace_end - today).days
    if days_left < 0:
        days_left = 0   # льготный период уже прошёл — считаем «сегодня»

    spent = card.spent
    enough = savings_balance >= spent
    shortfall = max(0.0, spent - savings_balance)

    # сколько откладывать в день, чтобы добрать shortfall к grace_end
    if days_left > 0:
        need_per_day = shortfall / days_left
    else:
        need_per_day = shortfall   # «сегодня» — нужно всё сразу

    # недополученный % накопительного: spent * rate / 365 * days_left
    lost_interest = spent * savings_rate / 365.0 * days_left

    return {
        "card": card,
        "grace_end": grace_end,
        "days_left": days_left,
        "spent": spent,
        "enough": enough,
        "shortfall": round(shortfall, 2),
        "need_per_day": round(need_per_day, 2),
        "lost_interest": round(lost_interest, 2),
    }


def analyze_all_cards(cards, savings_balance, today, savings_rate):
    """Анализ всех кредиток. Возвращает список dict (по одному на карту)."""
    return [
        analyze_card(card, savings_balance, today, savings_rate)
        for card in cards
    ]
    