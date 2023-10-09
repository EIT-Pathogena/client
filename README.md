# gpas-client

The command line interface and Python API for the Global Pathogen Analysis Service. Enables secure sample upload with client-side human read removal, progress monitoring, and retrieval of analytical outputs.



## Install

### Installing Miniconda

If the conda package manager is already installed, skip this step, otherwise:

**Linux**

- In a terminal console, install Miniconda, following instructions and accepting default options:
  ```bash
  curl -L https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh | bash
  ```

**MacOS**

- If your Mac has an Apple processor (M1/M2), first run the following command using Terminal:
  ```bash
  arch -x86_64 zsh
  ```
- Install Miniconda using Terminal, following instructions and accepting default options:
  ```bash
  curl -L https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh | bash
  ```



### Installing the GPAS CLI

If your Mac has an Apple processor (M1/M2), first run the following command using Terminal:
```bash
arch -x86_64 zsh
```

Then proceed with installing the GPAS CLI:


```bash
conda create -n gpas -c conda-forge -c bioconda hostile
conda activate gpas
curl -O https://github.com/GlobalPathogenAnalysisService/cli/archive/refs/heads/main.zip
unzip cli-main.zip
pip install cli-main
```



## Usage

Ensure the conda environment is active by running `conda activate gpas`. If using a Mac with an Apple processor, be sure to run `arch -x86_64 zsh` after opening a new Terminal window.

#### Authentication (`gpas auth`)

The first time you use the CLI, you will need to authenticate by running `gpas auth` and entering your username and password. This token will be used automatically for subsequent commands.

```
gpas auth
Enter your username: bede.constantinides@ndm.ox.ac.uk
Enter your password: ***************
```



#### Uploading samples (`gpas upload`)

Performs metadata validation and client-side removal of human reads before uploading sequences to the GPAS platform.

```bash
gpas upload tests/data/illumina.csv
```



#### Querying existing samples (`gpas query`) 🚧

Fetch status, metadata, and output file information for one or more samples, or a batch thereof. Optionally restricted to include only status or output file information with respective flags `--status` and `--files`.

```bash
gpas query --samples 103,674  # Show info for samples 103 and 674
gpas query --batch 684  # Show info for each sample in batch 584
gpas query --batch abcde.mapping.csv  # As above, using local sample names
gpas query --batch abcde.mapping.csv --status  # Only show status info
gpas query --batch abcde.mapping.csv --files  # Only show output status
```



#### Downloading output files (`gpas download`) 🚧

Used to download output files associated with a one or many samples, or a batch thereof.

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



#### Reanalysing existing samples  (`gpas run`) ✅

Triggers reanalysis of one or many existing samples or a batch thereof.

```bash
gpas run --samples 103,674
gpas run --batch 684  # Not yet implemented
gpas run --batch abcde.mapping.csv
```



## Creating a Rosetta Terminal on MacOS

1. Using Finder, locate the Terminal application within the Utilities folder (Finder → `Go` → `Utilities`)
2. Right-click on the Terminal icon, and choose `Duplicate`
3. Right-click on the duplicated Terminal icon, choose `Rename`, and rename it to e.g. 'Rosetta Terminal'
4. Right-click on the 'Rosetta Terminal' icon and choose `Get Info` (or hit Command+i)
5. Check the box for `Open using Rosetta`, and close the `Get Info` window
6. Open the `Rosetta Terminal` application, type `uname -m`, and press Enter, which should print `x86_64`



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

```
cd cli
git pull origin main
gpas --version
```



### Custom API hostnames

```bash
export GPAS_HOST="localhost:1234"

unset GPAS_HOST  # To undo
```
