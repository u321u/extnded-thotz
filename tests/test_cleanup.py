from extnded_thotz.cleanup import clean_transcript


def test_removes_leading_filler():
    assert clean_transcript("um hello world") == "Hello world"


def test_removes_mid_sentence_filler_with_comma():
    assert clean_transcript("I think, uh, we should ship it.") == "I think, we should ship it."


def test_fillers_can_be_disabled():
    assert clean_transcript("um hi", remove_fillers_enabled=False) == "Um hi"


def test_new_line_command():
    assert clean_transcript("first point new line second point") == "First point\nSecond point"


def test_new_paragraph_command():
    assert clean_transcript("one new paragraph two") == "One\n\nTwo"


def test_command_swallows_adjacent_punctuation():
    assert clean_transcript("note, new line, buy milk") == "Note\nBuy milk"


def test_voice_commands_can_be_disabled():
    out = clean_transcript("go to a new line please", voice_commands_enabled=False)
    assert out == "Go to a new line please"


def test_spacing_before_punctuation_fixed():
    assert clean_transcript("hello ,  world .") == "Hello, world."


def test_space_added_after_comma():
    assert clean_transcript("hello,world") == "Hello, world"


def test_capitalizes_each_sentence():
    assert clean_transcript("this is one. this is two.") == "This is one. This is two."


def test_empty_and_whitespace():
    assert clean_transcript("") == ""
    assert clean_transcript("   ") == ""


def test_filler_like_words_kept():
    # 'um' inside words must never be touched
    assert clean_transcript("the summer hummus is yummy") == "The summer hummus is yummy"
