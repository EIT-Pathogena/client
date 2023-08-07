# gpas-client

Under construction. Currently named `gpas-client` to avoid collisions with `gpas` (gpas-tb backend) and `gpas-cli` (gpas-sars2 CLI).

## Install

**Conda/mamba**

```bash
conda create -n gpas-cli -c conda-forge -c bioconda hostile  # Mamba is faster
conda activate gpas-cli
git clone https://github.com/GlobalPathogenAnalysisService/cli.git
cd cli
pip install --editable '.[dev]'
```

## CLI Usage

**Authentication**

Saves token to `~/.config/gpas/tokens/$HOSTNAME.json`

```
$ gpas-cli auth
Enter your username: bede.constantinides@ndm.ox.ac.uk
Enter your password: ***************
09:22:08 INFO: HTTP Request: POST https://dev.portal.gpas.world/api/v1/auth/token "HTTP/1.1 200 OK"
```

**Upload**

Uses existing token for hostname

```
$ gpas-cli upload tests/data/illumina-2.csv
09:26:12 INFO: Using Bowtie2 (paired reads)
09:26:12 INFO: Found cached index (/Users/bede/Library/Application Support/hostile/human-t2t-hla)
09:26:12 INFO: Cleaning…
Cleaning: 100%|███████████████████████████████████| 2/2 [00:00<00:00,  2.51it/s]
09:26:13 INFO: Complete
09:26:13 INFO: HTTP Request: POST https://dev.portal.gpas.world/api/v1/batches "HTTP/1.1 201 Created"
09:26:13 INFO: HTTP Request: POST https://dev.portal.gpas.world/api/v1/samples "HTTP/1.1 201 Created"
09:26:14 INFO: HTTP Request: POST https://dev.portal.gpas.world/api/v1/samples/658/files "HTTP/1.1 201 Created"
09:26:14 INFO: HTTP Request: POST https://dev.portal.gpas.world/api/v1/samples/658/files "HTTP/1.1 201 Created"
09:26:14 INFO: Uploaded sample1
09:26:15 INFO: HTTP Request: POST https://dev.portal.gpas.world/api/v1/samples "HTTP/1.1 201 Created"
09:26:15 INFO: HTTP Request: POST https://dev.portal.gpas.world/api/v1/samples/659/files "HTTP/1.1 201 Created"
09:26:16 INFO: HTTP Request: POST https://dev.portal.gpas.world/api/v1/samples/659/files "HTTP/1.1 201 Created"
09:26:16 INFO: Uploaded sample2
09:26:16 INFO: Uploaded batch fynh56
```
