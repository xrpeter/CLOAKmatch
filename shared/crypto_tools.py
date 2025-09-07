import os
from typing import Optional
import os
import sys
import platform
import ctypes
import ctypes.util
import hashlib


class MissingLibraryError(RuntimeError):
    """Raised when a required crypto library is not available."""
    pass


def generate_ristretto255_private_key() -> bytes:
    """
    Generate a 32-byte private key suitable for Ristretto255-based schemes.

    Note: This returns uniformly random 32 bytes. Higher-level protocols may
    map this to a scalar mod the group order as needed. Public key derivation
    and signing/encryption are intentionally not included here.
    """
    # 32 bytes of cryptographically secure randomness
    return os.urandom(32)


_SODIUM_LIB: Optional[ctypes.CDLL] = None
_SODIUM_PATH: Optional[str] = None


def _load_libsodium() -> ctypes.CDLL:
    """Load libsodium and cache the CDLL handle; raise clear guidance if missing."""
    global _SODIUM_LIB, _SODIUM_PATH
    if _SODIUM_LIB is not None:
        return _SODIUM_LIB

    env_path = os.getenv("SODIUM_LIBRARY_PATH")
    candidates = []
    if env_path:
        candidates.append(env_path)
    try:
        found = ctypes.util.find_library("sodium")
    except Exception:
        found = None
    if found:
        candidates.append(found)
    if platform.system() == "Darwin":
        candidates.extend([
            "/opt/homebrew/lib/libsodium.dylib",
            "/usr/local/lib/libsodium.dylib",
        ])
    elif platform.system() == "Linux":
        candidates.extend([
            "libsodium.so",
            "libsodium.so.23",
            "/usr/lib/x86_64-linux-gnu/libsodium.so",
            "/usr/local/lib/libsodium.so",
        ])

    for path in candidates:
        try:
            lib = ctypes.CDLL(path, mode=getattr(ctypes, "RTLD_GLOBAL", 0))
            # Initialize and set prototypes
            try:
                lib.sodium_init.restype = ctypes.c_int
                lib.sodium_init.argtypes = []
                lib.sodium_init()
            except Exception:
                pass

            lib.crypto_core_ristretto255_from_hash.argtypes = [
                ctypes.POINTER(ctypes.c_ubyte),
                ctypes.POINTER(ctypes.c_ubyte),
            ]
            lib.crypto_scalarmult_ristretto255.restype = ctypes.c_int
            lib.crypto_scalarmult_ristretto255.argtypes = [
                ctypes.POINTER(ctypes.c_ubyte),
                ctypes.POINTER(ctypes.c_ubyte),
                ctypes.POINTER(ctypes.c_ubyte),
            ]

            _SODIUM_LIB = lib
            _SODIUM_PATH = path
            return lib
        except Exception:
            continue

    hint = ""
    if platform.system() == "Darwin":
        hint = (
            "Install via Homebrew: 'brew install libsodium'. "
            "Or set SODIUM_LIBRARY_PATH to the dylib (e.g., /opt/homebrew/lib/libsodium.dylib)."
        )
    raise MissingLibraryError(f"Unable to load libsodium. Tried: {candidates}. {hint}")


# liboprf no longer required; we use libsodium directly


