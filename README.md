![GitHub release (latest SemVer)][latest-release]
![License][license-image-mit]

# Wildcard Labeler Action

## Overview

Wildcard Labeler is a GitHub action that labels pull requests based on file patterns of changed files. It uses the
Python library [`wcmatch`][wcmatch] to perform the file matching.

By default, [`wcmatch`][wcmatch] is configured with the following flags:

- [SPLIT][split]: enables chaining multiple patterns together with `|` so they are evaluated together. For instance, if
  we wanted to find all Markdown and HTML files in a folder, we could use the following pattern:

    ```
    folder/*.md|folder/*.html
    ```

- [GLOBSTAR][globstar]: enables the pattern `**` to match zero or more folders. For instance, if we wanted to find
  Python files under any child folder of a given folder:

    ```
    src/**/*.py
    ```

- [DOTGLOB][dotglob]: enables the matching of `.` at the start of a file in patterns such as `*`, `**`, `?` etc. Since
  this is enabled, we should be able to match files that start with `.` like `.travis.yml` by simply using `*`.

- [NEGATE][negate]: allows inverse match patterns by starting a pattern with `!`. It is meant to filter other normal
  patterns. For instance if we wanted to find all Python files except those under our *tests* folder:

    ```
    **/*.py|!tests/**
    ```

- [NEGATEALL][negateall]: allows using inverse patterns when no normal patterns are given. When an inverse pattern is
  given with no normal patterns, the pattern of `**` is assumed as the normal pattern to filter. So if we wanted find
  any file accept HTML files:

  ```
  !*.html
  ```

Check out the libraries [documentation][glob] for more information on syntax.

## Usage

Wildcard Labeler is set up on pull request actions:

```yml
name: "wildcard labeler"
on: [pull_request]

jobs:
  pull-labels:
    runs-on: ubuntu-latest
    steps:
    - name: Wildcard Labeler
      uses: facelessuser/wildcard-labeler-action@v1
      with:
        token: "${{ secrets.GITHUB_TOKEN }}"
```

Parameters | Required | Default               | Description
---------- | -------- | --------------------- | -----------
`token`    | True     |                       | Access token.
`file`     | False    | `.github/labeler.yml` | Path to YAML configuration file containing label rules.

## Configuration File

The configuration file should be in the YAML format. Configuration files consist of two parts: flags that control the
behavior of the glob patterns, and rules that define pattens of files that must be modified to have a label applied
along with the associated label names to apply.

The global flags alter the default behavior of the glob patterns:

Flag                             | Description
-------------------------------- | -----------
[`brace_expansion`][brace]       | Allows Bash style brace expansion in patterns: `a{b,{c,d}}` → `ab ac ad`.
[`extended_glob`][extglob]       | Enables Bash style extended glob patterns: `@(ab\|ac\|ad)`, etc. When this is enabled, the flag [`MINUSNEGATE`][minusnegate] is also enabled. `MINUSNEGATE` changes inverse patterns to use `-` instead of `!` to avoid conflicts with the extended glob patterns of `!(...)`.
[`case_insensitive`][ignorecase] | As the action is run in a Linux environment, matches are case sensitive by default. This enables case insensitive matching.

Global flags are placed at the top of the configuration file:

```yml

case_insensitive: true

rules:
  - labels: [python, code]
    patterns:
    - '**/*.py'
    - '**/*.pyc'
```

`rules` should contain a list of patterns coupled with associated to labels to apply. Both the `labels` key and the
`patterns` key should be lists.

For each entry in a `patterns` list are handled independently from the other patterns in the list. So if we wanted to
augment a normal pattern with an inverse pattern, we should use `|` on the same line:

```yml
rules:
  - labels: [python, code]
    patterns:
    - '**/*.py|!tests'  # Any Python file not under tests
```

Having these patterns on different lines will **not** provide the same behavior as they will be evaluated independently.

```yml
rules:
  - labels: [python, code]
    patterns:
    - '**/*.py'  # All Python files
    - '!tests'   # Any file not under tests
```

[wcmatch]: https://github.com/facelessuser/wcmatch
[split]: https://facelessuser.github.io/wcmatch/glob/#globsplit
[globstar]: https://facelessuser.github.io/wcmatch/glob/#globglobstar
[dotglob]: https://facelessuser.github.io/wcmatch/glob/#globdotglob
[negate]: https://facelessuser.github.io/wcmatch/glob/#globnegate
[negateall]: https://facelessuser.github.io/wcmatch/glob/#globnegateall
[minusnegate]: https://facelessuser.github.io/wcmatch/glob/#globminusnegate
[extglob]: https://facelessuser.github.io/wcmatch/glob/#globextglob
[brace]: https://facelessuser.github.io/wcmatch/glob/#globbrace
[ignorecase]: https://facelessuser.github.io/wcmatch/glob/#globignorecase
[glob]: https://facelessuser.github.io/wcmatch/glob/

[latest-release]: https://img.shields.io/github/v/release/facelessuser/wildcard-labeler-action
[license-image-mit]: https://img.shields.io/badge/license-MIT-blue.svg
