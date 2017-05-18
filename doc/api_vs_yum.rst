..
    Copyright (C) 2014-2015  Red Hat, Inc.

  This copyrighted material is made available to anyone wishing to use,
  modify, copy, or redistribute it subject to the terms and conditions of
  the GNU General Public License v.2, or (at your option) any later version.
  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY expressed or implied, including the implied warranties of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
  Public License for more details.  You should have received a copy of the
  GNU General Public License along with this program; if not, write to the
  Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
  02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
  source code or documentation are not subject to the GNU General Public
  License and may only be used or replicated with the express permission of
  Red Hat, Inc.

#########################################
 Changes in DNF hook api compared to Yum
#########################################


.. only :: html
   

This table provides what alternative hooks are available in DNF compared to
yum.

===========  =================  ==============================
Hook Number  Yum hook           DNF hook
-----------  -----------------  ------------------------------
``1``        ``config``         ``init``
``2``        ``postconfig``     ``init``
``3``        ``init``           ``init``
``4``        ``predownload``          
``5``        ``postdownload``         
``6``        ``prereposetup``          
``7``        ``postreposetup``  ``sack``
``8``        ``exclude``        ``resolved``
``9``        ``preresolve``              
``10``       ``postresolve``    ``resolved but no re-resolve``
``11``       ``pretrans``       ``pre_transaction``
``12``       ``postrans``       ``transaction``
``13``       ``close``          ``transaction``
``14``       ``clean``                   
===========  =================  ==============================

Feel free to file a RFE_ for missing functionality if you need it.

.. _RFE: https://github.com/rpm-software-management/dnf/wiki/Bug-Reporting#new-feature-request

