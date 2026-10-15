"""Tests for the Brazilian Portuguese normalizer"""

import re
import time

import pytest
from hypothesis import (
    given,
    strategies as st,
)

from api.src.services.text_processing.normalization import get_normalizer
from api.src.structures.schemas import NormalizationOptions

PORTUGUESE = get_normalizer("p")
OPTIONS = NormalizationOptions()
BUDGET_S = 2.0

CASES = [
    # cardinals
    ("Comprei 3 livros", "Comprei três livros"),
    ("São 16 anos", "São dezesseis anos"),
    ("Tem 100 anos", "Tem cem anos"),
    ("Tem 101 anos", "Tem cento e um anos"),
    ("Há 1.200 carros", "Há mil e duzentos carros"),
    ("Há 1.234 carros", "Há mil duzentos e trinta e quatro carros"),
    ("Há 1.000.000 de habitantes", "Há um milhão de habitantes"),
    ("Em 2024 choveu", "Em dois mil e vinte e quatro choveu"),
    ("Fez -5 graus", "Fez menos cinco graus"),
    ("Itens 1, 2 e 3.", "Itens um, dois e três."),
    # decimals
    ("O valor é 3,14", "O valor é três vírgula um quatro"),
    ("Cresceu 0,05", "Cresceu zero vírgula zero cinco"),
    ("Mede 1.234,5 metros", "Mede mil duzentos e trinta e quatro vírgula cinco metros"),
    ("Subiu 50%", "Subiu cinquenta por cento"),
    ("Caiu 2,5 %", "Caiu dois vírgula cinco por cento"),
    # currency
    ("Custa R$ 10", "Custa dez reais"),
    ("Custa R$ 1", "Custa um real"),
    ("Custa R$ 1,50", "Custa um real e cinquenta centavos"),
    ("Custa R$10,5", "Custa dez reais e cinquenta centavos"),
    ("Custa R$ 0,01", "Custa zero reais e um centavo"),
    (
        "Pagou R$ 1.234,56",
        "Pagou mil duzentos e trinta e quatro reais e cinquenta e seis centavos",
    ),
    ("Ganhou R$ 1.000.000", "Ganhou um milhão de reais"),
    ("Ganhou R$ 1.200.000", "Ganhou um milhão e duzentos mil reais"),
    ("Lucro de R$ 2,5 milhões", "Lucro de dois vírgula cinco milhões de reais"),
    ("Salário de R$ 5 mil", "Salário de cinco mil reais"),
    ("Custa US$ 100", "Custa cem dólares"),
    ("Custa $5", "Custa cinco dólares"),
    ("Custa € 20,10", "Custa vinte euros e dez centavos"),
    ("Gasolina a R$ 5,899", "Gasolina a cinco vírgula oito nove nove reais"),
    # time
    ("Chego às 14:30", "Chego às catorze horas e trinta minutos"),
    ("Chego às 9:30h", "Chego às nove horas e trinta minutos"),
    ("Chego à 1:00", "Chego à uma hora"),
    ("Chego às 00:00", "Chego às zero hora"),
    ("Chego às 22:01", "Chego às vinte e duas horas e um minuto"),
    ("Chego às 14h", "Chego às catorze horas"),
    ("Chego às 14h30", "Chego às catorze horas e trinta minutos"),
    ("Chego às 14h30min", "Chego às catorze horas e trinta minutos"),
    ("Abre das 10h às 12h", "Abre das dez horas às doze horas"),
    ("Abre das 10:00-12:00", "Abre das dez horas-doze horas"),
    ("Atendimento 24h", "Atendimento vinte e quatro horas"),
    ("Chego às 25:00", "Chego às 25:00"),
    ("Chego às 10:30:45", "Chego às 10:30:45"),
    # ordinary text
    ("Ação, coração, você está à vontade.", "Ação, coração, você está à vontade."),
    ("São Paulo é ótima, não é?", "São Paulo é ótima, não é?"),
    # left to espeak
    (
        "Veja https://exemplo.com.br/pagina/2024?id=5",
        "Veja https://exemplo.com.br/pagina/2024?id=5",
    ),
    ("Acesse www.site.com:8080", "Acesse www.site.com:8080"),
    ("Escreva para contato123@gmail.com", "Escreva para contato123@gmail.com"),
    ("Servidor 192.168.0.1", "Servidor 192.168.0.1"),
    ("versão 2.0.1 e Python 3.12", "versão 2.0.1 e Python 3.12"),
    ("CPF 123.456.789-00", "CPF 123.456.789-00"),
    ("CEP 01310-100", "CEP 01310-100"),
    ("Em 15/10/2026", "Em 15/10/2026"),
    ("O art. 5º e a 1ª vez", "O art. 5º e a 1ª vez"),
    ("nº 007", "nº 007"),
    ("Dr. Silva e Sra. Lima", "Dr. Silva e Sra. Lima"),
    ("var_5 e x=5", "var_5 e x=5"),
    ("covid-19 e MP3", "covid-19 e MP3"),
    ("I paid $5.50", "I paid $5.50"),
]


