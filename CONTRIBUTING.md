# Contributing to Meanwhile

Thanks for helping. Bug reports and ideas are welcome as issues.

> [!IMPORTANT]
> Meanwhile is still in active development, so pull requests are not accepted for now; they are
> closed without review. The steps below describe how it will work once that changes.

## Issues

Use the issue forms: **Bug report** (what you did, what you expected, what happened, the
version) or **Feature request** (the problem first, then the idea). Remove personal data
from logs and screenshots. **Security issues** never go into a public issue — see
[SECURITY.md](SECURITY.md).

## Pull requests

1. Discuss larger changes in an issue first.
2. Fork, branch from `main`, keep the change focused on one topic.
3. Set up the project as described in the [README](README.md).
4. Follow the conventions in [AGENTS.md](AGENTS.md): structure, services, UUID models,
   strict typing, English and German texts, no inline scripts.
5. Add or update tests; coverage must stay at or above the minimums (backend 90 %,
   frontend 95/95/95/90 lines/statements/functions/branches).
6. After model changes run `just migrations`, after API changes `just api-types`, and
   commit the generated files.
7. Update the documentation when users or operators notice the change.
8. Run `just check` before you push; CI runs the same recipes on the pull request.

## Commits and releases

Pull requests are squash-merged, and their title becomes the commit on `main`. Write it as a
[Conventional Commit](https://www.conventionalcommits.org/) in English: `feat: show the owner
on the detail page`, `fix: …`, `docs: …`, `chore: …`; `feat!:` or a `BREAKING CHANGE:` footer
for incompatible changes. Releases are made from these titles (CHANGELOG.md, version number),
so they describe the change for users.

## License

Meanwhile is licensed under the [AGPL-3.0-or-later](LICENSE). By submitting a contribution
you agree that it is licensed under the same terms. New dependencies must not be under
GPL, AGPL or SSPL (checked in CI); Radicale (GPL-3.0, the CalDAV server) is the one
deliberate exception, compatible with the AGPL.
