__help__

This command will output the steps required to enable auto-completion in either a Bash or ZSH shell, follow the output
to enable autocompletion, this will need to be executed on every new shell session, instructions are provided on how to
make this permanent depending on your environment. More information and instructions for other shells can be found in
the [Click documentation](https://click.palletsprojects.com/en/8.1.x/shell-completion/).

### Usage

```bash
$ pathogena autocomplete
Run this command to enable autocompletion:
    eval "$(_PATHOGENA_COMPLETE=bash_source pathogena)"
Add this to your ~/.bashrc file to enable this permanently:
    command -v pathogena > /dev/null 2>&1 && eval "$(_PATHOGENA_COMPLETE=bash_source pathogena)"
```

Tab completion can optionally be enabled by adding the lines output by the command to your shell source files.
This will enable the ability to press tab after writing `pathogena ` to list possible sub-commands. It can also be used
for sub-command options, if `--` is entered prior to pressing tab.
