## Install

There are two recommended methods for installing the GPAS Client, either by using the popular package and
environment manager Conda or by using our publicly available Docker container which we build at release time.

### Installing Miniconda

If a Conda package manager is already installed, skip to [Installing the client](#installing-or-updating-the-client-with-miniconda),
otherwise the following instructions have been taken from the [Miniconda install process documentation](https://docs.anaconda.com/miniconda/miniconda-install/)

#### Installing Miniconda on Linux

In a terminal console, install Miniconda with the following instructions and accepting default options:

    ```bash
    mkdir -p ~/miniconda3
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
    bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
    rm -rf ~/miniconda3/miniconda.sh
    ```

#### Installing Miniconda on MacOS

The client requires the Conda platform to be using `x86_64` when creating the environment.

- If your Mac has an Apple processor, using Terminal, firstly run:

  ```bash
  mkdir -p ~/miniconda3
  curl https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh -o ~/miniconda3/miniconda.sh
  bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
  rm -rf ~/miniconda3/miniconda.sh
  ```

- Initialise Miniconda using either of the following commands depending on your Shell (Bash|ZSH)
  ```bash
  ~/miniconda3/bin/conda init bash
  ~/miniconda3/bin/conda init zsh
  ```

### Installing or updating the client with Miniconda

<a id="installing-or-updating-the-client-with-miniconda"></a>

The client has at least one dependency that requires `bioconda`, which itself
depends on `conda-forge`. Note that for the `conda create` step (see below), installation can be very slow,
so please leave it running. For more verbose output, you can add the `-v` or `-vv` flags, though
it is not recommended to show the full debug output with `-vvv` as this has been seen to lead to OOM errors.

#### Linux

```bash
conda create -y -n gpas -c conda-forge -c bioconda hostile==1.1.0
conda activate gpas
pip install --upgrade gpas
```

#### MacOS

Please note the additional argument `--platform osx-64` in this command, compared to the above.

```bash
conda create --platform osx-64 -y -n gpas -c conda-forge -c bioconda hostile==1.1.0
conda activate gpas
pip install --upgrade gpas
```

A simple test to verify installation would be to run a version check:

```bash
gpas --version
```
