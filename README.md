# GPAS client

The command line interface for the GPAS mycobacterial platform. The client enables privacy-preserving sequence data submission and retrieval of analytical output files. Prior to upload, sample identifiers are anonymised and human host sequences are removed. For the best experience, a multicore machine with 16GB of RAM running Linux or MacOS is recommended.



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

You will need to authenticate the first time you use the client. Do this by running `gpas auth` and entering your username and password. A token will be saved automatically inside your home directory.

```
gpas auth
Enter your username: bede.constantinides@ndm.ox.ac.uk
Enter your password: ***************
```



#### Uploading samples (`gpas upload`)

The upload subcommand performs metadata validation and client-side removal of human reads for each of your samples, before uploading sequences to the GPAS platform for analysis.

```bash
gpas upload tests/data/illumina.csv
```

During upload, a mapping CSV is created (e.g. `a5w2e8.mapping.csv`) linking your local sample names with their randomly generated remote names. Keep this file safe, as it is useful for downloading and relinking results later.

A 4GB human genome index is downloaded the first time you run `gpas upload`. If for any reason this is interrupted, simply run the upload command again. Upload will not proceed until the index has been downloaded and passed an integrity check.

To retain the decontaminated FASTQ files uploaded to GPAS, include the optional `--save` flag. To perform decontamination without uploading anything, use the optional `--dry-run` flag.



#### Downloading files (`gpas download`)

The download subcommand retrieves the output (and/or input) files associated with a batch of samples given a mapping CSV generated during upload, or one or more sample GUIDs. When a mapping CSV is used, by default downloaded file names are prefixed with the sample names provided at upload. Otherwise downloaded files are prefixed with the sample GUID.

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
gpas download a5w2e8.mapping.csv --inputs --filenames ""
```

The complete list of `--filenames` available for download varies by sample, and can be found in the Downloads section of sample view pages in the GPAS web portal.



#### Querying sample metadata (`gpas query`)

The query subcommand fetches either the processing status (`gpas query status`) or raw metadata (`gpas query raw`) of one more samples given a mapping CSV generated during upload, or one or more sample GUIDs.

```bash
# Query the processing status of all samples in a5w2e8.mapping.csv
gpas query status a5w2e8.mapping.csv

# Query the processing status of a single sample
gpas query status 3bf7d6f9-c883-4273-adc0-93bb96a499f6

# Query all available metadata in JSON format
gpas query raw a5w2e8.mapping.csv
```



#### Downloading decontamination indexes (`gpas download-index`)

The human genome index used for host decontamination is downloaded automatically when running `gpas upload` for the first time. You may however trigger this manually by running `gpas download-index`.



## Support

For technical support, please open an issue or contact `support@gpas.global`



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
   ```export GPAS_HOST="dev.portal.gpas.world"
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
# Increment version strings inside src/gpas/__init__.py, Dockerfile
git tag 0.xx.0
git push origin main --tags
flit build
flit publish  # Uploads to PyPI given appropriate permission
# Announce in Slack CLI channel
# PR gpas/gpas/settings.py with new version
```
