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


# ── A comprehensive description, modelled on the sibling channel ─────────
# What actually published for indo-european-origin (oPy6XS6KOM4):
#
#     Chapters: 1. Grave mystery 2.
#
#     Chapters:
#     00:00 Two Centuries of Search
#     ...
#
# Two bugs, both in the hook. gen_script asks the model for "SEO description
# with a chapters list", so it writes its OWN list — but the real chapters are
# computed post-render from clip durations, so there are two. And the hook was
# scavenged with re.split(r"(?<=[.!?]) ", desc)[:2], which treats the "1. " and
# "2. " of that list as sentence ends: "Chapters: 1." + "Grave mystery 2.".
#
# The replacement follows the sibling pipeline — a snippet head inside
# Google's budget, chapters, a load-bearing sources block, a channel
# boilerplate paragraph, then hashtags.
import build_description as bd


class TestTheHookIsProse:
    def test_a_numbered_list_is_not_mistaken_for_sentences(self):
        """The exact 2026-08-21 failure."""
        desc = ("Chapters: 1. Grave mystery 2. Ancient genomes 3. The reveal. "
                "Sources: Lazaridis et al., Nature 2025.")
        assert bd.hook_from(desc) != "Chapters: 1. Grave mystery 2."
        assert "Chapters:" not in bd.hook_from(desc)

    def test_a_models_own_chapter_block_is_stripped_before_the_hook(self):
        desc = ("Yamnaya DNA rewrote where Indo-European languages began. "
                "435 ancient genomes point to the Caucasus-Volga steppe. "
                "Chapters: 1. Grave mystery 2. Ancient genomes")
        h = bd.hook_from(desc)
        assert h.startswith("Yamnaya DNA rewrote")
        assert "Grave mystery" not in h

    def test_a_leading_chapter_block_does_not_leave_an_empty_hook(self):
        """When the model wrote ONLY a chapter list there is no prose to take."""
        assert bd.hook_from("Chapters: 1. Grave mystery 2. Ancient genomes") == ""

    def test_abbreviations_do_not_end_the_hook_early(self):
        desc = "Lazaridis et al. found the answer in 435 genomes. Then everything changed."
        assert "435 genomes" in bd.hook_from(desc)

    def test_the_hook_fits_the_google_search_snippet(self):
        desc = ("A" * 400) + ". Second sentence here."
        assert len(bd.hook_from(desc)) <= bd.SNIPPET_LIMIT

    def test_the_hook_is_trimmed_at_a_word_boundary_never_mid_word(self):
        desc = " ".join(["consequential"] * 40) + ". Next."
        h = bd.hook_from(desc)
        assert not h.rstrip(".").endswith("consequen")
        assert h.endswith(".")


class TestTheDescriptionStructure:
    def _built(self, hook="Yamnaya DNA rewrote where Indo-European languages began."):
        return bd.format_description(
            hook,
            [("00:00", "Two Centuries of Search"),
             ("05:58", "Half the genome points westward"),
             ("13:38", "Exotic goods travel with the Yamnaya")],
            "Lazaridis et al., Nature 2025",
            ["#ancientdna", "#yamnaya", "#steppeancestry"])

    def test_the_hook_is_the_very_first_line(self):
        assert self._built().splitlines()[0].startswith("Yamnaya DNA rewrote")

    def test_every_block_is_present_and_in_order(self):
        d = self._built()
        for a, b in zip(["Chapters", "Sources", "#ancientdna"],
                        ["Sources", "#ancientdna", None]):
            if b:
                assert d.index(a) < d.index(b), f"{a} must come before {b}"

    def test_the_sources_block_is_load_bearing(self):
        assert "Lazaridis et al., Nature 2025" in self._built()

    def test_the_channel_boilerplate_is_included(self):
        assert bd.BOILERPLATE.strip()
        assert bd.BOILERPLATE.strip() in self._built()

    def test_chapters_still_render_as_youtube_chapters(self):
        assert bd.has_chapters(self._built())

    def test_a_thin_chapter_list_is_skipped_not_emitted_broken(self):
        d = bd.format_description("Hook.", [("00:00", "Only one")], "S", ["#a"])
        assert "00:00 Only one" not in d
        assert "S" in d and "#a" in d          # the rest survives

    def test_it_is_substantially_more_than_the_six_lines_that_shipped(self):
        assert len(self._built()) > 400

    def test_it_stays_inside_youtubes_5000_char_field(self):
        d = bd.format_description("H." * 200, [("00:00", "A"), ("01:00", "B"),
                                               ("02:00", "C")],
                                  "S" * 500, ["#x"] * 40)
        assert len(d) <= 5000


class TestDescriptionQA:
    def test_a_missing_sources_block_is_reported(self):
        d = bd.format_description("Hook.", [("00:00", "A"), ("01:00", "B"),
                                            ("02:00", "C")], "", ["#a"])
        assert any("source" in v.lower() for v in bd.check_description(d))

    def test_a_complete_description_reports_nothing(self):
        d = bd.format_description("Hook.", [("00:00", "A"), ("01:00", "B"),
                                            ("02:00", "C")], "Estes 2012", ["#a"])
        assert bd.check_description(d) == []

    def test_the_garbled_2026_08_21_hook_would_have_been_caught(self):
        d = bd.format_description("Chapters: 1. Grave mystery 2.",
                                  [("00:00", "A"), ("01:00", "B"), ("02:00", "C")],
                                  "Estes 2012", ["#a"])
        assert any("chapter" in v.lower() for v in bd.check_description(d)), (
            "the exact text that published would still publish silently")


# --- chapters crammed into the opening are not a chapter list ---------------
# 2026-08-22 (`human-bottleneck`, 1_wRdnbFw7s): the three chapter beats landed at
# 0:04, 0:30 and 0:38 because every beat between them was unnarrated and had
# collapsed to the 2.6s card minimum. `chapters_ok` counted three stamps starting
# at 0:00 and published them. The user: "the chapters are nonsense, just 3
# chapters with seconds of difference".

def test_chapters_crammed_into_the_opening_are_rejected():
    from build_description import chapters_ok
    assert not chapters_ok([("00:00", "A"), ("00:30", "B"), ("00:38", "C")])


def test_normally_spaced_chapters_still_pass():
    from build_description import chapters_ok
    assert chapters_ok([("00:00", "A"), ("02:10", "B"), ("05:40", "C")])


def test_check_description_reports_crammed_chapters():
    from build_description import check_description
    d = ("A real prose hook about the finding.\n\n"
         "⏱ Chapters\n00:00 A\n00:30 B\n00:38 C\n\n"
         "\U0001f52c Sources\nSomething et al.\n")
    assert any("apart" in v or "spacing" in v for v in check_description(d))


def test_check_description_quiet_on_well_spaced_chapters():
    from build_description import check_description
    d = ("A real prose hook about the finding.\n\n"
         "⏱ Chapters\n00:00 A\n02:10 B\n05:40 C\n\n"
         "\U0001f52c Sources\nSomething et al.\n")
    assert not any("apart" in v or "spacing" in v for v in check_description(d))
