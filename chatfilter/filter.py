"""聊天过滤与频控。

缺陷：只做子串匹配（加分隔符能绕过、正常词被误伤）、频控只看当前固定窗口桶。
"""

BANNED = ["坏词", "代练", "苹果"]
WINDOW = 10
LIMIT = 3


def normalize(text):
    """缺陷：没有做分隔符、全半角与大小写归一。"""
    return text


def blocked(text):
    """缺陷：子串匹配，加字就绕过、加后缀就误伤。"""
    content = normalize(text)
    return any(word in content for word in BANNED)


def allow(times, now):
    """缺陷：只统计当前固定窗口桶，跨桶边界可以刷屏。"""
    bucket = now // WINDOW
    count = sum(1 for stamp in times if stamp // WINDOW == bucket)
    return count < LIMIT


def sample_messages():
    """1 个误伤（苹果派）+ 3 个该封但没封的（坏·词、坏 词、代练）。"""
    return ["坏·词", "坏 词", "苹果派", "代练"]


def sample_times():
    """在窗口边界前后各发 3 条。"""
    return [8, 9, 10, 11, 12, 20]
