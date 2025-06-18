# Development Install Information

## Development install

Installation of the client requires the `conda` package manager, as well as
`conda-forge` and `bioconda`, in order to install the required libraries. For more
information on how to install that, please refer to [this section](install.md#installing-miniconda).

```bash
git clone https://github.com/EIT-Pathogena/client.git
cd client
conda env create -y -f environment.yml
conda activate pathogena
pip install --editable '.[dev]'
pre-commit install
```

## Updating your installed version

```bash
git pull origin main
pathogena --version
```

## Using an alternate host

You will most likely need to specify a different host to the default if you're developing, below are details on how
to do so.

1. The stateless way (use `--host` with every command):
   ```bash
   pathogena auth --host "portal.eit-pathogena.com"
   pathogena upload samples.csv --host "portal.eit-pathogena.com"
   ```

2. The stateful way (no need to use `--host` with each command):
   ```bash
   export PATHOGENA_HOST="portal.eit-pathogena.com"
   ```

   Then, as usual:
   ```bash
   pathogena auth
   pathogena upload samples.csv
   ```

   To reset:
   ```bash
   unset PATHOGENA_HOST
   ```

## Installing a pre-release version

```bash
conda create --yes -n pathogena -c conda-forge -c bioconda hostile==1.1.0
conda activate pathogena
pip install --pre pathogena
```

## Using a local development server
## pathogena portal runs on port 8000, whilst the upload-api runs on 8003

```bash
export PATHOGENA_HOST="localhost:8000"
export PATHOGENA_PROTOCOL="http"
export PATHOGENA_UPLOAD_HOST="localhost:8003"
export PATHOGENA_APP_HOST="localhost:3000"
```

To unset:

```bash
unset PATHOGENA_HOST
unset PATHOGENA_PROTOCOL
```
