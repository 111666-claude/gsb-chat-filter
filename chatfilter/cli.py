"""命令行入口：跑过滤与频控样例。"""

import argparse

from .filter import LIMIT, WINDOW, allow, blocked, sample_messages, sample_times


def build_parser():
    parser = argparse.ArgumentParser(prog="chat-filter", description="聊天过滤与频控")
    parser.add_argument("--messages", default="sample", help="sample")
    parser.add_argument("--flood", action="store_true", help="跑频控样例")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.flood:
        times = sample_times()
        passed = 0
        for now in times:
            history = [stamp for stamp in times if stamp <= now]
            if allow(history, now):
                passed += 1
        print("passed=%d limit=%d window=%d" % (passed, LIMIT, WINDOW))
        return 0
    messages = sample_messages()
    banned = sum(1 for message in messages if blocked(message))
    print("messages=%d blocked=%d" % (len(messages), banned))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
