"""Who is signed in on which connection. Connections are plain strings here."""

from server.net.sessions import Sessions


def numbers(*values):
    """A `pick_number` that returns the given numbers one after the other."""
    remaining = list(values)
    return lambda: remaining.pop(0)


def test_a_new_connection_is_signed_out():
    sessions = Sessions()
    assert not sessions.is_signed_in("a")
    assert sessions.name_of("a") is None
    assert not sessions.is_guest("a")


def test_an_account_can_sign_in():
    sessions = Sessions()
    assert sessions.sign_in_account("a", "Mara") is None
    assert sessions.is_signed_in("a")
    assert sessions.name_of("a") == "Mara"
    assert not sessions.is_guest("a")


def test_a_guest_gets_guest_plus_four_digits():
    sessions = Sessions()
    assert sessions.sign_in_guest("a", numbers(1234)) == "Guest1234"
    assert sessions.is_signed_in("a")
    assert sessions.is_guest("a")
    assert sessions.name_of("a") == "Guest1234"


def test_small_guest_numbers_are_filled_with_zeros():
    assert Sessions().sign_in_guest("a", numbers(7)) == "Guest0007"


def test_two_guests_who_draw_the_same_number_get_different_names():
    sessions = Sessions()
    first = sessions.sign_in_guest("a", numbers(1234))
    second = sessions.sign_in_guest("b", numbers(1234))
    assert first == "Guest1234"
    assert second == "Guest1235"


def test_the_guest_number_after_9999_is_0000():
    sessions = Sessions()
    sessions.sign_in_guest("a", numbers(9999))
    assert sessions.sign_in_guest("b", numbers(9999)) == "Guest0000"


def test_when_every_guest_name_is_in_use_nobody_is_signed_in():
    sessions = Sessions()
    for number in range(10_000):
        sessions.sign_in_guest(number, numbers(number))
    assert sessions.sign_in_guest("late", numbers(5)) is None
    assert not sessions.is_signed_in("late")


def test_a_second_log_in_of_an_account_replaces_the_first():
    sessions = Sessions()
    sessions.sign_in_account("a", "Mara")
    assert sessions.sign_in_account("b", "Mara") == "a"
    assert not sessions.is_signed_in("a")
    assert sessions.name_of("b") == "Mara"


def test_replacing_ignores_the_case_of_the_name():
    sessions = Sessions()
    sessions.sign_in_account("a", "Mara")
    assert sessions.sign_in_account("b", "mara") == "a"


def test_different_accounts_do_not_replace_each_other():
    sessions = Sessions()
    sessions.sign_in_account("a", "Mara")
    assert sessions.sign_in_account("b", "Tiago") is None
    assert sessions.name_of("a") == "Mara"
    assert sessions.name_of("b") == "Tiago"


def test_sign_out_works_once():
    sessions = Sessions()
    sessions.sign_in_account("a", "Mara")
    assert sessions.sign_out("a") is True
    assert not sessions.is_signed_in("a")
    assert sessions.sign_out("a") is False


def test_sign_out_of_a_connection_that_never_signed_in_is_refused():
    assert Sessions().sign_out("a") is False


def test_a_guest_name_is_free_again_after_the_guest_left():
    sessions = Sessions()
    sessions.sign_in_guest("a", numbers(1234))
    sessions.sign_out("a")
    assert sessions.sign_in_guest("b", numbers(1234)) == "Guest1234"


def test_an_account_that_left_can_log_in_again_without_replacing_anyone():
    sessions = Sessions()
    sessions.sign_in_account("a", "Mara")
    sessions.sign_out("a")
    assert sessions.sign_in_account("b", "Mara") is None
