#! /usr/bin/python -tt
##Copyright (C) 2003,2005,2009  Jens B. Jorgensen <jbj1@ultraemail.net>
##
##This program is free software; you can redistribute it and/or
##modify it under the terms of the GNU General Public License
##as published by the Free Software Foundation; either version 2
##of the License, or (at your option) any later version.
##
##This program is distributed in the hope that it will be useful,
##but WITHOUT ANY WARRANTY; without even the implied warranty of
##MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##GNU General Public License for more details.
##
##You should have received a copy of the GNU General Public License
##along with this program; if not, write to the Free Software
##Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
import struct, time, cStringIO, base64, types

#  We use this so that we can work on python-2.4 and python-2.6, and thus.
# use import md5/import sha on the older one and import hashlib on the newer.
#  Stupid deprecation warnings.

# pylint: disable-msg=W0108 
# Ignore :W0108: *Lambda may not be necessary*


try:
    import hashlib
except ImportError:
    # Python-2.4.z ... gah!
    import sha
    import md5
    class hashlib:

        @staticmethod
        def new(algo):
            if algo == 'md5':
                return md5.new()
            if algo == 'sha1':
                return sha.new()
            raise ValueError, "Bad checksum type"

debug = None

# Cypher Type Byte
# bits 7,6 of the CTB say what kind it is
# we only have reserved defined
CTB_76_NORMAL = 0x80
CTB_76_NEW = 0xc0
CTB_76_MASK = 0xc0

# CTB packet type, bits 5,4,3,2
CTB_PKTV2_MASK = 0x3c    # 1111 - mask for this field
CTB_PKT_MASK = 0x3f      # 111111 - all the lower bits

CTB_PKT_PK_ENC = 1       # 0001 - public-key encrypted session packet
CTB_PKT_SIG = 2          # 0010 - signature packet
CTB_PKT_SK_ENC = 3       # 0011 - symmetric-key encrypted session packet
CTB_PKT_OP_SIG = 4       # 0100 - one-pass signature packet
CTB_PKT_SK_CERT = 5      # 0101 - secret-key certificate packet
CTB_PKT_PK_CERT = 6      # 0110 - public-key certificate packet
CTB_PKT_SK_SUB = 7       # 0111 - secret-key subkey packet
CTB_PKT_COMPRESSED = 8   # 1000 - compressed data packet
CTB_PKT_ENC = 9          # 1001 - symmetric-key encrypted data packet
CTB_PKT_MARKER = 10      # 1010 - marker packet
CTB_PKT_LIT = 11         # 1011 - literal data packet
CTB_PKT_TRUST = 12       # 1100 - trust packet
CTB_PKT_USER_ID = 13     # 1101 - user id packet
CTB_PKT_PK_SUB = 14      # 1110 - public subkey packet
CTB_PKT_USER_ATTR = 17   # 10001 - user attribute packet
CTB_PKT_SYM_ENC_INT = 18 # 10010 - symmetric encrypted integrity packet
CTB_PKT_MOD_DETECT = 19  # 10011 - modification detection code packet

ctb_pkt_to_str = {
    CTB_PKT_PK_ENC : 'public-key encrypted session packet',
    CTB_PKT_SIG : 'signature packet',
    CTB_PKT_SK_ENC : 'symmetric-key encrypted session packet',
    CTB_PKT_OP_SIG : 'one-pass signature packet',
    CTB_PKT_SK_CERT : 'secret-key certificate packet',
    CTB_PKT_PK_CERT : 'public-key certificate packet',
    CTB_PKT_SK_SUB : 'secret-key subkey packet',
    CTB_PKT_COMPRESSED : 'compressed data packet',
    CTB_PKT_ENC : 'symmetric-key encrypted data packet',
    CTB_PKT_MARKER : 'marker packet',
    CTB_PKT_LIT : 'literal data packet',
    CTB_PKT_TRUST : 'trust packet',
    CTB_PKT_USER_ID : 'user id packet',
    CTB_PKT_PK_SUB : 'public subkey packet',
    CTB_PKT_USER_ATTR : 'user attribute packet',
    CTB_PKT_SYM_ENC_INT : 'symmetric encrypted integrity packet',
    CTB_PKT_MOD_DETECT : 'modification detection code packet'
}


# CTB packet-length
CTB_PKT_LEN_MASK = 0x3   # 11 - mask

CTB_PKT_LEN_1 = 0        # 00 - 1 byte
CTB_PKT_LEN_2 = 1        # 01 - 2 bytes
CTB_PKT_LEN_4 = 2        # 10 - 4 bytes
CTB_PKT_LEN_UNDEF = 3    # 11 - no packet length supplied

# Algorithms

# Public Key Algorithms
ALGO_PK_RSA_ENC_OR_SIGN = 1        # RSA (Encrypt or Sign)
ALGO_PK_RSA_ENC_ONLY = 2           # RSA Encrypt-Only
ALGO_PK_RSA_SIGN_ONLY = 3          # RSA Sign-Only
ALGO_PK_ELGAMAL_ENC_ONLY = 16      # Elgamal (Encrypt-Only)
ALGO_PK_DSA = 17                   # DSA (Digital Signature Standard)
ALGO_PK_ELLIPTIC_CURVE = 18        # Elliptic Curve
ALGO_PK_ECDSA = 19                 # ECDSA
ALGO_PK_ELGAMAL_ENC_OR_SIGN = 20   # Elgamal (Encrypt or Sign)
ALGO_PK_DH = 21                    # Diffie-Hellman

algo_pk_to_str = {
    ALGO_PK_RSA_ENC_OR_SIGN : 'RSA (Encrypt or Sign)',
    ALGO_PK_RSA_ENC_ONLY : 'RSA Encrypt-Only',
    ALGO_PK_RSA_SIGN_ONLY : 'RSA Sign-Only',
    ALGO_PK_ELGAMAL_ENC_ONLY : 'Elgamal Encrypt-Only',
    ALGO_PK_DSA : 'DSA (Digital Signature Standard)',
    ALGO_PK_ELLIPTIC_CURVE : 'Elliptic Curve',
    ALGO_PK_ECDSA : 'ECDSA',
    ALGO_PK_ELGAMAL_ENC_OR_SIGN : 'Elgamal (Encrypt or Sign)',
    ALGO_PK_DH : 'Diffie-Hellman'
}    

# Symmetric Key Algorithms
ALGO_SK_PLAIN = 0 # Plaintext or unencrypted data
ALGO_SK_IDEA = 1 # IDEA
ALGO_SK_3DES = 2 # Triple-DES
ALGO_SK_CAST5 = 3 # CAST5
ALGO_SK_BLOWFISH = 4 # Blowfish
ALGO_SK_SAFER_SK128 = 5 # SAFER-SK128
ALGO_SK_DES_SK = 6 # DES/SK
ALGO_SK_AES_128 = 7 # AES 128-bit
ALGO_SK_AES_192 = 8 # AES 192-bit
ALGO_SK_AES_256 = 9 # AES 256-bit
ALGO_SK_TWOFISH_256 = 10 # Twofish 256

algo_sk_to_str = {
    ALGO_SK_PLAIN : 'Plaintext or unencrypted data',
    ALGO_SK_IDEA : 'IDEA',
    ALGO_SK_3DES : 'Triple-DES',
    ALGO_SK_CAST5 : 'CAST5',
    ALGO_SK_BLOWFISH : 'Blowfish',
    ALGO_SK_SAFER_SK128 : 'SAFER-SK128',
    ALGO_SK_DES_SK : 'DES/SK',
    ALGO_SK_AES_128 : 'AES 128-bit',
    ALGO_SK_AES_192 : 'AES 192-bit',
    ALGO_SK_AES_256 : 'AES 256-bit',
    ALGO_SK_TWOFISH_256 : 'Twofish 256-bit'
}

