__help__

This command will attempt to remove human reads from a given input CSV file, in the same structure as the input CSV that
would be used for uploading to EIT Pathogena, an [example can be found here](https://github.com/EIT-Pathogena/client/tree/__version__/docs/assets).

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
