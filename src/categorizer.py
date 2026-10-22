"""Категоризация транзакций по правилам из rules.json.

Логика:
1. Правила сортируются по убыванию priority (subscriptions=10 раньше groceries=5).
2. Для каждой транзакции:
   - если is_transfer=True — пропускаем (перевод, не расход);
   - если category уже задана вручную — уважаем;
   - иначе идём по правилам, первое совпадение даёт категорию;
   - если ни одно не подошло — "uncategorized".
"""

from src.models import Transaction, CategoryRule


def categorize(transactions, rules):
    """Проставляет category каждой транзакции по правилам.

    Возвращает тот же список (мутирует объекты на месте), чтобы удобно
    было использовать в цепочке вызовов.
    """
    # приоритет: чем больше priority, тем раньше проверяем
    sorted_rules = sorted(rules, key=lambda r: r.priority, reverse=True)

    for tx in transactions:
        if tx.is_transfer:
            # перевод между своими счетами — не расход, категория не нужна
            continue
        if tx.category:
            # ручная категория — уважаем, не перезаписываем
            continue

        tx.category = "uncategorized"
        for rule in sorted_rules:
            if rule.matches(tx.description):
                tx.category = rule.category
                break

    return transactions


def mark_transfers(transactions):
    """Эвристика: если в описании есть 'перевод' — ставим is_transfer=True.

    Вынесено из storage.py, чтобы бизнес-логика (что считать переводом)
    жила в одном месте — categorizer.py. Если завтра правило изменится
    ('transfer', 'перевод между счетами'), правим только здесь.
    """
    for tx in transactions:
        if "перевод" in tx.description.lower():
            tx.is_transfer = True
    return transactions