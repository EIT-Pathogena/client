## Releases

### Creating a new release version

Having installed an editable [development environment](./install-dev.md#development-install)
(with pre-commit, pytest and flit):

```bash
pytest
# Bump version strings inside src/gpas/__init__.py AND Dockerfile
# Run the `./generate_pypi_readme.sh` to generate the PyPI README.
# Use format e.g. 1.0.0a1 for pre-releases (following example of Pydantic)
git tag 0.0.0. # e.g.
git push origin main --tags
flit build  # Build package
flit publish  # Authenticate and upload package to PyPI
# Announce in Slack CLI channel
# PR gpas/gpas/settings.py with new version
```
