#!/usr/bin/env python
"""Auto add labels to pull request."""
import codecs
import yaml
import json
import sys
import os
import re
import requests
import urllib.parse
from wcmatch import glob
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

__version__ = "1.1.0"


class Api:
    """Class to post commands to the REST API."""

    def __init__(self, token, user, repo):
        """Initialize."""

        self.url = 'https://api.github.com'
        self.token = token
        self.user = user
        self.repo = repo

    def _delete(self, command, timeout=60, expected=200, headers=None):
        """Send a DELETE REST command."""

        if timeout == 0:
            timeout = None

        if headers is None:
            headers = {}

        headers['Authorization'] = 'token {}'.format(self.token)

        try:
            resp = requests.delete(
                command,
                headers=headers,
                timeout=timeout
            )

            assert resp.status_code == expected

        except Exception:
            raise RuntimeError('DELETE command failed: {}'.format(command))

    def _patch(self, command, payload, timeout=60, expected=200, headers=None):
        """Send a PATCH REST command."""

        if timeout == 0:
            timeout = None

        if headers is None:
            headers = {}

        headers['Authorization'] = 'token {}'.format(self.token)

        if payload is not None:
            payload = json.dumps(payload)
            headers['content-type'] = 'application/json'

        try:
            resp = requests.patch(
                command,
                data=payload,
                headers=headers,
                timeout=timeout
            )

            assert resp.status_code == expected

        except Exception:
            raise RuntimeError('PATCH command failed: {}'.format(command))

    def _post(self, command, payload, timeout=60, expected=200, headers=None):
        """Send a POST REST command."""

        if timeout == 0:
            timeout = None

        if headers is None:
            headers = {}

        headers['Authorization'] = 'token {}'.format(self.token)

        if payload is not None:
            payload = json.dumps(payload)
            headers['content-type'] = 'application/json'

        try:
            resp = requests.post(
                command,
                data=payload,
                headers=headers,
                timeout=timeout
            )

            assert resp.status_code == expected

        except Exception:
            raise RuntimeError('POST command failed: {}'.format(command))

    def _get(self, command, payload=None, timeout=60, pages=False, expected=200, headers=None, text=False):
        """Send a GET REST request."""

        if timeout == 0:
            timeout = None

        if headers is None:
            headers = {}

        headers['Authorization'] = 'token {}'.format(self.token)

        data = None

        while command:
            try:
                resp = requests.get(
                    command,
                    params=payload,
                    headers=headers,
                    timeout=timeout
                )

                assert resp.status_code == expected

                command = resp.links.get('next', {}).get('url', '') if pages else ''
                data = json.loads(resp.text) if not text else resp.text
                if pages and not text:
                    for entry in data:
                        yield entry
                else:
                    yield data

            except Exception:
                raise RuntimeError('GET command failed: {}'.format(command))

    def get_contents(self, file, ref="master"):
        """Get contents."""

        return list(
            self._get(
                '/'.join([self.url, 'repos', self.user, self.repo, 'contents',  urllib.parse.quote(file)]),
                headers={'Accept': 'application/vnd.github.v3.raw'},
                payload={'ref': ref},
                text=True
            )
        )[0]

    def get_issue_labels(self, number):
        """Get issue labels."""

        return list(
            self._get(
                '/'.join([self.url, 'repos', self.user, self.repo, 'issues', number, 'labels']),
                pages=True,
                headers={'Accept': 'application/vnd.github.symmetra-preview+json'}
            )
        )

    def add_issue_labels(self, number, labels):
        """Add labels."""

        self._post(
            '/'.join([self.url, 'repos', self.user, self.repo, 'issues', number, 'labels']),
            {'labels': labels},
            headers={'Accept': 'application/vnd.github.symmetra-preview+json'}
        )

    def remove_issue_labels(self, number, labels):
        """Remove labels."""

        for label in labels:
            self._delete(
                '/'.join(
                    [self.url, 'repos', self.user, self.repo, 'issues', number, 'labels',  urllib.parse.quote(label)]
                ),
                headers={'Accept': 'application/vnd.github.symmetra-preview+json'}
            )

    def get(self, url):
        """Get the url."""

        return list(self._get(url, headers={'Accept': 'application/vnd.github.v3+json'}))[0]


