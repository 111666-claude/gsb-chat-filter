"""聊天过滤与频控：先归一化再整词匹配，频控用滑动窗口。"""

import unicodedata
from collections import deque

BANNED = ["坏词", "代练", "苹果"]
WINDOW = 10
LIMIT = 3

_DROPPED_CATEGORIES = ("Z", "P", "C")


def _dropped(char):
    """分隔符、空白与不可见字符在匹配前去掉。"""
    return unicodedata.category(char)[0] in _DROPPED_CATEGORIES


def normalize(text):
    """全角转半角、大小写折叠、去掉分隔符与空白。"""
    folded = unicodedata.normalize("NFKC", text).casefold()
    if folded.isalnum():
        return folded
    return "".join(char for char in folded if not _dropped(char))


def _build_banned_map(words):
    mapping = {}
    for word in words:
        mapping.setdefault(normalize(word), word)
    return mapping


_BANNED_MAP = _build_banned_map(BANNED)


def match(text):
    """整词匹配：归一化后整条消息等于某个禁词才算命中，返回禁词原样或 None。"""
    return _BANNED_MAP.get(normalize(text))


def blocked(text):
    return match(text) is not None


def allow(times, now):
    """滑动窗口：[now - WINDOW, now] 内（含 now 本身）最多 LIMIT 条。"""
    count = 0
    for stamp in times:
        if now - WINDOW <= stamp <= now:
            count += 1
    return count <= LIMIT


class ChatFilter:
    """面向消息流的过滤器：整词匹配 + 每玩家滑动窗口频控。

    禁词命中走哈希表查找，不重扫禁词表；每玩家一个双端队列，
    每条消息 O(1) 均摊，内存 O(玩家数 × 窗口内消息数)。
    """

    def __init__(self, banned=BANNED, window=WINDOW, limit=LIMIT):
        self.window = window
        self.limit = limit
        self._banned_map = _build_banned_map(banned)
        self._attempts = {}

    def check(self, player, text, now):
        """返回 (passed, hit)：passed 为是否放行，hit 为命中的禁词（未命中为 None）。"""
        hit = self._banned_map.get(normalize(text))
        if hit is not None:
            return False, hit
        attempts = self._attempts.get(player)
        if attempts is None:
            attempts = self._attempts[player] = deque()
        cutoff = now - self.window
        while attempts and attempts[0] < cutoff:
            attempts.popleft()
        attempts.append(now)
        if len(attempts) > self.limit:
            return False, None
        return True, None


def sample_messages():
    """3 个该封的（坏·词、坏 词、代练）+ 1 个不该封的（苹果派）。"""
    return ["坏·词", "坏 词", "苹果派", "代练"]


def sample_times():
    """在窗口边界前后各发 3 条。"""
    return [8, 9, 10, 11, 12, 20]
