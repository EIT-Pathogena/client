**help**

This command generates a CSV from a given directory of fastq sample files. An [example](https://github.com/EIT-Pathogena/client/tree/__version__/docs/assets) of such a CSV file is given in the assets directory. A CSV file in this format is required to run the [gpas upload](#gpas-upload) command.

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
