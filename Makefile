SUBDIRS = repomd rpmUtils urlgrabber yum etc docs
PYFILES = $(wildcard *.py)

PKGNAME = yum
VERSION=$(shell awk '/Version:/ { print $$2 }' ${PKGNAME}.spec)
RELEASE=$(shell awk '/Release:/ { print $$2 }' ${PKGNAME}.spec)
CVSTAG=yum-$(subst .,_,$(VERSION)-$(RELEASE))

PYTHON=python

all: subdirs

clean:
	rm -f *.pyc *.pyo *~
	for d in $(SUBDIRS); do make -C $$d clean ; done

subdirs:
	for d in $(SUBDIRS); do make -C $$d; [ $$? = 0 ] || exit 1 ; done

install:
	mkdir -p $(DESTDIR)/usr/share/yum
	for p in $(PYFILES) ; do \
		install -m 644 $$p $(DESTDIR)/usr/share/yum/$$p; \
	done
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/usr/share/yum', 1, '$(PYDIR)', 1)"

	mkdir -p $(DESTDIR)/usr/bin $(DESTDIR)/usr/bin
	install -m 755 yum.sh $(DESTDIR)/usr/bin/yum

	mkdir -p $(DESTDIR)/var/cache/yum

	for d in $(SUBDIRS); do make DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; [ $$? = 0 ] || exit 1; done

archive:
	@rm -rf ${PKGNAME}-%{VERSION}.tar.gz
	@rm -rf /tmp/${PKGNAME}-$(VERSION) /tmp/${PKGNAME}
	@dir=$$PWD; cd /tmp; cp -a $$dir ${PKGNAME}
	@mv /tmp/${PKGNAME} /tmp/${PKGNAME}-$(VERSION)
	@dir=$$PWD; cd /tmp; tar cvzf $$dir/${PKGNAME}-$(VERSION).tar.gz ${PKGNAME}-$(VERSION)
	@rm -rf /tmp/${PKGNAME}-$(VERSION)	
	@echo "The archive is in ${PKGNAME}-$(VERSION).tar.gz"
