# Bioconda-based build against latest PyPI release
# Created for a specific user. Not part of the pypi release process
FROM condaforge/miniforge3:latest
ENV PATHOGENA_CLIENT_VERSION=1.0.3a1
RUN mamba install -c bioconda hostile==1.1.0
RUN pip install https://pypi.io/packages/source/g/gpas/gpas-${PATHOGENA_CLIENT_VERSION}.tar.gz
