# EIT Pathogena client

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
  conda create -y -n pathogena -c conda-forge -c bioconda hostile==1.1.0
  conda activate pathogena
  pip install --upgrade pathogena
  ```

- Test:
  ```
  pathogena --version
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
pathogena --version
```


### Using an alternate host

1. The stateless way (use `--host` with every command):
   ```bash
   pathogena auth --host dev.portal.pathogena.world
   pathogena upload samples.csv --host dev.portal.pathogena.world
   ```

2. The stateful way (no need to use `--host` with each command):
   ```bash
   export pathogena_HOST="dev.portal.gpas.world"
   ```

   Then, as usual:
   ```bash
   pathogena auth
   pathogena upload samples.csv
   ```

   To reset:
   ```bash
   unset PATHOGENA_HOST
   ```

### Tab completion

Tab completion can optionally be enabled by adding the following lines to your shell source files. 
This will enable the ability to press tab after writing `pathogena ` to list possible sub-commands. It can also be used
for sub-command options, if `--` is entered prior to pressing tab.

#### Example usage

![tab-complete.gif](src/assets/tab-complete.gif)

#### Enabling tab completion

Run the following command and follow the output to enable autocompletion, this will need to be executed
on every new shell session, instructions are provided on how to make this permanent depending on your
environment. More information and instructions for other shells can be found in the 
[Click documentation](https://click.palletsprojects.com/en/8.1.x/shell-completion/).

```bash
$ pathogena autocomplete
Run this command to enable autocompletion:
    eval "$(_PATHOGENA_COMPLETE=zsh_source pathogena)"
Add this to your ~/.zshrc file to enable this permanently:
    command -v pathogena > /dev/null 2>&1 && eval "$(_PATHOGENA_COMPLETE=zsh_source pathogena)"
```


### Installing a pre-release version

```bash
conda create --yes -n pathogena -c conda-forge -c bioconda hostile==1.1.0
conda activate pathogena
pip install --pre pathogena
```



### Using a local development server

```bash
export PATHOGENA_HOST="localhost:8000"
export PATHOGENA_PROTOCOL="http"
```
To unset:
```bash
unset PATHOGENA_HOST
unset PATHOGENA_PROTOCOL
```



### Releasing a new version

Having installed an editable [development environment](https://github.com/GlobalPathogenAnalysisService/client?tab=readme-ov-file#development) (with pre-commit, pytest and flit):

```bash
pytest
# Bump version strings inside src/pathogena/__init__.py AND Dockerfile
# Use format e.g. 1.0.0a1 for pre-releases (following example of Pydantic)
git tag 0.0.0. # e.g.
git push origin main --tags
flit build  # Build package
flit publish  # Authenticate and upload package to PyPI
# Announce in Slack CLI channel
# PR pathogena/pathogena/settings.py with new version
```
