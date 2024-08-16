## `pathogena query-raw`

```text
pathogena query-raw -h
15:36:39 INFO: EIT Pathogena client version 2.0.0rc1
Usage: pathogena query-raw [OPTIONS] SAMPLES

  Fetch metadata for one or more SAMPLES in JSON format.
  SAMPLES should be command separated list of GUIDs or path to mapping CSV.

Options:
  --host TEXT  API hostname (for development)
  -h, --help   Show this message and exit.
```

The `query-raw` command fetches either the raw metadata of one more samples given a mapping CSV 
generated during upload, or one or more sample GUIDs.

### Usage

```bash
# Query all available metadata in JSON format
pathogena query-raw a5w2e8.mapping.csv
```
