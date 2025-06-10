__help__

The `validate` command will check that a Batch can be created from a given CSV and if your user account has permission
to upload the samples, the individual FastQ files are then checked for validity. These checks are already performed
by default with the `upload` command but using this can ensure validity without commiting to the subsequent upload
if you're looking to check a CSV during writing it.
