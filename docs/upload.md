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
