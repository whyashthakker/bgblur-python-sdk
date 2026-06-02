# Deployment Guide

This guide covers publishing a new `bgblur-ai` package version to PyPI.

## Package Names

- PyPI install name: `bgblur-ai`
- Python import name: `bgblur_ai`
- CLI command: `bgblur-ai`

## Run Tests

```bash
pytest
```

Expected result:

```text
16 passed
```

## Bump Version

Edit `pyproject.toml`:

```toml
version = "0.1.1"
```

PyPI does not allow re-uploading the same version. Every new release needs a new version.

## Install Build Tools

```bash
python3 -m pip install --upgrade build twine
```

## Build

```bash
python3 -m build
```

This creates files under `dist/`, for example:

```text
dist/bgblur_ai-0.1.1-py3-none-any.whl
dist/bgblur_ai-0.1.1.tar.gz
```

## Validate Build

```bash
twine check dist/*
```

## Publish To PyPI

```bash
twine upload dist/*
```

When prompted:

```text
username: __token__
password: pypi-...
```

Use a PyPI API token, not your account password.

For the first upload, an account-wide token may be needed because the project does not exist yet. After the first publish, create a project-scoped token for `bgblur-ai`.

## Verify Install

```bash
python3 -m venv /tmp/bgblur-prod-test
source /tmp/bgblur-prod-test/bin/activate
pip install bgblur-ai
python -c "from bgblur_ai import PrivacyBlur; print(PrivacyBlur)"
```

## PyPI Account And Ownership

Create a PyPI account:

```text
https://pypi.org/account/register/
```

Enable 2FA:

```text
https://pypi.org/manage/account/2fa/
```

The GitHub repository does not need to be public to publish to PyPI. However, the PyPI package itself is public, and users can inspect the Python source included in the package.

To transfer project control later:

1. Ask the new owner to create a PyPI account and enable 2FA.
2. Open `Your projects` in PyPI.
3. Open `bgblur-ai`.
4. Go to `Manage project`.
5. Open `Collaborators`.
6. Add the new owner by PyPI username.
7. Set role to `Owner`.
8. After confirming access, remove your account or keep it as `Maintainer`.

Role notes:

- `Owner` can manage collaborators and publish releases.
- `Maintainer` can publish releases but cannot manage owners.
