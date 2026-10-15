"""Brazilian Portuguese text normalization: numbers, money, time."""

import functools
import re

from num2words import num2words

from .base import Normalizer

CURRENCIES = {
    "R$": ("real", "reais"),
    "US$": ("dólar", "dólares"),
    "$": ("dólar", "dólares"),
    "€": ("euro", "euros"),
}

# scale nouns take "de" before the currency, as in num2words' own pt_BR to_currency
LARGE_SCALES = (
    "milhão",
    "milhões",
    "bilhão",
    "bilhões",
    "trilhão",
    "trilhões",
    "quatrilhão",
    "quatrilhões",
)


def cardinal(number: int) -> str:
    # num2words writes "mil, duzentos e trinta", the comma would be read as a pause
    return num2words(number, lang="pt_BR").replace(",", "")


DIGITS = tuple(cardinal(d) for d in range(10))


def decimal(integer: str, fraction: str | None) -> str:
    """Integer part as a cardinal, fraction digit by digit like num2words floats."""
    words = cardinal(int(integer))
    if fraction:
        words += " vírgula " + " ".join(DIGITS[int(d)] for d in fraction)
    return words


def feminine(words: str) -> str:
    return re.sub(r"\bdois$", "duas", re.sub(r"\bum$", "uma", words))


def clock(hour: int, minute: int) -> str:
    words = f"{feminine(cardinal(hour))} {'hora' if hour < 2 else 'horas'}"
    if minute:
        words += f" e {cardinal(minute)} {'minuto' if minute == 1 else 'minutos'}"
    return words


def unchanged_on_error(handler):
    """Leave the token as is when the number is beyond what num2words or int() accept."""

    @functools.wraps(handler)
    def wrapped(m: re.Match[str]) -> str:
        try:
            return handler(m)
        except (OverflowError, ValueError):
            return m.group()

    return wrapped


class PortugueseNormalizer(Normalizer):
    lang_codes = ("p", "pt-br")

    # 14:30 and 9:30h. Ratios and verse refs like 3:16 read as times too.
    CLOCK_PATTERN = re.compile(
        r"(?<![\w.,:])([01]?[0-9]|2[0-3]):([0-5][0-9])h?(?![\w:]|[.,][0-9])"
    )
    HOURS_PATTERN = re.compile(
        r"(?<![\w.,:])([0-9]{1,2})h(?:([0-5][0-9])(?:min)?)?(?!\w)"
    )

    def times(self, text: str) -> str:
        def handle(m: re.Match[str]) -> str:
            return clock(int(m.group(1)), int(m.group(2) or 0))

        text = self.CLOCK_PATTERN.sub(handle, text)
        return self.HOURS_PATTERN.sub(handle, text)

    def numbers(self, text: str) -> str:
        return self._cardinals(self._money(text))

    # Digits joined to letters or to other digits by . , : / = - are left to
    # espeak: dates, phone numbers, CEPs, versions, ids, URL parts.
    NOT_GLUED_BEFORE = r"(?<![\w.,:/=-])"
    NOT_GLUED_AFTER = r"(?!\w|[.,:/=-]\w)"
    # pt-BR separators: 1.234.567,89
    AMOUNT = r"([0-9]{1,3}(?:\.[0-9]{3})+|[0-9]+)(?:,([0-9]+))?"

    MONEY_PATTERN = re.compile(
        r"(?<!\w)(R\$|US\$|\$|€) ?"
        + AMOUNT
        + r"(?: (mil|milhão|milhões|bilhão|bilhões|trilhão|trilhões))?"
        + NOT_GLUED_AFTER
    )

    def _money(self, text: str) -> str:
        @unchanged_on_error
        def handle(m: re.Match[str]) -> str:
            singular, plural = CURRENCIES[m.group(1)]
            integer = m.group(2).replace(".", "")
            fraction, scale = m.group(3), m.group(4)

            cents = 0
            if scale:
                amount = f"{decimal(integer, fraction)} {scale}"
            elif fraction and len(fraction) > 2:
                amount = decimal(integer, fraction)
            else:
                amount = cardinal(int(integer))
                cents = int(fraction.ljust(2, "0")) if fraction else 0

            unit = singular if amount == "um" else plural
            de = " de" if amount.endswith(LARGE_SCALES) else ""
            words = f"{amount}{de} {unit}"
            if cents:
                coin = "centavo" if cents == 1 else "centavos"
                words += f" e {cardinal(cents)} {coin}"
            return words

        return self.MONEY_PATTERN.sub(handle, text)

    NUMBER_PATTERN = re.compile(
        NOT_GLUED_BEFORE + r"(-?)" + AMOUNT + r"( ?%)?" + NOT_GLUED_AFTER
    )

    def _cardinals(self, text: str) -> str:
        @unchanged_on_error
        def handle(m: re.Match[str]) -> str:
            sign, integer, fraction, percent = m.groups()
            integer = integer.replace(".", "")
            # leading zeros mark codes (007, 0800), not quantities
            if len(integer) > 1 and integer.startswith("0"):
                return m.group()

            words = decimal(integer, fraction)
            if sign:
                words = f"menos {words}"
            if percent:
                words += " por cento"
            return words

        return self.NUMBER_PATTERN.sub(handle, text)
