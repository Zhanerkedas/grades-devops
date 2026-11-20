"""Проверка корректности расчётов среднего балла и GPA (unit-тесты)."""
import pytest

from app import services


@pytest.mark.parametrize("score,letter,gpa", [
    (100, "A", 4.0), (95, "A", 4.0), (94, "A-", 3.67), (90, "A-", 3.67), (85, "B+", 3.33),
    (80, "B", 3.0), (75, "B-", 2.67), (70, "C+", 2.33), (65, "C", 2.0), (60, "C-", 1.67),
    (55, "D+", 1.33), (50, "D", 1.0), (49, "F", 0.0), (0, "F", 0.0),
])
def test_letter_grade_boundaries(score, letter, gpa):
    assert services.letter_grade(score) == (letter, gpa)


@pytest.mark.parametrize("bad", [-1, 101, "90", None])
def test_letter_grade_invalid(bad):
    with pytest.raises(services.ValidationError):
        services.letter_grade(bad)


def test_average_simple():
    assert services.average_score([90, 80, 70]) == 80.0


def test_average_rounding():
    assert services.average_score([90, 85, 82]) == 85.67


def test_average_empty():
    assert services.average_score([]) is None


def test_weighted_gpa_by_credits():
    # 95 (A, 4.0) × 5 кредитов + 72 (C+, 2.33) × 3 кредита = (20 + 6.99) / 8 = 3.37
    assert services.weighted_gpa([(95, 5), (72, 3)]) == 3.37


def test_weighted_gpa_equal_credits():
    assert services.weighted_gpa([(100, 4), (50, 4)]) == 2.5


def test_weighted_gpa_empty():
    assert services.weighted_gpa([]) is None