# Compression Algorithms
ALGO_COMP_UNCOMP = 0 # Uncompressed
ALGO_COMP_ZIP = 1    # ZIP
ALGO_COMP_ZLIB = 2   # ZLIB
ALGO_COMP_BZIP2 = 3  # BZip2

algo_comp_to_str = {
    ALGO_COMP_UNCOMP : 'Uncompressed',
    ALGO_COMP_ZIP : 'ZIP',
    ALGO_COMP_ZLIB : 'ZLIB',
    ALGO_COMP_BZIP2 : 'BZip2'
}

# Hash Algorithms
ALGO_HASH_MD5 = 1                  # MD5
ALGO_HASH_SHA1 = 2                 # SHA1
ALGO_HASH_RIPEMD160 = 3            # RIPEMD160
ALGO_HASH_SHA_DBL = 4              # double-width SHA
ALGO_HASH_MD2 = 5                  # MD2
ALGO_HASH_TIGER192 = 6             # TIGER192
ALGO_HASH_HAVAL_5_160 = 7          # HAVAL-5-160
ALGO_HASH_SHA256 = 8               # SHA256
ALGO_HASH_SHA384 = 9               # SHA384
ALGO_HASH_SHA512 = 10              # SHA512
ALGO_HASH_SHA224 = 11              # SHA224

algo_hash_to_str = {
    ALGO_HASH_MD5 : 'MD5',
    ALGO_HASH_SHA1 : 'SHA1',
    ALGO_HASH_RIPEMD160 : 'RIPEMD160',
    ALGO_HASH_SHA_DBL : 'double-width SHA',
    ALGO_HASH_MD2 : 'MD2',
    ALGO_HASH_TIGER192 : 'TIGER192',
    ALGO_HASH_HAVAL_5_160 : 'HAVAL-5-160',
    ALGO_HASH_SHA256 : 'SHA256',
    ALGO_HASH_SHA384 : 'SHA384',
    ALGO_HASH_SHA512 : 'SHA512',
    ALGO_HASH_SHA224 : 'SHA224'
}

# Signature types
SIG_TYPE_DOCUMENT = 0x00           # document signature, binary image
SIG_TYPE_DOCUMENT_CANON = 0x01     # document signature, canonical text
SIG_TYPE_STANDALONE = 0x02         # signature over just subpackets
SIG_TYPE_PK_USER_GEN = 0x10        # public key packet and user ID packet, generic certification
SIG_TYPE_PK_USER_PER = 0x11        # public key packet and user ID packet, persona
SIG_TYPE_PK_USER_CAS = 0x12        # public key packet and user ID packet, casual certification
SIG_TYPE_PK_USER_POS = 0x13        # public key packet and user ID packet, positive certification
SIG_TYPE_SUBKEY_BIND = 0x18        # subkey binding
SIG_TYPE_KEY = 0x1F                # key signature
SIG_TYPE_KEY_REVOKE = 0x20      # key revocation
SIG_TYPE_SUBKEY_REVOKE = 0x28   # subkey revocation
SIG_TYPE_CERT_REVOKE = 0x30     # certificate revocation
SIG_TYPE_TIMESTAMP = 0x40       # timestamp

sig_type_to_str = {
    SIG_TYPE_DOCUMENT : 'document signature, binary image',
    SIG_TYPE_DOCUMENT_CANON : 'document signature, canonical text',
    SIG_TYPE_STANDALONE : 'signature over just subpackets',
    SIG_TYPE_PK_USER_GEN : 'public key packet and user ID packet, generic certification',
    SIG_TYPE_PK_USER_PER : 'public key packet and user ID packet, persona',
    SIG_TYPE_PK_USER_CAS : 'public key packet and user ID packet, casual certification',
    SIG_TYPE_PK_USER_POS : 'public key packet and user ID packet, positive certification',
    SIG_TYPE_SUBKEY_BIND : 'subkey binding',
    SIG_TYPE_KEY : 'key signature',
    SIG_TYPE_KEY_REVOKE : 'key revocation',
    SIG_TYPE_SUBKEY_REVOKE : 'subkey revocation',
    SIG_TYPE_CERT_REVOKE : 'certificate revocation',
    SIG_TYPE_TIMESTAMP : 'timestamp'
}

# Signature sub-packet types
SIG_SUB_TYPE_CREATE_TIME = 2        # signature creation time
SIG_SUB_TYPE_EXPIRE_TIME = 3        # signature expiration time
SIG_SUB_TYPE_EXPORT_CERT = 4        # exportable certification
SIG_SUB_TYPE_TRUST_SIG = 5          # trust signature
SIG_SUB_TYPE_REGEXP = 6             # regular expression
SIG_SUB_TYPE_REVOCABLE = 7          # revocable
SIG_SUB_TYPE_KEY_EXPIRE = 9         # key expiration time
SIG_SUB_TYPE_PLACEHOLDER = 10       # placeholder for backward compatibility
SIG_SUB_TYPE_PREF_SYMM_ALGO = 11    # preferred symmetric algorithms
SIG_SUB_TYPE_REVOKE_KEY = 12        # revocation key
SIG_SUB_TYPE_ISSUER_KEY_ID = 16     # issuer key ID
SIG_SUB_TYPE_NOTATION = 20          # notation data
SIG_SUB_TYPE_PREF_HASH_ALGO = 21    # preferred hash algorithms
SIG_SUB_TYPE_PREF_COMP_ALGO = 22    # preferred compression algorithms
SIG_SUB_TYPE_KEY_SRV_PREF = 23      # key server preferences
SIG_SUB_TYPE_PREF_KEY_SRVR = 24     # preferred key server
SIG_SUB_TYPE_PRIM_USER_ID = 25      # primary user id
SIG_SUB_TYPE_POLICY_URI = 26        # policy URI
SIG_SUB_TYPE_KEY_FLAGS = 27         # key flags
SIG_SUB_TYPE_SGNR_USER_ID = 28      # signer's user id
SIG_SUB_TYPE_REVOKE_REASON = 29     # reason for revocation
SIG_SUB_TYPE_FEATURES = 30          # features
SIG_SUB_TYPE_SIG_TARGET = 31        # signature target
SIG_SUB_TYPE_EMBEDDED_SIG = 32      # embedded signature

sig_sub_type_to_str = {
    SIG_SUB_TYPE_CREATE_TIME : 'signature creation time',
    SIG_SUB_TYPE_EXPIRE_TIME : 'signature expiration time',
    SIG_SUB_TYPE_EXPORT_CERT : 'exportable certification',
    SIG_SUB_TYPE_TRUST_SIG : 'trust signature',
    SIG_SUB_TYPE_REGEXP : 'regular expression',
    SIG_SUB_TYPE_REVOCABLE : 'revocable',
    SIG_SUB_TYPE_KEY_EXPIRE : 'key expiration time',
    SIG_SUB_TYPE_PLACEHOLDER : 'placeholder for backward compatibility',
    SIG_SUB_TYPE_PREF_SYMM_ALGO : 'preferred symmetric algorithms',
    SIG_SUB_TYPE_REVOKE_KEY : 'revocation key',
    SIG_SUB_TYPE_ISSUER_KEY_ID : 'issuer key ID',
    SIG_SUB_TYPE_NOTATION : 'notation data',
    SIG_SUB_TYPE_PREF_HASH_ALGO : 'preferred hash algorithms',
    SIG_SUB_TYPE_PREF_COMP_ALGO : 'preferred compression algorithms',
    SIG_SUB_TYPE_KEY_SRV_PREF : 'key server preferences',
    SIG_SUB_TYPE_PREF_KEY_SRVR : 'preferred key server',
    SIG_SUB_TYPE_PRIM_USER_ID : 'primary user id',
    SIG_SUB_TYPE_POLICY_URI : 'policy URI',
    SIG_SUB_TYPE_KEY_FLAGS : 'key flags',
    SIG_SUB_TYPE_SGNR_USER_ID : "signer's user id",
    SIG_SUB_TYPE_REVOKE_REASON : 'reason for revocation',
    SIG_SUB_TYPE_FEATURES : 'features',
    SIG_SUB_TYPE_SIG_TARGET : 'signature target',
    SIG_SUB_TYPE_EMBEDDED_SIG : 'embedded signature'
}

