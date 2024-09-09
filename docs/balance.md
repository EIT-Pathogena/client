## `pathogena balance`

```bash balance help
pathogena balance -h
15:55:36 INFO: EIT Pathogena client version 2.0.0
Usage: pathogena balance [OPTIONS]

  Check your EIT Pathogena account balance.

Options:
  --host TEXT  API hostname (for development)
  -h, --help   Show this message and exit.
```

Credits are required to upload samples and initiate the analysis process. Users can check their credit balance in the 
header of the Pathogena Portal or by using the `pathogena balance` command when logged in.

### Usage

```bash balance usage
pathogena balance
15:56:56 INFO: EIT Pathogena client version 2.0.0
15:56:56 INFO: Getting credit balance for portal.eit-pathogena.com
15:56:57 INFO: Your remaining account balance is 1000 credits
```