class GhLabeler:
    """GitHub label sync class."""

    def __init__(self, config, git, debug=False):
        """Initialize."""

        self.debug = debug
        self.git = git
        with codecs.open(os.getenv('GITHUB_EVENT_PATH'), 'r', encoding='utf-8') as f:
            workflow = json.loads(f.read())
        self.workflow = workflow
        config = self._get_config(config)
        self._setup_flags(config)
        self.labels = config['rules']

    def _get_config(self, config):
        """Get config."""

        print('Reading labels from {}'.format(config))
        return yaml.load(self.git.get_contents(config, ref=os.getenv("GITHUB_SHA")), Loader=Loader)

    def _setup_flags(self, config):
        """Setup flags."""

        self.flags = glob.GLOBSTAR | glob.DOTGLOB | glob.NEGATE | glob.SPLIT | glob.NEGATEALL
        if config.get('brace_expansion', False):
            self.flags |= glob.BRACE
        if config.get('extended_glob', False):
            self.flags |= glob.EXTGLOB | glob.MINUSNEGATE
        if config.get('case_insensitive', False):
            self.flags |= glob.IGNORECASE

    def _validate_str(self, name):
        """Validate name."""

        if not isinstance(name, str):
            raise TypeError("Key value is not of type 'str', type '{}' received instead".format(type(name)))

    def _get_changed_files(self):
        """Get changed files."""

        files = []
        compare = self.git.get(
            self.workflow['repository']['compare_url'].format(
                base=self.workflow['pull_request']['base']['label'],
                head=self.workflow['pull_request']['head']['label']
            )
        )
        for file in compare['files']:
            files.append(file['filename'])
        return files

    def _update_issue_labels(self, add_labels, remove_labels):
        """Update issue labels."""

        number = str(self.workflow['number'])
        labels = set([l['name'].lower() for l in self.git.get_issue_labels(number)])

        if remove_labels:
            remove = []
            seen = set()
            for name in remove_labels:
                low = name.lower()
                if low in labels and low not in seen:
                    remove.append(name)
                seen.add(low)
            if remove:
                self.git.remove_issue_labels(number, remove)
        if add_labels:
            self.git.add_issue_labels(number, list(add_labels))

    def apply(self):
        """Sync labels."""

        add_labels = set()
        i_add_labels = set()
        seen = set()

        for file in self._get_changed_files():
            for label in self.labels:
                names = label['labels']
                lows = [n.lower() for n in names]
                match = False
                for pattern in label['patterns']:
                    if glob.globmatch(file, pattern, flags=self.flags):
                        match = True
                        break
                if match:
                    for index, low in enumerate(lows):
                        if low not in i_add_labels:
                            add_labels.add(names[index])
                            i_add_labels.add(low)
                    break

        remove_labels = set()
        i_remove_labels = set()
        for label in self.labels:
            names = label['labels']
            lows = [n.lower() for n in names]
            for index, low in enumerate(lows):
                if low not in i_add_labels and low not in i_remove_labels:
                    remove_labels.add(names[index])
                    i_remove_labels.add(low)

        self._update_issue_labels(add_labels, remove_labels)


def main():
    """Main."""

    dbg = os.getenv("INPUT_DEBUG", 'disable')
    if dbg == 'enable':
        debug = True
    elif dbg == 'disable':
        debug = False
    else:
        raise ValueError('Unknown value for debug: {}'.format(dbg))

    # Get the user's name and repository so we can access the labels for the repository
    repository =  os.getenv("GITHUB_REPOSITORY")
    if repository and '/' in repository:
        user, repo = repository.split('/')
    else:
        raise ValueError('Could not acquire user name and repository name')

    # Acquire access token
    token = os.getenv("INPUT_TOKEN", '')
    if not token:
        raise ValueError('No token provided')

    # Get label file
    config = os.getenv("INPUT_FILE", '.github/labeler.yml')

    # Sync the labels
    git = Api(token, user, repo)
    GhLabeler(config, git, debug).apply()
    return 0


if __name__ == "__main__":
    sys.exit(main())
