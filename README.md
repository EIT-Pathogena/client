# gpas-client (myco)

The command line interface and Python API for the Global Pathogen Analysis Service. Enables secure sample upload with client-side human read removal, progress monitoring, and retrieval of analytical outputs.



## Install

### Installing Miniconda

If the conda package manager is already installed, skip this step, otherwise:

**Linux**

- In a terminal console, install Miniconda, following instructions and accepting default options:
  ```bash
  curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  bash Miniconda3-latest-Linux-x86_64.sh
  ```

**MacOS**

- If your Mac has an Apple processor (M1/M2), first run the following command using Terminal:
  ```bash
  arch -x86_64 zsh
  ```
- Install Miniconda using Terminal, following instructions and accepting default options:
  ```bash
  curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh
  bash Miniconda3-latest-MacOSX-x86_64.sh
  ```



### Installing the GPAS CLI

- If your Mac has an Apple processor (M1/M2), first run the following command using Terminal:

  ```bash
  arch -x86_64 zsh
  ```

- Download [cli-main.zip](https://github.com/GlobalPathogenAnalysisService/cli/archive/refs/heads/main.zip), and move it into your terminal's current working directory.

- Complete the installation:
  ```bash
  unzip cli-main.zip
  conda create -n gpas -c conda-forge -c bioconda hostile
  conda activate gpas
  pip install ./cli-main
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

This generates a mapping CSV (e.g. `a5w2e8.mapping.csv`) linking your local sample names with their randomly generated remote identifiers (GUIDs). Keep this file safe as it's useful for linking results later.



#### Downloading output files (`gpas download`)

Download output files associated with a one or more sample GUIDs, or a batch defined by the mapping CSV generated during upload. When a mapping CSV is used, files are prefixed with the sample names provided at upload, otherwise files are prefixed with the sample GUID.

```bash
# Download the report for sample 3bf7d6f9-c883-4273-adc0-93bb96a499f6
gpas download 3bf7d6f9-c883-4273-adc0-93bb96a499f6

# Download the report for all samples in a5w2e8.mapping.csv
gpas download a5w2e8.mapping.csv

# Dowload the main and speciation reports for samples in a5w2e8.mapping.csv
gpas download a5w2e8.mapping.csv --filenames speciation_report.json,main_report.json

# Save downloaded files to a specific directory
gpas download a5w2e8.mapping.csv --out-dir results
```



#### Querying existing samples (`gpas query`)

*not yet implemented*

Fetch status, metadata, and output file information for one or more samples, or a batch thereof. Optionally restricted to include only status or output file information with respective flags `--status` and `--files`.

```bash
gpas query --samples 103,674  # Show info for samples 103 and 674
gpas query --batch 684  # Show info for each sample in batch 584
gpas query --batch abcde.mapping.csv  # As above, using local sample names
gpas query --batch abcde.mapping.csv --status  # Only show status info
gpas query --batch abcde.mapping.csv --files  # Only show output status
```





#### Reanalysing existing samples  (`gpas run`)

*not yet implemented*

Triggers reanalysis of one or many existing samples or a batch thereof.

```bash
gpas run --samples 103,674
gpas run --batch 684  # Not yet implemented
gpas run --batch abcde.mapping.csv
```



## Support

For technical support, please open an issue or contact `support@gpas.global`



## Development

**Development install**

```bash
conda create -n gpas -c conda-forge -c bioconda hostile
conda activate gpas
git clone https://github.com/GlobalPathogenAnalysisService/cli.git
cd cli
pip install --editable '.[dev]'
```

**Updating**

```bash
cd cli
git pull origin main
gpas --version
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
