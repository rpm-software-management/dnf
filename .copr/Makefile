# Copyright David Cantrell <dcantrell@redhat.com>
# SPDX-License-Identifier: GPL-3.0-or-later

# Set the top level source directory
topdir := $(shell realpath $(dir $(lastword $(MAKEFILE_LIST)))/..)

# Install packages before anything else
_install := $(shell dnf install -y git)
_safedir := $(shell git config --global --add safe.directory $(topdir))

# Pass BUILDTYPE=release to generate a release SRPM
BUILDTYPE ?= copr

# Spec file and template
SPEC_TEMPLATE = $(shell ls -1 $(topdir)/*.spec)
SPEC = $(topdir)/$(shell basename $(SPEC_TEMPLATE))

# Replace placeholders in the spec file template
RPMDATE = $(shell date +'%a %b %d %Y')
#RPMAUTHOR = $(shell git log | grep ^Author: | head -n 1 | cut -d ' ' -f 2,3,4)
RPMAUTHOR = "David Cantrell <dcantrell@redhat.com>"

# Various things we need to generate a tarball
PKG = $(shell grep ^Name: "$(SPEC_TEMPLATE)" | awk '{ print $$2; }')
VER = $(shell grep ^Version: "$(SPEC_TEMPLATE)" | awk '{ print $$2; }')

ifeq ($(BUILDTYPE),copr)
GITDATE          = $(shell date +'%Y%m%d%H%M')
GITHASH          = $(shell git rev-parse --short HEAD)
TARBALL_BASENAME = $(PKG)-$(VER)-$(GITDATE)git$(GITHASH)
TAG              = HEAD
else
0TAG             = $(shell git tag -l | sort -V | tail -n 1)
endif

ifeq ($(BUILDTYPE),release)
TARBALL_BASENAME = $(PKG)-$(VER)
endif

# Where to insert the changelog entry
STARTING_POINT = $(shell expr $(shell grep -n ^%changelog "$(SPEC)" | cut -d ':' -f 1) + 1)

srpm:
	sed -e 's|%%VERSION%%|$(VER)|g' < "$(SPEC_TEMPLATE)" > "$(SPEC)".new
	mv "$(SPEC)".new "$(SPEC)"
ifeq ($(BUILDTYPE),copr)
	sed -i -e '/^Release:/ s/1[^%]*/0.1.$(GITDATE)git$(GITHASH)/' "$(SPEC)"
	sed -i -e 's|^Source0:.*$$|Source0: $(TARBALL_BASENAME).tar.gz|g' "$(SPEC)"
	sed -i -e 's|^%autosetup.*$$|%autosetup -n $(TARBALL_BASENAME)|g' "$(SPEC)"
	sed -i -e '$(STARTING_POINT)i\\' "$(SPEC)"
	sed -i -e '$(STARTING_POINT)i - Build $(PKG)-$(VER)-$(GITDATE)git$(GITHASH) snapshot' "$(SPEC)"
	sed -i -e '$(STARTING_POINT)i * $(RPMDATE) $(RPMAUTHOR) - $(VER)-$(GITDATE)git$(GITHASH)' "$(SPEC)"
endif
	git archive \
		--format=tar \
		--output='$(topdir)/$(TARBALL_BASENAME).tar' \
		--prefix='$(TARBALL_BASENAME)/' $(TAG) $(topdir)
	gzip -9f $(topdir)/$(TARBALL_BASENAME).tar
	rpmbuild \
		-bs --nodeps \
		--define "_sourcedir $(topdir)" \
		--define "_srcrpmdir $(outdir)" \
		--define "_rpmdir $(outdir)" "$(SPEC)"
