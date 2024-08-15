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
