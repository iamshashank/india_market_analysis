"""Backtest / comparison math — pure-function regression tests."""
from signals.backtest_scores import spearman, quantile_spread


def test_spearman_perfect_positive():
    xs = [1, 2, 3, 4, 5, 6]
    ys = [10, 20, 30, 40, 50, 60]
    assert spearman(xs, ys) == 1.0


def test_spearman_perfect_negative():
    xs = [1, 2, 3, 4, 5, 6]
    ys = [60, 50, 40, 30, 20, 10]
    assert spearman(xs, ys) == -1.0


def test_spearman_too_few_points():
    assert spearman([1, 2, 3], [3, 2, 1]) is None


def test_spearman_handles_ties():
    # ties shouldn't blow up; constant y -> zero variance -> None
    assert spearman([1, 1, 2, 2, 3], [5, 5, 5, 5, 5]) is None


def test_quantile_spread_orders_top_minus_bottom():
    # scores ascending with returns ascending -> positive spread
    pairs = [(i, i * 1.0) for i in range(1, 13)]  # 12 names
    sp = quantile_spread(pairs)
    assert sp is not None and sp > 0


def test_quantile_spread_too_few():
    assert quantile_spread([(1, 1), (2, 2)]) is None
