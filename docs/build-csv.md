## `pathogena build-csv`

```text
Usage: pathogena build-csv [OPTIONS] SAMPLES_FOLDER

  Command to create upload csv from SAMPLES_FOLDER containing sample fastqs.

  Use max_batch_size to split into multiple separate upload csvs.

  Adjust the read_suffix parameters to match the file endings for your read
  files.

Options:
  --output-csv FILE               Path to output CSV file  [required]
  --batch-name TEXT               Batch name  [required]
  --collection-date [%Y-%m-%d]    Collection date (YYYY-MM-DD)  [default:
                                  2024-10-24; required]
  --country TEXT                  3-letter Country Code  [required]
  --instrument-platform [illumina|ont]
                                  Sequencing technology
  --subdivision TEXT              Subdivision
  --district TEXT                 District
  --ont_read_suffix TEXT          Read file ending for ONT fastq files
                                  [default: .fastq.gz]
  --illumina_read1_suffix TEXT    Read file ending for Illumina read 1 files
                                  [default: _1.fastq.gz]
  --illumina_read2_suffix TEXT    Read file ending for Illumina read 2 files
                                  [default: _2.fastq.gz]
  --max-batch-size INTEGER        [default: 50]
  -h, --help                      Show this message and exit.
```

This command generates a CSV from a given directory of fastq sample files. An [example](./assets/example-input.csv) of such a CSV file is given in the assets directory. A CSV file in this format is required to run the [pathogena upload](./upload.md) command.


Note: the CSV file must be located in the same directory as the sample.fastq files to be used with the upload command.  