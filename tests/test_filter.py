import unittest

from chatfilter.filter import LIMIT, allow, blocked, normalize


class BlockedTest(unittest.TestCase):
    def test_plain_banned_word(self):
        self.assertTrue(blocked("代练"))

    def test_clean_message(self):
        self.assertFalse(blocked("今天我们一起打副本"))

    def test_normalize_is_identity_for_plain_text(self):
        self.assertEqual(normalize("abc"), "abc")

    def test_limit_is_three(self):
        self.assertEqual(LIMIT, 3)


class AllowTest(unittest.TestCase):
    def test_first_message_is_allowed(self):
        self.assertTrue(allow([], 0))

    def test_history_is_counted(self):
        self.assertFalse(allow([0, 1, 2, 3], 3))
