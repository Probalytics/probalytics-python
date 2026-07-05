# Repository Rules

Recommended GitHub rules for `main` on this public SDK:

- Require a pull request before merging.
- Require at least one approval.
- Dismiss stale approvals when new commits are pushed.
- Require review from Code Owners if a CODEOWNERS file is added later.
- Require status checks to pass before merging:
  - `Tests / Python 3.11`
  - `Tests / Python 3.12`
  - `ClickHouse integration tests`
- Require branches to be up to date before merging.
- Require conversation resolution before merging.
- Block force pushes.
- Block branch deletion.
- Restrict direct pushes to repository administrators or a release automation actor.
- Allow Dependabot to open pull requests for dependency and GitHub Actions
  updates, but require the same status checks before merge.

These rules are configured in GitHub repository settings or through the GitHub
rulesets API; they are not applied by files committed to the repository.
