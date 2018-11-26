# dnssec.py
# DNS extension for automatic GPG key verification
#
# Copyright (C) 2012-2018 Red Hat, Inc.
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

from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

from enum import Enum
import base64
import hashlib
import logging
import re

from dnf.i18n import _
import dnf.rpm.transaction
import dnf.exceptions

logger = logging.getLogger("dnf")


RR_TYPE_OPENPGPKEY = 61


class DnssecError(dnf.exceptions.Error):
    """
    Exception used in the dnssec module
    """
    def __repr__(self):
        return "<DnssecError, value='{}'>"\
            .format(self.value if self.value is not None else "Not specified")


def email2location(email_address, tag="_openpgpkey"):
    # type: (str, str) -> str
    """
    Implements RFC 7929, section 3
    https://tools.ietf.org/html/rfc7929#section-3
    :param email_address:
    :param tag:
    :return:
    """
    split = email_address.split("@")
    if len(split) != 2:
        msg = "Email address should contain exactly one '@' sign."
        logger.error(msg)
        raise DnssecError(msg)

    local = split[0]
    domain = split[1]
    hash = hashlib.sha256()
    hash.update(local.encode('utf-8'))
    digest = base64.b16encode(hash.digest()[0:28])\
        .decode("utf-8")\
        .lower()
    return digest + "." + tag + "." + domain


class Validity(Enum):
    """
    Output of the verification algorithm.
    TODO: this type might be simplified in order to less reflect the underlying DNS layer.
    TODO: more specifically the variants from 3 to 5 should have more understandable names
    """
    VALID = 1
    REVOKED = 2
    PROVEN_NONEXISTENCE = 3
    RESULT_NOT_SECURE = 4
    BOGUS_RESULT = 5
    ERROR = 9


class NoKey:
    """
    This class represents an absence of a key in the cache. It is an expression of non-existence
    using the Python's type system.
    """
    pass


class KeyInfo:
    """
    Wrapper class for email and associated verification key, where both are represented in
    form of a string.
    """
    def __init__(self, email=None, key=None):
        self.email = email
        self.key = key

    @staticmethod
    def from_rpm_key_object(userid, raw_key):
        # type: (str, bytes) -> KeyInfo
        """
        Since dnf uses different format of the key than the one used in DNS RR, I need to convert
        the former one into the new one.
        """
        input_email = re.search('<(.*@.*)>', userid)
        if input_email is None:
            raise DnssecError

        email = input_email.group(1)
        key = raw_key.decode('ascii').split('\n')

        start = 0
        stop = 0
        for i in range(0, len(key)):
            if key[i] == '-----BEGIN PGP PUBLIC KEY BLOCK-----':
                start = i
            if key[i] == '-----END PGP PUBLIC KEY BLOCK-----':
                stop = i

        cat_key = ''.join(key[start + 2:stop - 1]).encode('ascii')
        return KeyInfo(email, cat_key)


