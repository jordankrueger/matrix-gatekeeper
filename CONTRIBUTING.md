# Contributing

Thanks for your interest in matrix-gatekeeper! This is a small project and contributions are welcome.

## Reporting Issues

If you find a bug or have a feature request, open an issue on GitHub. Include:

- What you expected to happen
- What actually happened
- Your homeserver type (Synapse, Dendrite, Conduit, etc.)
- Relevant log output (redact any tokens or user IDs)

## Pull Requests

1. Fork the repo and create a branch
2. Make your changes
3. Test against a real Matrix homeserver (or a local one via Docker)
4. Open a PR with a clear description of what changed and why

## Code Style

- This is a single-file bot — keep it that way unless there's a strong reason to split
- No external dependencies beyond what's in `requirements.txt` unless truly necessary
- DM failures should always be non-blocking (the core gating flow must never break)

## License

By contributing, you agree that your contributions are released under [The Unlicense](LICENSE) (public domain).
