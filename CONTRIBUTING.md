# Contribution Policy

## Branching rules

**Never push directly to `main`.**

`main` is the protected release branch. Every change lands through a pull request.

| Change | How it lands |
| --- | --- |
| New feature | Feature branch → PR → merge to `main` |
| Bug fix | Fix branch → PR → merge to `main` |
| Documentation only | Docs branch → PR → merge to `main` |

There are no exceptions. Not for small fixes, not for "obvious" changes, not
when a test is already green locally.

## How to work

1. **Sync first.** `git checkout main && git pull --ff-only`
2. **Branch.** `git checkout -b feat/short-description`
   - `feat/` new capability
   - `fix/` bug fix
   - `docs/` documentation only
   - `chore/` maintenance
3. **Commit.** Small, single-purpose commits with a real message.
4. **Push the branch.** `git push -u origin HEAD`
5. **Open a PR.** `gh pr create` against `main`.
6. **Wait for CI.** Do not merge with a red build.
7. **Merge, then delete the branch.**

## Why

Review exists to catch mistakes the author cannot see. I pushed to `main`
directly and shipped a `TypeError` that broke every supported Python version
except the one on my machine. A PR with CI on 3.9 and 3.12 would have caught it
before anyone saw it.

## Verifying before you push

CI runs Python 3.9 and 3.12. Your local interpreter is almost certainly neither.

```bash
python -m pytest tests/ -q -m "not live"
```

If you add code that touches annotations, syntax, or stdlib behavior, check the
oldest supported version too. `from __future__ import annotations` must be the
**first statement** in a module, after the docstring and before any import, or
the file will not compile at all.

## Protected branch

`main` is protected on GitHub. Direct pushes are expected to be rejected. If a
push to `main` succeeds, treat it as a mistake: say so immediately, and open a
follow-up PR with the fix rather than rewriting history.