# Development Install Information

### Development install

```bash
git clone https://github.com/EIT-Pathogena/client.git
cd cli
conda env create -y -f environment.yml
pip install --editable '.[dev]'
pre-commit install
```

## Updating your installed version

```bash
git pull origin main
pathogena --version
```

## Using an alternate host

1. The stateless way (use `--host` with every command):
   ```bash
   pathogena auth --host dev.portal.gpas.world
   pathogena upload samples.csv --host dev.portal.gpas.world
   ```

2. The stateful way (no need to use `--host` with each command):
   ```bash
   export PATHOGENA_HOST="dev.portal.gpas.world"
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

```bash
export PATHOGENA_HOST="localhost:8000"
export PATHOGENA_PROTOCOL="http"
```
To unset:
```bash
unset PATHOGENA_HOST
unset PATHOGENA_PROTOCOL
```Development install