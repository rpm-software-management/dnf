all:
	echo "Nothing to do"

clean:
	rm -f *~

install:
	mkdir -p $(DESTDIR)/etc/cron.daily
	mkdir -p $(DESTDIR)/etc/rc.d/init.d
	mkdir -p $(DESTDIR)/usr/sbin
	mkdir -p $(DESTDIR)/etc/sysconfig
	mkdir -p $(DESTDIR)/usr/share/yum-cron
	install -D -m 755 yum-update.cron.sh $(DESTDIR)/etc/cron.daily/yum-update.cron
	install -D -m 755 yum-cleanup.cron.sh $(DESTDIR)/etc/cron.daily/yum-cleanup.cron
	install -D -m 755 yum-cron.sysvinit $(DESTDIR)/etc/rc.d/init.d/yum-cron
	install -D -m 755 yum-cron.sh $(DESTDIR)/usr/sbin/yum-cron
	install -D -m 644 yum-cron.sysconfig $(DESTDIR)/etc/sysconfig/yum-cron
	install -D -m 644 update.yum $(DESTDIR)/usr/share/yum-cron/update.yum
	install -D -m 644 cleanup.yum $(DESTDIR)/usr/share/yum-cron/cleanup.yum
