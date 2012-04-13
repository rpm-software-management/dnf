
import rpmUtils.updates
import rpmUtils.arch

instlist = [('foo', 'i386', '0', '1', '1'),
            ('do', 'i386', '0', '2', '3'),
            ('glibc', 'i386', '0', '1', '1'),
            ('bar', 'noarch', '0', '2', '1'),
            ('baz', 'i686', '0', '2', '3'),
            ('baz', 'x86_64', '0','1','4'),
            ('foo', 'i686', '0', '1', '1'),
            ('cyrus-sasl','sparcv9', '0', '1', '1')]

availlist = [('foo', 'i686', '0', '1', '3'),
             ('do', 'noarch', '0', '3', '3'), 
             ('do', 'noarch', '0', '4', '3'),
             ('foo', 'i386', '0', '1', '3'),
             ('foo', 'i686', '0', '1', '2'),
             ('glibc', 'i686', '0', '1', '2'),
             ('glibc', 'i386', '0', '1', '2'),
             ('bar', 'noarch', '0', '2', '2'),
             ('baz', 'noarch', '0', '2', '4'),
             ('baz', 'i686', '0', '2', '4'),
             ('baz', 'x86_64', '0', '1', '5'),
             ('baz', 'ppc', '0', '1', '5'),
             ('cyrus-sasl','sparcv9', '0', '1', '2'),
             ('cyrus-sasl','sparc64', '0', '1', '2'),]

obslist = {('quux', 'noarch', '0', '1', '3'): [('bar', None, (None, None, None))],

           ('quuxish', 'noarch', '0', '1', '3'):[('foo', 'GE', ('0', '1', None))],
           }
           

up = rpmUtils.updates.Updates(instlist, availlist)
up.debug=1
up.exactarch=1
#up.myarch = 'sparc64'
up._is_multilib = rpmUtils.arch.isMultiLibArch(up.myarch)
up._archlist = rpmUtils.arch.getArchList(up.myarch)
print up._archlist
up._multilib_compat_arches = rpmUtils.arch.getMultiArchInfo(up.myarch)
up.doUpdates()
up.condenseUpdates()

for tup in up.updatesdict.keys():
    (old_n, old_a, old_e, old_v, old_r) = tup
    for (n, a, e, v, r) in up.updatesdict[tup]:
        print '%s.%s %s:%s-%s updated by %s.%s %s:%s-%s' % (old_n, 
                                old_a, old_e, old_v, old_r, n, a, e, v, r)

up.rawobsoletes = obslist
up.doObsoletes()
for tup in up.obsoletes.keys():
    (old_n, old_a, old_e, old_v, old_r) = tup
    for (n, a, e, v, r) in up.obsoletes[tup]:
        print '%s.%s %s:%s-%s obsoletes %s.%s %s:%s-%s' % (old_n, 
                                old_a, old_e, old_v, old_r, n, a, e, v, r)

    


        
