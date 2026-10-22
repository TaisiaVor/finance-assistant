"""Модели данных: счета, кредиты, кредитки, платежи, цели.

Используем обычные классы с __init__ и self (как на семинаре 8),
а не @dataclass, чтобы было видно каждую строчку и её можно было объяснить.

Для проверок используем @property (семинар 9): баланс не может быть
отрицательным, ставка — отрицательной.
"""

from datetime import date
from src.errors import ValidationError


class Account:
    """Счёт: дебетовая карта, накопительный, кредитка, кредит."""

    def __init__(self, account_id, name, balance, kind):
        self.account_id = account_id
        self.name = name
        self._balance = None          # ставим через property, чтобы сработала проверка
        self.balance = balance
        self.kind = kind              # "debit" | "savings" | "credit_card" | "loan"

    @property
    def balance(self):
        return self._balance

    @balance.setter
    def balance(self, value):
        if value < 0:
            raise ValidationError("Баланс счёта не может быть отрицательным", value=value)
        self._balance = value

    def __str__(self):
        return f"{self.name} ({self.kind}): {self.balance:.2f} RUB"


class Loan:
    """Кредит: остаток, ставка, ежемесячный платёж, день платежа, цель."""

    def __init__(self, loan_id, name, balance, rate, monthly_payment,
                 day_of_month, target_date=None):
        self.loan_id = loan_id
        self.name = name
        self._balance = None
        self.balance = balance
        self.rate = rate
        self.monthly_payment = monthly_payment
        self.day_of_month = day_of_month
        self.target_date = target_date   # date | None

    @property
    def balance(self):
        return self._balance

    @balance.setter
    def balance(self, value):
        if value < 0:
            raise ValidationError("Остаток кредита не может быть отрицательным", value=value)
        self._balance = value

    @property
    def rate(self):
        return self._rate

    @rate.setter
    def rate(self, value):
        if value < 0:
            raise ValidationError("Ставка не может быть отрицательной", value=value)
        self._rate = value

    def last_payment(self):
        """Сумма последнего платежа: либо обычный платёж, либо остаток, если он меньше."""
        return min(self.monthly_payment, self._balance)

    def __str__(self):
        return (
            f"Кредит «{self.name}»: остаток {self.balance:.2f} RUB, "
            f"платёж {self.monthly_payment:.2f} RUB {self.day_of_month}-го числа"
        )


class CreditCard:
    """Кредитка с льготным периодом."""

    def __init__(self, card_id, name, spent, grace_start, grace_days, rate_after):
        self.card_id = card_id
        self.name = name
        self.spent = spent
        self.grace_start = grace_start      # date
        self.grace_days = grace_days        # int, обычно 120
        self.rate_after = rate_after        # ставка после льготного периода

    @property
    def grace_end(self):
        """Дата окончания льготного периода: начало + grace_days."""
        from datetime import timedelta
        return self.grace_start + timedelta(days=self.grace_days)

    def __str__(self):
        return (
            f"Кредитка «{self.name}»: потрачено {self.spent:.2f} RUB, "
            f"льготный период до {self.grace_end}"
        )


class ScheduledPayment:
    """Плановый платёж или регулярный доход."""

    def __init__(self, payment_id, name, amount, day_of_month,
                 period_months=1, category="other"):
        self.payment_id = payment_id
        self.name = name
        self.amount = amount                # отрицательное — расход, положительное — доход
        self.day_of_month = day_of_month
        self.period_months = period_months
        self.category = category            # "credits" | "other_mandatory" | "income"

    def __str__(self):
        sign = "−" if self.amount < 0 else "+"
        return f"{self.name}: {sign}{abs(self.amount):.2f} RUB, {self.day_of_month}-го"


class CategoryRule:
    """Правило категоризации: если в описании есть ключевые слова — категория."""

    def __init__(self, category, keywords, priority=0):
        self.category = category
        self.keywords = keywords
        self.priority = priority

    def matches(self, description):
        """Возвращает True, если описание содержит хотя бы одно ключевое слово."""
        text = description.lower()
        return any(kw.lower() in text for kw in self.keywords)

    def __str__(self):
        return f"Правило «{self.category}»: {self.keywords} (приоритет {self.priority})"


class Goal:
    """Финансовая цель: закрыть кредит к дате или накопить сумму."""

    def __init__(self, name, target_amount, target_date=None, loan_id=None):
        self.name = name
        self.target_amount = target_amount
        self.target_date = target_date      # date | None
        self.loan_id = loan_id              # если цель про кредит — ссылка на Loan.loan_id

    def __str__(self):
        deadline = f" к {self.target_date}" if self.target_date else ""
        return f"Цель «{self.name}»: {self.target_amount:.2f} RUB{deadline}"