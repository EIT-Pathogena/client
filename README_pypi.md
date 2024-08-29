# EIT Pathogena Client

The command line interface for the EIT Pathogena platform.

The client enables privacy-preserving sequence data submission and retrieval of analytical output files. Prior to
upload, sample identifiers are anonymised and human host sequences are removed. A multicore machine with 16GB of RAM
running Linux or MacOS is recommended.


## Install

There are two recommended methods for installing the Pathogena Client, either by using the popular package and
environment manager Conda or by using our publicly available Docker container which we build at release time.

### Installing Miniconda

If a Conda package manager is already installed, skip to [Installing the client]
(##installing-or-updating-the-client-with-miniconda),
otherwise the following instructions have been taken from the [Miniconda install process documentation]
(https://docs.anaconda.com/miniconda/miniconda-install/)

#### Installing Miniconda on Linux

In a terminal console, install Miniconda with the following instructions and accepting default options:

    ```bash
    mkdir -p ~/miniconda3
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
    bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
    rm -rf ~/miniconda3/miniconda.sh
    ```

#### Installing Miniconda on MacOS

The client requires the Conda platform to be using `x86_64` when creating the environment.

- If your Mac has an Apple processor, using Terminal, firstly run:
    ```bash
    mkdir -p ~/miniconda3
    curl https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh -o ~/miniconda3/miniconda.sh
    bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
    rm -rf ~/miniconda3/miniconda.sh
    ```

- Initialise Miniconda using either of the following commands depending on your Shell (Bash|ZSH)
    ```bash
    ~/miniconda3/bin/conda init bash
    ~/miniconda3/bin/conda init zsh
    ```

### Installing or updating the client with Miniconda

#### Linux

```bash
conda create -y -n pathogena -c conda-forge -c bioconda hostile==1.1.0
conda activate pathogena
pip install --upgrade pathogena
```
  
#### MacOS

Please note the additional argument `--platform osx-64` in this command, compared to the above.

```bash
conda create --platform osx-64 -y -n pathogena -c conda-forge -c bioconda hostile==1.1.0
conda activate pathogena
pip install --upgrade pathogena
```

A simple test to verify installation would be to run a version check:

```bash
pathogena --version
```
## `pathogena auth`

```text
Usage: pathogena auth [OPTIONS]

  Authenticate with EIT Pathogena.

Options:
  --host                          API hostname (for development)
  --check-expiry                   Check for a current token and print the
                                  expiry if exists
  -h, --help                      Show this message and exit.
```

Most actions with the EIT Pathogena CLI require that the user have first authenticated with the EIT Pathogena server
with their login credentials. Upon successfully authentication, a bearer token is stored in the user's home directory
and will be used on subsequent CLI usage.

The token is valid for 7 days and a new token can be retrieved at anytime.

### Usage

Running `pathogena auth` will ask for your username and password for EIT Pathogena, your password will not be shown
in the terminal session.

```bash
$ pathogena auth

14:04:31 INFO: EIT Pathogena client version 2.0.0rc1
14:04:31 INFO: Authenticating with portal.eit-pathogena.com
Enter your username: pathogena-user@eit.org
Enter your password:
14:04:50 INFO: Authenticated (/Users/jdhillon/.config/pathogena/tokens/portal.eit-pathogena.com.json)
```

#### Troubleshooting Authentication

##### How do I get an account for EIT Pathogena?

Creating a Personal Account:

Navigate to EIT Pathogena and click on “Sign Up”. Follow the instructions to create a user account.

Shortly after filling out the form you'll receive a verification email. Click the link in the email to verify your 
account and email address. If you don’t receive the email, please contact pathogena.support@eit.org.

You are now ready to start using EIT Pathogena.

##### What happens when my token expires?

If you haven't already retrieved a token, you will receive the following error message. 

```bash No token file
$ pathogena upload tests/data/illumina-2.csv

12:46:42 INFO: EIT Pathogena client version 2.0.0rc1
12:46:43 INFO: Getting credit balance for portal.eit-pathogena.com
12:46:43 ERROR: FileNotFoundError: Token not found at /Users/jdhillon/.config/pathogena/tokens/portal.eit-pathogena.com.json, have you authenticated?
```

If your token is invalid or expired, you will receive the following message

```text Invalid token
14:03:26 INFO: EIT Pathogena client version 2.0.0rc1
14:03:26 ERROR: AuthorizationError: Authorization checks failed! Please re-authenticate with `pathogena auth` and 
try again.
```

##### How can I check my token expiry before long running processes?

You can check the expiry of your token with the following command:

```bash
$ pathogena auth --check-expiry
14:05:52 INFO: EIT Pathogena client version 2.0.0rc1
14:05:52 INFO: Current token for portal.eit-pathogena.com expires at 2024-08-13 14:04:50.672085
```
## `pathogena upload`

```text
Usage: pathogena upload [OPTIONS] UPLOAD_CSV

  Validate, decontaminate and upload reads to EIT Pathogena. Creates a mapping
  CSV file which can be used to download output files with original sample
  names.

Options:
  --threads INTEGER               Number of alignment threads used during decontamination
  --save                          Retain decontaminated reads after upload completion
  --host                           API hostname (for development)
  --skip-fastq-check              Skip checking FASTQ files for validity
  --skip-decontamination          Run decontamination prior to upload
  --output-dir DIRECTORY          Output directory for the cleaned FastQ files,
                                  defaults to the current working directory.
  -h, --help                      Show this message and exit.
```

> Where samples may contain human reads we strongly recommend using the provided decontamination functionality. This is
best practice to minimise the risk of personally identifiable information being uploaded to the cloud.

The upload command performs metadata validation and client-side removal of human reads for each of your samples, 
before uploading sequences to EIT Pathogena for analysis.

A 4GB human genome index is downloaded the first time you run `pathogena upload`. If for any reason this is interrupted,
run the upload command again. Upload will not proceed until the index has been downloaded and passed an integrity
check. You may optionally download the index ahead of time using the command `pathogena download-index`.

By default, the upload command will first run `pathogena decontaminate` to attempt to remove human reads prior to
uploading the input samples to EIT Pathogena, this option can be overridden but only do so if you're aware of the risks
stated above. 

To retain the decontaminated FASTQ files uploaded to EIT Pathogena, include the optional `--save` flag. To perform 
decontamination without uploading anything, use the `pathogena decontaminate` command.

During upload, a mapping CSV is created (e.g. `a5w2e8.mapping.csv`) linking your local sample names with their randomly
generated remote names. Keep this file safe, as it is useful for downloading and relinking results later, it cannot be
recreated after this step without re-uploading the same samples again.
## `pathogena decontaminate`

```text
Usage: pathogena decontaminate [OPTIONS] INPUT_CSV

  Decontaminate reads from a CSV file.

Options:
  --output-dir DIRECTORY  Output directory for the cleaned FastQ files,
                          defaults to the current working directory.
  --threads INTEGER       Number of alignment threads used during
                          decontamination
  --skip-fastq-check      Skip checking FASTQ files for validity
  -h, --help              Show this message and exit.
 ```

This command will attempt to remove human reads from a given input CSV file, in the same structure as the input CSV that
would be used for uploading to EIT Pathogena, an [example can be found here](assets/example-input.csv).

By default, the processed files will be output in the same directory that the command is run in, but you can choose a
different directory with the `--output-dir` argument.

### Usage

```bash
$ pathogena decontaminate tests/data/illumina.csv
15:24:39 INFO: EIT Pathogena client version 2.0.0rc1
15:24:39 INFO: Performing FastQ checks and gathering total reads
15:24:39 INFO: Calculating read count in: /Users/jdhillon/code/pathogena/client/tests/data/reads/tuberculosis_1_1.fastq
15:24:39 INFO: Calculating read count in: /Users/jdhillon/code/pathogena/client/tests/data/reads/tuberculosis_1_2.fastq
15:24:39 INFO: 2.0 reads in FASTQ file
15:24:39 INFO: Removing human reads from ILLUMINA FastQ files and storing in /Users/jdhillon/code/pathogena/client
15:24:39 INFO: Hostile version 1.1.0. Mode: paired short read (Bowtie2)
15:24:39 INFO: Found cached standard index human-t2t-hla-argos985-mycob140
15:24:39 INFO: Cleaning...
15:24:39 INFO: Cleaning complete
15:24:39 INFO: Human reads removed from input samples and can be found here: /Users/jdhillon/code/pathogena/client
```
## `pathogena download`

```text
$ pathogena download -h
16:07:34 INFO: EIT Pathogena client version 2.0.0rc1
Usage: pathogena download [OPTIONS] SAMPLES

  Download input and output files associated with sample IDs or a mapping CSV
  file created during upload.

Options:
  --filenames TEXT        Comma-separated list of output filenames to download
  --inputs                Also download decontaminated input FASTQ file(s)
  --output-dir DIRECTORY  Output directory for the downloaded files.
  --rename / --no-rename  Rename downloaded files using sample names when
                          given a mapping CSV
  --host TEXT             API hostname (for development)
  -h, --help              Show this message and exit.
```

The download command retrieves the output (and/or input) files associated with a batch of samples given a mapping CSV
generated during upload, or one or more sample GUIDs. When a mapping CSV is used, by default downloaded file names are
prefixed with the sample names provided at upload. Otherwise, downloaded files are prefixed with the sample GUID.

### Usage

```bash
# Download the main reports for all samples in a5w2e8.mapping.csv
pathogena download a5w2e8.mapping.csv

# Download the main and speciation reports for all samples in a5w2e8.mapping.csv
pathogena download a5w2e8.mapping.csv --filenames main_report.json,speciation_report.json

# Download the main report for one sample
pathogena download 3bf7d6f9-c883-4273-adc0-93bb96a499f6

# Download the final assembly for one M. tuberculosis sample
pathogena download 3bf7d6f9-c883-4273-adc0-93bb96a499f6 --filenames final.fasta

# Download the main report for two samples
pathogena download 3bf7d6f9-c883-4273-adc0-93bb96a499f6,6f004868-096b-4587-9d50-b13e09d01882

# Save downloaded files to a specific directory
pathogena download a5w2e8.mapping.csv --output-dir results

# Download only input fastqs
pathogena download a5w2e8.mapping.csv --inputs --filenames ""
```

The complete list of `--filenames` available for download varies by sample, and can be found in the Downloads section of
sample view pages in EIT Pathogena.
## `pathogena validate`

```text
$ pathogena validate -h
16:00:13 INFO: EIT Pathogena client version 2.0.0rc1
Usage: pathogena validate [OPTIONS] UPLOAD_CSV

  Validate a given upload CSV.

Options:
  --host TEXT  API hostname (for development)
  -h, --help   Show this message and exit.
```

The `validate` command will check that a Batch can be created from a given CSV and if your user account has permission 
to upload the samples, the individual FastQ files are then checked for validity. These checks are already performed 
by default with the `upload` command but using this can ensure validity without commiting to the subsequent upload
if you're looking to check a CSV during writing it.
## `pathogena query-raw`

```text
pathogena query-raw -h
15:36:39 INFO: EIT Pathogena client version 2.0.0rc1
Usage: pathogena query-raw [OPTIONS] SAMPLES

  Fetch metadata for one or more SAMPLES in JSON format.
  SAMPLES should be command separated list of GUIDs or path to mapping CSV.

Options:
  --host TEXT  API hostname (for development)
  -h, --help   Show this message and exit.
```

The `query-raw` command fetches either the raw metadata of one more samples given a mapping CSV 
generated during upload, or one or more sample GUIDs.

### Usage

```bash
# Query all available metadata in JSON format
pathogena query-raw a5w2e8.mapping.csv
```
## `pathogena query-status`

```text
pathogena query-status -h
15:36:39 INFO: EIT Pathogena client version 2.0.0rc1
Usage: pathogena query-status [OPTIONS] SAMPLES

  Fetch processing status for one or more SAMPLES in JSON format.
  SAMPLES should be command separated list of GUIDs or path to mapping CSV.

Options:
  --host TEXT  API hostname (for development)
  -h, --help   Show this message and exit.
```

The `query-status` command fetches the current processing status of one or more samples in a mapping CSV 
generated during upload, or one or more sample GUIDs.

### Usage

```bash
# Query the processing status of all samples in a5w2e8.mapping.csv
pathogena query-status a5w2e8.mapping.csv

# Query the processing status of a single sample
pathogena query-status 3bf7d6f9-c883-4273-adc0-93bb96a499f6
```
## `pathogena autocomplete`

This command will output the steps required to enable auto-completion in either a Bash or ZSH shell, follow the output 
to enable autocompletion, this will need to be executed on every new shell session, instructions are provided on how to
make this permanent depending on your environment. More information and instructions for other shells can be found in 
the [Click documentation](https://click.palletsprojects.com/en/8.1.x/shell-completion/).

### Usage

```bash
$ pathogena autocomplete
Run this command to enable autocompletion:
    eval "$(_PATHOGENA_COMPLETE=bash_source pathogena)"
Add this to your ~/.bashrc file to enable this permanently:
    command -v pathogena > /dev/null 2>&1 && eval "$(_PATHOGENA_COMPLETE=bash_source pathogena)"
```

Tab completion can optionally be enabled by adding the lines output by the command to your shell source files. 
This will enable the ability to press tab after writing `pathogena ` to list possible sub-commands. It can also be used
for sub-command options, if `--` is entered prior to pressing tab.

## Support

For technical support, please open an issue or contact pathogena.support@eit.org
