import importlib
import inspect
import os
import re
import sys
import unittest
import warnings

__author__ = 'Tom Ritchford <tom@swirly.com>'
__version__ = '0.9.2'

"""
    A unit test that imports every module in a Python repository,
    treating warnings as errors by default."""


class TestCase(unittest.TestCase):
    """Import every Python module or file in a hierarchy and fail on errors.
    """

    PROJECT_PATHS = None
    """A sequence of path roots that will be recusively loaded.

       If empty, guess the project paths from the root Python directory
       that contains the definition of the class.
    """

    WARNINGS_ACTION = 'error'
    """What action to take if a Python warning occurs.

       `warnings.simplefilter` will be set to this value while testing: see
       https://docs.python.org/3/library/warnings.html#the-warnings-filter
    """

    INCLUDE = None
    """A list or tuple of regular expressions, or None.

       If non-empty, only modules whose full pathname matches one of these
       regular expressions will be imported.
    """

    EXCLUDE = None
    """A list or tuple of regular expressions, or None.

       If non-empty, modules whose name matches any of these regular
       expressions will not be imported.
    """

    EXPECTED_TO_FAIL = ()
    """A list of specific module names that are expected to fail.

       This differs from EXCLUDE because those modules aren't imported at all,
       but the modules in EXPECTED_TO_FAIL must exist, are imported, and then
       must fail when imported.
    """

    def test_all(self):
        successes, failures = self.import_all()
        self.assertTrue(successes or failures)
        failed = []
        for module, ex in failures:
            if module not in self.EXPECTED_TO_FAIL:
                failed.append(module)
                print('Failed ' + module, ex, '', sep='\n')
        self.assertEqual(failed, [])

    def import_all(self):
        p = _list(self.PROJECT_PATHS or self._guess_paths())

        warnings.simplefilter(self.WARNINGS_ACTION)
        try:
            return import_all(*p, include=self.INCLUDE, exclude=self.EXCLUDE)
        finally:
            warnings.filters.pop(0)

    def _guess_paths(self):
        sourcefile = inspect.getsourcefile(__class__)
        path = python_path(os.path.dirname(sourcefile))

        for c in os.listdir(path):
            if has_init_file(c) and not c.startswith('__'):
                yield c


def import_all(*paths, include=None, exclude=None):
    """
    Try to import all .py files and directories below each path in `paths`;

    Returns a pair of sorted lists `successes, failures`.
       `successes` is a list of module names that successfully imported

       `failures` is a list of (module name, exception) pairs for modules that
        failed to import

    If `include` is If non-empty, only modules whose full pathname matches
    one of these regular expressions will be imported.

    If 'exclude` is non-empty, modules whose name matches any of these
    regular expressions will not be imported.
    """
    inc = include and [re.compile(i) for i in _list(include)]
    exc = exclude and [re.compile(i) for i in _list(exclude)]

    def accept(x):
        return (exc is None or not any(r.match(x) for r in exc)) and (
            inc is None or any(r.match(x) for r in inc)
        )

    successes, failures = [], []
    for module in _all_imports(paths):
        if accept(module):
            sys_modules = dict(sys.modules)
            try:
                importlib.import_module(module)
                successes.append(module)
            except Exception as e:
                failures.append((module, e))
            sys.modules = sys_modules

    return successes, failures


def _all_imports(paths):
    for path in paths:
        root = python_path(path)
        sys_path = sys.path[:]
        sys.path.insert(0, root)
        try:
            for directory, files in walk_code(path):
                rel = os.path.relpath(directory, root)
                module = '.'.join(split_all(rel))
                yield module

                for f in files:
                    if f.endswith('.py') and not f.startswith('__'):
                        yield '%s.%s' % (module, f[:-3])
        finally:
            sys.path[:] = sys_path


def split_all(path):
    """Use os.path.split repeatedly to split a path into components"""
    old_path = None
    components = []

    while path != old_path:
        (path, tail), old_path = os.path.split(path), path
        tail and components.insert(0, tail)

    old_path and components.insert(0, old_path)
    return components


def python_path(path):
    """
    Find the lowest directory in `path` and its parents that does not contain
    an __init__.py file
    """
    while has_init_file(path):
        path = os.path.dirname(path)

    return path


def has_init_file(path):
    """Return True if `path` is a directory containing an __init__.py file"""
    return os.path.exists(os.path.join(path, '__init__.py'))


def walk_code(path, omit_prefixes=('__', '.')):
    """
    os.walk through subdirectories and files, ignoring any that begin
    with any of the strings in `omit_prefixes`
    """
    for directory, sub_dirs, files in os.walk(path):
        if (directory != path and not has_init_file(directory)) or (
            any(directory.startswith(p) for p in omit_prefixes)
        ):
            sub_dirs.clear()
        else:
            yield directory, files


def _list(s):
    return [s] if isinstance(s, str) else s


def report(*args, file=sys.stdout):
    successes, failures = import_all(*args)
    if successes:
        print('Successes', *successes, sep='\n  ', file=file)
        print(file=file)

    if failures:
        failures = ['%s (%s)' % (m, e) for (m, e) in failures]
        print('Failures', *failures, sep='\n  ', file=file)
        print(file=file)


if __name__ == '__main__':
    args = sys.argv[1:] or [os.getcwd()]
