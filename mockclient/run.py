"""Scenario runner: python -m mockclient.run [scenario ...|all]"""
import sys
import traceback

from mockclient import scenarios
from mockclient.stack import LocalStack


def main(argv):
    names = argv or ["all"]
    if names == ["all"]:
        picked = scenarios.ALL
    else:
        picked = [getattr(scenarios, n) for n in names]
    failures = 0
    with LocalStack() as stack:
        for fn in picked:
            stack.reset()
            try:
                judge = fn(stack)
            except Exception:
                print("%s: ERROR\n%s" % (fn.__name__, traceback.format_exc()))
                failures += 1
                continue
            print(judge.report())
            if not judge.passed:
                failures += 1
    print("\n%d/%d scenarios passed" % (len(picked) - failures, len(picked)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
