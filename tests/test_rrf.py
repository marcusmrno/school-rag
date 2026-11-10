from pytest import approx
from retrieval.search import rrf

def test_rrf_sums_reciprocal_ranks():
    assert rrf([[10, 20], [20, 30]]) == approx({10: 1 / 61, 20: 1 / 62 + 1 / 61, 30: 1 / 62})

def test_rrf_orders_by_score():
    assert list(rrf([[10, 20], [20, 30]])) == [20, 10, 30]

def test_rrf_empty_list_keeps_other_order():
    assert list(rrf([[3, 1, 2], []])) == [3, 1, 2]

def test_rrf_ties_keep_first_list_order():
    assert list(rrf([[1], [2]])) == [1, 2]

def test_rrf_custom_k():
    assert rrf([[7]], k=0) == {7: 1.0}