# in a signature subpacket there may be a revocation reason, these codes indicate
# the reason
REVOKE_REASON_NONE = 0              # No reason specified
REVOKE_REASON_SUPER = 0x01          # Key is superceded
REVOKE_REASON_COMPR = 0x02          # Key has been compromised
REVOKE_REASON_NOT_USED = 0x03       # Key is no longer used
REVOKE_REASON_ID_INVALID = 0x20     # user id information is no longer valid

revoke_reason_to_str = {
    REVOKE_REASON_NONE : 'No reason specified',
    REVOKE_REASON_SUPER : 'Key is superceded',
    REVOKE_REASON_COMPR : 'Key has been compromised',
    REVOKE_REASON_NOT_USED : 'Key is no longer used',
    REVOKE_REASON_ID_INVALID : 'user id information is no longer valid'
}

# These flags are used in a 'key flags' signature subpacket
KEY_FLAGS1_MAY_CERTIFY = 0x01 # This key may be used to certify other keys
KEY_FLAGS1_MAY_SIGN = 0x02 # This key may be used to sign data
KEY_FLAGS1_MAY_ENC_COMM = 0x04 # This key may be used to encrypt communications
KEY_FLAGS1_MAY_ENC_STRG = 0x08 # This key may be used to encrypt storage
KEY_FLAGS1_PRIV_MAYBE_SPLIT = 0x10 # Private component have be split through secret-sharing mech.
KEY_FLAGS1_GROUP = 0x80 # Private component may be among group

# A revocation key subpacket has these class values
REVOKE_KEY_CLASS_MAND = 0x80 # this bit must always be set
REVOKE_KEY_CLASS_SENS = 0x40 # sensitive

# Features may be indicated in a signature hashed subpacket
PGP_FEATURE_1_MOD_DETECT = 0x01 # Modification detection

pgp_feature_to_str = {
    PGP_FEATURE_1_MOD_DETECT : 'Modification Detection'
}

def get_whole_number(msg, idx, numlen) :
    """get_whole_number(msg, idx, numlen)
extracts a "whole number" field of length numlen from msg at index idx
returns (<whole number>, new_idx) where the whole number is a long integer
and new_idx is the index of the next element in the message"""
    n = 0L 
    while numlen > 0 :
        b = (struct.unpack("B", msg[idx:idx+1]))[0]
        n = n * 256L + long(b)
        idx = idx + 1
        numlen = numlen - 1
    return (n, idx)

def get_whole_int(msg, idx, numlen) :
    """get_whole_int(msg, idx, numlen)
same as get_whole_number but returns the number as an int for convenience"""
    n, idx = get_whole_number(msg, idx, numlen)
    return int(n), idx

def pack_long(l) :
    """pack_long(l)
    returns big-endian representation of unsigned long integer"""
    arr = []
    while l > 0 :
        arr.insert(0, struct.pack("B", l & 0xff))
        l >>= 8
    return ''.join(arr)
    
def pack_mpi(l) :
    """pack_mpi(l)
    returns the PGP Multi-Precision Integer representation of unsigned long integer"""
    s = pack_long(l)
    # the len is the number of bits, counting only from the MSB,
    # so we need to account for that
    bits = (len(s) - 1) * 8
    if len(s) > 0 :
        n = ord(s[0])
        while n != 0 :
            bits += 1
            n >>= 1
    else :
        bits = 0 # otherwise bits == -8
    return struct.pack(">H", bits) + s

def get_sig_subpak_len(msg, idx) :
    """get_sig_subpak_len(msg, idx)
extracts a signature subpacket length field
returns (subpak_len, new_idx)"""
    plen, idx = get_whole_int(msg, idx, 1)
    if plen < 192 :
        return plen, idx
    if plen < 255 :
        plen2, idx = get_whole_int(msg, idx, 1)
        return ((plen - 192) << 8) + plen2 + 192, idx
    return get_whole_int(msg, idx, 4)

def get_n_mpi(msg, idx) :
    """get_mpi(msg, idx)
    extracts a multi-precision integer field from the message msg at index idx
    returns (n, <mpi>, new_idx) where the mpi is a long integer and new_idx is
    the index of the next element in the message and n is the number of bits of
    precision in <mpi>"""
    ln, idx = get_whole_int(msg, idx, 2)
    return (ln,) + get_whole_number(msg, idx, (ln+7)/8)

def get_mpi(msg, idx) :
    """get_mpi(msg, idx)
extracts a multi-precision integer field from the message msg at index idx
returns (<mpi>, new_idx) where the mpi is a long integer and new_idx is
the index of the next element in the message"""
    l = get_n_mpi(msg, idx)
    return (l[1], l[2])

def str_to_hex(s) :
    return ''.join(map(lambda x : hex(ord(x))[2:].zfill(2), list(s)))

def duration_to_str(s) :
    if s == 0 :
        return 'never'
    secs = s % 60
    s = s / 60
    mins = s % 60
    s = s / 60
    hrs = s % 60
    s = s / 24
    days = s
    return '%d days %02d:%02d:%02d' % (days, hrs, mins, secs)

def map_to_str(m, vals) :
    slist = []
    # change to a list if it's a single value
    if type(vals) != types.ListType and type(vals) != types.TupleType :
        vals = list((vals,))
    for i in vals :
        if i in m :
            slist.append(m[i])
        else :
            slist.append('unknown(' + str(i) + ')')
    return ', '.join(slist)

class pgp_packet(object) :
    def __init__(self) :
        self.pkt_typ = None

    def __str__(self) :
        return map_to_str(ctb_pkt_to_str, self.pkt_typ)

