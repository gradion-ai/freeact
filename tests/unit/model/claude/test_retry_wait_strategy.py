from freeact.model.claude.retry import WaitExponential


def test_basic_exponential_backoff():
    strategy = WaitExponential(multiplier=1)
    assert strategy.compute_wait_time(1) == 1  # 1 * 2^0
    assert strategy.compute_wait_time(2) == 2  # 1 * 2^1
    assert strategy.compute_wait_time(3) == 4  # 1 * 2^2
    assert strategy.compute_wait_time(4) == 8  # 1 * 2^3


def test_with_multiplier():
    strategy = WaitExponential(multiplier=0.5)
    assert strategy.compute_wait_time(1) == 0.5  # 0.5 * 2^0
    assert strategy.compute_wait_time(2) == 1.0  # 0.5 * 2^1
    assert strategy.compute_wait_time(3) == 2.0  # 0.5 * 2^2


def test_with_min_max():
    strategy = WaitExponential(multiplier=1, min=2, max=6)
    assert strategy.compute_wait_time(1) == 2  # min bound
    assert strategy.compute_wait_time(2) == 2
    assert strategy.compute_wait_time(3) == 4
    assert strategy.compute_wait_time(4) == 6  # max bound
    assert strategy.compute_wait_time(5) == 6  # max bound


def test_overflow_returns_max():
    strategy = WaitExponential(multiplier=1, max=100)
    # Using a very large retry attempt that would cause overflow
    assert strategy.compute_wait_time(1000) == 100
