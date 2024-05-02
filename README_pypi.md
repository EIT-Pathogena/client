# GPAS client

The command line interface for the GPAS mycobacterial platform. The client enables privacy-preserving sequence data submission and retrieval of analytical output files. Prior to upload, sample identifiers are anonymised and human host sequences are removed. A multicore machine with 16GB of RAM running Linux or MacOS is recommended.



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

A 4GB human genome index is downloaded the first time you run `gpas upload`. If for any reason this is interrupted, simply run the upload command again. Upload will not proceed until the index has been downloaded and passed an integrity check. You may optionally download the index ahead of time using the command `gpas download-index`.

To retain the decontaminated FASTQ files uploaded to GPAS, include the optional `--save` flag. To perform decontamination without uploading anything, use the optional `--dry-run` flag.



#### Downloading files (`gpas download`)

The download subcommand retrieves the output (and/or input) files associated with a batch of samples given a mapping CSV generated during upload, or one or more sample GUIDs. When a mapping CSV is used, by default downloaded file names are prefixed with the sample names provided at upload. Otherwise downloaded files are prefixed with the sample GUID.

```bash
# Download the main reports for all samples in a5w2e8.mapping.csv
gpas download a5w2e8.mapping.csv

# Download the main and speciation reports for all samples in a5w2e8.mapping.csv
gpas download a5w2e8.mapping.csv --filenames main_report.json,speciation_report.json

# Download the main report for one sample
gpas download 3bf7d6f9-c883-4273-adc0-93bb96a499f6

# Download the final assembly for one M. tuberculosis sample
gpas download 3bf7d6f9-c883-4273-adc0-93bb96a499f6 --filenames final.fasta

# Download the main report for two samples
gpas download 3bf7d6f9-c883-4273-adc0-93bb96a499f6,6f004868-096b-4587-9d50-b13e09d01882

# Save downloaded files to a specific directory
gpas download a5w2e8.mapping.csv --out-dir results

# Download only input fastqs
gpas download a5w2e8.mapping.csv --inputs --filenames ""
```

The complete list of `--filenames` available for download varies by sample, and can be found in the Downloads section of sample view pages in the GPAS web portal.


#### Generating Upload CSV (`gpas build-csv`)

If you have a folder containing all the reads you would like to upload, then `gpas build-csv` can be used to help generate the upload csv. See the GPAS User Guide for detailed descriptions of all the fields.
You'll need to fill in some of the required parameters.

```bash
gpas build-csv --output-csv upload.csv --batch-name test_batch --collection-date 2024-04-15 --country GBR --max-batch-size 25 my_folder
```

You can then go through the csv and manually mark samples as positive/negative controls, or give them sample names (by default they are named based on the filename).


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

The human genome index used for host decontamination is downloaded automatically when running `gpas upload` for the first time. You may trigger this manually ahead of upload with `gpas download-index`.



## Support

For technical support, please open an issue or contact `support@gpas.global`
