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
RPMAUTHOR = David Cantrell <dcantrell@redhat.com>

# Various things we need to generate a tarball
PKG = $(shell rpmspec -P "$(SPEC_TEMPLATE)" | grep ^Name: | awk '{ print $$2; }')
VER = $(shell rpmspec -P "$(SPEC_TEMPLATE)" | grep ^Version: | awk '{ print $$2; }')

ifeq ($(BUILDTYPE),copr)
GITDATE          = $(shell date +'%Y%m%d%H%M')
GITHASH          = $(shell git rev-parse --short HEAD)
TARBALL_BASENAME = $(PKG)-$(VER)-$(GITDATE)git$(GITHASH)
TAG              = HEAD
else
TAG              = $(shell git describe --tags --abbrev=0)
endif

ifeq ($(BUILDTYPE),release)
TARBALL_BASENAME = $(PKG)-$(VER)
endif

# Where to insert the changelog entry
STARTING_POINT = $(shell expr $(shell grep -n ^%changelog "$(SPEC)" | cut -d ':' -f 1) + 1)

srpm:
	sed -i -e '1i %global source_date_epoch_from_changelog 0' "$(SPEC)"
	sed -e 's|%%VERSION%%|$(VER)|g' < "$(SPEC_TEMPLATE)" > "$(SPEC)".new
	mv "$(SPEC)".new "$(SPEC)"
ifeq ($(BUILDTYPE),copr)
	sed -i -e '/^Release:/ s/1[^%]*/0.1.$(GITDATE)git$(GITHASH)/' "$(SPEC)"
	sed -i -e 's|^Source0:.*$$|Source0: $(TARBALL_BASENAME).tar.gz|g' "$(SPEC)"
	sed -i -e 's|^%autosetup.*$$|%autosetup -n $(TARBALL_BASENAME)|g' "$(SPEC)"
	sed -i -e '$(STARTING_POINT)a\\' "$(SPEC)"
	sed -i -e '$(STARTING_POINT)a - Build $(PKG)-$(VER)-$(GITDATE)git$(GITHASH) snapshot' "$(SPEC)"
	sed -i -e '$(STARTING_POINT)a * $(RPMDATE) $(RPMAUTHOR) - $(VER)-$(GITDATE)git$(GITHASH)' "$(SPEC)"
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
