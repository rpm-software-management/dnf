#!/usr/bin/python3

# script to get rid of
# "'msgid' and 'msgstr' entries do not both begin/end with '\n'"
# error messages during .po to .mo files conversion via msgfmt tool
#
# 'polib' module is needed for run: https://pypi.python.org/pypi/polib
#
# usage: python3 sanitize_po_files.py [po_file...]
#
# in order to update translations from zanata, do:
#  * cmake .
#  * make gettext-update
#  * git add po/*.po
#  * ./scripts/sanitize_po_files.py po/*.po
#  * git commit -m "zanata update"

import polib
import re
import sys


def sanitize_po_file(po_file):
    print("Processing", po_file)
    po = polib.pofile(po_file)
    for entry in po:
        msgid_without_indents = entry.msgid.strip()
        msgstr_without_indents = entry.msgstr.strip()
        entry.msgstr = entry.msgid.replace(
            msgid_without_indents, msgstr_without_indents)
        if re.match(r"^\s+$", entry.msgstr):
            entry.msgstr = ""

        if entry.msgid_plural:
            msgid_plural_without_indents = entry.msgid_plural.strip()
            for i in entry.msgstr_plural.keys():
                msgstr_plural_without_indents = entry.msgstr_plural[i].strip()
                entry.msgstr_plural[i] = entry.msgid_plural.replace(
                    msgid_plural_without_indents,
                    msgstr_plural_without_indents)
                if re.match(r"^\s+$", entry.msgstr_plural[i]):
                    entry.msgstr_plural[i] = ""
    po.save()


if __name__ == "__main__":
    for po_file in sys.argv[1:]:
        sanitize_po_file(po_file)
