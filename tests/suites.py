"""Run the offline or explicitly marked live HydraDB unittest partition."""
import argparse
import sys
import unittest
from pathlib import Path


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


def is_integration(test):
    method = getattr(test, test._testMethodName, None)
    return bool(getattr(test.__class__, 'hydradb_integration', False)
                or getattr(method, 'hydradb_integration', False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', choices=('offline', 'integration'))
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent.parent
    loader = unittest.TestLoader()
    discovered = loader.discover(str(root / 'tests'), top_level_dir=str(root))
    if loader.errors:
        for error in loader.errors:
            print(error, file=sys.stderr)
        return 1
    all_cases = list(cases(discovered))
    selected = [test for test in all_cases if is_integration(test) == (args.suite == 'integration')]
    if not selected:
        print(f'No tests selected for {args.suite}', file=sys.stderr)
        return 1
    print(f'{args.suite}: selected {len(selected)} of {len(all_cases)} discovered tests', flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(selected))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
