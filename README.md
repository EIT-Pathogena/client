# gpas-client

The command line interface and Python API for the Global Pathogen Analysis Service. Enables secure sample upload, progress monitoring, and retrieval of analytical outputs.



## Install

**Development install**

Miniconda is recommended ([Miniconda installation guide](https://conda.io/projects/conda/en/latest/user-guide/install/index.html)).

```bash
conda create -n gpas -c conda-forge -c bioconda hostile  # Mamba is faster
conda activate gpas
git clone https://github.com/GlobalPathogenAnalysisService/cli.git
cd cli
pip install --editable '.[dev]'

# Updating
cd cli
git pull origin main
gpas --version
```

**Macs with Apple Silicon (M1, M2) processors**

The easiest way to install on an M1 or M2 Mac is to use Rosetta, otherwise all the components have to be compiled for the ARM architecture. To do this open a Finder window and naviagate to `Applications | Utilities`, then right-click on `Terminal` and choose `Get Info`. In the portrait window that appears there is a checkbox in the `General` section entitled `Open using Rosetta`. Make sure this is ticked and close the window. If `Terminal` was open, close it and open it again. Now you can follow the above instructions i.e. install Miniconda etc. 

## Usage

#### Authentication (`gpas auth`) ✅

The first time you use the CLI, you will need to generate a token by running `gpas auth` and entering your username and password. Your token will be saved inside  `~/.config/gpas/tokens/` and used automatically  for subsequent commands.

```
gpas auth
Enter your username: bede.constantinides@ndm.ox.ac.uk
Enter your password: ***************
```



#### Uploading samples (`gpas upload`) ✅
Used to submit samples for analysis. Performs metadata validation and client-side removal of human reads before uploading sequences to the GPAS cloud platform.

```bash
gpas upload tests/data/illumina.csv
gpas upload --resume tests/data/illumina.csv  # Not yet implemented
```



#### Querying existing samples (`gpas query`) 🚧

Used to fetch status, metadata, and output file information for one or many samples, or a batch thereof. Optionally restricted to include only status or output file information with respective flags `--status` and `--files`.

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



## Using custom hosts

```bash
export GPAS_HOST="localhost:1234"

unset GPAS_HOST  # To undo
```



## Support

For technical support, please open an issue or contact `support@gpas.global`
