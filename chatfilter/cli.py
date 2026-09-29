"""命令行入口：跑过滤与频控样例。"""

import argparse

from .filter import LIMIT, WINDOW, allow, matched_words, sample_messages, sample_times


def build_parser():
    parser = argparse.ArgumentParser(prog="chat-filter", description="聊天过滤与频控")
    parser.add_argument("--messages", default="sample", help="sample")
    parser.add_argument("--flood", action="store_true", help="跑频控样例")
    parser.add_argument("--explain", action="store_true", help="打印命中的禁词与频控判定")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.flood:
        times = sample_times()
        passed = 0
        history = []
        for now in times:
            if allow(history, now):
                passed += 1
                if args.explain:
                    print("t=%d pass" % now)
            elif args.explain:
                print("t=%d block" % now)
            history.append(now)
        print("passed=%d limit=%d window=%d" % (passed, LIMIT, WINDOW))
        return 0
    messages = sample_messages()
    hits = [(message, matched_words(message)) for message in messages]
    if args.explain:
        for message, words in hits:
            if words:
                print("blocked: %s -> %s" % (message, ",".join(words)))
    banned = sum(1 for _message, words in hits if words)
    print("messages=%d blocked=%d" % (len(messages), banned))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
