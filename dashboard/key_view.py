"""Decode a 2011 WIF private key and show it as hex and words."""
import hashlib

from bip39 import Bip39


class Base58:
    ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    BASE = 58
    CHECKSUM_BYTES = 4

    @classmethod
    def decode_check(cls, text: str) -> bytes:
        value = 0
        for ch in text:
            value = value * cls.BASE + cls.ALPHABET.index(ch)
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        leading_zeros = len(text) - len(text.lstrip(cls.ALPHABET[0]))
        raw = b"\x00" * leading_zeros + raw
        body, check = raw[:-cls.CHECKSUM_BYTES], raw[-cls.CHECKSUM_BYTES:]
        if hashlib.sha256(hashlib.sha256(body).digest()).digest()[:cls.CHECKSUM_BYTES] != check:
            raise ValueError("bad Base58Check checksum")
        return body


class KeyView:
    WIF_VERSION = 0x80
    SECRET_BYTES = 32
    _bip39 = Bip39()

    def __init__(self, address: str, wif: str):
        body = Base58.decode_check(wif)
        if body[0] != self.WIF_VERSION or len(body) != 1 + self.SECRET_BYTES:
            raise ValueError("not an uncompressed WIF key")
        self.address = address
        self.wif = wif
        self.secret = body[1:]

    def as_dict(self) -> dict:
        return {
            "address": self.address,
            "wif": self.wif,
            "hex": self.secret.hex(),
            "words": self._bip39.to_words(self.secret),
        }