def evaluate_oprf_ristretto255(server_private_key: bytes, input_data: bytes, data_name: str) -> bytes:
    """
    Evaluate the server-side output for OPRF(ristretto255, SHA-512) using
    libsodium's Ristretto255 primitives via ctypes.

    Process:
      1) H1(x): map input to group with crypto_core_ristretto255_from_hash on a
         64-byte SHA-512 digest using domain separation.
      2) Q = k * H1(x) via crypto_scalarmult_ristretto255.
      3) Finalize: SHA-512(domain || x || Q) to produce 64-byte output.

    Domain separation:
      - Uses the provided 'data_name' as the hash-to-group context (DST_H2G).

    Returns: 64 bytes (SHA-512 digest) representing the PRF output.
    """
    if not isinstance(server_private_key, (bytes, bytearray)) or len(server_private_key) != 32:
        raise ValueError("server_private_key must be 32 bytes")
    if not isinstance(input_data, (bytes, bytearray)):
        raise ValueError("input_data must be bytes-like")
    if not isinstance(data_name, str) or not data_name:
        raise ValueError("data_name must be a non-empty string")

    lib = _load_libsodium()

    # 1) Hash-to-group using SHA-512 with domain separation
    DST_H2G = data_name.encode("utf-8")
    wide_hash = hashlib.sha512(DST_H2G + bytes(input_data)).digest()  # 64 bytes

    p_out = (ctypes.c_ubyte * 32)()
    wide_buf = (ctypes.c_ubyte * 64).from_buffer_copy(wide_hash)
    lib.crypto_core_ristretto255_from_hash(p_out, wide_buf)

    # 2) Scalar multiplication: Q = k * P
    q_out = (ctypes.c_ubyte * 32)()
    sk_buf = (ctypes.c_ubyte * 32).from_buffer_copy(bytes(server_private_key))
    rc = lib.crypto_scalarmult_ristretto255(q_out, sk_buf, p_out)
    if rc != 0:
        raise MissingLibraryError("crypto_scalarmult_ristretto255 failed (invalid scalar/point)")

    q_bytes = bytes(q_out)

    # 3) Finalize: hash with domain separation
    DST_FIN = f"{data_name}-FINALIZE".encode("utf-8")
    out = hashlib.sha512(DST_FIN + bytes(input_data) + q_bytes).digest()
    return out


def evaluate_oprf_ristretto255_components(server_private_key: bytes, input_data: bytes, data_name: str) -> tuple[bytes, bytes]:
    """Return (PRF_output, Q_bytes) for OPRF(ristretto255, SHA-512).

    PRF_output: 64-byte SHA-512 digest (finalization)
    Q_bytes: 32-byte Ristretto encoded group element k*H1(x)
    """
    if not isinstance(server_private_key, (bytes, bytearray)) or len(server_private_key) != 32:
        raise ValueError("server_private_key must be 32 bytes")
    if not isinstance(input_data, (bytes, bytearray)):
        raise ValueError("input_data must be bytes-like")
    if not isinstance(data_name, str) or not data_name:
        raise ValueError("data_name must be a non-empty string")

    lib = _load_libsodium()

    DST_H2G = data_name.encode("utf-8")
    wide_hash = hashlib.sha512(DST_H2G + bytes(input_data)).digest()
    p_out = (ctypes.c_ubyte * 32)()
    wide_buf = (ctypes.c_ubyte * 64).from_buffer_copy(wide_hash)
    lib.crypto_core_ristretto255_from_hash(p_out, wide_buf)

    q_out = (ctypes.c_ubyte * 32)()
    sk_buf = (ctypes.c_ubyte * 32).from_buffer_copy(bytes(server_private_key))
    rc = lib.crypto_scalarmult_ristretto255(q_out, sk_buf, p_out)
    if rc != 0:
        raise MissingLibraryError("crypto_scalarmult_ristretto255 failed (invalid scalar/point)")
    q_bytes = bytes(q_out)

    DST_FIN = f"{data_name}-FINALIZE".encode("utf-8")
    prf = hashlib.sha512(DST_FIN + bytes(input_data) + q_bytes).digest()
    return prf, q_bytes


# Client/Server OPRF helpers (blinding flow)

def ristretto_hash_to_group(data_name: str, input_data: bytes) -> bytes:
    if not isinstance(data_name, str) or not data_name:
        raise ValueError("data_name must be non-empty string")
    lib = _load_libsodium()
    wide_hash = hashlib.sha512(data_name.encode("utf-8") + bytes(input_data)).digest()
    p_out = (ctypes.c_ubyte * 32)()
    wide_buf = (ctypes.c_ubyte * 64).from_buffer_copy(wide_hash)
    lib.crypto_core_ristretto255_from_hash(p_out, wide_buf)
    return bytes(p_out)


