# GPAS client

The command line interface for the GPAS mycobacterial platform. The client enables privacy-preserving sequence data submission and retrieval of analytical output files. Prior to upload, sample identifiers are anonymised and human host sequences are removed. A multicore machine with 16GB of RAM running Linux or MacOS is recommended.

See [PyPi readme](README_pypi.md) for details for using the client usage.

## Install

### Installing Miniconda

If a conda package manager is already installed, skip to [Installing the client](#installing-or-updating-the-client), otherwise:

**Linux**

- In a terminal console, install Miniconda, following instructions and accepting default options:
  ```bash
  curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  bash Miniconda3-latest-Linux-x86_64.sh
  ```

**MacOS**

The client requires an `x86_64` conda installation. If your Mac has an Apple processor, disable or delete existing `arm64` conda installations before continuing.

- If your Mac has an Apple processor, using Terminal, firstly run:
  ```bash
  arch -x86_64 zsh
  ```
- Install Miniconda using Terminal, following instructions and accepting default options:
  ```bash
  curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh
  bash Miniconda3-latest-MacOSX-x86_64.sh
  ```



### Installing or updating the client

- If using a Mac with an Apple processor, using Terminal, firstly run:

  ```bash
  arch -x86_64 zsh
  ```

- Perform the installation/upgrade:
  ```bash
  conda create -y -n gpas -c conda-forge -c bioconda hostile==1.1.0
  conda activate gpas
  pip install --upgrade gpas
  ```

- Test:
  ```
  gpas --version
  ```


## Development

**Development install**

```bash
git clone https://github.com/GlobalPathogenAnalysisService/cli.git
cd cli
conda env create -y -f environment.yml
pip install --editable '.[dev]'
pre-commit install
```

**Updating**

```bash
git pull origin main
gpas --version
```



### Using an alternate host

1. The stateless way (use `--host` with every command):
   ```bash
   gpas auth --host dev.portal.gpas.world
   gpas upload samples.csv --host dev.portal.gpas.world
   ```

2. The stateful way (no need to use `--host` with each command):
   ```bash
   export GPAS_HOST="dev.portal.gpas.world"
   ```

   Then, as usual:
   ```bash
   gpas auth
   gpas upload samples.csv
   ```

   To reset:
   ```bash
   unset GPAS_HOST
   ```



### Installing a pre-release version

```bash
conda create --yes -n gpas -c conda-forge -c bioconda hostile==1.1.0
conda activate gpas
pip install --pre gpas
```



### Using a local development server

```bash
export GPAS_HOST="localhost:8000"
export GPAS_PROTOCOL="http"
```
To unset:
```bash
unset GPAS_HOST
unset GPAS_PROTOCOL
```



### Releasing a new version

Having installed an editable [development environment](https://github.com/GlobalPathogenAnalysisService/client?tab=readme-ov-file#development) (with pre-commit, pytest and flit):

```bash
pytest
# Bump version strings inside src/gpas/__init__.py AND Dockerfile
# Use format e.g. 1.0.0a1 for pre-releases (following example of Pydantic)
git tag 0.0.0. # e.g.
git push origin main --tags
flit build  # Build package
flit publish  # Authenticate and upload package to PyPI
# Announce in Slack CLI channel
# PR gpas/gpas/settings.py with new version
```
