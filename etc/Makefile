all:
	echo "Nothing to do"

clean:
	rm -f *.pyc *.pyo *~

install:
	mkdir -p $(DESTDIR)/etc/security/console.apps 
	install -m 644 yum.console $(DESTDIR)/etc/security/console.apps/yum

	mkdir -p $(DESTDIR)/etc/pam.d
	install -m 644 yum.pam $(DESTDIR)/etc/pam.d/yum

	mkdir -p $(DESTDIR)/etc/yum.repos.d
	install -m 644 yum.conf $(DESTDIR)/etc/yum.conf

	mkdir -p $(DESTDIR)/etc/cron.daily
	install -m 600 yum.cron $(DESTDIR)/etc/cron.daily/yum.cron

	mkdir -p $(DESTDIR)/etc/rc.d/init.d
	install -m 755 yum.init $(DESTDIR)/etc/rc.d/init.d/yum

	mkdir -p $(DESTDIR)/etc/logrotate.d
	install -m 644 yum.logrotate $(DESTDIR)/etc/logrotate.d/yum

