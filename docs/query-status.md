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
