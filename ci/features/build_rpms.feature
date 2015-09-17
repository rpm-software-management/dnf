# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

Feature: Build RPMs of a project
  In order to test a project, I want to build its software packages.

  Background: Copr project is configured
    Given a Copr project _stack-ci_test exists
    Given following options are configured as follows:
       | Option  | Value          |
       | PROJECT | _stack-ci_test |

  Scenario: Build tito-enabled project
     When I build RPMs of the tito-enabled project
     Then the build should have succeeded

  Scenario: Build librepo fork
     When I build RPMs of the librepo project fork
     Then the build should have succeeded

  Scenario: Configure librepo release
    Given following options are configured as follows:
       | Option    | Value                                                    |
       | --release | 99.2.20150102git3a45678901b23c456d78ef90g1234hijk56789lm |
     When I build RPMs of the librepo project fork
     Then the release number of the resulting RPMs of the librepo fork should be 99.2.20150102git3a45678901b23c456d78ef90g1234hijk56789lm

  Scenario: Build libcomps fork
     When I build RPMs of the libcomps project fork
     Then the build should have succeeded

  Scenario: Configure libcomps release
    Given following options are configured as follows:
       | Option    | Value                                                    |
       | --release | 99.2.20150102git3a45678901b23c456d78ef90g1234hijk56789lm |
     When I build RPMs of the libcomps project fork
     Then the release number of the resulting RPMs of the libcomps fork should be 99.2.20150102git3a45678901b23c456d78ef90g1234hijk56789lm