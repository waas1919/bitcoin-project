"""32-byte secret -> 24 BIP39 words (encoding only, for fun).

In 2011 there were no seed words: each key was random. Here we only write
the private key itself as words. It is NOT a BIP39 seed, so a modern
wallet would derive different keys from these words.
"""
import hashlib
import pathlib


class Bip39:
    WORDLIST_FILE = pathlib.Path(__file__).with_name("bip39_english.txt")
    WORDLIST_SIZE = 2048
    ENTROPY_BYTES = 32
    BITS_PER_WORD = 11
    BITS_PER_BYTE = 8
    CHECKSUM_DIVISOR = 32           # checksum bits = entropy bits / 32

    def __init__(self):
        self.words = self.WORDLIST_FILE.read_text().split()
        if len(self.words) != self.WORDLIST_SIZE:
            raise ValueError("bad BIP39 wordlist")

    def to_words(self, entropy: bytes) -> list:
        if len(entropy) != self.ENTROPY_BYTES:
            raise ValueError("need 32 bytes")
        ent_bits = len(entropy) * self.BITS_PER_BYTE               # 256
        cs_bits = ent_bits // self.CHECKSUM_DIVISOR                # 8
        checksum = hashlib.sha256(entropy).digest()[0] >> (self.BITS_PER_BYTE - cs_bits)
        value = (int.from_bytes(entropy, "big") << cs_bits) | checksum  # 264 bits
        count = (ent_bits + cs_bits) // self.BITS_PER_WORD         # 24
        mask = (1 << self.BITS_PER_WORD) - 1
        return [self.words[(value >> (self.BITS_PER_WORD * (count - 1 - i))) & mask]
                for i in range(count)]


if __name__ == "__main__":
    words = Bip39().to_words(bytes(32))
    assert words == ["abandon"] * 23 + ["art"], words
    print("bip39 selftest OK:", " ".join(words[-2:]))
