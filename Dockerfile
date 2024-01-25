# Bioconda-based build against latest PyPI release
FROM condaforge/miniforge3:latest
ENV GPAS_CLIENT_VERSION=0.25.0rc1
RUN mamba install -c bioconda hostile>=1.0.0
RUN pip install https://pypi.io/packages/source/g/gpas/gpas-${GPAS_CLIENT_VERSION}.tar.gz
