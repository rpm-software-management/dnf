#!/bin/bash

YEAR="$1"

if [[ -z "$YEAR" ]] ; then
    echo "$0" '<year>' >&2
    exit 1
fi

PREV_YEAR="$(($YEAR-1))"
PREV_YEARS="$(seq -s '|' 2000 "$PREV_YEAR")"

git log --pretty=format: --name-only --author='redhat\.com' \
        --after "${YEAR}"-01-01 --before "${YEAR}"-12-31 | \
        xargs perl -i -pe 's!^(#|--| \*|<source>| *) *Copyright (\([c]\)|©|\&(?:amp;)?#169;) ('"{$PREV_EARS}"')((
?:(-?|\&(?:amp;)?#x'"${YEAR}"';)('"${PREV_YEARS}"'))?,? +Red Hat,? Inc\.!$1Copyright $2 $3@{[($4 eq "") ? "-" : ${4}]}'"${YEAR}"' Red Hat, Inc.!i and s!^(#|--| \*) *Copyright!$1 Copyright!;'

exit
