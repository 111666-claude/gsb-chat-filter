"""口径不变量测试：归一化绕过、误伤、滑窗边界、参考实现对照。"""

import random
import unicodedata
import unittest

from chatfilter.filter import BANNED, LIMIT, WINDOW, ChatFilter, allow, blocked, match, normalize


def reference_normalize(text):
    """参考归一化：全角转半角、大小写折叠、去分隔符与空白。"""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return "".join(
        char for char in folded if unicodedata.category(char)[0] not in ("Z", "P", "C")
    )


def reference_run(events, banned, window, limit):
    """参考实现：归一化 + 整词匹配 + 滑窗计数，逐条暴力统计。

    events 为 (player, text, now) 列表，按时间升序。
    返回与 events 等长的 (passed, word_blocked) 列表。
    """
    norm_banned = {reference_normalize(word) for word in banned}
    attempts = {}
    results = []
    for player, text, now in events:
        if reference_normalize(text) in norm_banned:
            results.append((False, True))
            continue
        history = attempts.setdefault(player, [])
        history.append(now)
        count = sum(1 for stamp in history if now - window <= stamp <= now)
        results.append((count <= limit, False))
    return results


class NormalizeTest(unittest.TestCase):
    def test_separator_bypass_is_blocked(self):
        self.assertTrue(blocked("坏·词"))
        self.assertTrue(blocked("坏 词"))
        self.assertTrue(blocked("坏　词"))
        self.assertTrue(blocked("坏.词"))
        self.assertTrue(blocked("代 练"))

    def test_fullwidth_and_case_fold(self):
        self.assertEqual(normalize("ＡＢＣ"), "abc")
        self.assertEqual(normalize("AbC"), "abc")
        self.assertEqual(normalize("坏　词"), "坏词")

    def test_zero_width_bypass_is_blocked(self):
        self.assertTrue(blocked("代​练"))

    def test_no_false_positive_on_normal_text(self):
        self.assertFalse(blocked("苹果派"))
        self.assertFalse(blocked("苹果派真好吃"))
        self.assertFalse(blocked("今天我们一起打副本"))
        self.assertFalse(blocked("代练吗"))

    def test_match_returns_hit_word(self):
        self.assertEqual(match("坏·词"), "坏词")
        self.assertEqual(match("代练"), "代练")
        self.assertIsNone(match("苹果派"))


class AllowBoundaryTest(unittest.TestCase):
    def test_exactly_at_limit_passes(self):
        self.assertTrue(allow([0, 1, 2], 2))

    def test_one_over_limit_fails(self):
        self.assertFalse(allow([0, 1, 2, 3], 3))

    def test_window_edge_is_inclusive(self):
        self.assertTrue(allow([0, 5, 10], 10))
        self.assertFalse(allow([0, 5, 9, 10], 10))

    def test_stamp_before_window_is_ignored(self):
        self.assertTrue(allow([-1, 8, 9], 9))
        self.assertTrue(allow([0, 11, 12], 20))

    def test_cross_boundary_flood_is_capped(self):
        times = [8, 9, 10, 11, 12, 20]
        passed = sum(
            1 for now in times if allow([s for s in times if s <= now], now)
        )
        self.assertEqual(passed, 3)


class ChatFilterTest(unittest.TestCase):
    def test_flood_sample_matches_allow(self):
        filt = ChatFilter()
        results = [filt.check("p", "你好", now)[0] for now in [8, 9, 10, 11, 12, 20]]
        self.assertEqual(results, [True, True, True, False, False, False])

    def test_blocked_message_explains_hit(self):
        passed, hit = ChatFilter().check("p", "坏·词", 0)
        self.assertFalse(passed)
        self.assertEqual(hit, "坏词")

    def test_repeat_filtering_is_deterministic(self):
        rng = random.Random(42)
        events = [
            ("p%d" % rng.randint(0, 9), rng.choice(["坏词", "苹果派", "你好"]), rng.randint(0, 100))
            for _ in range(500)
        ]
        events.sort(key=lambda event: event[2])
        first = [ChatFilter().check(*event) for event in events]
        second = [ChatFilter().check(*event) for event in events]
        self.assertEqual(first, second)

    def test_passed_messages_respect_sliding_window(self):
        rng = random.Random(7)
        filt = ChatFilter()
        passed = {}
        for _ in range(3000):
            player = "p%d" % rng.randint(0, 9)
            now = rng.randint(0, 300)
            ok, _ = filt.check(player, "你好", now)
            if ok:
                passed.setdefault(player, []).append(now)
        for stamps in passed.values():
            for index, start in enumerate(stamps):
                count = sum(1 for stamp in stamps if start <= stamp <= start + WINDOW)
                self.assertLessEqual(count, LIMIT)


class ReferenceComparisonTest(unittest.TestCase):
    def test_random_streams_match_reference(self):
        pool = [
            "坏词", "坏·词", "坏 词", "坏　词", "坏.词", "代练", "代 练",
            "苹果", "苹果派", "今天我们一起打副本", "你好", "ＡＢＣ", "AbC",
        ]
        rng = random.Random(20260930)
        for _ in range(200):
            players = ["p%d" % index for index in range(rng.randint(1, 5))]
            events = [
                (rng.choice(players), rng.choice(pool), rng.randint(0, 50))
                for _ in range(rng.randint(1, 40))
            ]
            events.sort(key=lambda event: event[2])
            filt = ChatFilter()
            actual = [filt.check(player, text, now) for player, text, now in events]
            expected = reference_run(events, BANNED, WINDOW, LIMIT)
            diff = 0
            for (ok, hit), (exp_ok, exp_word_blocked) in zip(actual, expected):
                if ok != exp_ok:
                    diff += 1
                if exp_word_blocked:
                    self.assertIsNotNone(hit)
                else:
                    self.assertIsNone(hit)
            self.assertEqual(diff, 0)
            self.assertEqual(
                sum(1 for ok, _ in actual if ok),
                sum(1 for ok, _ in expected if ok),
            )


if __name__ == "__main__":
    unittest.main()
