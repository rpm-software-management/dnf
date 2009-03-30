SUBDIRS = rpmUtils yum etc docs po
PYFILES = $(wildcard *.py)
PYLINT_MODULES =  *.py yum rpmUtils
PYLINT_IGNORE = oldUtils.py

PKGNAME = yum
VERSION=$(shell awk '/Version:/ { print $$2 }' ${PKGNAME}.spec)
RELEASE=$(shell awk '/Release:/ { print $$2 }' ${PKGNAME}.spec)
CVSTAG=yum-$(subst .,_,$(VERSION)-$(RELEASE))
PYTHON=python

all: subdirs

clean:
	rm -f *.pyc *.pyo *~ *.bak
	for d in $(SUBDIRS); do make -C $$d clean ; done
	cd test; rm -f *.pyc *.pyo *~ *.bak

subdirs:
	for d in $(SUBDIRS); do make PYTHON=$(PYTHON) -C $$d; [ $$? = 0 ] || exit 1 ; done

install:
	mkdir -p $(DESTDIR)/usr/share/yum-cli
	for p in $(PYFILES) ; do \
		install -m 644 $$p $(DESTDIR)/usr/share/yum-cli/$$p; \
	done
	mv $(DESTDIR)/usr/share/yum-cli/yum-updatesd.py $(DESTDIR)/usr/share/yum-cli/yumupd.py
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/usr/share/yum-cli', 1, '$(PYDIR)', 1)"

	mkdir -p $(DESTDIR)/usr/bin $(DESTDIR)/usr/sbin
	install -m 755 bin/yum.py $(DESTDIR)/usr/bin/yum
	install -m 755 bin/yum-updatesd.py $(DESTDIR)/usr/sbin/yum-updatesd

	mkdir -p $(DESTDIR)/var/cache/yum
	mkdir -p $(DESTDIR)/var/lib/yum	

	for d in $(SUBDIRS); do make PYTHON=$(PYTHON) DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; [ $$? = 0 ] || exit 1; done

.PHONY: docs test

DOCS = yum rpmUtils callback.py yumcommands.py shell.py output.py cli.py \
	   yummain.py
docs:
	epydoc -n yum -o docs/epydoc -u http://linux.duke.edu/projects/yum $(DOCS)

doccheck:
	epydoc --check $(DOCS)

test:
	@nosetests -i ".*test" test
	@test/check-po-yes-no.py

test-skipbroken:
	@nosetests -i ".*test" test/skipbroken-tests.py

check: test

pylint:
	@pylint --rcfile=test/yum-pylintrc --ignore=$(PYLINT_IGNORE) $(PYLINT_MODULES)

pylint-short:
	@pylint -r n --rcfile=test/yum-pylintrc --ignore=$(PYLINT_IGNORE) $(PYLINT_MODULES)

changelog:
	git log --since=2007-05-16 --pretty --numstat --summary | git2cl  > ChangeLog

testnewbehavior:
	@NEW_BEHAVIOR=1 nosetests -i ".*test" test

archive: remove_spec = ${PKGNAME}-daily.spec
archive: _archive

daily: remove_spec = ${PKGNAME}.spec
daily: _archive

_archive:
	@rm -rf ${PKGNAME}-%{VERSION}.tar.gz
	@rm -rf /tmp/${PKGNAME}-$(VERSION) /tmp/${PKGNAME}
	@dir=$$PWD; cd /tmp; cp -a $$dir ${PKGNAME}
	lynx -dump 'http://wiki.linux.duke.edu/WritingYumPlugins?action=print' > /tmp/${PKGNAME}/PLUGINS
	lynx -dump 'http://wiki.linux.duke.edu/YumFaq?action=print' > /tmp/${PKGNAME}/FAQ
	@rm -f /tmp/${PKGNAME}/$(remove_spec)
	@rm -rf /tmp/${PKGNAME}/.git
	@mv /tmp/${PKGNAME} /tmp/${PKGNAME}-$(VERSION)
	@dir=$$PWD; cd /tmp; tar cvzf $$dir/${PKGNAME}-$(VERSION).tar.gz ${PKGNAME}-$(VERSION)
	@rm -rf /tmp/${PKGNAME}-$(VERSION)	
	@echo "The archive is in ${PKGNAME}-$(VERSION).tar.gz"

