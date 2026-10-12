from app.quota import QuotaManager


def make(**overrides):
    params = dict(budget=100, reserve_fraction=0.2, global_rpm=10_000, user_rpm=10_000, uploads_per_day=5)
    params.update(overrides)
    return QuotaManager(**params)


def use(manager, user, times):
    granted = 0
    for _ in range(times):
        if manager.check_and_consume(user).ok:
            granted += 1
    return granted


def test_single_user_gets_the_pool_and_reserve_is_kept():
    q = make()
    assert use(q, "a", 200) == 80
    denied = q.check_and_consume("a")
    assert not denied.ok and denied.reason == "reserve"


def test_new_user_can_use_the_reserve():
    q = make()
    use(q, "a", 200)
    assert use(q, "b", 200) == 20
    assert q.check_and_consume("b").reason == "daily_budget"


def test_two_users_split_evenly_and_a_third_gets_the_reserve():
    q = make()
    q.check_and_consume("a")
    granted = {"a": 1, "b": 0}
    for _ in range(100):
        for user in ("a", "b"):
            if q.check_and_consume(user).ok:
                granted[user] += 1
    assert granted == {"a": 40, "b": 40}
    assert use(q, "c", 100) == 20


def test_share_shrinks_as_users_join():
    q = make()
    q.check_and_consume("a")
    assert q.status("a")["your_share"] == 80
    q.check_and_consume("b")
    assert q.status("a")["your_share"] == 40
    q.check_and_consume("c")
    assert q.status("a")["your_share"] == 26


def test_per_user_rate_limit():
    q = make(user_rpm=2)
    assert q.check_and_consume("a").ok
    assert q.check_and_consume("a").ok
    third = q.check_and_consume("a")
    assert not third.ok and third.reason == "user_rpm" and third.retry_after > 0


def test_global_rate_limit():
    q = make(global_rpm=2)
    assert q.check_and_consume("a").ok
    assert q.check_and_consume("b").ok
    assert q.check_and_consume("c").reason == "global_rpm"


def test_upload_limit():
    q = make(uploads_per_day=3)
    assert [q.consume_upload("a") for _ in range(4)] == [True, True, True, False]


def test_refund_restores_quota():
    q = make()
    q.check_and_consume("a")
    q.refund("a")
    status = q.status("a")
    assert status["your_used"] == 0 and status["total_used"] == 0
