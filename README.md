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

Performs metadata validation and client-side removal of human reads before uploading sequences to the GPAS platform. Generates a 'mapping CSV' for the uploaded batch of samples in the current working directory, linking local and remote sample names while preserving privacy.

```bash
gpas upload tests/data/illumina.csv
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



#### Downloading output files (`gpas download`)

*not yet implemented*

Download output files associated with a one or more sample guids, or a batch defined by a mapping CSV generate during upload.

```bash
# Download final.fasta for samples 103 and 674
gpas download --samples 103,674 --filenames final.fasta
# Download final.fasta and fastp_report.json for samples in batch 684
gpas download --batch 684 --filenames final.fasta,fastp_report.json
# As above, using local sample identifiers
gpas download --batch abcde.mapping.csv --filenames final.fasta,fastp_report.json
# Download all files
gpas download --batch abcde.mapping.csv --all
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