class public_key(pgp_packet) :
    def __init__(self) :
        pgp_packet.__init__(self)
        self.version = None
        self.pk_algo = None
        self.key_size = 0
        self.fingerprint_ = None # we cache this upon calculation

    def fingerprint(self) :
        # return cached value if we have it
        if self.fingerprint_ :
            return self.fingerprint_
        
        # otherwise calculate it now and cache it
        # v3 and v4 are calculated differently
        if self.version == 3 :
            h = hashlib.new('md5')
            h.update(pack_long(self.pk_rsa_mod))
            h.update(pack_long(self.pk_rsa_exp))
            self.fingerprint_ = h.digest()
        elif self.version == 4 :
            # we hash what would be the whole PGP message containing
            # the pgp certificate
            h = hashlib.new('sha1')
            h.update('\x99')
            # we need to has the length of the packet as well
            buf = self.serialize()
            h.update(struct.pack(">H", len(buf)))
            h.update(buf)
            self.fingerprint_ = h.digest()
        else :
            raise RuntimeError("unknown public key version %d" % self.version)
        return self.fingerprint_

    def key_id(self) :
        if self.version == 3 :
            return pack_long(self.pk_rsa_mod & 0xffffffffffffffffL)
        elif self.version == 4 :
            return self.fingerprint()[-8:]

    def serialize(self) :
        chunks = []
        if self.version == 3 :
            chunks.append(struct.pack('>BIHB', self.version, int(self.timestamp), self.validity, self.pk_algo))
            chunks.append(pack_mpi(self.pk_rsa_mod))
            chunks.append(pack_mpi(self.pk_rsa_exp))
        elif self.version == 4 :
            chunks.append(struct.pack('>BIB', self.version, int(self.timestamp), self.pk_algo))
            if self.pk_algo == ALGO_PK_RSA_ENC_OR_SIGN or self.pk_algo == ALGO_PK_RSA_SIGN_ONLY :
                chunks.append(pack_mpi(self.pk_rsa_mod))
                chunks.append(pack_mpi(self.pk_rsa_exp))
            elif self.pk_algo == ALGO_PK_DSA :
                chunks.append(pack_mpi(self.pk_dsa_prime_p))
                chunks.append(pack_mpi(self.pk_dsa_grp_ord_q))
                chunks.append(pack_mpi(self.pk_dsa_grp_gen_g))
                chunks.append(pack_mpi(self.pk_dsa_pub_key))
            elif self.pk_algo == ALGO_PK_ELGAMAL_ENC_OR_SIGN or self.pk_algo == ALGO_PK_ELGAMAL_ENC_ONLY :
                chunks.append(pack_mpi(self.pk_elgamal_prime_p))
                chunks.append(pack_mpi(self.pk_elgamal_grp_gen_g))
                chunks.append(pack_mpi(self.pk_elgamal_pub_key))
            else :
                raise RuntimeError("unknown public key algorithm %d" % (self.pk_algo))
        return ''.join(chunks)
    
    def deserialize(self, msg, idx, pkt_len) :
        idx_save = idx
        self.version, idx = get_whole_int(msg, idx, 1)
        if self.version != 2 and self.version != 3 and self.version != 4 :
            raise RuntimeError('unknown public key packet version %d at %d' % (self.version, idx_save))
        if self.version == 2 : # map v2 into v3 for coding simplicity since they're structurally the same
            self.version = 3
        self.timestamp, idx = get_whole_number(msg, idx, 4)
        self.timestamp = float(self.timestamp)
        if self.version == 3 :
            self.validity, idx = get_whole_number(msg, idx, 2)
        self.pk_algo, idx = get_whole_int(msg, idx, 1)
        if self.pk_algo == ALGO_PK_RSA_ENC_OR_SIGN or self.pk_algo == ALGO_PK_RSA_SIGN_ONLY :
            self.key_size, self.pk_rsa_mod, idx = get_n_mpi(msg, idx)
            self.pk_rsa_exp, idx = get_mpi(msg, idx)
        elif self.pk_algo == ALGO_PK_DSA :
            l1, self.pk_dsa_prime_p, idx = get_n_mpi(msg, idx)
            self.pk_dsa_grp_ord_q, idx = get_mpi(msg, idx)
            self.pk_dsa_grp_gen_g, idx = get_mpi(msg, idx)
            l2, self.pk_dsa_pub_key, idx = get_n_mpi(msg, idx)
            self.key_size = l1 + l2
        elif self.pk_algo == ALGO_PK_ELGAMAL_ENC_OR_SIGN or self.pk_algo == ALGO_PK_ELGAMAL_ENC_ONLY :
            self.key_size, self.pk_elgamal_prime_p, idx = get_n_mpi(msg, idx)
            self.pk_elgamal_grp_gen_g, idx = get_mpi(msg, idx)
            self.pk_elgamal_pub_key, idx = get_mpi(msg, idx)
        else :
            raise RuntimeError("unknown public key algorithm %d at %d" % (self.pk_algo, idx_save))

    def __str__(self) :
        sio = cStringIO.StringIO()
        sio.write(pgp_packet.__str__(self) + "\n")
        sio.write("version: " + str(self.version) + "\n")
        sio.write("timestamp: " + time.ctime(self.timestamp) + "\n")
        if self.version == 3 :
            sio.write("validity: " + time.ctime(self.timestamp + self.validity * 24 * 60 * 60) + "\n")
        sio.write("pubkey algo: " + algo_pk_to_str[self.pk_algo] + "\n")
        if self.pk_algo == ALGO_PK_RSA_ENC_OR_SIGN or self.pk_algo == ALGO_PK_RSA_SIGN_ONLY :
            sio.write("pk_rsa_mod: " + hex(self.pk_rsa_mod) + "\n")
            sio.write("pk_rsa_exp: " + hex(self.pk_rsa_exp) + "\n")
        elif self.pk_algo == ALGO_PK_DSA :
            sio.write("pk_dsa_prime_p: " + hex(self.pk_dsa_prime_p) + "\n")
            sio.write("pk_dsa_grp_ord_q: " + hex(self.pk_dsa_grp_ord_q) + "\n")
            sio.write("pk_dsa_grp_gen_g: " + hex(self.pk_dsa_grp_gen_g) + "\n")
            sio.write("pk_dsa_pub_key: " + hex(self.pk_dsa_pub_key) + "\n")
        elif self.pk_algo == ALGO_PK_ELGAMAL_ENC_OR_SIGN or self.pk_algo == ALGO_PK_ELGAMAL_ENC_ONLY :
            sio.write("pk_elgamal_prime_p: " + hex(self.pk_elgamal_prime_p) + "\n")
            sio.write("pk_elgamal_grp_gen_g: " + hex(self.pk_elgamal_grp_gen_g) + "\n")
            sio.write("pk_elgamal_pub_key: " + hex(self.pk_elgamal_pub_key) + "\n")
        return sio.getvalue()

class user_id(pgp_packet) :
    def __init__(self) :
        pgp_packet.__init__(self)
        self.id = None

    def deserialize(self, msg, idx, pkt_len) :
        self.id = msg[idx:idx + pkt_len]

    def __str__(self) :
        return pgp_packet.__str__(self) + "\n" + "id: " + self.id + "\n"

class user_attribute(pgp_packet) :
    def __init__(self) :
        pgp_packet.__init__(self)
        self.sub_type = None
        self.data = None

    def deserialize(self, msg, idx, pkt_len) :
        self.sub_type, idx = get_whole_int(msg, idx, 1)
        pkt_len = pkt_len - 1
        self.data = msg[idx:idx + pkt_len]

    def __str__(self) :
        return pgp_packet.__str__(self) + "\n" + "sub_type: " + str(self.sub_type) + "\ndata: " + str_to_hex(self.data)

