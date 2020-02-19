#!/usr/bin/python2
#
# Copyright (C) 2015 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

r"""A script intended to update release notes.

Works on Python >= 2.7 and < 3.0.

This module, when run as a script, provides a command line interface.
The interface usage is::

    usage: prog [-h]

    Extend the list of issues of the next version in release notes. It
    updates the release notes found in the DNF repository which contains
    this module. The module location is obtained from the __file__
    variable. The version number is parsed from the spec file. If the
    release notes already contains given issue, it is not added again.
    Otherwise, it is added to the beginning of the list. If the release
    notes does not contain the next version, a new section is appended
    right before the first section. The diff between the new release
    notes and the Git index is printed to the standard error stream. The
    message starts with "INFO Update finished. See the diff to the Git
    index: ".

    optional arguments:
      -h, --help  show this help message and exit

    If the version is already released or if another error occurs the
    exit status is non-zero.

:var LOGGER: the logger used by this script
:type LOGGER: logging.Logger
:var SPEC_FN: a name of the DNF spec file relative to the working
   directory of the Git repository which contains this script
:type SPEC_FN: str
:var TAG_PAT: a string pattern of DNF tags where the "{version}" field
   should be replaced with the given version of DNF
:type TAG_PAT: str
:var ISSUE_RE: a regular expression matching numbers of resolved issues
   in the first line of a commit message
:type ISSUE_RE: re.RegexObject
:var RELATED_RE: a regular expression matching numbers of related issues
   in a commit message
:type RELATED_RE: re.RegexObject
:var SIMILAR_RE: a regular expression matching numbers which look like a
   number of an issue referred in a commit message
:type SIMILAR_RE: re.RegexObject
:var NOTES_FN: a name of the DNF release notes file relative to the
   working directory of the Git repository which contains this script
:type NOTES_FN: str
:var TITLE_PAT: a string pattern of a DNF release notes section title
   (including a trailing "\n") where the "{version}" field should be
   replaced with the given release version
:type TITLE_PAT: str
:var ISSUE_PAT: a string pattern of a reference to a resolved issue in
   DNF release notes (including a trailing "\n") where the "{number}"
   field should be replaced with the number of the given issue
:type ISSUE_PAT: str
:var OVERLINE_RE: a regular expression matching a section title overline
   in a line of DNF release notes
:type OVERLINE_RE: re.RegexObject
:var TITLE_RE_PAT: a string pattern of a regular expression matching a
   section title in a line of DNF release notes where the "{maxlen}"
   field should be replaced with the maximum expected length of the
   release version
:type TITLE_RE_PAT: str

"""

import update_releasenotes_python3

from __future__ import absolute_import

import argparse
import contextlib
import io
import itertools
import logging
import os
import re
import shutil
import sys
import tempfile
import unittest

import git
import rpm
import tests.mock


LOGGER = logging.getLogger(sys.argv[0])

SPEC_FN = 'dnf.spec'

TAG_PAT = 'dnf-{version}-1'

ISSUE_RE = re.compile(ur'(?<!Related: )RhBug:(\d+)')

RELATED_RE = re.compile(ur'Related: RhBug:(\d+)')

SIMILAR_RE = re.compile(ur'\d{6,}')

NOTES_FN = os.path.join('doc', 'release_notes.rst')

TITLE_PAT = '{version} Release Notes\n'

ISSUE_PAT = '* :rhbug:`{number}`\n'

OVERLINE_RE = re.compile('^(=+)\n$')

TITLE_RE_PAT = '^(.{{,{maxlen}}}) Release Notes\n$'


@contextlib.contextmanager
def _safe_overwrite(name):
    """Open a file in order to overwrite it safely.

    Until the context manager successfully exits, the file remains
    unchanged.

    :param name: name of the file
    :type name: str
    :returns: a context manager that returns a readable text file object
        intended to read the content of the file and a writable text
        file object intended to write the new content of the file
    :rtype: contextmanager[tuple[file, file]]
    :raises exceptions.IOError: if the file cannot be opened

    """
    with open(name, 'rt+') as file_, tempfile.TemporaryFile('wt+') as tmpfile:
        yield file_, tmpfile
        tmpfile.seek(0)
        file_.seek(0)
        shutil.copyfileobj(tmpfile, file_)


def detect_repository():
    """Detect the DNF Git repository which contains this module.

    The module location is obtained from :const:`__file__`.

    :returns: the repository
    :rtype: git.Repo

    """
    dirname = os.path.dirname(__file__)
    # FIXME remove this once we can get rid of supporting GitPython < 0.3.5
    try:
        return git.Repo(dirname, search_parent_directories=True)
    except TypeError:
        return git.Repo(dirname)


def detect_version(repository):
    """Detect the DNF version from its spec file.

    :param repository: a non-bare DNF repository which contains the spec
       file
    :type repository: git.Repo
    :returns: the detected version
    :rtype: str

    """
    filename = os.path.join(repository.working_dir, SPEC_FN)
    return rpm.spec(filename).sourceHeader[rpm.RPMTAG_VERSION]


def find_tag(repository, version):
    """Find the Git tag corresponding to a DNF version.

    :param repository: a DNF repository
    :type repository: git.Repo
    :returns: the name of the tag
    :rtype: str | None

    """
    tagname = TAG_PAT.format(version=version)
    return tagname if tagname in repository.tags else None


def iter_unreleased_commits(repository):
    """Iterate over the commits that were not tagged as a release.

    :param repository: a repository
    :type repository: git.Repo
    :returns: a generator yielding the commits
    :rtype: generator[git.Commit]

    """
    tagshas = {tag.commit.hexsha for tag in repository.tags}
    for commit in repository.iter_commits():
        if commit.hexsha in tagshas:
            # FIXME encode() once we get rid of supporting GitPython < 0.3.4
            LOGGER.debug(
                'Unreleased commits iteration stopped on the first tagged '
                'commit: %s', commit.hexsha.encode())
            break
        yield commit


def parse_issues(commits):
    """Parse the numbers of the resolved DNF issues from commit messages.

    :param commits: the DNF commits
    :type commits: collections.Iterable[git.Commit]
    :returns: a generator yielding the issue numbers
    :rtype: generator[str]

    """
    for commit in commits:
        firstline = commit.message.splitlines()[0]
        valid = {match.group(1) for match in ISSUE_RE.finditer(firstline)}
        for issue in valid:
            issue = issue.encode()
            # FIXME decode() once we get rid of supporting GitPython < 0.3.4
            LOGGER.debug(
                'Recognized %s in commit %s.', issue,
                commit.hexsha.decode().encode())
            yield issue.encode()
        valid |= {mat.group(1) for mat in RELATED_RE.finditer(commit.message)}
        for match in SIMILAR_RE.finditer(commit.message):
            if match.group(0) not in valid:
                # FIXME decode once we get rid of supporting GitPython < 0.3.4
                LOGGER.warning(
                    'Skipped %s in commit %s which looks like an issue '
                    'number.', match.group(0).encode(),
                    commit.hexsha.decode().encode())


def extend_releases(releases, version, issues):
    r"""Extend the list of issues of a release version in release notes.

    The issues are appended to the beginning of the list. If an issue is
    already in the list of the release version, it is not added again.
    If the release version is not found, the release version
    (``version, '\n', issues, '\n'``) is yielded right before the first
    release version in the release notes.

    :param releases: the version, the description, the list of issue
       numbers and the epilog for each release version in release notes
    :type releases: collections.Iterable[tuple[str | None, str, list[str], str]]
    :param version: the release version to be extended
    :type version: str
    :param issues: the issues to be added
    :type issues: collections.Iterable[str]
    :returns: a generator yielding the modified release notes
    :rtype:  generator[tuple[str | None, str, list[str], str]]

    """
    releases, issues = list(releases), list(issues)
    prepend = not any(release[0] == version for release in releases)
    for version_, description, issues_, epilog in releases:
        if prepend and version_ is not None:
            yield version, '\n', issues, '\n'
            prepend = False
        elif version_ == version:
            issues_ = issues_[:]
            for issue in reversed(issues):
                if issue not in issues_:
                    issues_.insert(0, issue)
        yield version_, description, issues_, epilog


def format_release(version, description, issues, epilog):
    """Compose a string in form of DNF release notes from a release.

    The order of issues is preserved.

    :param version: the version of the release
    :type version: str | None
    :param description: the description of the release
    :type description: str
    :param issues: the list of issue numbers of the release
    :type issues: list[str]
    :param epilog: the epilog of the release
    :type epilog: str
    :returns: the formatted string
    :rtype: str

    """
    titlestr = ''
    if version:
        title = TITLE_PAT.format(version=version)
        length = len(title) - 1
        titlestr = '{}\n{}{}\n'.format('=' * length, title, '=' * length)
    issuestr = ''.join(ISSUE_PAT.format(number=issue) for issue in issues)
    return ''.join([titlestr, description, issuestr, epilog])


