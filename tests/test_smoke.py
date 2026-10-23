"""Простые проверки на assert. Запуск: python3 -m tests.test_smoke.

pytest не было в курсе (ни базовый, ни продвинутый), поэтому тесты
простые: assert + print в конце. Если assert упал — видно, какой тест.
"""

from datetime import date

from src.errors import DataError, ValidationError
from src.forecast import payment_dates_between
from src.models import Account, Loan, CategoryRule, Transaction
from src.storage import load_accounts
from src.categorizer import categorize
from src.purchases import check_purchase


def test_payment_31_in_february():
    """31-е число в феврале → 28-е (или 29-е в високосный)."""
    loan = Loan("l1", "x", 10000, 0.1, 1000, 31)
    dates = payment_dates_between(loan, date(2026, 2, 1), date(2026, 2, 28))
    assert dates == [date(2026, 2, 28)], f"ожидали 28 фев, получили {dates}"


def test_payment_31_in_april():
    """31-е в апреле (30 дней) → 30-е."""
    loan = Loan("l1", "x", 10000, 0.1, 1000, 31)
    dates = payment_dates_between(loan, date(2026, 4, 1), date(2026, 4, 30))
    assert dates == [date(2026, 4, 30)], f"ожидали 30 апр, получили {dates}"


def test_load_missing_file():
    """Несуществующий файл → DataError."""
    try:
        load_accounts("nonexistent.csv")
        assert False, "ожидали DataError"
    except DataError:
        pass


def test_negative_balance_raises():
    """Отрицательный баланс → ValidationError."""
    try:
        Account("a1", "x", -100, "debit")
        assert False, "ожидали ValidationError"
    except ValidationError:
        pass


def test_categorize_yo_e():
    """Правило 'перекрёсток' (ё) находит 'Перекресток' (е)."""
    rules = [CategoryRule("groceries", ["перекрёсток"], priority=5)]
    tx = Transaction("t1", date(2026, 10, 1), -350, "Перекресток покупка", "acc1")
    categorize([tx], rules)
    assert tx.category == "groceries", f"ожидали groceries, получили {tx.category}"


def test_check_purchase_negative():
    """Отрицательная покупка → ValidationError."""
    rules = {"raw": {"safety_cushion": 0}, "goal": None}
    try:
        check_purchase(-100, [], [], [], [], rules, date.today())
        assert False, "ожидали ValidationError"
    except ValidationError:
        pass


if __name__ == "__main__":
    test_payment_31_in_february()
    test_payment_31_in_april()
    test_load_missing_file()
    test_negative_balance_raises()
    test_categorize_yo_e()
    test_check_purchase_negative()
    print("Все проверки прошли")