class signature(pgp_packet) :
    def __init__(self) :
        pgp_packet.__init__(self)
        self.version = None
        self.sig_type = None
        self.pk_algo = None
        self.hash_algo = None
        self.hash_frag = None

    def key_id(self) :
        if self.version == 3 :
            return self.key_id_
        else :
            i = self.get_hashed_subpak(SIG_SUB_TYPE_ISSUER_KEY_ID)
            if i :
                return i[1]
            i = self.get_unhashed_subpak(SIG_SUB_TYPE_ISSUER_KEY_ID)
            if i :
                return i[1]
            return None

    def creation_time(self) :
        if self.version == 3 :
            return self.timestamp
        else :
            i = self.get_hashed_subpak(SIG_SUB_TYPE_CREATE_TIME)
            return i[1]

    def expiration(self) :
        if self.version != 4 :
            raise ValueError('v3 signatures don\'t have expirations')
        i = self.get_hashed_subpak(SIG_SUB_TYPE_KEY_EXPIRE)
        if i :
            return i[1]
        return 0 # if not present then it never expires

    def get_hashed_subpak(self, typ) :
        for i in self.hashed_subpaks :
            if i[0] == typ :
                return i
        return None
    
    def get_unhashed_subpak(self, typ) :
        for i in self.unhashed_subpaks :
            if i[0] == typ :
                return i
        return None
    
    def deserialize_subpacket(self, msg, idx) :
        sublen, idx = get_sig_subpak_len(msg, idx)
        subtype, idx = get_whole_int(msg, idx, 1)
        if subtype == SIG_SUB_TYPE_CREATE_TIME : # key creation time
            tm, idx = get_whole_number(msg, idx, 4)
            return (subtype, float(tm)), idx
        if subtype == SIG_SUB_TYPE_EXPIRE_TIME or subtype == SIG_SUB_TYPE_KEY_EXPIRE :
            s, idx = get_whole_int(msg, idx, 4)
            return (subtype, s), idx
        if subtype == SIG_SUB_TYPE_EXPORT_CERT or subtype == SIG_SUB_TYPE_REVOCABLE :
            bool, idx = get_whole_int(msg, idx, 1)
            return (subtype, bool), idx
        if subtype == SIG_SUB_TYPE_TRUST_SIG : # trust signature
            trust_lvl, idx = get_whole_int(msg, idx, 1)
            trust_amt, idx = get_whole_int(msg, idx, 1)
            return (subtype, trust_lvl, trust_amt), idx
        if subtype == SIG_SUB_TYPE_REGEXP : # regular expression
            expr = msg[idx:idx+sublen-1]
            idx = idx + sublen - 1
            return (subtype, expr), idx
        if subtype == SIG_SUB_TYPE_PREF_SYMM_ALGO or subtype == SIG_SUB_TYPE_PREF_HASH_ALGO or subtype == SIG_SUB_TYPE_PREF_COMP_ALGO or subtype == SIG_SUB_TYPE_KEY_FLAGS :
            algo_list = map(lambda x : ord(x), list(msg[idx:idx+sublen-1]))
            idx = idx + sublen - 1
            return (subtype, algo_list), idx
        if subtype == SIG_SUB_TYPE_REVOKE_KEY : # revocation key
            cls, idx = get_whole_int(msg, idx, 1)
            algo, idx = get_whole_int(msg, idx, 1)
            fprint = msg[idx:idx+20]
            idx = idx + 20
            return (subtype, cls, algo, fprint), idx
        if subtype == SIG_SUB_TYPE_ISSUER_KEY_ID : # issuer key ID
            k_id = msg[idx:idx+8]
            idx = idx + 8
            return (subtype, k_id), idx
        if subtype == SIG_SUB_TYPE_NOTATION : # notation data
            flg1, idx = get_whole_int(msg, idx, 1)
            flg2, idx = get_whole_int(msg, idx, 1)
            flg3, idx = get_whole_int(msg, idx, 1)
            flg4, idx = get_whole_int(msg, idx, 1)
            name_len, idx = get_whole_int(msg, idx, 2)
            val_len, idx = get_whole_int(msg, idx, 2)
            nam = msg[idx:idx+name_len]
            idx = idx + name_len
            val = msg[idx:idx+val_len]
            idx = idx + val_len
            return (subtype, flg1, flg2, flg3, flg4, nam, val), idx
        if subtype == SIG_SUB_TYPE_KEY_SRV_PREF : # key server preferences
            prefs = [ ord(x) for x in msg[idx:idx+sublen-1] ]
            idx = idx + sublen - 1
            return (subtype, prefs), idx
        if subtype == SIG_SUB_TYPE_PREF_KEY_SRVR : # preferred key server
            url = msg[idx:idx+sublen-1]
            idx = idx + sublen - 1
            return (subtype, url), idx
        if subtype == SIG_SUB_TYPE_PRIM_USER_ID : # primary user id
            bool, idx = get_whole_int(msg, idx, 1)
            return (subtype, bool), idx
        if subtype == SIG_SUB_TYPE_POLICY_URI : # policy URI
            uri = msg[idx:idx+sublen-1]
            idx = idx + sublen - 1
            return (subtype, uri), idx
        if subtype == SIG_SUB_TYPE_SGNR_USER_ID : # signer's user id
            signer_id = msg[idx:idx+sublen-1]
            idx = idx + sublen - 1
            return (subtype, signer_id), idx
        if subtype == SIG_SUB_TYPE_REVOKE_REASON : # reason for revocation
            rev_code, idx = get_whole_int(msg, idx, 1)
            reas_len = sublen - 2
            reas = msg[idx:idx+reas_len]
            idx = idx + reas_len
            return (subtype, rev_code, reas), idx
        if subtype == SIG_SUB_TYPE_FEATURES : # features
            sublen = sublen - 1
            l = [subtype]
            while sublen > 0 :
                oct, idx = get_whole_int(msg, idx, 1)
                l.append(oct)
                sublen = sublen - 1
            return tuple(l), idx
        if subtype == SIG_SUB_TYPE_SIG_TARGET : # signature target
            public_key_algo, idx = get_whole_int(msg, idx, 1)
            hash_algo, idx = get_whole_int(msg, idx, 1)
            hash = msg[idx:idx+sublen-3]
            idx = idx + sublen - 3
            return (subtype, public_key_algo, hash_algo, hash), idx
        if subtype == SIG_SUB_TYPE_EMBEDDED_SIG : # embedded signature
            # don't do anything fancy, just the raw bits
            dat = msg[idx:idx+sublen-1]
            idx = idx + sublen - 1
            return (subtype, dat), idx

        # otherwise the subpacket is an unknown type, so we just pack the data in it
        dat = msg[idx:idx+sublen-1]
        idx = idx + sublen - 1
        return (subtype, dat), idx

    def is_primary_user_id(self) :
        """is_primary_user_id()
        returns true if this signature contains a primary user id subpacket with value true"""
        for i in self.hashed_subpaks :
            if i[0] == SIG_SUB_TYPE_PRIM_USER_ID :
                return i[1]
        return 0
    
    def subpacket_to_str(self, sp) :
        if sp[0] == SIG_SUB_TYPE_CREATE_TIME : # signature creation time
            return 'creation time: ' + time.ctime(sp[1])
        if sp[0] == SIG_SUB_TYPE_EXPIRE_TIME : # signature expiration time
            return 'signature expires: ' + duration_to_str(sp[1])
        if sp[0] == SIG_SUB_TYPE_EXPORT_CERT : # exportable certification
            if sp[1] :
                return 'signature exportable: TRUE'
            else :
                return 'signature exportable: FALSE'
        if sp[0] == SIG_SUB_TYPE_TRUST_SIG : # trust signature
            if sp[1] == 0 :
                return 'trust: ordinary'
            if sp[1] == 1 :
                return 'trust: introducer (%d)' % sp[2]
            if sp[1] == 2 :
                return 'trust: meta-introducer (%d)' % sp[2]
            return 'trust: %d %d' % (sp[1], sp[2])
        if sp[0] == SIG_SUB_TYPE_REGEXP : # regular expression
            return 'regexp: ' + sp[1]
        if sp[0] == SIG_SUB_TYPE_REVOCABLE : # revocable
            if sp[1] :
                return 'signature revocable: TRUE'
            else :
                return 'signature revocable: FALSE'
        if sp[0] == SIG_SUB_TYPE_KEY_EXPIRE : # key expiration time
            return 'key expires: ' + duration_to_str(sp[1])
        if sp[0] == SIG_SUB_TYPE_PREF_SYMM_ALGO : # preferred symmetric algorithms
            return 'preferred symmetric algorithms: ' + map_to_str(algo_sk_to_str, sp[1])
        if sp[0] == SIG_SUB_TYPE_REVOKE_KEY : # revocation key
            s = 'revocation key: '
            if sp[1] & REVOKE_KEY_CLASS_SENS :
                s = s + '(sensitive) '
            return s + map_to_str(algo_pk_to_str, sp[2]) + ' ' + str_to_hex(sp[3])
        if sp[0] == SIG_SUB_TYPE_ISSUER_KEY_ID : # issuer key ID
            return 'issuer key id: ' + str_to_hex(sp[1])
        if sp[0] == SIG_SUB_TYPE_NOTATION : # notation data
            return 'notation: flags(%d, %d, %d, %d) name(%s) value(%s)' % sp[1:]
        if sp[0] == SIG_SUB_TYPE_PREF_HASH_ALGO : # preferred hash algorithms
            return 'preferred hash algorithms: ' + map_to_str(algo_hash_to_str, sp[1])
        if sp[0] == SIG_SUB_TYPE_PREF_COMP_ALGO : # preferred compression algorithms
            return 'preferred compression algorithms: ' + map_to_str(algo_comp_to_str, sp[1])
        if sp[0] == SIG_SUB_TYPE_KEY_SRV_PREF : # key server preferences
            s = 'key server preferences: '
            prefs = []
            if sp[1][0] & 0x80 :
                prefs.append('No-modify')
            return s + ', '.join(prefs)
        if sp[0] == SIG_SUB_TYPE_PREF_KEY_SRVR : # preferred key server
            return 'preferred key server: %s' % sp[1]
        if sp[0] == SIG_SUB_TYPE_PRIM_USER_ID : # primary user id
            if sp[1] :
                return 'is primary user id'
            else :
                return 'is not primary user id'
        if sp[0] == SIG_SUB_TYPE_POLICY_URI : # policy URL
            return 'policy url: %s' % sp[1]
        if sp[0] == SIG_SUB_TYPE_KEY_FLAGS : # key flags
            flags = []
            flgs1 = 0
            if len(sp[1]) >= 1 :
                flgs1 = sp[1][0]
            if flgs1 & KEY_FLAGS1_MAY_CERTIFY :
                flags.append('may certify other keys')
            if flgs1 & KEY_FLAGS1_MAY_SIGN :
                flags.append('may sign data')
            if flgs1 & KEY_FLAGS1_MAY_ENC_COMM :
                flags.append('may encrypt communications')
            if flgs1 & KEY_FLAGS1_MAY_ENC_STRG :
                flags.append('may encrypt storage')
            if flgs1 & KEY_FLAGS1_PRIV_MAYBE_SPLIT :
                flags.append('private component may have been secret-sharing split')
            if flgs1 & KEY_FLAGS1_GROUP :
                flags.append('group key')
            return 'key flags: ' + ', '.join(flags)
        if sp[0] == SIG_SUB_TYPE_SGNR_USER_ID : # signer's user id
            return 'signer id: ' + sp[1]
        if sp[0] == SIG_SUB_TYPE_REVOKE_REASON : # reason for revocation
            reas = revoke_reason_to_str.get(sp[1], '')
            return 'reason for revocation: %s, %s' % (reas, sp[2])
        if sp[0] == SIG_SUB_TYPE_FEATURES : # features
            features = []
            if len(sp) > 1 :
                val = sp[1]
                if val & PGP_FEATURE_1_MOD_DETECT :
                    features.append('Modification Detection')
                val = val & ~PGP_FEATURE_1_MOD_DETECT
                if val != 0 :
                    features.append('[0]=0x%x' % val)
            for i in range(2, len(sp)) :
                features.append('[%d]=0x%x' % (i-1,sp[i]))
            return 'features: ' + ', '.join(features)
        # this means we don't know what the thing is so we just have raw data
        return 'unknown(%d): %s' % (sp[0], str_to_hex(sp[1]))

    def deserialize(self, msg, idx, pkt_len) :
        self.version, idx = get_whole_int(msg, idx, 1)
        if self.version == 2 :
            self.version = 3
        if self.version == 3 :
            hash_len, idx = get_whole_number(msg, idx, 1)
            self.sig_type, idx = get_whole_int(msg, idx, 1)
            self.timestamp, idx = get_whole_number(msg, idx, 4)
            self.timestamp = float(self.timestamp)
            self.key_id_ = msg[idx:idx+8]
            idx = idx + 8
            self.pk_algo, idx = get_whole_int(msg, idx, 1)
            self.hash_algo, idx = get_whole_int(msg, idx, 1)
        elif self.version == 4:
            self.sig_type, idx = get_whole_int(msg, idx, 1)
            self.pk_algo, idx = get_whole_int(msg, idx, 1)
            self.hash_algo, idx = get_whole_int(msg, idx, 1)
            sub_paks_len, idx = get_whole_int(msg, idx, 2)
            sub_paks_end = idx + sub_paks_len
            self.hashed_subpaks = []
            while idx < sub_paks_end :
                sp, idx = self.deserialize_subpacket(msg, idx)
                self.hashed_subpaks.append(sp)
            sub_paks_len, idx = get_whole_int(msg, idx, 2)
            sub_paks_end = idx + sub_paks_len
            self.unhashed_subpaks = []
            while idx < sub_paks_end :
                sp, idx = self.deserialize_subpacket(msg, idx)
                self.unhashed_subpaks.append(sp)
        else :
            raise RuntimeError('unknown signature packet version %d at %d' % (self.version, idx))
        self.hash_frag, idx = get_whole_number(msg, idx, 2)
        if self.pk_algo == ALGO_PK_RSA_ENC_OR_SIGN or self.pk_algo == ALGO_PK_RSA_SIGN_ONLY :
            self.rsa_sig, idx = get_mpi(msg, idx)
        elif self.pk_algo == ALGO_PK_DSA :
            self.dsa_sig_r, idx = get_mpi(msg, idx)
            self.dsa_sig_s, idx = get_mpi(msg, idx)
        else :
            raise RuntimeError('unknown public-key algorithm (%d) in signature at %d' % (self.pk_algo, idx))
        return idx

    def __str__(self) :
        sio = cStringIO.StringIO()
        sio.write(pgp_packet.__str__(self) + "\n")
        sio.write("version: " + str(self.version) + "\n")
        sio.write("type: " + sig_type_to_str[self.sig_type] + "\n")
        if self.version == 3 :
            sio.write("timestamp: " + time.ctime(self.timestamp) + "\n")
            sio.write("key_id: " + str_to_hex(self.key_id_) + "\n")
        elif self.version == 4 :
            sio.write("hashed subpackets:\n")
            for i in self.hashed_subpaks :
                sio.write("    " + self.subpacket_to_str(i) + "\n")
            sio.write("unhashed subpackets:\n")
            for i in self.unhashed_subpaks :
                sio.write("    " + self.subpacket_to_str(i) + "\n")
        sio.write("hash_algo: " + algo_hash_to_str[self.hash_algo] + "\n")
        sio.write("hash_frag: " + hex(self.hash_frag) + "\n")
        if self.pk_algo == ALGO_PK_RSA_ENC_OR_SIGN or self.pk_algo == ALGO_PK_RSA_SIGN_ONLY :
            sio.write("pk_algo: RSA\n")
            sio.write("rsa_sig: " + hex(self.rsa_sig) + "\n")
        elif self.pk_algo == ALGO_PK_DSA :
            sio.write("pk_algo: DSA\n")
            sio.write("dsa_sig_r: " + hex(self.dsa_sig_r) + "\n")
            sio.write("dsa_sig_s: " + hex(self.dsa_sig_s) + "\n")
        return sio.getvalue()

