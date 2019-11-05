#!/bin/bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

PACKAGE="tmt"

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm $PACKAGE
        rlRun "TMP=\$(mktemp -d)" 0 "Creating tmp directory"
        rlRun "pushd $TMP"
        rlRun "set -o pipefail"
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "dnf --help | tee output" 0 "Check help message"
        rlAssertGrep "List of Main Commands" "output"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "popd"
        rlRun "rm -r $TMP" 0 "Removing tmp directory"
    rlPhaseEnd
rlJournalEnd
