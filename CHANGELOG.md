## Unreleased

## 1.0.3rc1 (2024-07-15)

### Feat

- Check for a new version in PyPi.
- Added `gpas autocomplete` sub-command to enable tab completion
- Introduce tab completion with host example.
- Added __main__ to enable easier IDE debugging.
- Add debug to all commands, print cli version always.

### Fix

- Re-implement version check when uploading samples.
- Add logging to GZIP func and reduce compression to increase speed.
- Checksums incorrectly set on sample creation.
- Remove failing test temporarily.
- File upload logic and spurious test failure on CI.
- Illumina upload without decontamination, refactor validation.
- Use `type` instead of `command -v`.
- Tests and gzip handling.
- Added tests for .gz files and further util tests.
- comment out test breaking Github actions.
- Tests require authentication, commented out for now.
- Allow skip fastq check
- FASTQ checking info
- Remove auto-click-auto and manually output instructions.

## 1.0.3a1 (2024-06-12)

### Fix

- check fastqs have multiple of 4 lines
- Report numbers of lines in fastq files when different
- Check for empty fastq files
- rework fastq checking to use warnings
- Read fastqs as text for checking
- Handle checking of fastq (not gzipped)
- Check and raise explicit error if illumina fastq files unmatched
- Function to check paired fastqs

## 1.0.2 (2024-05-09)

## 1.0.2a1 (2024-05-09)

### Fix

- Bump version in files
- Set output files to empty list if no files

## 1.0.1 (2024-05-03)

### Fix

- Client 1.0.1 in init

## 1.0.1a4 (2024-05-03)

### Fix

- Continue batch file downloads even if files missing
- Pin hostile version to 1.1.0

## 1.0.1a3 (2024-04-16)

### Fix

- add note to dockerfile
- use pydantic for UploadData object
- use dataclass for upload csv
- remove defopt dependency
- default values of district and subdivision
- add click dependency
- use click and add build csv command
- script to generate upload csv

## 1.0.1a2 (2024-04-15)

### Feat

- add basic retry policy

### Fix

- increase version
- use CACHE_DIR for hostile 1.1.0
- only run tests for PR and main
- add some tenacity retries for a few processes
- add newline to messafe
- expand/add some timeouts
- improve client error messages
- use transport rather than depreciated Retry
- add validate subcommand to pre-check if an upload CSV is valid

## 1.0.1a1 (2024-03-01)

## 1.0.0 (2024-02-22)

### Feat

- include dirty checksum in file upload

### Fix

- bump version for release
- remove erroneous arg

## 1.0.0a3 (2024-02-19)

### Fix

- remove debug parameter in download call

## 1.0.0a2 (2024-02-13)

## 1.0.0a1 (2024-02-05)

## 0.25.0 (2024-01-25)

## 0.25.0rc1 (2024-01-22)

## 0.24.0 (2024-01-03)

## 0.23.0 (2023-12-21)

## 0.22.0 (2023-12-05)

## 0.21.0 (2023-12-04)

## 0.20.0 (2023-12-04)

## 0.19.0 (2023-12-04)

## 0.18.0 (2023-12-04)

## 0.17.0 (2023-11-24)

## 0.16.0 (2023-11-23)

## 0.15.0 (2023-11-21)

## 0.14.0 (2023-11-15)

### Feat

- **passwords**: hide passwords on input