from mattergraph_benchmarks import dcg, ndcg_at_k


def test_dcg_and_ndcg_bounds() -> None:
  rel = [3, 2, 1]
  assert dcg(rel) > 0
  score = ndcg_at_k(rel, k=3)
  assert 0.0 <= score <= 1.0
  assert ndcg_at_k([], k=3) == 0.0
