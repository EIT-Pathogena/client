__help__

This command generates a CSV from a given directory of fastq sample files. An [example](https://eit-oxford.atlassian.net/wiki/spaces/EPP/pages/220594178/GPAS+User+guide#GPAS-Client-Command-Line-Interface-(CLI)) of such a CSV file is given in the assets directory. A CSV file in this format is required to run the [pathogena upload](#pathogena-upload) command.


Note: the CSV file must be located in the same directory as the sample.fastq files to be used with the upload command.

### Usage

```sh
pathogena build-csv ~/Downloads/samples --batch-name <batch-name> --country <three-letter-country-code>
```

for ex:

```sh
pathogena build-csv ~/Downloads/samples --batch-name mybatch123 --country GBR
```


This will generate a CSV file in the samples folder named upload.csv, prompting users to manually fill in optional fields later (like instrument-platform, amplicon-scheme, etc.). Alternatively, these optional parameters can be passed directly via the CLI rather than filling them in manually later; the example below shows how to include some of these.

For a complete list of available options and their input formats — whether used with the build-csv command or included in a CSV input file — see pathogena build-csv --help.

for ex:

```sh
pathogena build-csv ~/Downloads/samples \
  --batch-name mybatch123 \
  --country GBR \
  --instrument-platform illumina \
  --specimen-organism sars-cov-2 \
  --amplicon-scheme "Automatic Detection"
```