def ristretto_scalar_random() -> bytes:
    lib = _load_libsodium()
    try:
        fn = lib.crypto_core_ristretto255_scalar_random
    except AttributeError:
        raise MissingLibraryError("libsodium missing ristretto255 scalar_random")
    buf = (ctypes.c_ubyte * 32)()
    fn(buf)
    return bytes(buf)


def ristretto_scalar_invert(x: bytes) -> bytes:
    lib = _load_libsodium()
    try:
        fn = lib.crypto_core_ristretto255_scalar_invert
    except AttributeError:
        raise MissingLibraryError("libsodium missing ristretto255 scalar_invert")
    out = (ctypes.c_ubyte * 32)()
    x_buf = (ctypes.c_ubyte * 32).from_buffer_copy(bytes(x))
    fn(out, x_buf)
    return bytes(out)


def ristretto_scalarmult(scalar: bytes, point: bytes) -> bytes:
    lib = _load_libsodium()
    out = (ctypes.c_ubyte * 32)()
    s_buf = (ctypes.c_ubyte * 32).from_buffer_copy(bytes(scalar))
    p_buf = (ctypes.c_ubyte * 32).from_buffer_copy(bytes(point))
    rc = lib.crypto_scalarmult_ristretto255(out, s_buf, p_buf)
    if rc != 0:
        raise MissingLibraryError("crypto_scalarmult_ristretto255 failed")
    return bytes(out)


def oprf_finalize(data_name: str, input_data: bytes, q_point: bytes) -> bytes:
    DST_FIN = f"{data_name}-FINALIZE".encode("utf-8")
    return hashlib.sha512(DST_FIN + bytes(input_data) + bytes(q_point)).digest()


def _hkdf_sha512(ikm: bytes, info: bytes, length: int, salt: bytes | None = None) -> bytes:
    import hmac

    if salt is None:
        salt = b"\x00" * 64
    prk = hmac.new(salt, ikm, hashlib.sha512).digest()
    okm = b""
    t = b""
    counter = 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha512).digest()
        okm += t
        counter += 1
    return okm[:length]


def _sodium_xchacha20poly1305_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes | None = None) -> bytes:
    """Encrypt using libsodium crypto_aead_xchacha20poly1305_ietf_encrypt.

    Returns ciphertext (includes MAC tag; no prefix)."""
    lib = _load_libsodium()

    # Prototype setup
    try:
        fn = lib.crypto_aead_xchacha20poly1305_ietf_encrypt
    except AttributeError as e:
        raise MissingLibraryError("libsodium missing XChaCha20-Poly1305 IETF support")
    fn.restype = ctypes.c_int
    fn.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.POINTER(ctypes.c_ulonglong),
        ctypes.POINTER(ctypes.c_ubyte), ctypes.c_ulonglong,
        ctypes.POINTER(ctypes.c_ubyte), ctypes.c_ulonglong,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.POINTER(ctypes.c_ubyte),
    ]

    m = bytes(plaintext)
    ad = bytes(aad) if aad else None
    c_buf = (ctypes.c_ubyte * (len(m) + 16))()
    c_len = ctypes.c_ulonglong()
    m_buf = (ctypes.c_ubyte * len(m)).from_buffer_copy(m) if m else (ctypes.c_ubyte * 0)()
    ad_buf = (ctypes.c_ubyte * len(ad)).from_buffer_copy(ad) if ad else None
    n_buf = (ctypes.c_ubyte * 24).from_buffer_copy(nonce)
    k_buf = (ctypes.c_ubyte * 32).from_buffer_copy(key)

    ad_ptr = ctypes.cast(ad_buf, ctypes.POINTER(ctypes.c_ubyte)) if ad else None

    rc = fn(
        c_buf,
        ctypes.byref(c_len),
        m_buf, ctypes.c_ulonglong(len(m)),
        ad_ptr, ctypes.c_ulonglong(len(ad) if ad else 0),
        None,
        n_buf,
        k_buf,
    )
    if rc != 0:
        raise MissingLibraryError("XChaCha20-Poly1305 encryption failed")
    return bytes(c_buf)[: c_len.value]


