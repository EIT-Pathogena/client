# Development Install Information

## Development install

Installation of the client requires the `conda` package manager, as well as
`conda-forge` and `bioconda`, in order to install the required libraries. For more
information on how to install that, please refer to [this section](install.md#installing-miniconda).

```bash
git clone https://github.com/EIT-Pathogena/client.git
cd client
conda env create -y -f environment.yml
conda activate gpas
pip install --editable '.[dev]'
pre-commit install
```

## Updating your installed version

```bash
git pull origin main
gpas --version
```

## Using an alternate host

You will most likely need to specify a different host to the default if you're developing, below are details on how
to do so.

1. The stateless way (use `--host` with every command):

   ```bash
   gpas auth --host "portal.eit-pathogena.com"
   gpas upload samples.csv --host "portal.eit-pathogena.com"
   ```

2. The stateful way (no need to use `--host` with each command):

   ```bash
   export GPAS_HOST="portal.eit-pathogena.com"
   ```

   Then, as usual:

   ```bash
   gpas auth
   gpas upload samples.csv
   ```

   To reset:

   ```bash
   unset GPAS_HOST
   ```

## Installing a pre-release version

```bash
conda create --yes -n gpas -c conda-forge -c bioconda hostile==1.1.0
conda activate gpas
pip install --pre gpas
```

## Using a local development server

## gpas portal runs on port 8000, whilst the upload-api runs on 8003

```bash
export GPAS_HOST="localhost:8000"
export GPAS_PROTOCOL="http"
export GPAS_UPLOAD_HOST="localhost:8003"
export GPAS_APP_HOST="localhost:3000"
```

To unset:

```bash
unset GPAS_HOST
unset GPAS_PROTOCOL
```
