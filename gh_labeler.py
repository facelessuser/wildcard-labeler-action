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

__version__ = "1.0.0"


class Api:
    """Class to post commands to the REST API."""

    def __init__(self, token, user, repo):
        """Initialize."""

        self.url = 'https://api.github.com'
        self.token = token
        self.user = user
        self.repo = repo

    def _delete(self, command, timeout=60, expected=200):
        """Send a DELETE REST command."""

        if timeout == 0:
            timeout = None

        headers = {
            'Authorization': 'token {}'.format(self.token),
            'Accept': 'application/vnd.github.symmetra-preview+json'
        }

        try:
            resp = requests.delete(
                command,
                headers=headers,
                timeout=timeout
            )

            assert resp.status_code == expected

        except Exception:
            raise RuntimeError('DELETE command failed: {}'.format(command))

    def _patch(self, command, payload, timeout=60, expected=200):
        """Send a PATCH REST command."""

        if timeout == 0:
            timeout = None

        headers = {
            'Authorization': 'token {}'.format(self.token),
            'Accept': 'application/vnd.github.symmetra-preview+json'
        }

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

    def _post(self, command, payload, timeout=60, expected=200):
        """Send a POST REST command."""

        if timeout == 0:
            timeout = None

        headers = {
            'Authorization': 'token {}'.format(self.token),
            'Accept': 'application/vnd.github.symmetra-preview+json'
        }

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

    def _get(self, command, timeout=60, pages=False):
        """Send a GET REST request."""

        if timeout == 0:
            timeout = None

        headers = {
            'Authorization': 'token {}'.format(self.token),
            'Accept': 'application/vnd.github.symmetra-preview+json'
        }

        data = None

        while command:
            try:
                resp = requests.get(
                    command,
                    headers=headers,
                    timeout=timeout
                )

                assert resp.status_code == 200

                command = resp.links.get('next', {}).get('url', '') if pages else ''
                data = json.loads(resp.text)
                if pages:
                    for entry in data:
                        yield entry
                else:
                    yield data

            except Exception:
                import traceback
                print(traceback.format_exc())
                raise RuntimeError('GET command failed: {}'.format(command))

    def get_labels(self):
        """Get labels."""

        return list(self._get('/'.join([self.url, 'repos', self.user, self.repo, 'labels']), pages=True))

    def create_label(self, name, color, description):
        """Create label."""

        self._post(
            '/'.join([self.url, 'repos', self.user, self.repo, 'labels']),
            {'name': name, 'color': color, 'description': description},
            201
        )

    def add_labels(self, number, labels):
        """Add labels."""

        self._post(
            '/'.join([self.url, 'repos', self.user, self.repo, 'issues', number, 'labels']),
            {'labels': list(labels)}
        )

    def remove_labels(self, number, labels):
        """Remove labels."""

        for label in labels:
            self._delete(
                '/'.join([self.url, 'repos', self.user, self.repo, 'issues', number, 'labels', label])
            )

    def get(self, url):
        """Get the url."""

        return list(self._get(url))[0]


class GhLabeler:
    """GitHub label sync class."""

    def __init__(self, config, git, debug=False):
        """Initialize."""

        self.debug = debug
        self.git = git
        self._setup_flags(config)
        self.labels = config['labels']
        with codecs.open(os.getenv('GITHUB_EVENT_PATH'), 'r', encoding='utf-8') as f:
            workflow = json.loads(f.read())
        self.workflow = workflow

    def _setup_flags(self, config):
        """Setup flags."""

        self.flags = glob.GLOBSTAR | glob.DOTGLOB | glob.NEGATE | glob.SPLIT
        if config.get('brace_expansion', False):
            self.flags |= glob.BRACE
        if config.get('extended_glob', False):
            self.flags |= glob.EXTGLOB | glob.MINUSNEGATE

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
        labels = set([l['name'].lower() for l in self.workflow['pull_request']['labels']])

        if remove_labels:
            remove = labels - remove_labels
            if remove:
                self.git.remove_labels(number, remove)
        if add_labels:
            # repo_labels = set([l['name'].lower() for l in self.git.get_labels()])
            # missing = add_labels - repo_labels
            # for m in missing:
            #     self.git.create_label(m, '00ff00', '')
            self.git.add_labels(number, add_labels)

    def apply(self):
        """Sync labels."""

        managed_labels = set()
        add_labels = set()

        for file in self._get_changed_files():
            for label in self.labels:
                managed_labels.add(label['name'].lower())
                match = False
                for pattern in label['patterns']:
                    if glob.globmatch(file, pattern, flags=self.flags):
                        match = True
                        break
                if match:
                    add_labels.add(label['name'].lower())
                    break

        remove_labels = managed_labels - add_labels
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

    # Parse label file
    labels = os.getenv("INPUT_FILE", '.github/labeler.yml')
    print('Reading labels from {}'.format(labels))
    with codecs.open(labels, 'r', encoding='utf-8') as f:
        config = yaml.load(f.read(), Loader=Loader)

    # Sync the labels
    git = Api(token, user, repo)
    GhLabeler(config, git, debug).apply()
    return 0


if __name__ == "__main__":
    sys.exit(main())
