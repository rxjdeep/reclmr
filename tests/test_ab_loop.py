from routes import music


def test_a_loop_is_kept_only_when_it_makes_sense():
    assert music._clean_ab([10, 20]) == [10.0, 20.0]
    assert music._clean_ab([10, None]) == [10.0, None]          # the end is not chosen yet
    assert music._clean_ab([20, 10]) is None                    # end before start
    assert music._clean_ab([-1, 5]) is None
    assert music._clean_ab(['x', 5]) is None
    assert music._clean_ab(None) is None
    assert music._clean_ab([1, 2, 3]) is None