#
# This class encapsulates an openpgp public "certificate", which is formed in a message as
# a series of PGP packets of certain types in certain orders
#

class pgp_certificate(object):
    def __init__(self) :
        self.version = None
        self.public_key = None
        self.revocations = []
        self.user_ids = []
        self.primary_user_id = -1 # index of the primary user id

    def __str__(self) :
        sio = cStringIO.StringIO()
        sio.write("PGP Public Key Certificate v%d\n" % self.version)
        sio.write("Cert ID: %s\n" % str_to_hex(self.public_key.key_id()))
        sio.write("Primary ID: %s\n" % self.user_id)
        sio.write(str(self.public_key))
        for uid in self.user_ids :
            sio.write(str(uid[0]))
            for sig in uid[1:] :
                sio.write("   " + str(sig))
        if hasattr(self, 'user_attrs') :
            for uattr in self.user_attrs :
                sio.write(' ')
                sio.write(str(uattr[0]))
                for sig in uattr[1:] :
                    sio.write("   " + str(sig))
        return sio.getvalue()
    
    def get_user_id(self):
        # take the LAST one in the list, not first
        # they appear to be ordered FIFO from the key and that means if you
        # added a key later then it won't show the one you expect
        return self.user_ids[self.primary_user_id][0].id
        
    user_id = property(get_user_id)
    
    def expiration(self) :
        if self.version == 3 :
            if self.public_key.validity == 0 :
                return 0
            return self.public_key.timestamp + self.public_key.validity * 24 * 60 * 60
        else : # self.version == 4
            # this is a bit more complex, we need to find the signature on the
            # key and get its expiration
            u_id = self.user_ids[0]
            for i in u_id[1:] :
                if i.sig_type == SIG_TYPE_PK_USER_GEN :
                    exp = i.expiration()
                    if exp == 0 :
                        return 0
                    return self.public_key.timestamp + exp
            return 0

    def key_size(self) :
        return 0
    
    def load(self, pkts) :
        """load(pkts)
Initialize the pgp_certificate with a list of OpenPGP packets. The list of packets will
be scanned to make sure they are valid for a pgp certificate."""


        # each certificate should begin with a public key packet
        if pkts[0].pkt_typ != CTB_PKT_PK_CERT :
            raise ValueError('first PGP packet should be a public-key packet, not %s' % map_to_str(ctb_pkt_to_str, pkts[0].pkt_typ))

        # all versions have a public key although in a v4 cert the main key is only
        # used for signing, never encryption
        self.public_key = pkts[0]

        # ok, then what's the version
        self.version = self.public_key.version

        # now the behavior splits a little depending on the version
        if self.version == 3 :
            pkt_idx = 1

            # zero or more revocations
            while pkts[pkt_idx].pkt_typ == CTB_PKT_SIG :
                if pkts[pkt_idx].version != 3 :
                    raise ValueError('version 3 cert has version %d signature' % pkts[pkt_idx].version)
                if pkts[pkt_idx].sig_type != SIG_TYPE_KEY_REVOKE :
                    raise ValueError('v3 cert revocation sig has type %s' % map_to_str(sig_type_to_str, pkts[pkt_idx].sig_type))

                # ok, well at least the type is good, we'll assume the cert is
                # revoked
                self.revocations.append(pkts[pkt_idx])

                # increment the pkt_idx to go to the next one
                pkt_idx = pkt_idx + 1

            # the following packets are User ID, Signature pairs
            while pkt_idx < len(pkts) :
                # this packet is supposed to be a user id
                if pkts[pkt_idx].pkt_typ != CTB_PKT_USER_ID :
                    if len(self.user_ids) == 0 :
                        raise ValueError('pgp packet %d is not user id, is %s' % (pkt_idx, map_to_str(ctb_pkt_to_str, pkts[pkt_idx].pkt_typ)))
                    else :
                        break

                user_id = [pkts[pkt_idx]]
                pkt_idx = pkt_idx + 1
                is_revoked = 0
                is_primary_user_id = 0

                # there may be a sequence of signatures following the user id which
                # bind it to the key
                while pkt_idx < len(pkts) and pkts[pkt_idx].pkt_typ == CTB_PKT_SIG :
                    if pkts[pkt_idx].sig_type not in (SIG_TYPE_PK_USER_GEN, SIG_TYPE_PK_USER_PER, SIG_TYPE_PK_USER_CAS, SIG_TYPE_PK_USER_POS, SIG_TYPE_CERT_REVOKE) :
                        raise ValueError('signature %d doesn\'t bind user_id to key, is %s' % (pkt_idx, map_to_str(sig_type_to_str, pkts[pkt_idx].sig_typ)))

                    user_id.append(pkts[pkt_idx])

                    pkt_idx = pkt_idx + 1

                # append the user ID and signature(s) onto a list
                self.user_ids.append(user_id)

        else : # self.version == 4
            pkt_idx = 1
            self.direct_key_sigs = []
            self.subkeys = []
            self.rvkd_subkeys = []
            self.user_attrs = []

            cert_id = self.public_key.key_id()

            # second packet could be a revocation (or a direct key self signature)
            while pkt_idx < len(pkts) and pkts[pkt_idx].pkt_typ == CTB_PKT_SIG :
                if pkts[pkt_idx].version != 4 :
                    raise ValueError('version 4 cert has version %d signature' % pkts[pkt_idx].version)
                if pkts[pkt_idx].sig_type == SIG_TYPE_KEY_REVOKE :
                    self.revocations.append(pkts[pkt_idx])
                elif pkts[pkt_idx].sig_type == SIG_TYPE_KEY :
                    self.direct_key_sigs.append(pkts[pkt_idx])
                else :
                    raise ValueError('v4 cert signature has type %s, supposed to be revocation signature or direct key signature' % map_to_str(sig_type_to_str, pkts[pkt_idx].sig_type))

                # increment the pkt_idx to go to the next one
                pkt_idx = pkt_idx + 1
                
            # the following packets are:
            # User ID, signature... sets or
            # subkey, signature... sets or
            # user attribute, signature... sets
            prim_user_id_sig_time = 0

            while pkt_idx < len(pkts) :
                # this packet is supposed to be a user id
                if pkts[pkt_idx].pkt_typ == CTB_PKT_USER_ID :
                    user_id = [pkts[pkt_idx]]
                    is_revoked = 0
                    is_primary_user_id = 0

                    pkt_idx = pkt_idx + 1

                    # there may be a sequence of signatures following the user id which
                    # bind it to the key
                    while pkt_idx < len(pkts) and pkts[pkt_idx].pkt_typ == CTB_PKT_SIG :
                        if pkts[pkt_idx].sig_type not in (SIG_TYPE_PK_USER_GEN, SIG_TYPE_PK_USER_PER, SIG_TYPE_PK_USER_CAS, SIG_TYPE_PK_USER_POS, SIG_TYPE_CERT_REVOKE) :
                            raise ValueError('signature %d doesn\'t bind user_id to key, is %s' % (pkt_idx, map_to_str(sig_type_to_str, pkts[pkt_idx].sig_type)))
                        user_id.append(pkts[pkt_idx])

                        # is this the primary user id?
                        if pkts[pkt_idx].key_id() == cert_id :
                            if pkts[pkt_idx].is_primary_user_id() :
                                ct = pkts[pkt_idx].creation_time()
                                if ct > prim_user_id_sig_time :
                                    self.primary_user_id = len(self.user_ids)
                                    prim_user_id_sig_time = ct

                        pkt_idx = pkt_idx + 1

                    # append the user ID and signature(s) onto the list
                    self.user_ids.append(user_id)

                # this packet is supposed to be a user id
                elif pkts[pkt_idx].pkt_typ == CTB_PKT_USER_ATTR :
                    user_attr = [pkts[pkt_idx]]
                    is_revoked = 0

                    pkt_idx = pkt_idx + 1

                    # there may be a sequence of signatures following the user id which
                    # bind it to the key
                    while pkt_idx < len(pkts) and pkts[pkt_idx].pkt_typ == CTB_PKT_SIG :
                        if pkts[pkt_idx].sig_type not in (SIG_TYPE_PK_USER_GEN, SIG_TYPE_PK_USER_PER, SIG_TYPE_PK_USER_CAS, SIG_TYPE_PK_USER_POS, SIG_TYPE_CERT_REVOKE) :
                            raise ValueError('signature %d doesn\'t bind user_attr to key, is %s' % (pkt_idx, map_to_str(sig_type_to_str, pkts[pkt_idx].sig_type)))
                        user_attr.append(pkts[pkt_idx])
                        pkt_idx = pkt_idx + 1

                    # append the user ID and signature(s) onto the list
                    self.user_attrs.append(user_attr)

                elif pkts[pkt_idx].pkt_typ == CTB_PKT_PK_SUB :
                    # collect this list of subkey + signature [ + revocation ]
                    subkey = [pkts[pkt_idx]]
                    pkt_idx = pkt_idx + 1
                    is_revoked = 0

                    # there must be one signature following the subkey that binds it to the main key
                    if pkt_idx >= len(pkts) :
                        raise ValueError('subkey at index %d was not followed by a signature' % (pkt_idx-1))
                    if pkts[pkt_idx].pkt_typ != CTB_PKT_SIG or pkts[pkt_idx].sig_type != SIG_TYPE_SUBKEY_BIND :
                        raise ValueError('signature %d doesn\'t bind subkey to key, type is %s' % (pkt_idx, map_to_str(sig_type_to_str, pkts[pkt_idx].sig_typ)))
                    subkey.append(pkts[pkt_idx])

                    pkt_idx = pkt_idx + 1

                    # there may optionally be a revocation
                    if pkt_idx < len(pkts) and pkts[pkt_idx].pkt_typ == CTB_PKT_SIG and pkts[pkt_idx].sig_type == SIG_TYPE_SUBKEY_REVOKE :
                        is_revoked = 1
                        subkey.append(pkts[pkt_idx])
                        pkt_idx = pkt_idx + 1

                    # append the user ID and signature(s) onto the list
                    if is_revoked :
                        self.rvkd_subkeys.append(subkey)
                    else :
                        self.subkeys.append(subkey)
                elif pkts[pkt_idx].pkt_typ == CTB_PKT_SIG :

                    # ok, well at least the type is good, we'll assume the cert is
                    # revoked
                    self.revocations.append(pkts[pkt_idx])

                    # increment the pkt_idx to go to the next one
                    pkt_idx = pkt_idx + 1

                
                else :
                    break

        # did we get all the things we needed?
        #if not self.user_id :
        # just take the first valid user id we encountered then
        if len(self.user_ids) == 0 :
            raise ValueError('no user id packet was present in the cert %s' % str_to_hex(self.public_key.key_id()))
        return pkt_idx


