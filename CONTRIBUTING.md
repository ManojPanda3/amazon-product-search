# Contribution Policy

Solo-maintained project. There is one reviewer and they are the author, so
branch protection and required approvals are not used here.

## Branching

Work on a branch, push the branch, and merge it yourself:

```bash
git checkout main && git pull --ff-only
git checkout -b fix/short-description
# edit, test, commit
git push -u origin HEAD
gh pr create --base main
gh pr merge --squash --delete-branch
```

Branch names: `feat/` new capability, `fix/` bug fix, `docs/` docs only,
`chore/` maintenance.

A PR is still worth opening even when nobody else reviews it. It gives you the
CI run on the real 3.9 and 3.12 matrix, and a diff to read before it lands.

## Verify before you push

CI runs Python 3.9 and 3.12. Your local interpreter is usually neither, and
that gap has shipped a real bug before.

```bash
python -m pytest tests/ -q -m "not live"
```

If you touch annotations, syntax, or stdlib behavior, check the oldest
supported version too:

```bash
uv python install 3.9
uv run --python 3.9 python -m pytest tests/ -q -m "not live"
```

`from __future__ import annotations` must be the **first statement** in a
module, after the docstring and before any import. Placing it after an import
is a `SyntaxError`, and omitting it makes `int | None` fail at runtime on 3.9.

## If you want real review later

Add a second GitHub account as a collaborator with write access, then enable
branch protection on `main` with 1 required approving review and
`enforce_admins` on. That combination is unsatisfiable while you are the only
account, so do not turn it on until the second account exists.

More generally: enabling a rule that the repo cannot satisfy blocks your own
work without protecting anything.
