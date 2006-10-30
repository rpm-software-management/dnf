all:
	echo "Nothing to do"

clean:
	rm -f *.pyc *.pyo *~
	rm -fr epydoc

install:
	mkdir -p $(DESTDIR)/usr/share/man/man{5,8}
	install -m 644 yum.8 $(DESTDIR)/usr/share/man/man8/yum.8
	install -m 644 yum-shell.8 $(DESTDIR)/usr/share/man/man8/yum-shell.8
	install -m 644 yum.conf.5 $(DESTDIR)/usr/share/man/man5/yum.conf.5
	install -m 644 yum-updatesd.8 $(DESTDIR)/usr/share/man/man8/yum-updatesd.8
	install -m 644 yum-updatesd.conf.5 $(DESTDIR)/usr/share/man/man5/yum-updatesd.conf.5
