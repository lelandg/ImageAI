"""Offline regression check for the patched certifi floor.

requests, httpx, and the Google client libraries verify provider TLS against
certifi's bundle, so this tests the trusted roots, not the version string.
"""
import base64
import hashlib
import re

import certifi

# SHA-256 of each root's DER encoding, as listed in cacert.pem.
EMSIGN_ECC_ROOT_G3 = "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b"
UNAFFECTED_EMSIGN_ROOTS = {
    "40f6af0346a99aa1cd1d555a4e9cce62c7f9634603ee406615833dc8c8d00367",  # Root CA - G1
    "125609aa301da0a249b97a8239cb6a34216f44dcac9f3954b14292f2e8c8608f",  # Root CA - C1
    "bc4d809b15189d78db3e1d8cf4f9726a795da1643ca5f1358e1ddb0edc0d7eb3",  # ECC Root CA - C3
}


def bundle_fingerprints():
    pem = certifi.contents()
    blocks = re.findall(r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", pem, re.DOTALL)
    return {hashlib.sha256(base64.b64decode("".join(b.split()))).hexdigest() for b in blocks}


def test_compromised_emsign_root_is_not_trusted():
    """GHSA-6q48-6c7w-9gw2: the root whose intermediates leaked keys is gone."""
    assert EMSIGN_ECC_ROOT_G3 not in bundle_fingerprints()


def test_unaffected_emsign_roots_are_still_trusted():
    """SNYK-PYTHON-CERTIFI-21280764: 2026.10.18 dropped these by mistake."""
    assert UNAFFECTED_EMSIGN_ROOTS <= bundle_fingerprints()
