from build_description import chapter_times, format_description, hashtags_from_tags


def test_chapter_times_first_is_zero_and_cumulative():
    beats = [{"scene": "title"}, {"scene": "chapter", "headline": "The Myth"},
             {"scene": "plain"}, {"scene": "chapter", "headline": "The Study"}]
    durs = [25.0, 3.0, 40.0, 3.0]
    chaps = chapter_times(beats, durs, overlap=0.0)
    assert chaps[0][0] == "00:00"
    assert [c[1] for c in chaps] == ["The Myth", "The Study"]
    assert chaps[1][0] == "01:08"       # 25+3+40 = 68s


def test_chapter_times_accounts_for_overlap_shrink():
    beats = [{"scene": "chapter", "headline": "A"}, {"scene": "plain"},
             {"scene": "chapter", "headline": "B"}]
    durs = [3.0, 40.0, 3.0]
    chaps = chapter_times(beats, durs, overlap=0.5)
    assert chaps[-1][0] == "00:42"      # 3+40 - 0.5*2 = 42.0


def test_format_description_has_chapters_source_hashtags():
    d = format_description("A hook line.", [("00:00", "Intro"), ("01:08", "The Study"),
                                            ("02:00", "The Reveal")],
                           "Estes 2012", ["#dna", "#history", "#ancestry"])
    assert "A hook line." in d
    assert "00:00 Intro" in d and "01:08 The Study" in d
    assert "Estes 2012" in d
    assert "#dna" in d


def test_format_description_omits_chapter_block_when_too_few():
    d = format_description("Hook.", [("00:00", "Intro")], "Src", ["#x"])
    assert "00:00" not in d
    assert "Hook." in d and "#x" in d


def test_hashtags_from_tags_sanitizes_and_caps():
    tags = ["cherokee dna", "native american ancestry", "DNA Testing", "bryc et al."]
    h = hashtags_from_tags(tags, n=3)
    assert h == ["#cherokeedna", "#nativeamericanancestry", "#dnatesting"]
