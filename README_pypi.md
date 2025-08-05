# GPAS Client

The command line interface for the GPAS platform.

The client enables privacy-preserving sequence data submission and retrieval of analytical output files. Prior to
upload, sample identifiers are anonymised and human host sequences are removed. A computer with Linux or MacOS is
required to use the client. When running human read removal prior to upload a computer with a modern multi-core
processor and at least 16GB of RAM is recommended.

## Install

There are two recommended methods for installing the GPAS Client, either by using the popular package and
environment manager Conda or by using our publicly available Docker container which we build at release time.

### Installing Miniconda

If a Conda package manager is already installed, skip to [Installing the client](#installing-or-updating-the-client-with-miniconda),
otherwise the following instructions have been taken from the [Miniconda install process documentation](https://docs.anaconda.com/miniconda/miniconda-install/)

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

<a id="installing-or-updating-the-client-with-miniconda"></a>

The client has at least one dependency that requires `bioconda`, which itself
depends on `conda-forge`. Note that for the `conda create` step (see below), installation can be very slow,
so please leave it running. For more verbose output, you can add the `-v` or `-vv` flags, though
it is not recommended to show the full debug output with `-vvv` as this has been seen to lead to OOM errors.

#### Linux

```bash
conda create -y -n gpas -c conda-forge -c bioconda hostile==1.1.0
conda activate gpas
pip install --upgrade gpas
```

#### MacOS

Please note the additional argument `--platform osx-64` in this command, compared to the above.

```bash
conda create --platform osx-64 -y -n gpas -c conda-forge -c bioconda hostile==1.1.0
conda activate gpas
pip install --upgrade gpas
```

A simple test to verify installation would be to run a version check:

```bash
gpas --version
```
**help**

Most actions with the GPAS CLI require that the user have first authenticated with the GPAS server
with their login credentials. Upon successfully authentication, a bearer token is stored in the user's home directory
and will be used on subsequent CLI usage.

The token is valid for 7 days and a new token can be retrieved at anytime.

### Usage

Running `gpas auth` will ask for your username and password for GPAS, your password will not be shown
in the terminal session.

```bash
$ gpas auth

14:04:31 INFO: GPAS client version 2.0.0rc1
14:04:31 INFO: Authenticating with portal.eit-pathogena.com
Enter your username: gpas-user@eit.org
Enter your password:
14:04:50 INFO: Authenticated (/Users/<user>/.config/gpas/tokens/portal.eit-pathogena.com.json)
```

#### Troubleshooting Authentication

##### How do I get an account for GPAS?

Creating a Personal Account:

Navigate to GPAS and click on “Sign Up”. Follow the instructions to create a user account.

Shortly after filling out the form you'll receive a verification email. Click the link in the email to verify your
account and email address. If you don’t receive the email, please contact gpas.support@eit.org.

You are now ready to start using GPAS.

##### What happens when my token expires?

If you haven't already retrieved a token, you will receive the following error message.

```bash No token file
$ gpas upload tests/data/illumina-2.csv

12:46:42 INFO: GPAS client version 2.0.0rc1
12:46:43 INFO: Getting credit balance for portal.eit-pathogena.com
12:46:43 ERROR: FileNotFoundError: Token not found at /Users/<user>/.config/gpas/tokens/portal.eit-pathogena.com.json, have you authenticated?
```

If your token is invalid or expired, you will receive the following message

```text Invalid token
14:03:26 INFO: GPAS client version 2.0.0rc1
14:03:26 ERROR: AuthorizationError: Authorization checks failed! Please re-authenticate with `gpas auth` and
try again.
```

##### How can I check my token expiry before long running processes?

You can check the expiry of your token with the following command:

```bash
$ gpas auth --check-expiry
14:05:52 INFO: GPAS client version 2.0.0rc1
14:05:52 INFO: Current token for portal.eit-pathogena.com expires at 2024-08-13 14:04:50.672085
```

**help**

Credits are required to upload samples and initiate the analysis process. Users can check their credit balance in the
header of the GPAS Portal or by using the `gpas balance` command when logged in.

### Usage

```bash balance usage
gpas balance
15:56:56 INFO: GPAS client version 2.0.0
15:56:56 INFO: Getting credit balance for portal.eit-pathogena.com
15:56:57 INFO: Your remaining account balance is 1000 credits
```

**help**

> Where samples may contain human reads we strongly recommend using the provided decontamination functionality. This is
> best practice to minimise the risk of personally identifiable information being uploaded to the cloud.

The upload command performs metadata validation and client-side removal of human reads for each of your samples,
before uploading sequences to GPAS for analysis.

To generate a CSV file to use with this command see the [build-csv](#gpas-build-csv) documentation.

### Credits

Credits are required to upload samples and initiate the analysis process. Users can check their credit balance in the
header of the GPAS Portal or by using the `gpas balance` command. More information can be found in the
`gpas balance` section.

Each sample for Mycobacterium genomic sequencing will require 10 credits whereas SARS-CoV-2 sample sequencing will require 1 credits.
During the upload command process, a balance check is performed to ensure the user has enough credits for the number of samples in the batch.
Credits are then deducted when sample files are successfully uploaded and ready for processing.

### Human Read Removal

A 4GB human genome index is downloaded the first time you run `gpas upload`. If for any reason this is interrupted,
run the upload command again. Upload will not proceed until the index has been downloaded and passed an integrity
check. You may optionally download the index ahead of time using the command `gpas download-index`.

By default, the upload command will first run `gpas decontaminate` to attempt to remove human reads prior to
uploading the input samples to GPAS, this option can be overridden but only do so if you're aware of the risks
stated above.

To retain the decontaminated FASTQ files uploaded to GPAS, include the optional `--save` flag. To perform
decontamination without uploading anything, use the `gpas decontaminate` command.

During upload, a mapping CSV is created (e.g. `a5w2e8.mapping.csv`) linking your local sample names with their randomly
generated remote names. Keep this file safe, as it is useful for downloading and relinking results later, it cannot be
recreated after this step without re-uploading the same samples again.

### Usage

```bash Upload with running human read removal
gpas upload my-first-batch.csv
15:41:57 INFO: GPAS client version 2.0.0
15:41:57 INFO: Getting credit balance for portal.eit-pathogena.com
15:41:59 INFO: Your remaining account balance is 1000 credits
15:41:59 INFO: Performing FastQ checks and gathering total reads
15:41:59 INFO: Calculating read count in: /Users/<user>/samples/ERR4809187_1.fastq.gz
15:42:00 INFO: Calculating read count in: /Users/<user>/samples/ERR4809187_2.fastq.gz
15:42:02 INFO: 3958206.0 reads in FASTQ file
15:42:02 INFO: Removing human reads from ILLUMINA FastQ files and storing in /Users/<user>/code/gpas/client
15:42:02 INFO: Hostile version 1.1.0. Mode: paired short read (Bowtie2)
15:42:02 INFO: Found cached standard index human-t2t-hla-argos985-mycob140
15:42:02 INFO: Cleaning...
15:43:39 INFO: Cleaning complete
15:43:39 INFO: The mapping file gx5y5p.mapping.csv has been created.
15:43:39 INFO: You can monitor the progress of your batch in GPAS here: "..."
15:43:39 INFO: Uploading my-first-sample
15:45:27 INFO:   Uploaded 66433ffc-3c10-4576-8502-56b4805c7ecc_1.fastq.gz
15:45:27 INFO: Uploading my-first-sample
15:49:20 INFO:   Uploaded 66433ffc-3c10-4576-8502-56b4805c7ecc_2.fastq.gz
15:49:21 INFO: Upload complete. Created gx5y5p.mapping.csv (keep this safe)
15:49:21 INFO: Getting credit balance for portal.eit-pathogena.com
15:49:23 INFO: Your remaining account balance is 990 credits
```

```bash Upload without human read removal
gpas upload --skip-decontamination my-first-batch.csv
15:41:57 INFO: GPAS client version 2.0.0
15:41:57 INFO: Getting credit balance for portal.eit-pathogena.com
15:41:59 INFO: Your remaining account balance is 1000 credits
15:41:59 INFO: Performing FastQ checks and gathering total reads
15:41:59 INFO: Calculating read count in: /Users/<user>/samples/ERR4809187_1.fastq.gz
15:42:00 INFO: Calculating read count in: /Users/<user>/samples/ERR4809187_2.fastq.gz
15:42:02 INFO: 3958206.0 reads in FASTQ file
15:42:02 INFO: Removing human reads from ILLUMINA FastQ files and storing in /Users/<user>/code/gpas/client
15:43:39 INFO: The mapping file gx5y5p.mapping.csv has been created.
15:43:39 INFO: You can monitor the progress of your batch in GPAS here: "..."
15:43:39 INFO: Uploading my-first-sample
15:45:27 INFO:   Uploaded 66433ffc-3c10-4576-8502-56b4805c7ecc_1.fastq.gz
15:45:27 INFO: Uploading my-first-sample
15:49:20 INFO:   Uploaded 66433ffc-3c10-4576-8502-56b4805c7ecc_2.fastq.gz
15:49:21 INFO: Upload complete. Created gx5y5p.mapping.csv (keep this safe)
15:49:21 INFO: Getting credit balance for portal.eit-pathogena.com
15:49:23 INFO: Your remaining account balance is 990 credits
```

**help**

This command generates a CSV from a given directory of fastq sample files. An [example](https://github.com/EIT-Pathogena/client/tree/2.2.2rc1/docs/assets) of such a CSV file is given in the assets directory. A CSV file in this format is required to run the [gpas upload](#gpas-upload) command.

Note: the CSV file must be located in the same directory as the sample.fastq files to be used with the upload command.

### Usage

```sh
gpas build-csv ~/Downloads/samples --batch-name <batch-name> --country <three-letter-country-code>
```

for ex:

```sh
gpas build-csv ~/Downloads/samples --batch-name mybatch123 --country GBR
```

This will generate a CSV file in the samples folder named upload.csv, prompting users to manually fill in optional fields later (like instrument-platform, amplicon-scheme, etc.). Alternatively, these optional parameters can be passed directly via the CLI rather than filling them in manually later; the example below shows how to include some of these, but for the full list of available options, refer to `gpas build-csv --help`.

for ex:

```sh
gpas build-csv ~/Downloads/samples \
  --batch-name mybatch123 \
  --country GBR \
  --instrument-platform illumina \
  --specimen-organism sars-cov-2 \
  --amplicon-scheme "Automatic Detection"
```

**help**

This command will attempt to remove human reads from a given input CSV file, in the same structure as the input CSV that
would be used for uploading to GPAS, an [example can be found here](https://github.com/EIT-Pathogena/client/tree/2.2.2rc1/docs/assets).

By default, the processed files will be output in the same directory that the command is run in, but you can choose a
different directory with the `--output-dir` argument.

### Usage

```bash
$ gpas decontaminate tests/data/illumina.csv
15:24:39 INFO: GPAS client version 2.0.0rc1
15:24:39 INFO: Performing FastQ checks and gathering total reads
15:24:39 INFO: Calculating read count in: /Users/<user>/code/gpas/client/tests/data/reads/tuberculosis_1_1.fastq
15:24:39 INFO: Calculating read count in: /Users/<user>/code/gpas/client/tests/data/reads/tuberculosis_1_2.fastq
15:24:39 INFO: 2.0 reads in FASTQ file
15:24:39 INFO: Removing human reads from ILLUMINA FastQ files and storing in /Users/<user>/code/gpas/client
15:24:39 INFO: Hostile version 1.1.0. Mode: paired short read (Bowtie2)
15:24:39 INFO: Found cached standard index human-t2t-hla-argos985-mycob140
15:24:39 INFO: Cleaning...
15:24:39 INFO: Cleaning complete
15:24:39 INFO: Human reads removed from input samples and can be found here: /Users/<user>/code/gpas/client
```

**help**

The download command retrieves the output (and/or input) files associated with a batch of samples given a mapping CSV
generated during upload, or one or more sample GUIDs. When a mapping CSV is used, by default downloaded file names are
prefixed with the sample names provided at upload. Otherwise, downloaded files are prefixed with the sample GUID.

### Usage

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
gpas download a5w2e8.mapping.csv --output-dir results

# Download only input fastqs
gpas download a5w2e8.mapping.csv --inputs --filenames ""
```

The complete list of `--filenames` available for download varies by sample, and can be found in the Downloads section of
sample view pages in GPAS.

## `gpas validate`
<a id="gpas-validate"></a>

```text
Usage: gpas validate [OPTIONS] UPLOAD_CSV

  Validate a given upload CSV.

Options:
  --host TEXT  API hostname (for development)
  -h, --help   Show this message and exit.
```

The `validate` command will check that a Batch can be created from a given CSV and if your user account has permission
to upload the samples, the individual FastQ files are then checked for validity. These checks are already performed
by default with the `upload` command but using this can ensure validity without commiting to the subsequent upload
if you're looking to check a CSV during writing it.

**help**

The `query-raw` command fetches either the raw metadata of one more samples given a mapping CSV
generated during upload, or one or more sample GUIDs.

### Usage

```bash
# Query all available metadata in JSON format
gpas query-raw a5w2e8.mapping.csv
```

**help**

The `query-status` command fetches the current processing status of one or more samples in a mapping CSV
generated during upload, or one or more sample GUIDs.

### Usage

```bash
# Query the processing status of all samples in a5w2e8.mapping.csv
gpas query-status a5w2e8.mapping.csv

# Query the processing status of a single sample
gpas query-status 3bf7d6f9-c883-4273-adc0-93bb96a499f6
```

**help**

This command will output the steps required to enable auto-completion in either a Bash or ZSH shell, follow the output
to enable autocompletion, this will need to be executed on every new shell session, instructions are provided on how to
make this permanent depending on your environment. More information and instructions for other shells can be found in
the [Click documentation](https://click.palletsprojects.com/en/8.1.x/shell-completion/).

### Usage

```bash
$ gpas autocomplete
Run this command to enable autocompletion:
    eval "$(_GPAS_COMPLETE=bash_source gpas)"
Add this to your ~/.bashrc file to enable this permanently:
    command -v gpas > /dev/null 2>&1 && eval "$(_GPAS_COMPLETE=bash_source gpas)"
```

Tab completion can optionally be enabled by adding the lines output by the command to your shell source files.
This will enable the ability to press tab after writing `gpas ` to list possible sub-commands. It can also be used
for sub-command options, if `--` is entered prior to pressing tab.

## Support

For technical support, please open an issue or contact gpas.support@eit.org
