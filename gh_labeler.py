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

        self.url = 'https://api.github.com/'
        self.token = token
        self.user = user
        self.repo = repo

    def _delete(self, command, timeout=60):
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

            assert resp.status_code == 204

        except Exception:
            raise RuntimeError('DELETE command failed: {}'.format(self.url + command))

    def _patch(self, command, payload, timeout=60):
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

            assert resp.status_code == 200

        except Exception:
            raise RuntimeError('PATCH command failed: {}'.format(self.url + command))

    def _post(self, command, payload, timeout=60):
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

            assert resp.status_code == 201

        except Exception:
            raise RuntimeError('POST command failed: {}'.format(self.url + command))

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
                raise RuntimeError('GET command failed: {}'.format(command))

    def get(self, url):
        """Get the url."""

        return list(self._get(url))[0]


class GhLabeler:
    """GitHub label sync class."""

    def __init__(self, config, git, debug=False):
        """Initialize."""

        self.debug = debug
        self.git = git
        with codecs.open(os.getenv('GITHUB_EVENT_PATH'), 'r', encoding='utf-8') as f:
            workflow = json.loads(f.read())
        self.workflow = workflow

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

    def apply(self):
        """Sync labels."""

        print(json.dumps(self.workflow))
        for file in self._get_changed_files():
            print(file)


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
