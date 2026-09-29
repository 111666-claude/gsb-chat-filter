"""聊天过滤与频控。

匹配前先归一化（去分隔符与空白、全角转半角、大小写折叠），再按整词匹配；
频控使用滑动窗口：任意 WINDOW 秒内同一玩家最多 LIMIT 条。
"""

import re
import unicodedata
from collections import deque

BANNED = ["坏词", "代练", "苹果"]
WINDOW = 10
LIMIT = 3

_SEPARATORS = re.compile(r"[\W_]+")


def _fold(text):
    return unicodedata.normalize("NFKC", text).casefold()


def normalize(text):
    """去掉分隔符与空白、全角转半角、大小写折叠。"""
    return _SEPARATORS.sub("", _fold(text))


def _tokenize(text):
    """归一化，但把分隔符折叠成单个空格，保留词边界信息。"""
    return _SEPARATORS.sub(" ", _fold(text))


def _build_matcher(words):
    pairs = []
    seen = set()
    for word in words:
        normed = normalize(word)
        if normed and normed not in seen:
            seen.add(normed)
            pairs.append((normed, word))
    if not pairs:
        return None, [], None
    pairs.sort(key=lambda pair: -len(pair[0]))
    groups = "|".join(
        "(?P<w%d>%s)" % (index, " *".join(re.escape(char) for char in normed))
        for index, (normed, _word) in enumerate(pairs)
    )
    pattern = re.compile(r"(?<![\w])(?:%s)(?![\w])" % groups)
    first = re.compile("[%s]" % "".join(re.escape(normed[0]) for normed, _word in pairs))
    return pattern, [word for _normed, word in pairs], first


_PATTERN, _WORDS, _FIRST_CHARS = _build_matcher(BANNED)


def matched_words(text):
    """返回文本命中的禁词（按出现顺序去重），供 --explain 使用。"""
    if _PATTERN is None:
        return []
    folded = _fold(text)
    if not _FIRST_CHARS.search(folded):
        return []
    tokenized = _SEPARATORS.sub(" ", folded)
    hits = []
    for match in _PATTERN.finditer(tokenized):
        word = _WORDS[int(match.lastgroup[1:])]
        if word not in hits:
            hits.append(word)
    return hits


def blocked(text):
    """整词匹配：禁词被分隔符包住算命中，被其它字粘住（如 苹果派）不算。"""
    return bool(matched_words(text))


def allow(times, now):
    """滑动窗口：times 为此前已尝试的时间戳（不含本次），
    [now - WINDOW, now] 内已有 LIMIT 条则拒绝。"""
    cutoff = now - WINDOW
    return sum(1 for stamp in times if cutoff <= stamp <= now) < LIMIT


class RateLimiter:
    """单玩家一个双端队列的滑动窗口频控，均摊 O(1)，内存 O(窗口内消息数)。"""

    def __init__(self, window=WINDOW, limit=LIMIT):
        self.window = window
        self.limit = limit
        self._hits = {}

    def allow(self, player, now):
        hits = self._hits.setdefault(player, deque())
        cutoff = now - self.window
        while hits and hits[0] < cutoff:
            hits.popleft()
        granted = len(hits) < self.limit
        hits.append(now)
        return granted


def sample_messages():
    """2 个分隔符绕过（坏·词、坏 词）+ 1 个正常词（苹果派）+ 1 个禁词（代练）。"""
    return ["坏·词", "坏 词", "苹果派", "代练"]


def sample_times():
    """在窗口边界前后各发 3 条。"""
    return [8, 9, 10, 11, 12, 20]
