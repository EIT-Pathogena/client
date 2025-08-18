#!/bin/bash

# This script will combine the various sources of information to generate the README_pypi.md file.
#
# The intention behind this method is to make it clear where the information is maintained and allow for easier
# maintaining of documentation.

# shellcheck disable=SC2028
cat docs/intro.md > README_pypi.md
# commitlint doesn't allow an extra EOF at the end of files, so we are adding an extra line between sections here
echo "" >> README_pypi.md
cat docs/install.md >> README_pypi.md

commands=("auth" "balance" "upload" "build-csv" "decontaminate" "download" "validate" "query-raw" "query-status" "autocomplete")

for i in "${commands[@]}"; do
  COMMAND_OUTPUT=$(pathogena "$i" -h)
  DOC_CONTENT=$(< "docs/$i.md")
  UPDATED_DOC=$(awk -v cmd="$i" -v help="$COMMAND_OUTPUT" '{
    if ($0 == "__help__") {
      print "## `pathogena " cmd "`\n<a id=\"pathogena-" cmd "\"></a>\n\n```text\n" help "\n```"
    } else {
      print $0
    }
  }' <<< "$DOC_CONTENT")
  echo "$UPDATED_DOC" >> README_pypi.md
  echo "" >> README_pypi.md
done

cat docs/support.md >> README_pypi.md

# Extract version from __init__.py
VERSION=$(grep '__version__' src/pathogena/__init__.py | cut -d '"' -f2)

# Replace __version__ in links with actual version
sed -i '' "s|__version__|$VERSION|g" README_pypi.md
