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

## Usage

```
gpas-cli --help
```
