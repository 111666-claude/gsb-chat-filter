import contextlib
import io
import random
import re
import time
import unicodedata
import unittest

from chatfilter.cli import main
from chatfilter.filter import (
    BANNED,
    LIMIT,
    WINDOW,
    RateLimiter,
    allow,
    blocked,
    matched_words,
    normalize,
    sample_messages,
    sample_times,
)

_WORD_CHAR = re.compile(r"\w")


def _ref_kept(text):
    folded = unicodedata.normalize("NFKC", text).casefold()
    return [(index, char) for index, char in enumerate(folded) if _WORD_CHAR.match(char) and char != "_"]


def ref_normalize(text):
    return "".join(char for _index, char in _ref_kept(text))


def ref_blocked(text, words=BANNED):
    """参考实现：暴力枚举禁词在归一化文本中的出现位置并检查整词边界。"""
    kept = _ref_kept(text)
    flat = "".join(char for _index, char in kept)
    positions = [index for index, _char in kept]
    for word in words:
        normed = ref_normalize(word)
        if not normed:
            continue
        size = len(normed)
        for start in range(len(flat) - size + 1):
            if flat[start:start + size] != normed:
                continue
            before_ok = start == 0 or positions[start] - positions[start - 1] > 1
            last = start + size - 1
            after_ok = last == len(flat) - 1 or positions[last + 1] - positions[last] > 1
            if before_ok and after_ok:
                return True
    return False


def ref_allow(times, now, window=WINDOW, limit=LIMIT):
    """参考实现：暴力统计 [now - window, now] 内此前已尝试的条数。"""
    return sum(1 for stamp in times if now - window <= stamp <= now) < limit


class NormalizeTest(unittest.TestCase):
    def test_fullwidth_to_halfwidth_and_casefold(self):
        self.assertEqual(normalize("ＡＢＣ１２３"), "abc123")

    def test_separators_and_whitespace_removed(self):
        self.assertEqual(normalize("坏·词"), "坏词")
        self.assertEqual(normalize("坏 词"), "坏词")
        self.assertEqual(normalize("坏　词"), "坏词")
        self.assertEqual(normalize("坏-词_"), "坏词")

    def test_zero_width_and_punctuation_removed(self):
        self.assertEqual(normalize("坏​词"), "坏词")
        self.assertEqual(normalize("坏。词，"), "坏词")


class NormalizeBypassTest(unittest.TestCase):
    def test_separator_bypass_is_blocked(self):
        for text in ["坏·词", "坏 词", "坏　词", "坏-词", "坏_词", "坏​词", "坏★词", "坏。词"]:
            self.assertTrue(blocked(text), text)

    def test_plain_banned_words_still_blocked(self):
        self.assertTrue(blocked("坏词"))
        self.assertTrue(blocked("代练"))
        self.assertTrue(blocked("苹果"))


class FalsePositiveTest(unittest.TestCase):
    def test_prefix_extension_is_not_blocked(self):
        self.assertFalse(blocked("苹果派"))
        self.assertFalse(blocked("苹果手机"))
        self.assertFalse(blocked("坏词语"))

    def test_clean_messages_untouched(self):
        self.assertFalse(blocked("今天我们一起打副本"))
        self.assertFalse(blocked("晚上八点集合开团"))

    def test_word_boundary_with_separator_still_blocked(self):
        self.assertTrue(blocked("苹果 派"))
        self.assertTrue(blocked("代练，快来"))


class ExplainTest(unittest.TestCase):
    def test_matched_words_reported(self):
        self.assertEqual(matched_words("坏·词"), ["坏词"])
        self.assertEqual(matched_words("代练 和 坏词"), ["代练", "坏词"])

    def test_no_hit_gives_empty(self):
        self.assertEqual(matched_words("苹果派"), [])
        self.assertEqual(matched_words("今天我们一起打副本"), [])


