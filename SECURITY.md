# Security

TashevLoop stores project learning data locally.

- Do not record credentials or other sensitive values in event descriptions.
- TashevLoop writes .tashevloop/.gitignore, so the local store stays out of Git history in any project.
- Review exported context before publishing it.
- The core performs no network upload.
- The autopilot agent can read and edit files in its worktree but cannot run commands or use the web. The verification command then runs code the agent wrote, with your user permissions. Enable the autopilot only in repositories you trust.

For security reports, contact the repository owner privately.