def update_notes():
    r"""Extend the list of issues of the next version in release notes.

    It updates the release notes found in the DNF repository which
    contains this module. The module location is obtained from
    :const:`__file__`. The version number is parsed from the spec file.
    If the release notes already contains given issue, it is not added
    again. Otherwise, it is added to the beginning of the list. If the
    release notes does not contain the next version, a new section is
    appended right before the first section. The diff between the new
    release notes and the Git index is logged to :const:`.LOGGER` with
    level :const:`INFO`. The message starts with "Update finished. See
    the diff to the Git index:\n".

    :raises exceptions.ValueError: if the version is already released

    """
    repository = detect_repository()
    LOGGER.info('Detected the repository at: %s', repository.working_dir)
    notesfn = os.path.join(repository.working_dir, NOTES_FN)
    version = detect_version(repository)
    LOGGER.info('Detected DNF version (from the spec file): %s', version)
    issues = parse_issues(iter_unreleased_commits(repository))
    parser = ReleaseNotesParser()
    tagname = find_tag(repository, version)
    if tagname:
        LOGGER.warning('Found a tag matching the current version: %s', tagname)
        LOGGER.error('Extending an already released version is not allowed!')
        raise ValueError('version already released')
    with _safe_overwrite(notesfn) as (source, destination):
        releases = extend_releases(parser.parse_lines(source), version, issues)
        for version_, desc, issues_, epilog in releases:
            destination.write(format_release(version_, desc, issues_, epilog))
    diff = repository.index.diff(None, NOTES_FN, create_patch=True)[0].diff
    LOGGER.info(
        'Update finished. See the diff to the Git index:\n%s',
        re.sub(r'^', '    ', diff, flags=re.M))