class SlidingWindowTest(unittest.TestCase):
    def test_cutoff_is_inclusive(self):
        self.assertFalse(allow([0, 5, 9], 10))
        self.assertTrue(allow([0, 5], 10))

    def test_window_slides_forward(self):
        self.assertTrue(allow([0, 5, 9], 11))
        self.assertFalse(allow([1, 5, 9], 11))

    def test_cross_boundary_flood_is_blocked(self):
        times = sample_times()
        history = []
        passed = 0
        for now in times:
            passed += allow(history, now)
            history.append(now)
        self.assertEqual(passed, 3)

    def test_same_timestamp_flood_is_blocked(self):
        history = []
        granted = 0
        for _ in range(6):
            granted += allow(history, 5)
            history.append(5)
        self.assertEqual(granted, LIMIT)

    def test_any_window_holds_limit(self):
        rng = random.Random(42)
        times = sorted(rng.randint(0, 200) for _ in range(300))
        history = []
        granted = []
        for now in times:
            if allow(history, now):
                granted.append(now)
            history.append(now)
        for start in granted:
            count = sum(1 for t in granted if start <= t <= start + WINDOW)
            self.assertLessEqual(count, LIMIT)


class RateLimiterTest(unittest.TestCase):
    def test_consistent_with_allow_function(self):
        rng = random.Random(7)
        streams = {player: sorted(rng.randint(0, 60) for _ in range(rng.randint(0, 15))) for player in range(10)}
        events = sorted((stamp, player) for player, stamps in streams.items() for stamp in stamps)
        limiter = RateLimiter()
        seen = {player: [] for player in streams}
        for stamp, player in events:
            self.assertEqual(limiter.allow(player, stamp), allow(seen[player], stamp))
            seen[player].append(stamp)


class DeterminismTest(unittest.TestCase):
    def test_same_batch_same_result(self):
        batch = sample_messages() * 5
        self.assertEqual([blocked(m) for m in batch], [blocked(m) for m in batch])
        times = sample_times()

        def run():
            history = []
            out = []
            for now in times:
                out.append(allow(history, now))
                history.append(now)
            return out

        self.assertEqual(run(), run())


CHAR_POOL = list("坏词代练苹果派今天我们一起打副本abAB01") + ["·", " ", "　", "-", "_", ".", "。", "，", "★", "​", "Ａ", "ｂ"]


class ReferenceComparisonTest(unittest.TestCase):
    def test_random_streams_match_reference(self):
        rng = random.Random(20260930)
        for _ in range(200):
            messages = [
                "".join(rng.choice(CHAR_POOL) for _ in range(rng.randint(0, 12)))
                for _ in range(rng.randint(1, 20))
            ]
            times = sorted(rng.randint(0, 40) for _ in range(rng.randint(1, 20)))
            for message in messages:
                self.assertEqual(blocked(message), ref_blocked(message), message)
            history = []
            passed = 0
            ref_passed = 0
            for now in times:
                passed += allow(history, now)
                ref_passed += ref_allow(history, now)
                history.append(now)
            self.assertEqual(passed, ref_passed)


class CliTest(unittest.TestCase):
    def _run(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main(argv), 0)
        return buf.getvalue()

    def test_messages_output_format(self):
        self.assertEqual(self._run(["--messages", "sample"]), "messages=4 blocked=3\n")

    def test_flood_output_format(self):
        self.assertEqual(self._run(["--flood"]), "passed=3 limit=3 window=10\n")

    def test_explain_prints_hit_words(self):
        out = self._run(["--messages", "sample", "--explain"])
        self.assertIn("blocked: 坏·词 -> 坏词", out)
        self.assertIn("blocked: 代练 -> 代练", out)
        self.assertNotIn("苹果派 ->", out)
        self.assertTrue(out.endswith("messages=4 blocked=3\n"))


class ScaleTest(unittest.TestCase):
    def test_million_messages_within_two_seconds(self):
        players = 100000
        total = 1000000
        limiter = RateLimiter()
        clean = "今天我们一起打副本"
        start = time.perf_counter()
        passed = 0
        for index in range(total):
            if not blocked(clean) and limiter.allow(index % players, index // 10):
                passed += 1
        elapsed = time.perf_counter() - start
        self.assertGreater(passed, 0)
        self.assertLess(elapsed, 2.0, "处理 %d 条消息耗时 %.2fs" % (total, elapsed))


if __name__ == "__main__":
    unittest.main()
