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