@pytest.mark.parametrize("text, expected", CASES, ids=[text for text, _ in CASES])
def test_normalize(text, expected):
    assert PORTUGUESE.normalize(text, OPTIONS) == expected


@pytest.mark.parametrize("text, expected", CASES, ids=[text for text, _ in CASES])
def test_output_is_stable(text, expected):
    assert PORTUGUESE.normalize(expected, OPTIONS) == expected


@pytest.mark.parametrize("text", ["", " ", "\n\t"])
def test_empty_input(text):
    assert PORTUGUESE.normalize(text, OPTIONS).strip() == ""


number_token = st.one_of(
    st.integers(min_value=-999_999_999, max_value=999_999_999).map(str),
    st.integers(min_value=1000, max_value=999_999_999).map(
        lambda n: f"{n:,}".replace(",", ".")
    ),
    st.floats(min_value=-99_999, max_value=99_999, allow_nan=False).map(
        lambda f: f"{f:.2f}".replace(".", ",")
    ),
    st.integers(min_value=0, max_value=999_999).map(lambda n: f"R$ {n}"),
    st.integers(min_value=0, max_value=99_999).map(
        lambda n: f"R$ {n // 100},{n % 100:02d}"
    ),
    st.integers(min_value=1, max_value=999).map(lambda n: f"{n}%"),
    st.integers(min_value=0, max_value=23).flatmap(
        lambda h: st.integers(min_value=0, max_value=59).map(lambda m: f"{h}:{m:02d}")
    ),
    st.integers(min_value=0, max_value=23).map(lambda h: f"{h}h"),
)
plain_word = st.from_regex(r"\A[a-záéíóúâêôãõç]{1,12}\Z")
plain_prose = st.lists(plain_word, min_size=1, max_size=8).map(" ".join)
open_punct = st.sampled_from(["", "(", '"'])
close_punct = st.sampled_from(["", ".", ",", "!", "?", ")", ";", '"'])


@given(plain_prose, open_punct, number_token, close_punct, plain_prose)
def test_standalone_numbers_are_spelled_out(before, open_, number, close, after):
    out = PORTUGUESE.normalize(f"{before} {open_}{number}{close} {after}", OPTIONS)
    assert not re.search(r"\d", out), out


@given(plain_prose)
def test_plain_prose_is_untouched(text):
    assert PORTUGUESE.normalize(text, OPTIONS) == text


def _elapsed(payload: str) -> float:
    start = time.monotonic()
    PORTUGUESE.normalize(payload, OPTIONS)
    return time.monotonic() - start


def test_floods_are_fast():
    for payload in ("9" * 80_000, "a" * 100_000, "a." * 50_000, "-" * 100_000):
        assert _elapsed(payload) < BUDGET_S


def test_pattern_floods_scale_linearly():
    for unit in (
        "1 ",
        "1.",
        "1,",
        "123.",
        "1.234,",
        "R$1,",
        "R$ 1 mil ",
        "12:34 ",
        "1:2",
        "1h ",
        "1h1",
        " -5",
        "5%",
    ):
        small = _elapsed(unit * 2_000)
        large = _elapsed(unit * 8_000)
        assert large / max(small, 0.05) < 9.0, unit


def test_oversized_numbers_are_left_alone():
    assert PORTUGUESE.normalize("9" * 400, OPTIONS) == "9" * 400
    assert PORTUGUESE.normalize("R$ " + "9" * 400, OPTIONS) == "R$ " + "9" * 400
    assert PORTUGUESE.normalize("1.000" * 400, OPTIONS)