class DNSSECKeyVerification:
    """
    The main class when it comes to verification itself. It wraps Unbound context and a cache with
    already obtained results.
    """

    # Mapping from email address to b64 encoded public key or NoKey in case of proven nonexistence
    _cache = {}
    # type: Dict[str, Union[str, NoKey]]

    @staticmethod
    def _cache_hit(key_union, input_key_string):
        # type: (Union[str, NoKey], str) -> Validity
        """
        Compare the key in case it was found in the cache.
        """
        if key_union == input_key_string:
            logger.debug("Cache hit, valid key")
            return Validity.VALID
        elif key_union is NoKey:
            logger.debug("Cache hit, proven non-existence")
            return Validity.PROVEN_NONEXISTENCE
        else:
            logger.debug("Key in cache: {}".format(key_union))
            logger.debug("Input key   : {}".format(input_key_string))
            return Validity.REVOKED

    @staticmethod
    def _cache_miss(input_key):
        # type: (KeyInfo) -> Validity
        """
        In case the key was not found in the cache, create an Unbound context and contact the DNS
        system
        """
        try:
            import unbound
        except ImportError as e:
            raise RuntimeError("Configuration option 'gpgkey_dns_verification' requires\
            libunbound ({})".format(e))

        ctx = unbound.ub_ctx()
        if ctx.set_option("verbosity:", "0") != 0:
            logger.debug("Unbound context: Failed to set verbosity")

        if ctx.set_option("qname-minimisation:", "yes") != 0:
            logger.debug("Unbound context: Failed to set qname minimisation")

        if ctx.resolvconf() != 0:
            logger.debug("Unbound context: Failed to read resolv.conf")

        if ctx.add_ta_file("/var/lib/unbound/root.key") != 0:
            logger.debug("Unbound context: Failed to add trust anchor file")

        status, result = ctx.resolve(email2location(input_key.email),
                                     RR_TYPE_OPENPGPKEY, unbound.RR_CLASS_IN)
        if status != 0:
            logger.debug("Communication with DNS servers failed")
            return Validity.ERROR
        if result.bogus:
            logger.debug("DNSSEC signatures are wrong")
            return Validity.BOGUS_RESULT
        if not result.secure:
            logger.debug("Result is not secured with DNSSEC")
            return Validity.RESULT_NOT_SECURE
        if result.nxdomain:
            logger.debug("Non-existence of this record was proven by DNSSEC")
            return Validity.PROVEN_NONEXISTENCE
        if not result.havedata:
            # TODO: This is weird result, but there is no way to perform validation, so just return
            # an error
            logger.debug("Unknown error in DNS communication")
            return Validity.ERROR
        else:
            data = result.data.as_raw_data()[0]
            dns_data_b64 = base64.b64encode(data)
            if dns_data_b64 == input_key.key:
                return Validity.VALID
            else:
                # In case it is different, print the keys for further examination in debug mode
                logger.debug("Key from DNS: {}".format(dns_data_b64))
                logger.debug("Input key   : {}".format(input_key.key))
                return Validity.REVOKED

    @staticmethod
    def verify(input_key):
        # type: (KeyInfo) -> Validity
        """
        Public API. Use this method to verify a KeyInfo object.
        """
        logger.debug("Running verification for key with id: {}".format(input_key.email))
        key_union = DNSSECKeyVerification._cache.get(input_key.email)
        if key_union is not None:
            return DNSSECKeyVerification._cache_hit(key_union, input_key.key)
        else:
            result = DNSSECKeyVerification._cache_miss(input_key)
            if result == Validity.VALID:
                DNSSECKeyVerification._cache[input_key.email] = input_key.key
            elif result == Validity.PROVEN_NONEXISTENCE:
                DNSSECKeyVerification._cache[input_key.email] = NoKey()
            return result


def nice_user_msg(ki, v):
    # type: (KeyInfo, Validity) -> str
    """
    Inform the user about key validity in a human readable way.
    """
    prefix = _("DNSSEC extension: Key for user ") + ki.email + " "
    if v == Validity.VALID:
        return prefix + _("is valid.")
    else:
        return prefix + _("has unknown status.")


def any_msg(m):
    # type: (str) -> str
    """
    Label any given message with DNSSEC extension tag
    """
    return _("DNSSEC extension: ") + m


class RpmImportedKeys:
    """
    Wrapper around keys, that are imported in the RPM database.

    The keys are stored in packages with name gpg-pubkey, where the version and
    release is different for each of them. The key content itself is stored as
    an ASCII armored string in the package description, so it needs to be parsed
    before it can be used.
    """
    @staticmethod
    def _query_db_for_gpg_keys():
        # type: () -> List[KeyInfo]
        # TODO: base.conf.installroot ?? -----------------------\
        transaction_set = dnf.rpm.transaction.TransactionWrapper()
        packages = transaction_set.dbMatch("name", "gpg-pubkey")
        return_list = []
        for pkg in packages:
            packager = pkg['packager'].decode('ascii')
            email = re.search('<(.*@.*)>', packager).group(1)
            description = pkg['description']
            key_lines = description.decode('ascii').split('\n')[3:-3]
            key_str = ''.join(key_lines)
            return_list += [KeyInfo(email, key_str.encode('ascii'))]

        return return_list

    @staticmethod
    def check_imported_keys_validity():
        keys = RpmImportedKeys._query_db_for_gpg_keys()
        logger.info(any_msg(_("Testing already imported keys for their validity.")))
        for key in keys:
            try:
                result = DNSSECKeyVerification.verify(key)
            except DnssecError as e:
                # Errors in this exception should not be fatal, print it and just continue
                logger.exception("Exception raised in DNSSEC extension: email={}, exception={}"
                                 .format(key.email, repr(e)))
                continue
            # TODO: remove revoked keys automatically and possibly ask user to confirm
            if result == Validity.VALID:
                logger.debug(any_msg("GPG Key {} is valid".format(key.email)))
                pass
            elif result == Validity.PROVEN_NONEXISTENCE:
                logger.debug(any_msg("GPG Key {} does not support DNS"
                                    " verification".format(key.email)))
            elif result == Validity.BOGUS_RESULT:
                logger.info(any_msg("GPG Key {} could not be verified, because DNSSEC signatures"
                                    " are bogus. Possible causes: wrong configuration of the DNS"
                                    " server, MITM attack".format(key.email)))
            elif result == Validity.REVOKED:
                logger.info(any_msg("GPG Key {} has been revoked and should"
                                    " be removed immediately".format(key.email)))
            else:
                logger.debug(any_msg("GPG Key {} could not be tested".format(key.email)))
