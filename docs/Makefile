all:
	echo "Nothing to do"

clean:
	rm -f *.pyc *.pyo *~

install:
	mkdir -p $(DESTDIR)/usr/share/man/man{5,8}
	install -m 644 yum.8 $(DESTDIR)/usr/share/man/man8/yum.8
	install -m 644 yum-shell.8 $(DESTDIR)/usr/share/man/man8/yum-shell.8
	install -m 644 yum.conf.5 $(DESTDIR)/usr/share/man/man5/yum.conf.5
