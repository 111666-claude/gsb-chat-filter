# chat-filter

游戏内聊天过滤与频控，只用 Python 标准库。

```
python3 -m chatfilter.cli --messages sample
python3 -m chatfilter.cli --flood
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- **匹配前先归一化**：要去掉分隔符与空白、全角转半角、大小写折叠，再做匹配。
  `--messages sample` 里 `坏·词`、`坏 词` 都要被拦下，按口径 `blocked=3`（含 `代练`），
  现在只拦到 2 条，而且其中一条是误伤。
- **按词匹配，别误伤**：`苹果派` 不该被封（禁词是 `苹果` 本身，不是它的前缀）。
  现在用子串匹配，`苹果派` 被误封。
- **频控用滑动窗口**：任意 `WINDOW` 秒内同一玩家最多 `LIMIT` 条。`--flood`（在窗口边界前后各发 3 条）
  按口径 `passed=3`，现在只看固定窗口桶，给 `passed=5`。
- 不变量：同一批消息重复过滤结果相同；被拦下的消息要能给出命中的禁词（用 `--explain` 打印）；
  正常消息零误伤；频控在任意滑窗内都成立。
- 规模：100 万条消息、10 万玩家 2 秒内处理完，内存 O(玩家数 × 窗口内消息数)；不许每条消息重扫禁词表。

## 实现

- `normalize`：NFKC 全角转半角 + casefold 大小写折叠 + 去掉分隔符与空白（`[\W_]+`）。
- `blocked`：禁词表编译成一个正则（禁词内部允许插入分隔符，两侧要求词边界），
  整词匹配，`苹果派` 不误伤；`matched_words` 返回命中的禁词供 `--explain` 打印。
- `allow`：滑动窗口，`[now - WINDOW, now]` 内已有 `LIMIT` 条则拒绝；
  `RateLimiter` 用每玩家一个双端队列实现，均摊 O(1)，内存 O(玩家数 × 窗口内消息数)。

## 命令行

```
--messages sample
--flood
--explain
```

## 输出

```
messages=4 blocked=3
passed=3 limit=3 window=10
```

## 目录

```
chatfilter/filter.py   归一化、过滤与频控
chatfilter/cli.py      命令行入口
tests/                 unittest 用例
```
