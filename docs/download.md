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
