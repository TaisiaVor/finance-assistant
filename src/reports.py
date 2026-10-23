"""Сборка текстового отчёта из всех модулей.

reports.py НЕ печатает — он ВОЗВРАЩАЕТ строку. Печатает cli.py.
Это разделение: reports.py — сборка, cli.py — вывод.

Отчёт состоит из блоков:
1. Свободно сейчас (allocator.py).
2. Прогноз (forecast.py).
3. Кредиты (loans.py) — сценарии A vs B.
4. Кредитки (credit_cards.py).
5. Цель (rules.json).
"""

from datetime import date

from src.allocator import free_now
from src.forecast import forecast_balance_with_interest, min_balance
from src.loans import compare_scenarios
from src.credit_cards import analyze_all_cards


def format_money(value):
    """Форматирует число как деньги: 1234.5 → "1 234.50 RUB"."""
    if value is None:
        return "—"
    text = f"{value:,.2f}".replace(",", " ")
    return f"{text} RUB"


def _block_free(alloc):
    lines = ["=== Свободно сейчас ==="]
    lines.append(f"  Дебет:                {format_money(alloc['debit'])}")
    lines.append(f"  Накопительный:        {format_money(alloc['savings'])}")
    lines.append(f"  Заморожено (до {alloc['until']}): {format_money(alloc['frozen'])}")
    lines.append(f"  Подушка:              {format_money(alloc['cushion'])}")
    lines.append(f"  Долг по кредиткам:    {format_money(alloc['credit_card_debt'])}")
    lines.append("  " + "─" * 50)
    lines.append(f"  Реально свободно:     {format_money(alloc['free'])}")
    return lines


def _block_forecast(timeline):
    lines = ["", "=== Прогноз ==="]
    if not timeline:
        lines.append("  нет данных")
        return lines
    worst_date, worst_balance = min_balance(timeline)
    lines.append(f"  Дней:                 {len(timeline)}")
    lines.append(f"  Минимальный баланс:   {format_money(worst_balance)} ({worst_date})")
    if worst_balance < 0:
        lines.append("  ⚠ ВНИМАНИЕ: кассовый разрыв!")
    else:
        lines.append("  ✓ разрыва нет")
    return lines


def _block_loans(loans, today, extra_payment, savings_rate):
    lines = ["", "=== Кредиты (сценарии) ==="]
    for loan in loans:
        result = compare_scenarios(loan, today, extra_payment, savings_rate)
        a = result["A"]
        b = result["B"]
        lines.append(f"  Кредит «{loan.name}»:")
        lines.append(f"    Остаток:            {format_money(loan.balance)}")
        lines.append(f"    По графику:         закроется {a['close_date']}, "
                     f"переплата {format_money(a['total_interest'])}")
        lines.append(f"    Досрочно (+{format_money(extra_payment)}): "
                     f"закроется {b['close_date']}, "
                     f"переплата {format_money(b['total_interest'])}, "
                     f"потеря % на накопит.: {format_money(b['lost_savings'])}")
        if result["conclusion"] == "early_better":
            lines.append(f"    → ВЫГОДНО гасить досрочно: +{format_money(result['net_diff'])}")
        elif result["conclusion"] == "schedule_better":
            lines.append(f"    → НЕВЫГОДНО гасить досрочно: −{format_money(abs(result['net_diff']))}")
        else:
            lines.append("    → без разницы")
    return lines


def _block_cards(cards_results):
    lines = ["", "=== Кредитки ==="]
    for r in cards_results:
        lines.append(f"  {r['card'].name}:")
        lines.append(f"    Потрачено:          {format_money(r['spent'])}")
        lines.append(f"    Льготный до:        {r['grace_end']} ({r['days_left']} дней)")
        if r["enough"]:
            lines.append(f"    ✓ хватит накопительного (потеря %: "
                         f"{format_money(r['lost_interest'])})")
        else:
            lines.append(f"    ⚠ не хватает {format_money(r['shortfall'])} "
                         f"(нужно {format_money(r['need_per_day'])}/день)")
    return lines


def _block_goal(goal, free, today):
    lines = ["", "=== Цель ==="]
    if goal is None:
        lines.append("  не задана")
        return lines
    lines.append(f"  {goal}")
    if goal.target_date is None:
        return lines
    days = (goal.target_date - today).days
    if days <= 0:
        lines.append("  ⚠ дата цели уже прошла")
        return lines
    need = goal.target_amount / days
    lines.append(f"  Дней до цели:         {days}")
    lines.append(f"  Нужно откладывать:    {format_money(need)}/день")
    if free >= goal.target_amount:
        lines.append(f"  ✓ свободно ({format_money(free)}) хватает на всю цель")
    else:
        lines.append(f"  ⚠ свободно ({format_money(free)}) < цели")
    return lines


def build_report(accounts, payments, loans, cards, rules, today, horizon_days=60):
    """Собирает полный отчёт. Возвращает строку.

    Args:
        accounts, payments, loans, cards: списки объектов.
        rules: словарь из load_rules.
        today: date.
        horizon_days: на сколько дней прогноз (60 по умолчанию).

    Returns:
        str — готовый отчёт (cli.py её печатает).
    """
    alloc = free_now(accounts, payments, loans, cards, rules, today)

    end = today.replace(year=today.year)   # просто копия
    # прибавляем horizon_days через timedelta
    from datetime import timedelta
    end = today + timedelta(days=horizon_days)
    timeline = forecast_balance_with_interest(accounts, payments, loans, rules, today, end)

    savings_rate = rules["raw"]["savings_rates"][0]["rate"]
    goal = rules["goal"]

    lines = []
    lines.extend(_block_free(alloc))
    lines.extend(_block_forecast(timeline))
    lines.extend(_block_loans(loans, today, extra_payment=10000, savings_rate=savings_rate))
    lines.extend(_block_cards(analyze_all_cards(cards, alloc["savings"], today, savings_rate)))
    lines.extend(_block_goal(goal, alloc["free"], today))
    return "\n".join(lines)