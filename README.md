# GPAS CLI

The command line and Python API client for the GPAS mycobacterial platform. Enables secure sample upload with client-side human read removal and retrieval of analytical outputs.



## Install

### Installing Miniconda

If a conda package manager is already installed, skip to [Installing the GPAS CLI](#installing-or-updating-the-gpas-cli), otherwise:

**Linux**

- In a terminal console, install Miniconda, following instructions and accepting default options:
  ```bash
  curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  bash Miniconda3-latest-Linux-x86_64.sh
  ```

**MacOS**

The GPAS CLI requires an `x86_64` conda installation. If your Mac has an Apple processor, you must disable or delete any existing `arm64` conda installations before continuing.

- If your Mac has an Apple processor, using Terminal, firstly run:
  ```bash
  arch -x86_64 zsh
  ```
- Install Miniconda using Terminal, following instructions and accepting default options:
  ```bash
  curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh
  bash Miniconda3-latest-MacOSX-x86_64.sh
  ```



### Installing or updating the GPAS CLI

- If using a Mac with an Apple processor, using Terminal, firstly run:

  ```bash
  arch -x86_64 zsh
  ```

- Perform the installation/upgrade:
  ```bash
  conda create --yes -n gpas -c conda-forge -c bioconda hostile
  conda activate gpas
  pip install gpas
  ```

- Test:
  ```
  gpas --version
  ```



## Usage

Ensure that the conda environment is active:

```bash
conda activate gpas
```



#### Help

Run `gpas --help` for an overview of CLI subcommands. For help with a specific subcommand, use e.g. `gpas auth --help`



#### Authentication (`gpas auth`)

The first time you use the CLI, you will need to authenticate by running `gpas auth` and entering your username and password. This token will be used automatically for subsequent commands.

```
gpas auth
Enter your username: bede.constantinides@ndm.ox.ac.uk
Enter your password: ***************
```



#### Uploading samples (`gpas upload`)

Performs metadata validation and client-side removal of human reads in each of your samples before uploading sequences to the GPAS platform.

```bash
gpas upload tests/data/illumina.csv
```

This generates a mapping CSV (e.g. `a5w2e8.mapping.csv`) linking your local sample names with their randomly generated remote identifiers (GUIDs). Keep this file safe as it's useful for downloading and relinking results later.



#### Downloading files (`gpas download`)

Downloads the output (and/or input) files associated with a batch of samples given a mapping CSV generated during upload, or one or more sample GUIDs. When a mapping CSV is used, by default downloaded file names are prefixed with the sample names provided at upload. Otherwise downloaded files are prefixed with the sample GUID.

```bash
# Download the main reports for all samples in a5w2e8.mapping.csv
gpas download a5w2e8.mapping.csv

# Download the main and speciation reports for samples in a5w2e8.mapping.csv
gpas download a5w2e8.mapping.csv --filenames main_report.json,speciation_report.json

# Download the main report for one sample
gpas download 3bf7d6f9-c883-4273-adc0-93bb96a499f6

# Download the main report for two samples
gpas download 3bf7d6f9-c883-4273-adc0-93bb96a499f6,6f004868-096b-4587-9d50-b13e09d01882

# Save downloaded files to a specific directory
gpas download a5w2e8.mapping.csv --out-dir results

# Download input files
gpas download --inputs a5w2e8.mapping.csv --filenames ""
```



#### Querying sample metadata (`gpas query`)

Fetches either the processing status (`gpas query status`) or raw metadata (`gpas query raw`) of one more samples given a mapping CSV generated during upload, or one or more sample GUIDs.

```bash
# Query the processing status of all samples in a5w2e8.mapping.csv
gpas query status a5w2e8.mapping.csv

# Query the processing status of a single sample
gpas query status 3bf7d6f9-c883-4273-adc0-93bb96a499f6

# Query all available metadata in JSON format
gpas query raw a5w2e8.mapping.csv
```



## Support

For technical support, please open an issue or contact `support@gpas.global`



## Development

**Development install**

```bash
git clone https://github.com/GlobalPathogenAnalysisService/cli.git
cd cli
conda env create -y -f environment-dev.yml
pip install --editable .
```

**Updating**

```bash
git pull origin main
gpas --version
```



### Using alternate API servers

```bash
export GPAS_HOST="dev.portal.gpas.world"
```

To unset

```bash
unset GPAS_HOST
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

```bash
pytest
# Increment version string inside src/gpas/__init__.py
git tag 0.xx.0  # Tag new version
git push origin main --tags  # Push including tags
flit build
flit publish  # Uploads to PyPI given appropriate permission
# Announce in Slack CLI channel
# PR gpas/gpas/settings.py with new version
```
