all:
	echo "Nothing to do"

clean:
	rm -f *.pyc *.pyo *~

install:
	mkdir -p $(DESTDIR)/etc/yum/
	mkdir -p $(DESTDIR)/etc/yum/repos.d

	install -m 644 yum.conf $(DESTDIR)/etc/yum/yum.conf

	mkdir -p $(DESTDIR)/etc/logrotate.d
	install -m 644 yum.logrotate $(DESTDIR)/etc/logrotate.d/yum