def get_ctb(msg, idx) :
    """get_ctb(msg, idx)
extracts a the "cypher type bit" information from message msg at index idx
returns (type, len, new_idx) where type is the enumerated type of the packet,
len is the length of the packet, and new_idx is the index of the next element
in the message"""
    b, idx = get_whole_int(msg, idx, 1)
    if (b & CTB_76_MASK) == CTB_76_NORMAL :
        n_len = 0 # undefined length
        if (b & CTB_PKT_LEN_MASK) == CTB_PKT_LEN_1 :
            n_len = 1
        if (b & CTB_PKT_LEN_MASK) == CTB_PKT_LEN_2 :
            n_len = 2
        if (b & CTB_PKT_LEN_MASK) == CTB_PKT_LEN_4 :
            n_len = 4
        if (b & CTB_PKT_LEN_MASK) == CTB_PKT_LEN_UNDEF :
            n_len = 0
        pkt_len = 0
        if n_len > 0 :
            pkt_len, idx = get_whole_int(msg, idx, n_len)
        return (b & CTB_PKTV2_MASK) >> 2, pkt_len, idx
    elif (b & CTB_76_MASK) == CTB_76_NEW :
        plen, idx = get_whole_int(msg, idx, 1)
        if plen < 192 :
            return b & CTB_PKT_MASK, plen, idx
        if plen < 224 :
            plen2, idx = get_whole_int(msg, idx, 1)
            return b & CTB_PKT_MASK, ((plen - 192) << 8) + plen2 + 192, idx
        if plen == 255 :
            plen, idx = get_whole_int(msg, idx, 4)
            return b & CTB_PKT_MASK, plen, idx
        else :
            raise Exception, 'partial message bodies are not supported by this version (%d)', b
    else :
        raise Exception, "unknown (not \"normal\") cypher type bit %d at byte %d" % (b, idx)

