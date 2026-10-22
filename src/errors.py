"""Иерархия исключений проекта.

Все ошибки проекта наследуются от FinanceError, чтобы вызывающий код мог
поймать либо конкретную ошибку, либо всё разом через родителя.

Пример:
    try:
        load_accounts("data/accounts.csv")
    except FinanceError as err:
        print(f"Не удалось загрузить данные: {err}")
"""


class FinanceError(Exception):
    """Базовая ошибка проекта. От неё наследуются все остальные."""


class DataError(FinanceError):
    """Ошибка данных: файл не найден, битый формат, невалидное значение.

    Атрибуты:
        line_no: номер строки в файле (если известен), начиная с 1.
        field:   имя поля/колонки, в котором проблема (если известно).
    """

    def __init__(self, message, line_no=None, field=None):
        super().__init__(message)
        self.line_no = line_no
        self.field = field

    def __str__(self):
        parts = [super().__str__()]
        if self.line_no is not None:
            parts.append(f"строка {self.line_no}")
        if self.field is not None:
            parts.append(f"поле {self.field!r}")
        return " | ".join(parts)


class ValidationError(FinanceError):
    """Ошибка валидации значения: отрицательный баланс, нулевая ставка и т.п.

    Атрибуты:
        value: само «плохое» значение, чтобы было видно, что пришло.
    """

    def __init__(self, message, value=None):
        super().__init__(message)
        self.value = value

    def __str__(self):
        base = super().__str__()
        if self.value is None:
            return base
        return f"{base} (получено: {self.value!r})"