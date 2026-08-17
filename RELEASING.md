# Releasing `xii-django-river`

This repo publishes to PyPI through a two-step GitOps pipeline:

```
push/merge to master
        │
        ▼
release-please.yml  ──►  keeps a "chore(master): release X.Y.Z" PR
        │                up to date (version bump + CHANGELOG.md),
        │                gated by the normal CI checks like any PR
        ▼
   (you merge that PR)
        │
        ▼
release-please tags master + creates a GitHub Release
        │
        ▼
publish.yml  ──►  builds sdist+wheel, publishes to PyPI via
                   Trusted Publishing (OIDC) — no secrets involved
```

You never manually bump a version number, edit a changelog file for the
release notes, run `python -m build`, or run `twine upload`. You write
commits in [Conventional Commits](https://www.conventionalcommits.org/)
format, and merge exactly two kinds of pull requests: your normal feature
PRs, and the release PR that release-please keeps open for you.

## What you need to do once, by hand

Everything below is a one-time setup step. None of it can be done from
inside this repo's code — it's account/repo settings on PyPI and GitHub.

### 1. Register a "pending publisher" on PyPI

`xii-django-river` doesn't exist as a PyPI project yet, so there's no
project settings page to configure a trusted publisher on. PyPI has a
separate flow for exactly this case — a **pending publisher** — that
creates the project automatically the first time this workflow publishes
through it:

1. Log into (or create) the PyPI account that should own this project.
2. Go to <https://pypi.org/manage/account/publishing/>.
3. Under "Add a new pending publisher", fill in:
   - **PyPI Project Name**: `xii-django-river`
   - **Owner**: `xiidigital` (the GitHub org/user)
   - **Repository name**: `xii-django-river`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
4. Submit. That's it — no token, no secret to copy anywhere. The first
   successful run of `publish.yml` will create the project on PyPI under
   this account.

If `xii-django-river` ever does get published as a project on PyPI already
(e.g. someone did a one-off manual upload before this pipeline existed),
use the normal (non-pending) "Trusted Publishers" tab on that project's
management page instead — same fields, just not "pending".

### 2. Create a protected `pypi` GitHub Environment

This is what makes `environment: pypi` in `publish.yml` mean something, and
it's what the `Environment name` you typed into PyPI in step 1 has to match
exactly.

1. In the GitHub repo: **Settings → Environments → New environment**,
   name it `pypi`.
2. Turn on **Required reviewers** and add whoever should get the final say
   before a build actually reaches PyPI (yourself is fine to start). This
   means: version bump, tagging, and the GitHub Release itself are fully
   automatic, but the actual `pip install` — the irreversible part — still
   waits for a human click.
3. (Optional but recommended) Restrict the environment to the `master`
   branch under **Deployment branches**, so a publish can never be
   triggered from anywhere else.

### 3. Enable required status checks on `master`

Make sure the existing `ci.yml` jobs (`test`, `bdd`) are set as **required
status checks** for `master` under **Settings → Branches → Branch
protection rules**. Without this, nothing stops the release PR (or any PR)
from being merged with a red CI run.

That's the entire one-time setup. Steps 1–2 need a human with the right
PyPI/GitHub permissions; nothing here can be scripted from this repo.

## Day to day: what you actually do

1. Write commits using Conventional Commits prefixes:
   - `fix: ...` → patch release (`4.0.0` → `4.0.1`)
   - `feat: ...` → minor release (`4.0.0` → `4.1.0`)
   - `feat!: ...` or a `BREAKING CHANGE:` footer → major release
     (`4.0.0` → `5.0.0`)
   - `chore:`, `docs:`, `test:`, `refactor:`, `ci:`, etc. → included in the
     changelog under their own section, but don't bump the version by
     themselves.

   This matters for PRs specifically at merge time: if you squash-merge a
   PR (the usual setup), the **squash commit message** is what
   release-please reads, not the individual commits inside the PR. Title
   your PRs accordingly.

2. Merge your PRs into `master` as normal. `release-please.yml` runs on
   every push to `master` and keeps a single "chore(master): release
   X.Y.Z" PR open, continuously updated with whatever has landed since the
   last release. It computes the next version from the commits, so you
   don't need to (and normally shouldn't) change the version number by
   hand anywhere.

3. When you're ready to cut a release, review and merge that release PR
   like any other PR. That merge is the actual trigger: release-please
   tags the resulting commit and publishes a GitHub Release from it.

4. `publish.yml` picks up that `release: published` event, builds the
   sdist+wheel, and — after the `pypi` environment's required reviewer(s)
   approve — uploads to PyPI.

## Files involved

- `release-please-config.json` / `.release-please-manifest.json` — tell
  release-please this is a single Python package (`release-type: python`),
  currently at version `4.0.0` (matches `pyproject.toml` and
  `xii/django_river/__init__.py`'s `__version__`), and that
  `xii/django_river/__init__.py` needs its version string bumped alongside
  `pyproject.toml`'s `[project].version` (which release-please's `python`
  strategy updates automatically without extra config).
- `.github/workflows/release-please.yml` — step 1 (the PR/tag/release
  automation).
- `.github/workflows/publish.yml` — step 2 (build + Trusted Publishing
  upload).
- `CHANGELOG.md` (repo root, created by release-please on the first
  release) — the terse, autogenerated log derived straight from commit
  messages. This is **separate from `docs/changelog.rst`**, which stays a
  hand-curated, prose changelog with the fuller "why", the way it's been
  maintained throughout this fork's history (see `TECH_DEBT.md` for the
  running rationale behind every change). Nothing here retires that file
  or automates it — after a release, it's still worth a manual pass to add
  a proper entry to `docs/changelog.rst` for anything release-please's
  one-line summaries don't do justice to.

## Sanity-checking before the first real release

Before merging the very first release-please-generated PR, it's worth
running the same build the CI would run locally, to catch anything
project-metadata-related before it reaches PyPI:

```bash
python -m pip install --upgrade build twine
python -m build
twine check dist/*
```

`publish.yml` runs the identical two commands as its own gate before ever
reaching the `pypi` environment, so this isn't strictly required — but
seeing a clean local build once before trusting the pipeline is cheap
reassurance.