def _sodium_xchacha20poly1305_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes | None = None) -> bytes:
    lib = _load_libsodium()
    try:
        fn = lib.crypto_aead_xchacha20poly1305_ietf_decrypt
    except AttributeError:
        raise MissingLibraryError("libsodium missing XChaCha20-Poly1305 IETF support")
    fn.restype = ctypes.c_int
    fn.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ulonglong),
        ctypes.c_void_p,  # nsec (unused)
        ctypes.POINTER(ctypes.c_ubyte), ctypes.c_ulonglong,
        ctypes.POINTER(ctypes.c_ubyte), ctypes.c_ulonglong,
        ctypes.POINTER(ctypes.c_ubyte),  # nonce
        ctypes.POINTER(ctypes.c_ubyte),  # key
    ]
    c = bytes(ciphertext)
    ad = bytes(aad) if aad else None
    m_buf = (ctypes.c_ubyte * (len(c) - 16))()
    m_len = ctypes.c_ulonglong()
    c_buf = (ctypes.c_ubyte * len(c)).from_buffer_copy(c)
    ad_buf = (ctypes.c_ubyte * len(ad)).from_buffer_copy(ad) if ad else None
    n_buf = (ctypes.c_ubyte * 24).from_buffer_copy(nonce)
    k_buf = (ctypes.c_ubyte * 32).from_buffer_copy(key)
    ad_ptr = ctypes.cast(ad_buf, ctypes.POINTER(ctypes.c_ubyte)) if ad else None
    rc = fn(
        m_buf, ctypes.byref(m_len), None,
        c_buf, ctypes.c_ulonglong(len(c)),
        ad_ptr, ctypes.c_ulonglong(len(ad) if ad else 0),
        n_buf, k_buf,
    )
    if rc != 0:
        raise MissingLibraryError("XChaCha20-Poly1305 decryption failed")
    return bytes(m_buf)[: m_len.value]


def evaluate_and_encrypt_metadata(server_private_key: bytes, ioc: bytes, data_name: str, metadata: bytes) -> tuple[bytes, bytes, bytes]:
    """Compute OPRF(PRF) and encrypt metadata with HKDF-derived key.

    - ikm for HKDF: PRF || Q, where PRF is final output (64 bytes), Q is 32-byte scalar-mult result
    - info: b"meta|" + data_name
    - key length: 32 bytes
    - AEAD: XChaCha20-Poly1305-IETF with random 24-byte nonce
    - AAD: ioc bytes (binds ciphertext to specific IOC)

    Returns (prf, nonce, ciphertext).
    """
    prf, q_bytes = evaluate_oprf_ristretto255_components(server_private_key, ioc, data_name)
    ikm = prf + q_bytes
    info = ("meta|" + data_name).encode("utf-8")
    key = _hkdf_sha512(ikm, info, 32)
    nonce = os.urandom(24)
    ct = _sodium_xchacha20poly1305_encrypt(key, nonce, metadata, aad=ioc)
    return prf, nonce, ct


def decrypt_metadata_from_prf_and_q(data_name: str, ioc: bytes, prf: bytes, q_point: bytes, nonce: bytes, ct: bytes) -> bytes:
    """Derive key via HKDF(PRF||Q) and decrypt metadata (XChaCha20-Poly1305, AAD=ioc).
    Returns plaintext bytes.
    """
    ikm = prf + q_point
    info = ("meta|" + data_name).encode("utf-8")
    key = _hkdf_sha512(ikm, info, 32)
    return _sodium_xchacha20poly1305_decrypt(key, nonce, ct, aad=ioc)


def evaluate_blinded_point(server_private_key: bytes, blinded_point: bytes) -> bytes:
    """Server evaluation: return k * B given k (server sk) and blinded point B."""
    return ristretto_scalarmult(server_private_key, blinded_point)


def _fmt_loaded(path: Optional[str]) -> str:
    if path:
        return f"Preloaded libsodium from: {path}. "
    return ""
