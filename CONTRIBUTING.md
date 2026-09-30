# Contributing

Contributions are welcome! Here's how you can help.

## Development Setup

Requires Python 3.11+.

```bash
# Clone the repository
git clone https://github.com/jr2804/pyreorder.git
cd pyreorder

# Install the pinned tool versions, then the dev dependencies
mise install
uv sync --dev
```

## Running Tests

```bash
mise test        # pytest with coverage
```

## Code Quality

```bash
mise lint        # ruff check --fix
mise format      # ruff format
mise format-md   # rumdl, for Markdown
mise typecheck   # ty
mise spell       # codespell

mise all         # all of the above
```

`mise docs` builds the documentation site into `site/`. Every task maps to the
plain command CI also runs, so `mise` is optional.

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

See the [Development page](https://jr2804.github.io/pyreorder/development/) for
the full task list, the release process, and the project layout.
