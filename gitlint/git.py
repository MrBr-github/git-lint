# Copyright 2013-2014 Sebastian Kreft
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Functions to get information from git."""

import os.path
import subprocess

import gitlint.utils as utils


def repository_root():
    """Returns the root of the repository as an absolute path."""
    try:
        root = subprocess.check_output(
            ['git', 'rev-parse', '--show-toplevel'],
            stderr=subprocess.STDOUT).strip()
        # Convert to unicode first
        return root.decode('utf-8')
    except subprocess.CalledProcessError:
        return None


def last_commit():
    """Returns the SHA1 of the last commit."""
    try:
        root = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], stderr=subprocess.STDOUT).strip()
        # Convert to unicode first
        return root.decode('utf-8')
    except subprocess.CalledProcessError:
        return None


def _remove_filename_quotes(filename):
    """Removes the quotes from a filename returned by git status."""
    if filename.startswith('"') and filename.endswith('"'):
        return filename[1:-1]

    return filename


def modified_files(root, tracked_only=False, commit=None):
    """Returns a list of files that has been modified since the last commit.

    Args:
      root: the root of the repository, it has to be an absolute path.
      tracked_only: exclude untracked files when True.
      commit: SHA1 of the commit. If None, it will get the modified files in the
        working copy.

    Returns: a dictionary with the modified files as keys, and additional
      information as value. In this case it adds the status returned by
      git status.
    """
    assert os.path.isabs(root), "Root has to be absolute, got: %s" % root

    if commit:
        return _modified_files_with_commit(root, commit)

    # Convert to unicode and split
    status_lines = subprocess.check_output([
        'git', 'status', '--porcelain', '--untracked-files=all',
        '--ignore-submodules=all'
    ]).decode('utf-8').split(os.linesep)

    modes = ['M ', ' M', 'A ', 'AM', 'MM']
    if not tracked_only:
        modes.append(r'\?\?')
    modes_str = '|'.join(modes)

    modified_file_status = utils.filter_lines(
        status_lines,
        r'(?P<mode>%s) (?P<filename>.+)' % modes_str,
        groups=('filename', 'mode'))

    return dict((os.path.join(root, _remove_filename_quotes(filename)), mode)
                for filename, mode in modified_file_status)


def _modified_files_with_commit(root, commit):
    root_commit = commit + '~1'
    lcommit = last_commit()

    if commit != lcommit:
        root_commit = lcommit

    # Convert to unicode and split
    status_lines = subprocess.check_output([
        'git', 'diff-tree', '-r', '--root', '--no-commit-id', '--name-status',
        commit, root_commit
    ]).decode('utf-8').split(os.linesep)

    modified_file_status = utils.filter_lines(
        status_lines,
        r'(?P<mode>A|M)\s(?P<filename>.+)',
        groups=('filename', 'mode'))

    # We need to add a space to the mode, so to be compatible with the output
    # generated by modified files.
    return dict((os.path.join(root, _remove_filename_quotes(filename)),
                 mode + ' ') for filename, mode in modified_file_status)


def modified_lines(filename, extra_data, commit=None):
    """Returns the lines that have been modifed for this file.

    Args:
      filename: the file to check.
      extra_data: is the extra_data returned by modified_files. Additionally, a
        value of None means that the file was not modified.
      commit: the complete sha1 (40 chars) of the commit. Note that specifying
        this value will only work (100%) when commit == last_commit (with
        respect to the currently checked out revision), otherwise, we could miss
        some lines.

    Returns: a list of lines that were modified, or None in case all lines are
      new.
    """
    if extra_data is None:
        return []
    if extra_data not in ('M ', ' M', 'MM'):
        return None

    if commit is None:
        commit = '0' * 40
    commit = commit.encode('utf-8')

    # Split as bytes, as the output may have some non unicode characters.
    blame_lines = subprocess.check_output(
        ['git', 'blame', '--porcelain', filename]).split(
            os.linesep.encode('utf-8'))

    commit_list = []
    lcommit = last_commit().encode('utf-8')
    if lcommit != commit:
        tmp = subprocess.check_output([
        'git', 'rev-list', commit.decode("utf-8")  + '..' + lcommit.decode("utf-8")
        ])
        a = tmp.split(os.linesep.encode('utf-8'))
        commit_list = subprocess.check_output([
        'git', 'rev-list', commit.decode("utf-8")  + '..' + lcommit.decode("utf-8")
        ]).strip().split(os.linesep.encode('utf-8'))
    else:
        commit_list.append(commit)

    modified_line_numbers_list = []
    for cmt in commit_list:
        modified_line_numbers_generator = utils.filter_lines(blame_lines, cmt + br' (?P<line>\d+) (\d+)', groups=('line', ))
        modified_line_numbers_list.extend(list(map(int, modified_line_numbers_generator)))

    return list(modified_line_numbers_list)