def crc24(msg) :
    crc24_init = 0xb704ce
    crc24_poly = 0x1864cfb

    crc = crc24_init
    for i in list(msg) :
        crc = crc ^ (ord(i) << 16)
        for j in range(0, 8) :
            crc = crc << 1
            if crc & 0x1000000 :
                crc = crc ^ crc24_poly
    return crc & 0xffffff

def decode(msg) :
    # each message is a sequence of packets so we go through the message
    # and generate a list of packets and return that
    pkt_list = []
    idx = 0
    msg_len = len(msg)
    while idx < msg_len :
        pkt_typ, pkt_len, idx = get_ctb(msg, idx)
        pkt = None
        if pkt_typ == CTB_PKT_PK_CERT or pkt_typ == CTB_PKT_PK_SUB :
            pkt = public_key()

        elif pkt_typ == CTB_PKT_USER_ID :
            pkt = user_id()

        elif pkt_typ == CTB_PKT_SIG :
            pkt = signature()

        elif pkt_typ == CTB_PKT_USER_ATTR :
            pkt = user_attribute()

        if pkt :
            pkt.pkt_typ = pkt_typ
            pkt.deserialize(msg, idx, pkt_len)
            if debug :
                debug.write(pkt.__str__() + "\n")
        else :
            raise ValueError('unexpected pgp packet type %s at %d' % (map_to_str(ctb_pkt_to_str, pkt_typ), idx))

        pkt_list.append(pkt)

        idx = idx + pkt_len
    return pkt_list

def decode_msg(msg, multi=False) :
    """decode_msg(msg) ==> list of OpenPGP "packet" objects
Takes an ascii-armored PGP block and returns a list of objects each of which
corresponds to a PGP "packets".

A PGP message is a series of packets. You need to understand how packets are
to be combined together in order to know what to do with them. For example
a PGP "certificate" includes a public key, user id(s), and signature. 
"""
    # first we'll break the block up into lines and trim each line of any 
    # carriage return chars
    pgpkey_lines = map(lambda x : x.rstrip(), msg.split('\n'))

    # check out block
    in_block = 0
    in_data = 0
    
    block_buf = cStringIO.StringIO()
    for l in pgpkey_lines :
        if not in_block :
            if l == '-----BEGIN PGP PUBLIC KEY BLOCK-----' :
                in_block = 1
            continue

        # are we at the actual data yet?
        if not in_data :
            if len(l) == 0 :
                in_data = 1
            continue
        
        # are we at the checksum line?
        if l and l[0] == '=' :
            # get the checksum number
            csum = base64.decodestring(l[1:5])
            i = 0
            csum, i = get_whole_number(csum, i, 3)

            # convert the base64 cert data to binary data
            cert_msg = base64.decodestring(block_buf.getvalue())
            block_buf.close()

            # check the checksum
            if csum != crc24(cert_msg) :
                raise Exception, 'bad checksum on pgp message'

            # ok, the sum looks ok so we'll actually decode the thing
            pkt_list = decode(cert_msg)
            # turn it into a real cert
            cert_list = []
            while len(pkt_list) > 0 :
                cert = pgp_certificate()
                cert.raw_key = msg
                pkt_idx = cert.load(pkt_list)
                cert_list.append(cert)
                pkt_list[0:pkt_idx] = []
            if not multi:
                if not cert_list:
                    return None
                return cert_list[0]
            return cert_list
        
        # add the data to our buffer then
        block_buf.write(l)

    if not multi:
        return None
    return []

def decode_multiple_keys(msg):
    #ditto of above - but handling multiple certs/keys per file
    certs = []

    pgpkey_lines = map(lambda x : x.rstrip(), msg.split('\n'))
    in_block = 0
    block = ''
    for l in pgpkey_lines :
        if not in_block :
            if l == '-----BEGIN PGP PUBLIC KEY BLOCK-----' :
                in_block = 1        
                block += '%s\n' % l
                continue

        block += '%s\n' % l
        if l == '-----END PGP PUBLIC KEY BLOCK-----':
            in_block = 0
            thesecerts = decode_msg(block, multi=True)
            if thesecerts:
                certs.extend(thesecerts)
            block = ''
            continue
    return certs


if __name__ == '__main__' :
    import sys
    for pgp_cert in decode_multiple_keys(open(sys.argv[1]).read()) :
        print pgp_cert
