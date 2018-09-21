# -*- coding: utf-8 -*-

# Copyright (C) 2014-2018  Red Hat, Inc.
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

import dnf.dnssec

import tests.support


RPM_USER = 'RPM Packager (The guy who creates packages) <packager@example.com>'
EMAIL = 'packager@example.com'
RPM_RAW_KEY = b'-----BEGIN PGP PUBLIC KEY BLOCK-----\n\nmQENBFqWzewBCADMHY8wL2Gm+aeShboOf' \
              b'G96/h/OJ8FHj+xrihPGY34FwLVqtvO+\nlRIO6t3w5y7O1MWzR1ePtQg1T1sg1s9UeoDRMZoV' \
              b'gzZdRXtQH1Jy9xpTeMfL31ml\nc3wOnitcH0AdWhT7xnnlaCeJuMrX82PWtiJNd+Cy+bgyLfL' \
              b'MwX18cimwYCnyIHQ5\n4qiiywXa1paVHkbEJdbd8f4AxArsHX33xCv76wct2uXiHYAHu67rE5' \
              b'FhQ0mEqfIZ\nHwuFljGPj5UMgyd6MRMuL2Ho1hL7FDPIxDBv5tMWeZJszixIsCkA9Kc1ibylD' \
              b'z9I\nx/keH1K9XXSb/o2EIfF6sWYcj0wNvJllIHAfABEBAAG0QlJQTSBQYWNrYWdlciAo\nVG' \
              b'hlIGd1eSB3aG8gY3JlYXRlcyBwYWNrYWdlcykgPHBhY2thZ2VyQGV4YW1wbGUu\nY29tPokBT' \
              b'gQTAQgAOBYhBMwU+9636QKkbYsjdMKSn1VZ4I5DBQJals3sAhsDBQsJ\nCAcCBhUKCQgLAgQW' \
              b'AgMBAh4BAheAAAoJEMKSn1VZ4I5D6icH/2GY2MMnmcDO+ApI\nF6gGg9itzAHLTNcxEMl9ht1' \
              b'Gu3JQ/VdsvMQ6lG+U8yffEmsfQebtt1UaMVXzyt0t\ncSOBJvVEI6qc6skvfea3hqL4srtTOC' \
              b'wu7ZBA9gOE+eB5BWBspFUVIwUO1GKT48uz\nV6CaODLitaxc7NrJ9HYw4C4+ICCfbIJhjM/Hq' \
              b'xLKOqVy/jsySqIHK96RrjY/m8Q9\nBzsi/6fj/GHkewaM8zaeNLHE7MgXFZAuJ8lzjD0r2oBD' \
              b'JGeBKfjjz9xh26YWjG/A\noiolXfliTEox6p0bf820eRhdX9UdSesBROL3rkB+hM5FOT8crSP' \
              b'JsuGZWJ9brikf\nsurWyU+5AQ0EWpbN7AEIAK0/PThuvsLdDGe5HeZn3VdrFcD9QSOV9Xjos8' \
              b'zWkwx8\nv0t4KXPM4GshyU2ddNjgA+00LhzjACm2ropT5vdvKPtf8lRGOcWWHkiMPdDW/R3/\n' \
              b'I5S0Oh1WFNrQZwQSXn/DoPnhUZNGErpZlUzF00BEltwoVWgT1n81Bp486U3oziZn\nUM8kxXXY' \
              b'2PN8aTfWjsxOSmjyu2m7abeyjTqX9s++vUCQhmCNboSY1AhXF8GQl1Ce\nmpHVv0hOuC6Bead' \
              b'ZRXEfEF0sQogswXpFhYG4GFUvVzKBn00/5phNWHvff1GDjzZz\nmVcRPje+rH6gGP8tpQn7NL' \
              b'1SvrazSqSOih//FfV73EMAEQEAAYkBNgQYAQgAIBYh\nBMwU+9636QKkbYsjdMKSn1VZ4I5DB' \
              b'QJals3sAhsMAAoJEMKSn1VZ4I5DshgIALSn\nLy7KL0bcqxoiEZT+P9O+gX34J2NEfITlu3MZ' \
              b'yN26LbyJS7HuN1vmuUc/UM0ff7AW\n6eElCNFr5HQOrFELUZWiX7f4U8ihRN39g1PKRGANlUc' \
              b'Lm1Z/JnKyYbyzRK70o5A3\n5EiXEHwY62c/b8I1N4kzNKpa0eQcJ7F8XoZhau0UsxqueVPeEI' \
              b'aHX+fjbalz67ea\niFTu8MurdGKntVE1dOPYbGvZE0+HxfDOoVo05bRUH8By7dDgVaI9EijrV' \
              b'zjA5jHP\nJxNIj9AQP9W8zst3l3d9v8o0Pw+L4cWzv+aBFakfjKGugs6lA53fB3RCfZ7OrMwC' \
              b'\nBvlTfDigK9X50K6XoP0=\n=6SRV\n-----END PGP PUBLIC KEY BLOCK-----\n'
