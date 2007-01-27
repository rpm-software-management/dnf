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

	mkdir -p $(DESTDIR)/etc/rc.d/init.d
	install -m 755 yum-updatesd.init $(DESTDIR)/etc/rc.d/init.d/yum-updatesd

	mkdir -p $(DESTDIR)/etc/dbus-1/system.d/
	install -m 755 yum-updatesd-dbus.conf $(DESTDIR)/etc/dbus-1/system.d/yum-updatesd.conf

	install -m 755 yum-updatesd.conf $(DESTDIR)/etc/yum/yum-updatesd.conf


