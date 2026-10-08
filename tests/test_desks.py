from office import look_for, short_name


def test_look_is_deterministic():
    assert look_for("abc") == look_for("abc")
    assert set(look_for("abc")) == {"hair", "shirt", "skin"}


def test_short_name_cuts_on_a_word_boundary():
    assert short_name("Agent office gamification brainstorm") == "Agent office"
    assert short_name("Supercalifragilisticexpialidocious") == "Supercalifragil…"
    assert short_name("   ") == "Untitled chat" and short_name(None) == "Untitled chat"


def test_short_name_drops_trailing_punctuation():
    assert short_name("Review-loop: Slack-triggered PR review") == "Review-loop"
    assert short_name("Fix: tap highlight") == "Fix: tap"