ASCII_RAW_KEY = b'mQENBFqWzewBCADMHY8wL2Gm+aeShboOfG96/h/OJ8FHj+xrihPGY34FwLVqtvO+lRIO6t3' \
                b'w5y7O1MWzR1ePtQg1T1sg1s9UeoDRMZoVgzZdRXtQH1Jy9xpTeMfL31mlc3wOnitcH0AdWh' \
                b'T7xnnlaCeJuMrX82PWtiJNd+Cy+bgyLfLMwX18cimwYCnyIHQ54qiiywXa1paVHkbEJdbd8' \
                b'f4AxArsHX33xCv76wct2uXiHYAHu67rE5FhQ0mEqfIZHwuFljGPj5UMgyd6MRMuL2Ho1hL7' \
                b'FDPIxDBv5tMWeZJszixIsCkA9Kc1ibylDz9Ix/keH1K9XXSb/o2EIfF6sWYcj0wNvJllIHA' \
                b'fABEBAAG0QlJQTSBQYWNrYWdlciAoVGhlIGd1eSB3aG8gY3JlYXRlcyBwYWNrYWdlcykgPH' \
                b'BhY2thZ2VyQGV4YW1wbGUuY29tPokBTgQTAQgAOBYhBMwU+9636QKkbYsjdMKSn1VZ4I5DB' \
                b'QJals3sAhsDBQsJCAcCBhUKCQgLAgQWAgMBAh4BAheAAAoJEMKSn1VZ4I5D6icH/2GY2MMn' \
                b'mcDO+ApIF6gGg9itzAHLTNcxEMl9ht1Gu3JQ/VdsvMQ6lG+U8yffEmsfQebtt1UaMVXzyt0' \
                b'tcSOBJvVEI6qc6skvfea3hqL4srtTOCwu7ZBA9gOE+eB5BWBspFUVIwUO1GKT48uzV6CaOD' \
                b'Litaxc7NrJ9HYw4C4+ICCfbIJhjM/HqxLKOqVy/jsySqIHK96RrjY/m8Q9Bzsi/6fj/GHke' \
                b'waM8zaeNLHE7MgXFZAuJ8lzjD0r2oBDJGeBKfjjz9xh26YWjG/AoiolXfliTEox6p0bf820' \
                b'eRhdX9UdSesBROL3rkB+hM5FOT8crSPJsuGZWJ9brikfsurWyU+5AQ0EWpbN7AEIAK0/PTh' \
                b'uvsLdDGe5HeZn3VdrFcD9QSOV9Xjos8zWkwx8v0t4KXPM4GshyU2ddNjgA+00LhzjACm2ro' \
                b'pT5vdvKPtf8lRGOcWWHkiMPdDW/R3/I5S0Oh1WFNrQZwQSXn/DoPnhUZNGErpZlUzF00BEl' \
                b'twoVWgT1n81Bp486U3oziZnUM8kxXXY2PN8aTfWjsxOSmjyu2m7abeyjTqX9s++vUCQhmCN' \
                b'boSY1AhXF8GQl1CempHVv0hOuC6BeadZRXEfEF0sQogswXpFhYG4GFUvVzKBn00/5phNWHv' \
                b'ff1GDjzZzmVcRPje+rH6gGP8tpQn7NL1SvrazSqSOih//FfV73EMAEQEAAYkBNgQYAQgAIB' \
                b'YhBMwU+9636QKkbYsjdMKSn1VZ4I5DBQJals3sAhsMAAoJEMKSn1VZ4I5DshgIALSnLy7KL' \
                b'0bcqxoiEZT+P9O+gX34J2NEfITlu3MZyN26LbyJS7HuN1vmuUc/UM0ff7AW6eElCNFr5HQO' \
                b'rFELUZWiX7f4U8ihRN39g1PKRGANlUcLm1Z/JnKyYbyzRK70o5A35EiXEHwY62c/b8I1N4k' \
                b'zNKpa0eQcJ7F8XoZhau0UsxqueVPeEIaHX+fjbalz67eaiFTu8MurdGKntVE1dOPYbGvZE0' \
                b'+HxfDOoVo05bRUH8By7dDgVaI9EijrVzjA5jHPJxNIj9AQP9W8zst3l3d9v8o0Pw+L4cWzv' \
                b'+aBFakfjKGugs6lA53fB3RCfZ7OrMwCBvlTfDigK9X50K6XoP0='


class EmailToLocationTest(tests.support.TestCase):

    def test_convert_simple_email_to_domain(self):
        input = 'hugh@example.com'
        output = 'c93f1e400f26708f98cb19d936620da35eec8f72e57f9eec01c1afd6._openpgpkey.example.com'
        self.assertEqual(dnf.dnssec.email2location(input), output)


class KeyInfoTest(tests.support.TestCase):

    def test_key_info_from_rpm_key_object_email_part(self):
        key_info = dnf.dnssec.KeyInfo.from_rpm_key_object(RPM_USER, RPM_RAW_KEY)
        self.assertEqual(key_info.email, EMAIL)

    def test_key_info_from_rpm_key_object_key_part(self):
        key_info = dnf.dnssec.KeyInfo.from_rpm_key_object(RPM_USER, RPM_RAW_KEY)
        self.assertEqual(key_info.key, ASCII_RAW_KEY)
