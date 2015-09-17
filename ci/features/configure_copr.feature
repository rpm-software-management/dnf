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

Feature: Configure Copr projects
  In order to test the stack in Copr, I want to easily configure the
  relevant Copr projects.

  Scenario: Create Copr project
    Given following options are configured as follows:
       | Option  | Value          |
       | CHROOT  | rawhide        |
       | PROJECT | _stack-ci_test |
     When I create a Copr project
     Then I should have a Copr project called _stack-ci_test with chroots fedora-rawhide-i386, fedora-rawhide-x86_64

  Scenario: Add URL to Copr project
    Given following options are configured as follows:
       | Option            | Value                  |
       | CHROOT            | rawhide                |
       | PROJECT           | _stack-ci_test         |
       | --add-repository  | http://www.example.com |
     When I create a Copr project
     Then I should have the http://www.example.com repository added to the Copr project called _stack-ci_test