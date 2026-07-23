# Maintenance — clean-sort

## Update triggers

- New Python version support
- Security updates
- Bug fixes
- Feature additions

## Release process

1. Push to `main` with `[skip release]` if needed
2. Workflow auto-creates CalVer tag and release
3. Verify release on Codeberg

## Dependencies

- Python 3.11+
- libcst
- tomllib
- typer
- uv

## Testing

- Run `uv run pytest` before pushing
- Ensure all tests pass
- Add new tests for new features