def main():
    """Start the main loop of the command line interface.

    The root logger is configured to write DEBUG+ messages into the
    directory where is this module located if not configured otherwise.
    A handler that writes INFO+ messages to :data:`sys.stderr` is added
    to :const:`.LOGGER`.

    The interface usage is::

        usage: prog [-h]

        Extend the list of issues of the next version in release notes.
        It updates the release notes found in the DNF repository which
        contains this module. The module location is obtained from the
        __file__ variable. The version number is parsed from the spec
        file. If the release notes already contains given issue, it is
        not added again. Otherwise, it is added to the beginning of the
        list. If the release notes does not contain the next version, a
        new section is appended right before the first section. The diff
        between the new release notes and the Git index is printed to
        the standard error stream. The message starts with "INFO Update
        finished. See the diff to the Git index: ".

        optional arguments:
          -h, --help  show this help message and exit

        If the version is already released or if another error occurs
        the exit status is non-zero.

    :raises exceptions.SystemExit: with a non-zero exit status if an
       error occurs

    """
    logging.basicConfig(
        filename='{}.log'.format(__file__),
        filemode='wt',
        format='%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:%(message)s',
        datefmt='%Y%m%dT%H%M%S',
        level=logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
    LOGGER.addHandler(handler)
    argparser = argparse.ArgumentParser(
        description='Extend the list of issues of the next version in release '
                    'notes. It updates the release notes found in the DNF '
                    'repository which contains this module. The module '
                    'location is obtained from the __file__ variable. The '
                    'version number is parsed from the spec file. If the '
                    'release notes already contains given issue, it is not '
                    'added again. Otherwise, it is added to the beginning of '
                    'the list. If the release notes does not contain the next '
                    'version, a new section is appended right before the first'
                    ' section. The diff between the new release notes and the '
                    'Git index is printed to the standard error stream. The '
                    'message starts with "INFO Update finished. See the diff '
                    'to the Git index:\n".',
        epilog='If the version is already released or if another error occurs '
               'the exit status is non-zero.')
    argparser.parse_args()
    try:
        update_notes()
    except ValueError:
        sys.exit(1)


class ReleaseNotesParser(object):

    """A class able to parse DNF release notes.

    :ivar _needline: an expected line which represents the end of a
       section title
    :type _needline: str | None
    :ivar _version: a version parsed from a potential next section title
    :type _version: str | None
    :ivar version: a version parsed from the last section title
    :type version: str | None
    :ivar description: lines parsed from the last section description
    :type description: list[str]
    :ivar issues: numbers of resolved issues parsed from the last
       section
    :type issues: list[str]
    :ivar epilog: lines parsed from the last section epilog
    :type epilog: list[str]

    """

    def __init__(self):
        """Initialize the parser."""
        super(ReleaseNotesParser, self).__init__()
        self._needline = None
        self._version = None
        self.version = None
        self.description = []
        self.issues = []
        self.epilog = []

    @property
    def _last_version(self):
        """The last parsed release version.

        :returns: the version, the description, the list of issue
           numbers and the epilog of the release
        :rtype: tuple[str | None, str, list[str], str]

        """
        return (
            self.version,
            ''.join(self.description),
            self.issues,
            ''.join(self.epilog))

    def _cancel_title(self):
        """Cancel expectations of a next section title.

        It modifies :attr:`_needline` and :attr:`_version`.

        :returns: the old values of :attr:`_needline` and
           :attr:`_version`
        :rtype: tuple[str | None, str | None]

        """
        needline, version = self._needline, self._version
        self._needline = self._version = None
        return needline, version

    def _parse_overline(self, line):
        """Parse the overline of the next section title from a line.

        It changes the state of the parser.

        :param line: the line to be parsed
        :type line: str
        :returns: returns :data:`True` if the line contains an
            overline, otherwise it returns :data:`False`
        :rtype: bool

        """
        match = OVERLINE_RE.match(line)
        if not match:
            return False
        self._cancel_title()
        self._needline = match.group(1)
        return True

    def _parse_title(self, line):
        """Parse the title from a line.

        It changes the state of the parser even if the line does not
        contain a title.

        :param line: the line to be parsed
        :type line: str
        :returns: returns :data:`True` if the line contains a title,
           otherwise it returns :data:`False`
        :rtype: bool

        """
        maxlen = len(self._needline) - len(' Release Notes')
        match = re.match(TITLE_RE_PAT.format(maxlen=maxlen), line)
        if not match:
            self._cancel_title()
            return False
        self._version = match.group(1)
        return True

    def _parse_underline(self, line):
        """Parse the underline of the next section title from a line.

        It changes the state of the parser.

        :param line: the line to be parsed
        :type line: str
        :returns: the version, the description, the list of issue
           numbers and the epilog of the previous release
        :rtype: tuple[str | None, str, list[str], str] | None

        """
        needline, version = self._cancel_title()
        if line != '{}\n'.format(needline):
            return None
        previous_version = self._last_version
        self.version = version
        self.description, self.issues, self.epilog = [], [], []
        return previous_version

    def _parse_issue(self, line):
        """Parse an issue number from a line.

        It changes the state of the parser.

        :param line: the line to be parsed
        :type line: str
        :returns: returns :data:`True` if the line refers to an issue,
           otherwise it returns :data:`False`
        :rtype: bool

        """
        match = re.match(r'^\* :rhbug:`(\d+)`\n$', line)
        if not match:
            return False
        self.issues.append(match.group(1))
        return True

    def _parse_line(self, line):
        """Parse a line of DNF release notes.

        It changes the state of the parser.

        :param line: the line to be parsed
        :type line: str
        :returns: the version, the description, the list of issue
           numbers and the epilog of the previous release
        :rtype: tuple[str | None, str, list[str], str] | None

        """
        needtitle = self._needline and self._version
        if not needtitle and self._parse_overline(line):
            return None
        if self._needline and not self._version and self._parse_title(line):
            return None
        if self._needline and self._version:
            previous_version = self._parse_underline(line)
            if previous_version:
                return previous_version
        if not self.epilog and self._parse_issue(line):
            return None
        if not self.issues:
            self.description.append(line)
            return None
        self.epilog.append(line)

    def parse_lines(self, lines):
        """Parse the lines of DNF release notes.

        :param lines: the line to be parsed
        :type lines: collections.Iterable[str]
        :returns: a generator yielding the version, the description, the
           list of issue numbers and the epilog of each release version
        :rtype: generator[tuple[str | None, str, list[str], str]]

        """
        self._needline = None
        self._version = None
        self.version = None
        self.description = []
        self.issues = []
        self.epilog = []
        for line in lines:
            previous_version = self._parse_line(line)
            if previous_version:
                yield previous_version
        yield self._last_version


class TestCase(unittest.TestCase):

    """A test fixture common to all tests.

    Among other things, the fixture contains a non-bare DNF repository
    with a spec file specifying an unreleased version, a tag dnf-1.0.1-1
    matching the version 1.0.1, one extra commit which resolves an issue
    and release notes matching the revision 9110490 of DNF.

    :cvar VERSION: the unreleased version specified in the spec file
    :type VERSION: str
    :cvar ISSUE: the number of the issue resolved by the extra commit
    :type ISSUE: str
    :ivar repository: the testing repository
    :type repository: git.Repo
    :ivar commit: the extra commit
    :type commit: unicode

    """

    VERSION = '999.9.9'

    ISSUE = '123456'

    def setUp(self):
        """Prepare the test fixture.

        :const:`__file__` is needed to prepare the fixture.

        """
        dirname = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, dirname)
        self.repository = detect_repository().clone(dirname)
        self.repository.head.reset(
            '9110490d690bbad10977b86e7ffbe1feeae26e03', working_tree=True)
        with open(os.path.join(dirname, SPEC_FN), 'wt') as specfile:
            specfile.write(
                'Name: dnf\n' +
                'Version: {}\n'.format(self.VERSION) +
                'Release: 1\n'
                'Summary: Package manager forked from Yum\n'
                'License: GPLv2+ and GPLv2 and GPL\n'
                '%description\n'
                'Package manager forked from Yum, using libsolv.\n'
                '%files\n')
        self.repository.index.add([SPEC_FN])
        self.commit = self.repository.index.commit(
            u'Version (RhBug:{})'.format(self.ISSUE.decode()))

    @staticmethod
    @contextlib.contextmanager
    def _read_copy(name):
        """Create and open a readable copy of a file.

        :param name: name of the file
        :type name: str
        :returns: the readable copy
        :rtype: file
        :raises exceptions.IOError: if the file cannot be opened

        """
        with tempfile.TemporaryFile('wt+') as copy:
            with open(name, 'rt') as original:
                shutil.copyfileobj(original, copy)
            copy.seek(0)
            yield copy

    @contextlib.contextmanager
    def _patch_file(self):
        """Temporarily set :const:`__file__` to point to the testing repo.

        :returns: a context manager
        :rtype: contextmanager

        """
        filename = os.path.join(
            self.repository.working_dir, 'scripts', 'update_releasenotes.py')
        original = __file__
        with tests.mock.patch('update_releasenotes.__file__', filename):
            assert __file__ != original, 'double check that the patch works'
            yield

    @contextlib.contextmanager
    def _assert_logs(self, level, regex):
        """Test whether a message matching an expression is logged.

        :param level: the level of the message
        :type level: int
        :param regex: the regular expression to be matched
        :type regex: re.RegexObject
        :returns: a context manager which represents the block in which
           the message should be logged
        :rtype: contextmanager
        :raises exceptions.AssertionError: if the test fails

        """
        class Handler(logging.Handler):
            def __init__(self, regex):
                super(Handler, self).__init__()
                self.regex = regex
                self.found = False

            def emit(self, record):
                if not self.found:
                    self.found = self.regex.match(record.getMessage())
        handler = Handler(regex)
        LOGGER.setLevel(level)
        LOGGER.addHandler(handler)
        yield
        self.assertTrue(handler.found)

    @contextlib.contextmanager
    def _assert_prints(self, regex, stream):
        """Test whether a message matching an expression is printed.

        :param regex: the regular expression to be matched
        :type regex: re.RegexObject
        :param stream: a name of the stream to be matched
        :type stream: str
        :returns: a context manager which represents the block in which
           the message should be printed
        :rtype: contextmanager
        :raises exceptions.AssertionError: if the test fails

        """
        with tests.mock.patch(stream, io.BytesIO()) as mock:
            yield
            self.assertRegexpMatches(mock.getvalue(), regex)

    def _assert_iter_equal(self, actual, expected):
        """Test whether two iterables are equal.

        :param actual: one of the iterables
        :type actual: collections.Iterable[object]
        :param expected: the other iterable
        :type expected: collections.Iterable[object]
        :raises exceptions.AssertionError: if the test fails

        """
        self.assertTrue(all(
            actual_ == expected_ for actual_, expected_ in
            itertools.izip_longest(actual, expected, fillvalue=object())))

    def test_detect_repository(self):
        """Test whether correct repository is detected.

        :raises exceptions.AssertionError: if the test fails

        """
        with self._patch_file():
            self.assertEqual(
                detect_repository().working_dir, self.repository.working_dir)

    def test_detect_version(self):
        """Test whether correct version is detected.

        :raises exceptions.AssertionError: if the test fails

        """
        self.assertEqual(detect_version(self.repository), self.VERSION)

    def test_find_tag_name(self):
        """Test whether correct tag is detected.

        :raises exceptions.AssertionError: if the test fails

        """
        self.assertEqual(find_tag(self.repository, '1.0.1'), 'dnf-1.0.1-1')

    def test_find_tag_none(self):
        """Test whether correct tag is detected.

        :raises exceptions.AssertionError: if the test fails

        """
        self.assertIsNone(find_tag(self.repository, '9999'))

    def test_iter_unreleased_commits(self):
        """Test whether correct commits are yielded.

        :raises exceptions.AssertionError: if the test fails

        """
        commits = iter_unreleased_commits(self.repository)
        self.assertItemsEqual(
            (commit.hexsha for commit in commits), [self.commit.hexsha])

    def test_parse_issues(self):
        """Test whether correct issues are yielded.

        :raises exceptions.AssertionError: if the test fails

        """
        self.assertItemsEqual(parse_issues([self.commit]), [self.ISSUE])

    def test_extend_releases_extend(self):
        """Test whether the release version is extended.

        :raises exceptions.AssertionError: if the test fails

        """
        releases = [
            (None, 'd1\n', [], ''),
            ('1.0.1', '\nd2\n', ['234567'], '\n'),
            ('999.9.9', '\nd3\n', ['345678'], '\n')]
        expected = [
            (None, 'd1\n', [], ''),
            ('1.0.1', '\nd2\n', ['456789', '234567'], '\n'),
            ('999.9.9', '\nd3\n', ['345678'], '\n')]
        self.assertItemsEqual(
            extend_releases(releases, '1.0.1', ['456789']), expected)

    def test_extend_releases_skip(self):
        """Test whether the already present issues are skipped.

        :raises exceptions.AssertionError: if the test fails

        """
        releases = [
            (None, 'd1\n', [], ''),
            ('1.0.1', '\nd2\n', ['234567'], '\n'),
            ('999.9.9', '\nd3\n', ['345678'], '\n')]
        expected = [
            (None, 'd1\n', [], ''),
            ('1.0.1', '\nd2\n', ['234567'], '\n'),
            ('999.9.9', '\nd3\n', ['345678'], '\n')]
        self.assertItemsEqual(
            extend_releases(releases, '1.0.1', ['234567']), expected)

    def test_extend_releases_append(self):
        """Test whether the rel. version is appended to the beginning.

        :raises exceptions.AssertionError: if the test fails

        """
        releases = [
            (None, 'd1\n', [], ''),
            ('1.0.1', '\nd2\n', ['234567'], '\n')]
        expected = [
            (None, 'd1\n', [], ''),
            ('999.9.9', '\n', ['345678'], '\n'),
            ('1.0.1', '\nd2\n', ['234567'], '\n')]
        self.assertItemsEqual(
            extend_releases(releases, '999.9.9', ['345678']), expected)

    def test_format_release_version(self):
        """Test whether correct string is returned.

        :raises exceptions.AssertionError: if the test fails

        """
        self.assertEqual(
            format_release('1.0.1', '\ndesc\n', ['123456', '234567'], '\ne\n'),
            '===================\n'
            '1.0.1 Release Notes\n'
            '===================\n'
            '\n'
            'desc\n'
            '* :rhbug:`123456`\n'
            '* :rhbug:`234567`\n'
            '\n'
            'e\n')

    def test_format_release_none(self):
        """Test whether no version is handled properly.

        :raises exceptions.AssertionError: if the test fails

        """
        self.assertEqual(format_release(None, 'l1\nl2\n', [], ''), 'l1\nl2\n')

    def test_update_notes_append(self):
        """Test whether the rel. version is appended to the beginning.

        :raises exceptions.AssertionError: if the test fails

        """
        regex = re.compile(
            '^Update finished. See the diff to the Git index:\n.+')
        notesfn = os.path.join(self.repository.working_dir, NOTES_FN)
        title = TITLE_PAT.format(version=self.VERSION)
        extra = [
            '\n',
            '{}\n'.format('=' * (len(title) - 1)),
            title,
            '{}\n'.format('=' * (len(title) - 1)),
            '\n',
            ISSUE_PAT.format(number=self.ISSUE)]
        with self._read_copy(notesfn) as original:
            # Insert the extra lines right after the 22nd line.
            expected = itertools.chain(
                itertools.islice(original, 0, 22), extra, original)
            with self._patch_file(), self._assert_logs(logging.INFO, regex):
                update_notes()
            with open(notesfn, 'rt') as actual:
                self._assert_iter_equal(actual, expected)

    def test_update_notes_released(self):
        """Test whether the released version is detected.

        :raises exceptions.AssertionError: if the test fails

        """
        self.repository.create_tag(TAG_PAT.format(version=self.VERSION))
        with self._patch_file():
            self.assertRaises(ValueError, update_notes)

    def test_main_append(self):
        """Test whether the release version is appended to the end.

        :raises exceptions.AssertionError: if the test fails

        """
        regex = re.compile(
            '^INFO Update finished. See the diff to the Git index:\n.+', re.M)
        notesfn = os.path.join(self.repository.working_dir, NOTES_FN)
        title = TITLE_PAT.format(version=self.VERSION)
        extra = [
            '\n',
            '{}\n'.format('=' * (len(title) - 1)),
            title,
            '{}\n'.format('=' * (len(title) - 1)),
            '\n',
            ISSUE_PAT.format(number=self.ISSUE)]
        with self._read_copy(notesfn) as original:
            # Insert the extra lines right after the 22nd line.
            expected = itertools.chain(
                itertools.islice(original, 0, 22), extra, original)
            with \
                    tests.mock.patch('sys.argv', ['prog']), \
                    self._patch_file(), \
                    self._assert_prints(regex, 'sys.stderr'):
                main()
            with open(notesfn, 'rt') as actual:
                self._assert_iter_equal(actual, expected)

    def test_main_released(self):
        """Test whether the released version is detected.

        :raises exceptions.AssertionError: if the test fails

        """
        self.repository.create_tag(TAG_PAT.format(version=self.VERSION))
        with \
                tests.mock.patch('sys.argv', ['prog']), self._patch_file(), \
                self.assertRaises(SystemExit) as context:
            main()
        self.assertNotEqual(context.exception.code, 0)

    def test_releasenotesparser(self):
        """Test whether correct release notes are yielded.

        :raises exceptions.AssertionError: if the test fails

        """
        notesfn = os.path.join(self.repository.working_dir, NOTES_FN)
        parser = ReleaseNotesParser()
        descriptions = [
            # None
            '..\n'
            '  Copyright (C) 2014  Red Hat, Inc.\n'
            '\n'
            '  This copyrighted material is made available to anyone wishing '
            'to use,\n  modify, copy, or redistribute it subject to the terms '
            'and conditions of\n  the GNU General Public License v.2, or (at '
            'your option) any later version.\n  This program is distributed in'
            ' the hope that it will be useful, but WITHOUT\n  ANY WARRANTY '
            'expressed or implied, including the implied warranties of\n  '
            'MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU'
            ' General\n  Public License for more details.  You should have '
            'received a copy of the\n  GNU General Public License along with '
            'this program; if not, write to the\n  Free Software Foundation, '
            'Inc., 51 Franklin Street, Fifth Floor, Boston, MA\n  02110-1301, '
            'USA.  Any Red Hat trademarks that are incorporated in the\n  '
            'source code or documentation are not subject to the GNU General '
            'Public\n  License and may only be used or replicated with the '
            'express permission of\n  Red Hat, Inc.\n'
            '\n'
            '###################\n'
            ' DNF Release Notes\n'
            '###################\n'
            '\n'
            '.. contents::\n'
            '\n',
            # 0.3.1
            '\n0.3.1 brings mainly changes to the automatic metadata '
            'synchronization. In\nFedora, ``dnf makecache`` is triggered via '
            'SystemD timers now and takes an\noptional ``background`` '
            'extra-argument to run in resource-considerate mode (no\nsyncing '
            'when running on laptop battery, only actually performing the '
            'check at\nmost once every three hours). Also, the IO and CPU '
            'priorities of the\ntimer-triggered process are lowered now and '
            "shouldn't as noticeably impact the\nsystem's performance.\n\nThe "
            'administrator can also easily disable the automatic metadata '
            'updates by\nsetting :ref:`metadata_timer_sync '
            '<metadata_timer_sync-label>` to 0.\n\nThe default value of '
            ':ref:`metadata_expire <metadata_expire-label>` was\nincreased '
            'from 6 hours to 48 hours. In Fedora, the repos usually set this\n'
            'explicitly so this change is not going to cause much impact.\n\n'
            'The following reported issues are fixed in this release:\n\n',
            # 0.3.2
            '\nThe major improvement in this version is in speeding up syncing'
            ' of repositories\nusing metalink by looking at the repomd.xml '
            'checksums. This effectively lets DNF\ncheaply refresh expired '
            'repositories in cases where the original has not\nchanged\\: for '
            'instance the main Fedora repository is refreshed with one 30 kB\n'
            'HTTP download. This functionality is present in the current Yum '
            "but hasn't\nworked in DNF since 3.0.0.\n\nOtherwise this is "
            'mainly a release fixing bugs and tracebacks. The following\n'
            'reported bugs are fixed:\n\n',
            # 0.3.3
            '\nThe improvements in 0.3.3 are only API changes to the logging. '
            'There is a new\nmodule ``dnf.logging`` that defines simplified '
            'logging structure compared to\nYum, with fewer logging levels and'
            ' `simpler usage for the developers\n<https://github.com/'
            'rpm-software-management/dnf/wiki/Hacking#logging>`_. The RPM '
            'transaction logs are\nno longer in ``/var/log/dnf.transaction.log'
            '`` but in ``/var/log/dnf.rpm.log`` by\ndefault.\n\nThe exception '
            'classes were simplified and moved to ``dnf.exceptions``.\n\nThe '
            'following bugs are fixed in 0.3.3:\n\n',
            # 0.3.4
            '\n0.3.4 is the first DNF version since the fork from Yum that is '
            'able to\nmanipulate the comps data. In practice, ``dnf group '
            'install <group name>`` works\nagain. No other group commands are '
            'supported yet.\n\nSupport for ``librepo-0.0.4`` and related '
            'cleanups and extensions this new\nversion allows are included '
            '(see the buglist below)\n\nThis version has also improved '
            'reporting of obsoleted packages in the CLI (the\nYum-style '
            '"replacing <package-nevra>" appears in the textual transaction\n'
            'overview).\n\nThe following bugfixes are included in 0.3.4:\n\n',
            # 0.3.5
            '\nBesides few fixed bugs this version should not present any '
            'differences for the\nuser. On the inside, the transaction '
            'managing mechanisms have changed\ndrastically, bringing code '
            'simplification, better maintainability and better\ntestability.\n'
            '\nIn Fedora, there is a change in the spec file effectively '
            'preventing the\nmakecache timer from running *immediately after '
            'installation*. The timer\nservice is still enabled by default, '
            'but unless the user starts it manually with\n``systemctl start '
            'dnf-makecache.timer`` it will not run until after the first\n'
            'reboot. This is in alignment with Fedora packaging best '
            'practices.\n\nThe following bugfixes are included in 0.3.5:\n\n',
            # 0.3.6
            '\nThis is a bugfix release, including the following fixes:\n\n',
            # 0.3.7
            '\nThis is a bugfix release:\n\n',
            # 0.3.8
            '\nA new locking module has been integrated in this version, '
            'clients should see the\nmessage about DNF lock being taken less '
            'often.\n\nPanu Matilainen has submitted many patches to this '
            'release to cleanup the RPM\ninterfacing modules.\n\nThe following'
            ' bugs are fixed in this release:\n\n',
            # 0.3.9
            '\nThis is a quick bugfix release dealing with reported bugs and '
            'tracebacks:\n\n',
            # 0.3.10
            '\nThe only major change is that ``skip_if_unavailable`` is '
            ':ref:`enabled by\ndefault now <skip_if_unavailable_default>`.\n\n'
            'A minor release otherwise, mainly to get a new version of DNF out'
            ' that uses a\nfresh librepo. The following issues are now a thing'
            ' of the past:\n\n',
            # 0.3.11
            '\nThe default multilib policy configuration value is ``best`` '
            'now. This does not\npose any change for the Fedora users because '
            'exactly the same default had been\npreviously achieved by a '
            'setting in ``/etc/dnf/dnf.conf`` shipped with the\nFedora '
            'package.\n\nAn important fix to the repo module speeds up package'
            ' downloads again is present\nin this release. The full list of '
            'fixes is:\n\n',
            # 0.4.0
            '\nThe new minor version brings many internal changes to the comps'
            ' code, most comps\nparsing and processing is now delegated to '
            '`libcomps\n<https://github.com/midnightercz/libcomps>`_ by '
            'Jind\xc5\x99ich Lu\xc5\xbea.\n\nThe ``overwrite_groups`` config '
            'option has been dropped in this version and DNF\nacts if it was '
            '0, that is groups with the same name are merged together.\n\nThe '
            'currently supported groups commands (``group list`` and '
            '``group install``)\nare documented on the manpage now.\n\nThe '
            '0.4.0 version is the first one supported by the DNF Payload for '
            'Anaconda and\nmany changes since 0.3.11 make that possible by '
            'cleaning up the API and making\nit more sane (cleanup of '
            '``yumvars`` initialization API, unifying the RPM\ntransaction '
            'callback objects hierarchy, slimming down ``dnf.rpmUtils.arch``,'
            '\nimproved logging).\n\nFixes for the following are contained in '
            'this version:\n\n',
            # 0.4.1
            '\nThe focus of this release was to support our efforts in '
            'implementing the DNF\nPayload for Anaconda, with changes on the '
            'API side of things (better logging,\nnew ``Base.reset()`` '
            'method).\n\nSupport for some irrelevant config options has been '
            'dropped (``kernelpkgnames``,\n``exactarch``, '
            '``rpm_check_debug``). We also no longer detect metalinks in the\n'
            '``mirrorlist`` option (see `Fedora bug 948788\n'
            '<https://bugzilla.redhat.com/show_bug.cgi?id=948788>`_).\n\nDNF '
            'is on its way to drop the urlgrabber dependency and the first set'
            ' of patches\ntowards this goal is already in.\n\nExpect the '
            'following bugs to go away with upgrade to 0.4.1:\n\n',
            # 0.4.2
            '\nDNF now downloads packages for the transaction in parallel with'
            ' progress bars\nupdated to effectively represent this. Since so '
            'many things in the downloading\ncode were changing, we figured it'
            ' was a good idea to finally drop urlgrabber\ndependency at the '
            "same time. Indeed, this is the first version that doesn't\n"
            'require urlgrabber for neither build nor run.\n\nSimilarly, since'
            ' `librepo started to support this\n<https://github.com/Tojaj/'
            'librepo/commit/acf458f29f7234d2d8d93a68391334343beae4b9>`_,\n'
            'downloads in DNF now use the fastests mirrors available by '
            "default.\n\nThe option to :ref:`specify repositories' costs "
            '<repo_cost-label>` has been\nreadded.\n\nInternally, DNF has seen'
            ' first part of ongoing refactorings of the basic\noperations '
            '(install, update) as well as a couple of new API methods '
            'supporting\ndevelopment of extensions.\n\nThese bugzillas are '
            'fixed in 0.4.2:\n\n',
            # 0.4.3
            '\nThis is an early release to get the latest DNF out with the '
            'latest librepo\nfixing the `Too many open files\n'
            '<https://bugzilla.redhat.com/show_bug.cgi?id=1015957>`_ bug.\n\n'
            'In Fedora, the spec file has been updated to no longer depend on '
            'precise\nversions of the libraries so in the future they can be '
            'released\nindependently.\n\nThis release sees the finished '
            'refactoring in error handling during basic\noperations and adds '
            'support for ``group remove`` and ``group info`` commands,\ni.e. '
            'the following two bugs:\n\n',
            # 0.4.4
            '\nThe initial support for Python 3 in DNF has been merged in this'
            ' version. In\npractice one can not yet run the ``dnf`` command in'
            ' Py3 but the unit tests\nalready pass there. We expect to give '
            'Py3 and DNF heavy testing during the\nFedora 21 development cycle'
            ' and eventually switch to it as the default. The plan\nis to drop'
            ' Python 2 support as soon as Anaconda is running in Python 3.\n\n'
            'Minor adjustments to allow Anaconda support also happened during '
            'the last week,\nas well as a fix to a possibly severe bug that '
            'one is however not really likely\nto see with non-devel Fedora '
            'repos:\n\n',
            # 0.4.5
            '\nA serious bug causing `tracebacks during package downloads\n'
            '<https://bugzilla.redhat.com/show_bug.cgi?id=1021087>`_ made it '
            'into 0.4.4 and\nthis release contains a fix for that. Also, a '
            'basic proxy support has been\nreadded now.\n\nBugs fixed in '
            '0.4.5:\n\n',
            # 0.4.6
            '\n0.4.6 brings two new major features. Firstly, it is the revival'
            ' of ``history\nundo``, so transactions can be reverted now.  '
            'Secondly, DNF will now limit the\nnumber of installed kernels and'
            ' *installonly* packages in general to the number\nspecified by '
            ':ref:`installonly_limit <installonly-limit-label>` configuration'
            '\noption.\n\nDNF now supports the ``group summary`` command and '
            'one-word group commands no\nlonger cause tracebacks, e.g. '
            '``dnf grouplist``.\n\nThere are vast internal changes to '
            '``dnf.cli``, the subpackage that provides CLI\nto DNF. In '
            'particular, it is now better separated from the core.\n\nThe '
            'hawkey library used against DNF from with this versions uses a '
            '`recent RPMDB\nloading optimization in libsolv\n'
            '<https://github.com/openSUSE/libsolv/commit/843dc7e1>`_ that '
            'shortens DNF\nstartup by seconds when the cached RPMDB is '
            'invalid.\n\nWe have also added further fixes to support Python 3 '
            "and enabled `librepo's\nfastestmirror caching optimization\n"
            '<https://github.com/Tojaj/librepo/commit/'
            'b8a063763ccd8a84b8ec21a643461eaace9b9c08>`_\nto tighten the '
            'download times even more.\n\nBugs fixed in 0.4.6:\n\n',
            # 0.4.7
            '\nWe start to publish the :doc:`api` with this release. It is '
            'largely\nincomprehensive at the moment, yet outlines the shape of'
            ' the documentation and\nthe process the project is going to use '
            'to maintain it.\n\nThere are two Yum configuration options that '
            'were dropped: :ref:`group_package_types '
            '<group_package_types_dropped>` and '
            ':ref:`upgrade_requirements_on_install '
            '<upgrade_requirements_on_install_dropped>`.\n\nBugs fixed in '
            '0.4.7:\n\n',
            # 0.4.8
            '\nThere are mainly internal changes, new API functions and '
            'bugfixes in this release.\n\nPython 3 is fully supported now, the'
            ' Fedora builds include the Py3 variant. The DNF program still '
            'runs under Python 2.7 but the extension authors can now choose '
            'what Python they prefer to use.\n\nThis is the first version of '
            'DNF that deprecates some of its API. Clients using deprecated '
            'code will see a message emitted to stderr using the standard '
            '`Python warnings module '
            '<http://docs.python.org/3.3/library/warnings.html>`_. You can '
            'filter out :exc:`dnf.exceptions.DeprecationWarning` to suppress '
            'them.\n\nAPI additions in 0.4.8:\n\n* :attr:`dnf.Base.sack`\n* '
            ':attr:`dnf.conf.Conf.cachedir`\n* '
            ':attr:`dnf.conf.Conf.config_file_path`\n* '
            ':attr:`dnf.conf.Conf.persistdir`\n* :meth:`dnf.conf.Conf.read`\n*'
            ' :class:`dnf.package.Package`\n* :class:`dnf.query.Query`\n* '
            ':class:`dnf.subject.Subject`\n* :meth:`dnf.repo.Repo.__init__`\n*'
            ' :class:`dnf.sack.Sack`\n* :class:`dnf.selector.Selector`\n* '
            ':class:`dnf.transaction.Transaction`\n\nAPI deprecations in '
            '0.4.8:\n\n* :mod:`dnf.queries` is deprecated now. If you need to '
            'create instances of :class:`.Subject`, import it from '
            ':mod:`dnf.subject`. To create :class:`.Query` instances it is '
            'recommended to use :meth:`sack.query() <dnf.sack.Sack.query>`.\n'
            '\nBugs fixed in 0.4.8:\n\n',
            # 0.4.9
            '\nSeveral Yum features are revived in this release. '
            '``dnf history rollback`` now works again. The '
            '``history userinstalled`` has been added, it displays a list of '
            'ackages that the user manually selected for installation on an '
            'installed system and does not include those packages that got '
            "installed as dependencies.\n\nWe're happy to announce that the "
            'API in 0.4.9 has been extended to finally support plugins. There '
            'is a limited set of plugin hooks now, we will carefully add new '
            'ones in the following releases. New marking operations have ben '
            'added to the API and also some configuration options.\n\nAn '
            'alternative to ``yum shell`` is provided now for its most common '
            'use case: :ref:`replacing a non-leaf package with a conflicting '
            'package <allowerasing_instead_of_shell>` is achieved by using the'
            ' ``--allowerasing`` switch now.\n\nAPI additions in 0.4.9:\n\n* '
            ':doc:`api_plugins`\n* :ref:`logging_label`\n* '
            ':meth:`.Base.read_all_repos`\n* :meth:`.Base.reset`\n* '
            ':meth:`.Base.downgrade`\n* :meth:`.Base.remove`\n* '
            ':meth:`.Base.upgrade`\n* :meth:`.Base.upgrade_all`\n* '
            ':attr:`.Conf.pluginpath`\n* :attr:`.Conf.reposdir`\n\nAPI '
            'deprecations in 0.4.9:\n\n* :exc:`.PackageNotFoundError` is '
            'deprecated for public use. Please catch :exc:`.MarkingError` '
            'instead.\n* It is deprecated to use :meth:`.Base.install` return '
            'value for anything. The method either returns or raises an '
            'exception.\n\nBugs fixed in 0.4.9:\n\n',
            # 0.4.10
            '\n0.4.10 is a bugfix release that also adds some long-requested '
            'CLI features and extends the plugin support with two new plugin '
            'hooks. An important feature for plugin developers is going to be '
            "the possibility to register plugin's own CLI command, available "
            'from this version.\n\n``dnf history`` now recognizes ``last`` as '
            'a special argument, just like other history commands.\n\n'
            '``dnf install`` now accepts group specifications via the ``@`` '
            'character.\n\nSupport for the ``--setopt`` option has been '
            'readded from Yum.\n\nAPI additions in 0.4.10:\n\n* '
            ':doc:`api_cli`\n* :attr:`.Plugin.name`\n* '
            ':meth:`.Plugin.__init__` now specifies the second parameter as an'
            ' instance of `.cli.Cli`\n* :meth:`.Plugin.sack`\n* '
            ':meth:`.Plugin.transaction`\n* :func:`.repo.repo_id_invalid`\n\n'
            'API changes in 0.4.10:\n\n* Plugin authors must specify '
            ':attr:`.Plugin.name` when authoring a plugin.\n\nBugs fixed in '
            '0.4.10:\n\n',
            # 0.4.11
            '\nThis is mostly a bugfix release following quickly after 0.4.10,'
            ' with many updates to documentation.\n\nAPI additions in 0.4.11:'
            '\n\n* :meth:`.Plugin.read_config`\n* :class:`.repo.Metadata`\n* '
            ':attr:`.repo.Repo.metadata`\n\nAPI changes in 0.4.11:\n\n* '
            ':attr:`.Conf.pluginpath` is no longer hard coded but depends on '
            'the major Python version.\n\nBugs fixed in 0.4.11:\n\n',
            # 0.4.12
            '\nThis release disables fastestmirror by default as we received '
            'many complains about it. There are also several bugfixes, most '
            'importantly an issue has been fixed that caused packages '
            'installed by Anaconda be removed together with a depending '
            'package. It is now possible to use ``bandwidth`` and ``throttle``'
            ' config values too.\n\nBugs fixed in 0.4.12:\n\n',
            # 0.4.13
            '\n0.4.13 finally ships support for `delta RPMS '
            '<https://gitorious.org/deltarpm>`_. Enabling this can save some '
            'bandwidth (and use some CPU time) when downloading packages for '
            'updates.\n\nSupport for bash completion is also included in this '
            'version. It is recommended to use the '
            '``generate_completion_cache`` plugin to have the completion work '
            'fast. This plugin will be also shipped with '
            '``dnf-plugins-core-0.0.3``.\n\nThe '
            ':ref:`keepcache <keepcache-label>` config option has been '
            'readded.\n\nBugs fixed in 0.4.13:\n\n',
            # 0.4.14
            '\nThis quickly follows 0.4.13 to address the issue of crashes '
            'when DNF output is piped into another program.\n\nAPI additions '
            'in 0.4.14:\n\n* :attr:`.Repo.pkgdir`\n\nBugs fixed in 0.4.14:\n'
            '\n',
            # 0.4.15
            '\nMassive refactoring of the downloads handling to provide better'
            ' API for reporting download progress and fixed bugs are the main '
            'things brought in 0.4.15.\n\nAPI additions in 0.4.15:\n\n* '
            ':exc:`dnf.exceptions.DownloadError`\n* '
            ':meth:`dnf.Base.download_packages` now takes the optional '
            '`progress` parameter and can raise :exc:`.DownloadError`.\n* '
            ':class:`dnf.callback.Payload`\n* '
            ':class:`dnf.callback.DownloadProgress`\n* '
            ':meth:`dnf.query.Query.filter` now also recognizes ``provides`` '
            'as a filter name.\n\nBugs fixed in 0.4.15:\n\n',
            # 0.4.16
            '\nThe refactorings from 0.4.15 are introducing breakage causing '
            'the background ``dnf makecache`` runs traceback. This release '
            'fixes that.\n\nBugs fixed in 0.4.16:\n\n',
            # 0.4.17
            '\nThis release fixes many bugs in the downloads/DRPM CLI area. A '
            'bug got fixed preventing a regular user from running read-only '
            'operations using ``--cacheonly``. Another fix ensures that '
            '``metadata_expire=never`` setting is respected. Lastly, the '
            'release provides three requested API calls in the repo management'
            ' area.\n\nAPI additions in 0.4.17:\n\n* '
            ':meth:`dnf.repodict.RepoDict.all`\n* '
            ':meth:`dnf.repodict.RepoDict.get_matching`\n* '
            ':meth:`dnf.repo.Repo.set_progress_bar`\n\nBugs fixed in 0.4.17:\n'
            '\n',
            # 0.4.18
            '\nSupport for ``dnf distro-sync <spec>`` finally arrives in this '
            'version.\n\nDNF has moved to handling groups as objects,  tagged '
            'installed/uninstalled independently from the actual installed '
            'packages. This has been in Yum as the ``group_command=objects`` '
            'setting and the default in recent Fedora releases. There are API '
            'extensions related to this change as well as two new CLI '
            'commands: ``group mark install`` and ``group mark remove``.\n\n'
            'API items deprecated in 0.4.8 and 0.4.9 have been dropped in '
            '0.4.18, in accordance with our :ref:`deprecating-label`.\n\nAPI '
            'changes in 0.4.18:\n\n* :mod:`dnf.queries` has been dropped as '
            'announced in `0.4.8 Release Notes`_\n* '
            ':exc:`dnf.exceptions.PackageNotFoundError` has been dropped from '
            'API as announced in `0.4.9 Release Notes`_\n* '
            ':meth:`dnf.Base.install` no longer has to return the number of '
            'marked packages as announced in `0.4.9 Release Notes`_\n\nAPI '
            'deprecations in 0.4.18:\n\n* :meth:`dnf.Base.select_group` is '
            'deprecated now. Please use :meth:`~.Base.group_install` instead.'
            '\n\nAPI additions in 0.4.18:\n\n* :meth:`dnf.Base.group_install`'
            '\n* :meth:`dnf.Base.group_remove`\n\nBugs fixed in 0.4.18:\n\n',
            # 0.4.19
            '\nArriving one week after 0.4.18, the 0.4.19 mainly provides a '
            'fix to a traceback in group operations under non-root users.\n\n'
            'DNF starts to ship separate translation files (.mo) starting with'
            ' this release.\n\nBugs fixed in 0.4.19:\n\n',
            # 0.5.0
            '\nThe biggest improvement in 0.5.0 is complete support for groups'
            ' `and environments '
            '<https://bugzilla.redhat.com/show_bug.cgi?id=1063666>`_, '
            'including internal database of installed groups independent of '
            'the actual packages (concept known as groups-as-objects from '
            'Yum). Upgrading groups is supported now with ``group upgrade`` '
            'too.\n\nTo force refreshing of metadata before an operation (even'
            ' if the data is not expired yet), `the refresh option has been '
            'added <https://bugzilla.redhat.com/show_bug.cgi?id=1064226>`_.\n'
            '\nInternally, the CLI went through several changes to allow for '
            'better API accessibility like `granular requesting of root '
            'permissions '
            '<https://bugzilla.redhat.com/show_bug.cgi?id=1062889>`_.\n\nAPI '
            'has got many more extensions, focusing on better manipulation '
            'with comps and packages. There are new entries in '
            ':doc:`cli_vs_yum` and :doc:`user_faq` too.\n\nSeveral resource '
            'leaks (file descriptors, noncollectable Python objects) were '
            'found and fixed.\n\nAPI changes in 0.5.0:\n\n* it is now '
            'recommended that either :meth:`dnf.Base.close` is used, or that '
            ':class:`dnf.Base` instances are treated as a context manager.\n\n'
            'API extensions in 0.5.0:\n\n* :meth:`dnf.Base.add_remote_rpms`\n* '
            ':meth:`dnf.Base.close`\n* :meth:`dnf.Base.group_upgrade`\n* '
            ':meth:`dnf.Base.resolve` optionally accepts `allow_erasing` '
            'arguments now.\n* :meth:`dnf.Base.package_downgrade`\n* '
            ':meth:`dnf.Base.package_install`\n* '
            ':meth:`dnf.Base.package_upgrade`\n* '
            ':class:`dnf.cli.demand.DemandSheet`\n* '
            ':attr:`dnf.cli.Command.base`\n* :attr:`dnf.cli.Command.cli`\n* '
            ':attr:`dnf.cli.Command.summary`\n* :attr:`dnf.cli.Command.usage`'
            '\n* :meth:`dnf.cli.Command.configure`\n* '
            ':attr:`dnf.cli.Cli.demands`\n* :class:`dnf.comps.Package`\n* '
            ':meth:`dnf.comps.Group.packages_iter`\n* '
            ':data:`dnf.comps.MANDATORY` etc.\n\nBugs fixed in 0.5.0:\n\n',
            # 0.5.1
            '\nBugfix release with several internal cleanups. One outstanding '
            'change for CLI users is that DNF is a lot less verbose now during'
            ' the dependency resolving phase.\n\nBugs fixed in 0.5.1:\n\n',
            # 0.5.2
            '\nThis release brings `autoremove command '
            '<https://bugzilla.redhat.com/show_bug.cgi?id=963345>`_ that '
            'removes any package that was originally installed as a dependency'
            ' (e.g. had not been specified as an explicit argument to the '
            'install command) and is no longer needed.\n\nEnforced '
            'verification of SSL connections can now be disabled with the '
            ':ref:`sslverify setting <sslverify-label>`.\n\nWe have been '
            'plagued with many crashes related to Unicode and encodings since '
            "the 0.5.0 release. These have been cleared out now.\n\nThere's "
            'more: improvement in startup time, `extended globbing semantics '
            'for input arguments '
            '<https://bugzilla.redhat.com/show_bug.cgi?id=1083679>`_ and '
            '`better search relevance sorting '
            '<https://bugzilla.redhat.com/show_bug.cgi?id=1093888>`_.\n\nBugs '
            'fixed in 0.5.2:\n\n',
            # 0.5.3
            '\nA set of bugfixes related to i18n and Unicode handling. There '
            'is a ``-4/-6`` switch and a corresponding :ref:`ip_resolve '
            '<ip-resolve-label>` configuration option (both known from Yum) to'
            ' force DNS resolving of hosts to IPv4 or IPv6 addresses.\n\n0.5.3'
            ' comes with several extensions and clarifications in the API: '
            'notably :class:`~.dnf.transaction.Transaction` is introspectible '
            'now, :class:`Query.filter <dnf.query.Query.filter>` is more '
            "useful with new types of arguments and we've hopefully shed more"
            ' light on how a client is expected to setup the configuration '
            ':attr:`~dnf.conf.Conf.substitutions`.\n\nFinally, plugin authors '
            'can now use a new :meth:`~dnf.Plugin.resolved` hook.\n\nAPI '
            'changes in 0.5.3:\n\n* extended description given for '
            ':meth:`dnf.Base.fill_sack`\n* :meth:`dnf.Base.select_group` has '
            'been dropped as announced in `0.4.18 Release Notes`_\n\nAPI '
            'additions in 0.5.3:\n\n* :attr:`dnf.conf.Conf.substitutions`\n* '
            ':attr:`dnf.package.Package.arch`\n* '
            ':attr:`dnf.package.Package.buildtime`\n* '
            ':attr:`dnf.package.Package.epoch`\n* '
            ':attr:`dnf.package.Package.installtime`\n* '
            ':attr:`dnf.package.Package.name`\n* '
            ':attr:`dnf.package.Package.release`\n* '
            ':attr:`dnf.package.Package.sourcerpm`\n* '
            ':attr:`dnf.package.Package.version`\n* '
            ':meth:`dnf.Plugin.resolved`\n* :meth:`dnf.query.Query.filter` '
            'accepts suffixes for its argument keys now which change the '
            'filter semantics.\n* :mod:`dnf.rpm`\n* '
            ':class:`dnf.transaction.TransactionItem`\n* '
            ':class:`dnf.transaction.Transaction` is iterable now.\n\nBugs '
            'fixed in 0.5.3:\n\n',
            # 0.5.4
            '\nSeveral encodings bugs were fixed in this release, along with '
            'some packaging issues and updates to :doc:`conf_ref`.\n\n'
            'Repository :ref:`priority <repo_priority-label>` configuration '
            'setting has been added, providing similar functionality to Yum '
            "Utils' Priorities plugin.\n\nBugs fixed in 0.5.4:\n\n",
            # 0.5.5
            '\nThe full proxy configuration, API extensions and several '
            'bugfixes are provided in this release.\n\nAPI changes in 0.5.5:\n'
            '\n* `cachedir`, the second parameter of '
            ':meth:`dnf.repo.Repo.__init__` is not optional (the method has '
            'always been this way but the documentation was not matching)\n\n'
            'API additions in 0.5.5:\n\n* extended description and an example '
            'provided for :meth:`dnf.Base.fill_sack`\n* '
            ':attr:`dnf.conf.Conf.proxy`\n* '
            ':attr:`dnf.conf.Conf.proxy_username`\n* '
            ':attr:`dnf.conf.Conf.proxy_password`\n* '
            ':attr:`dnf.repo.Repo.proxy`\n* '
            ':attr:`dnf.repo.Repo.proxy_username`\n* '
            ':attr:`dnf.repo.Repo.proxy_password`\n\nBugs fixed in 0.5.5:\n\n',
            # 0.6.0
            '\n0.6.0 marks a new minor version of DNF and the first release to'
            ' support advisories listing with the :ref:`udpateinfo command '
            '<updateinfo_command-label>`.\n\nSupport for the :ref:`include '
            'configuration directive <include-label>` has been added. Its '
            "functionality reflects Yum's ``includepkgs`` but it has been "
            'renamed to make it consistent with the ``exclude`` setting.\n\n'
            'Group operations now produce a list of proposed marking changes '
            'to group objects and the user is given a chance to accept or '
            'reject them just like with an ordinary package transaction.\n\n'
            'Bugs fixed in 0.6.0:\n\n',
            # 0.6.1
            '\nNew release adds :ref:`upgrade-type command '
            '<upgrade_type_automatic-label>` to `dnf-automatic` for choosing '
            'specific advisory type updates.\n\nImplemented missing '
            ':ref:`history redo command <history_redo_command-label>` for '
            'repeating transactions.\n\nSupports :ref:`gpgkey '
            '<repo_gpgkey-label>` repo config, :ref:`repo_gpgcheck '
            '<repo_gpgcheck-label>` and :ref:`gpgcheck <gpgcheck-label>` '
            '[main] and Repo configs.\n\nDistributing new package '
            ':ref:`dnf-yum <dnf_yum_package-label>` that provides '
            '`/usr/bin/yum` as a symlink to `/usr/bin/dnf`.\n\nAPI additions '
            'in 0.6.1:\n\n* `exclude`, the third parameter of '
            ':meth:`dnf.Base.group_install` now also accepts glob patterns of '
            'package names.\n\nBugs fixed in 0.6.1:\n\n',
            # 0.6.2
            '\nAPI additions in 0.6.2:\n\n* Now '
            ':meth:`dnf.Base.package_install` method ignores already installed'
            ' packages\n* `CliError` exception from :mod:`dnf.cli` documented'
            '\n* `Autoerase`, `History`, `Info`, `List`, `Provides`, '
            '`Repolist` commands do not force a sync of expired :ref:`metadata'
            ' <metadata_synchronization-label>`\n* `Install` command does '
            'installation only\n\nBugs fixed in 0.6.2:\n\n',
            # 0.6.3
            '\n:ref:`Deltarpm <deltarpm-label>` configuration option is set on'
            ' by default.\n\nAPI additions in 0.6.3:\n\n* dnf-automatic adds '
            ':ref:`motd emitter <emit_via_automatic-label>` as an alternative '
            'output\n\nBugs fixed in 0.6.3:\n\n',
            # 0.6.4
            '\nAdded example code snippets into :doc:`use_cases`.\n\nShows '
            'ordered groups/environments by `display_order` tag from :ref:`cli'
            ' <grouplist_command-label>` and :doc:`api_comps` DNF API.\n\nIn '
            'commands the environment group is specified the same as '
            ':ref:`group <specifying_groups-label>`.\n\n'
            ':ref:`skip_if_unavailable <skip_if_unavailable-label>` '
            'configuration option affects the metadata only.\n\nadded '
            '`enablegroups`, `minrate` and `timeout` :doc:`configuration '
            'options <conf_ref>`\n\nAPI additions in 0.6.4:\n\nDocumented '
            '`install_set` and `remove_set attributes` from '
            ':doc:`api_transaction`.\n\nExposed `downloadsize`, `files`, '
            '`installsize` attributes from :doc:`api_package`.\n\nBugs fixed '
            'in 0.6.4:\n\n',
            # 0.6.5
            '\nPython 3 version of DNF is now default in Fedora 23 and later.'
            '\n\nyum-dnf package does not conflict with yum package.\n\n'
            '`dnf erase` was deprecated in favor of `dnf remove`.\n\nExtended '
            'documentation of handling non-existent packages and YUM to DNF '
            'transition in :doc:`cli_vs_yum`.\n\nAPI additions in 0.6.5:\n\n'
            'Newly added `pluginconfpath` option in :doc:`configuration '
            '<conf_ref>`.\n\nExposed `skip_if_unavailable` attribute from '
            ':doc:`api_repos`.\n\nDocumented `IOError` exception of method '
            '`fill_sack` from :class:`dnf.Base`.\n\nBugs fixed in 0.6.5:\n\n',
            # 1.0.0
            '\nImproved documentation of YUM to DNF transition in '
            ':doc:`cli_vs_yum`.\n\n:ref:`Auto remove command '
            '<autoremove_command-label>` does not remove `installonly` '
            'packages.\n\n:ref:`Downgrade command <downgrade_command-label>` '
            'downgrades to specified package version if that is lower than '
            'currently installed one.\n\nDNF now uses :attr:`dnf.repo.Repo.id`'
            ' as a default value for :attr:`dnf.repo.Repo.name`.\n\nAdded '
            'support of repositories which use basic HTTP authentication.\n\n'
            'API additions in 1.0.0:\n\n:doc:`configuration <conf_ref>` '
            'options `username` and `password` (HTTP authentication)\n\n'
            ':attr:`dnf.repo.Repo.username` and :attr:`dnf.repo.Repo.password`'
            ' (HTTP authentication)\n\nBugs fixed in 1.0.0:\n\n',
            # 1.0.1
            '\nDNF follows the Semantic Versioning as defined at '
            '`<http://semver.org/>`_.\n\nDocumented SSL '
            ':doc:`configuration <conf_ref>` and :doc:`repository <api_repos>`'
            ' options.\n\nAdded virtual provides allowing installation of DNF'
            ' commands by their name in the form of\n'
            '``dnf install dnf-command(name)``.\n\n'
            ':doc:`dnf-automatic <automatic>` now by default waits random '
            'interval between 0 and 300 seconds before any network '
            'communication is performed.\n\n\nBugs fixed in 1.0.1:\n\n'
        ]
        rest = [
            (None, [], ''),
            ('0.3.1',
             ['916657', '921294', '922521', '926871', '878826', '922664',
              '892064', '919769'],
             '\n'),
            ('0.3.2', ['947258', '889202', '923384'], '\n'),
            ('0.3.3', ['950722', '903775'], '\n'),
            ('0.3.4', ['887317', '914919', '922667'], '\n'),
            ('0.3.5', ['958452', '959990', '961549', '962188'], '\n'),
            ('0.3.6',
             ['966372', '965410', '963627', '965114', '964467', '963680',
              '963133'],
             '\n'),
            ('0.3.7', ['916662', '967732'], '\n'),
            ('0.3.8',
             ['908491', '968159', '974427', '974866', '976652', '975858'],
             '\n'),
            ('0.3.9', ['964584', '979942', '980227', '981310'], '\n'),
            ('0.3.10', ['977661', '984483', '986545'], '\n'),
            ('0.3.11', ['979042', '977753', '996138', '993916'], '\n'),
            ('0.4.0', ['997403', '1002508', '1002798'], '\n'),
            ('0.4.1', ['998859', '1006366', '1008444', '1003220'], '\n'),
            ('0.4.2', ['909744', '984529', '967798', '995459'], '\n'),
            ('0.4.3', ['1013764', '1013773'], '\n'),
            ('0.4.4', ['1017278'], '\n'),
            ('0.4.5', ['1021087'], '\n'),
            ('0.4.6',
             ['878348', '880524', '1019957', '1020101', '1020934', '1023486'],
             '\n'),
            ('0.4.7', ['1019170', '1024776', '1025650'], '\n'),
            ('0.4.8',
             ['1014563', '1029948', '1030998', '1030297', '1030980'],
             '\n'),
            ('0.4.9',
             ['884615', '963137', '991038', '1032455', '1034607', '1036116'],
             '\n'),
            ('0.4.10',
             ['967264', '1018284', '1035164', '1036147', '1036211', '1038403',
              '1038937', '1040255', '1044502', '1044981', '1044999'],
             '\n'),
            ('0.4.11',
             ['1048402', '1048572', '1048716', '1048719', '1048988'],
             '\n'),
            ('0.4.12',
             ['1045737', '1048468', '1048488', '1049025', '1051554'],
             '\n'),
            ('0.4.13',
             ['909468', '1030440', '1046244', '1055051', '1056400'],
             '\n'),
            ('0.4.14', ['1062390', '1062847', '1063022', '1064148'],
             '\n'),
            ('0.4.15',
             ['1048788', '1065728', '1065879', '1065959', '1066743'],
             '\n'),
            ('0.4.16', ['1069996'], '\n'),
            ('0.4.17',
             ['1059704', '1058224', '1069538', '1070598', '1070710', '1071323',
              '1071455', '1071501', '1071518', '1071677'],
             '\n'),
            ('0.4.18', ['963710', '1067136', '1071212', '1071501'], '\n'),
            ('0.4.19', ['1077173', '1078832', '1079621'], '\n'),
            ('0.5.0',
             ['1029022', '1051869', '1061780', '1062884', '1062889', '1063666',
              '1064211', '1064226', '1073859', '1076884', '1079519', '1079932',
              '1080331', '1080489', '1082230', '1083432', '1083767', '1084139',
              '1084553', '1088166'],
             '\n'),
            ('0.5.1', ['1065882', '1081753', '1089864'], '\n'),
            ('0.5.2',
             ['963345', '1073457', '1076045', '1083679', '1092006', '1092777',
              '1093888', '1094594', '1095580', '1095861', '1096506'],
             '\n'),
            ('0.5.3',
             ['1047049', '1067156', '1093420', '1104757', '1105009', '1110800',
              '1111569', '1111997', '1112669', '1112704'],
             '\n'),
            ('0.5.4',
             ['1048973', '1108908', '1116544', '1116839', '1116845', '1117102',
              '1117293', '1117678', '1118178', '1118796', '1119032'],
             '\n'),
            ('0.5.5',
             ['1100946', '1117789', '1120583', '1121280', '1122900',
              '1123688'],
             '\n'),
            ('0.6.0',
             ['850912', '1055910', '1116666', '1118272', '1127206'],
             '\n'),
            ('0.6.1',
             ['1132335', '1071854', '1131969', '908764', '1130878', '1130432',
              '1118236', '1109915'],
             '\n'),
            ('0.6.2',
             ['909856', '1134893', '1138700', '1070902', '1124316', '1136584',
              '1135861', '1136223', '1122617', '1133830', '1121184'],
             '\n'),
            ('0.6.3',
             ['1153543', '1151231', '1163063', '1151854', '1151740', '1110780',
              '1149972', '1150474', '995537', '1149952', '1149350', '1170232',
              '1147523', '1148208', '1109927'],
             '\n'),
            ('0.6.4',
             ['1155877', '1175466', '1175466', '1186461', '1170156', '1184943',
              '1177002', '1169165', '1167982', '1157233', '1138096', '1181189',
              '1181397', '1175434', '1162887', '1156084', '1175098', '1174136',
              '1055910', '1155918', '1119030', '1177394', '1154476'],
             '\n'),
            ('0.6.5',
             ['1203151', '1187579', '1185977', '1195240', '1193914', '1195385',
              '1160806', '1186710', '1207726', '1157233', '1190671', '1191579',
              '1195325', '1154202', '1189083', '1193915', '1195661', '1190458',
              '1194685', '1160950'],
             '\n'),
            ('1.0.0',
             ['1215560', '1199648', '1208773', '1208018', '1207861', '1201445',
              '1210275', '1191275', '1207965', '1215289'],
             '\n'),
            ('1.0.1',
             ['1214968', '1222694', '1225246', '1213985', '1225277', '1223932',
              '1223614', '1203661', '1187741'],
             '')]
        expected = (
            (version, desc, issues, epilog)
            for desc, (version, issues, epilog) in zip(descriptions, rest))
        with open(notesfn) as notesfile:
            self.assertItemsEqual(parser.parse_lines(notesfile), expected)


if __name__ == '__main__':
    if sys.version < 3 :
        main()
    else :
        update_releasenotes_python3.main3()
        
