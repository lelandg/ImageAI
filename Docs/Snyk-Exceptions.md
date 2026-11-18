# Snyk applicability exceptions

Reviewed: 2026-11-18. No Snyk exceptions are currently approved, and `.snyk` carries no ignores.

The six exceptions that covered the proxy advisories of the former LLM wrapper library were removed on 2026-11-18, together with the dependency itself: ImageAI now reaches the provider SDKs through its own `core/chameleon_llm` package, and the old library is no longer installed. Earlier sections below are kept as a record of past reviews.

A policy-filtered passing scan is not a zero-advisory raw scan. Retain an unfiltered scan with --ignore-policy when reviewing applicability. Package vulnerability presence and application exploitability are distinct claims.

## November 5, 2026 reassessment (local SD stack)

Prompted by the weekly Snyk email. CLI scans on Python 3.12 of all four manifests, against an environment upgraded to what each manifest now resolves:

| Manifest | Dependencies | Result |
| --- | --- | --- |
| `requirements.txt` | 110 | Passed with the policy at the time; the raw (`--ignore-policy`) result was exactly the six proxy advisories of the removed dependency. |
| `requirements-security.txt` | 92 | Passed with the policy at the time (same six ignores). |
| `requirements-sprite-ml.txt` | 43 | Passes; nothing open. |
| `requirements-local-sd.txt` | 45 | 19 advisories: one fixable, 18 with no fixed version in any release. |

**Fixed.** `pygments>=2.20.0` is in `requirements-security.txt` and repeated in `requirements-local-sd.txt`. It clears SNYK-PYTHON-PYGMENTS-15746419 (CVE-2026-4539, ReDoS in `AdlLexer`; transformers > typer > rich > pygments). 2.20.0 is the lowest fixed release (2026-03-29). Fresh installs already got 2.21.0; an existing environment kept 2.19.2 until the floor. pygments is not in the base tree, so `requirements.txt` needs no Snyk SCM copy.

**Hardened.** MuseTalk checkpoints (`providers/video/musetalk_provider.py`) load only through `_restricted_load`: an explicit `torch.load(weights_only=True)` inside `torch.serialization.safe_globals`. The argument is explicit because `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD` reverts an implicit default to full pickle loading, and cannot override an explicit one. The UNet and Whisper checkpoints need no allowlist. The DWPose checkpoint (`yzd-v/DWPose`, mmengine format) needs exactly four numpy helpers, four numpy dtype classes and mmengine's `HistoryBuffer`, which maps to an inert local stub, so mmengine is never imported. Before this change DWPose did not load at all on torch >= 2.6, where restricted loading is already the default. Loading is refused, with a logged error, on torch below 2.6, where `weights_only=True` is bypassable (CVE-2025-32434). `tests/video/test_musetalk_weights_only.py` covers all of this, including a restricted load of the real installed DWPose checkpoint (skipped when it is absent).

**Open: installer torch pin.** `core/musetalk_installer.py` and `core/whisper_installer.py` install `torch==2.4.1` (cu121 index). That release has CVE-2025-32434 and sits below this repo's own `torch>=2.13.0` floor. After this change, MuseTalk refuses to load on it. Raising the pin needs a matching torchvision/torchaudio and a CUDA index that serves the release (cu121 stops at 2.5.1), and it must be checked against the MMLab stack (`mmcv`), whose prebuilt wheels track older torch. That is separate work.

**No upstream fix, not ignored.** Every advisory below is affected in all releases (`[0,]`; 19500670 from transformers 4.49.0). None is suppressed: no exception is approved.

| Package | Advisories (`SNYK-PYTHON-<PACKAGE>-`) | Class | ImageAI applicability |
| --- | --- | --- | --- |
| transformers | 14560695, 14563374, 14564275, 14564363, 14564364, 14564365, 14564366 | Code execution from a malicious checkpoint / config (`convert_config`, megatron_gpt2, weight parsing) | Reached only by loading an attacker-supplied model. `providers/local_sd.py` loads with `use_safetensors=True`, which refuses pickle weights. Upstream rejected several of these as out of scope. |
| transformers | 18965959 | Path traversal via a crafted local shard index `weight_map` | Requires a malicious local model directory. |
| transformers | 19500670 | `load_custom_generate()` runs model-supplied code before the trust check | No ImageAI code passes `trust_remote_code` or uses `custom_generate`. |
| diffusers | 14567485 | Code execution from a malicious model file | As for transformers. The MuseTalk VAE `.bin` goes through diffusers' loader, which calls `torch.load(weights_only=True)`. |
| diffusers | 18313062 | Path traversal via shard `weight_map` | Requires a malicious model index. |
| accelerate | 14566490, 18609772 | Checkpoint deserialization; shard-path traversal in `load_checkpoint_in_model` | ImageAI never calls accelerate's checkpoint loaders; diffusers uses accelerate for device placement. |
| torch | 15746467 | `.pt2` loader deserializes even with `weights_only=True` | ImageAI loads no `.pt2` (torch.export) files. |
| torch | 10332643, 10337825, 10337826, 10337834 | Local memory corruption / crash in `torch.jit`, NCCL reduce, the CUDA caching allocator | Local-access only; ImageAI calls none of these APIs directly. |

The residual risk is the one every local ML stack carries: a user loading a model ID or checkpoint from an untrusted source. Local SD is an optional extra. Its model list and custom model IDs come from the user, and `use_safetensors=True` is the defence. Snyk shows no fix, so floors cannot clear these. Ignoring them in `.snyk`, with a reason and an expiry, needs the maintainer's approval. Until then they stay open in the scan.


## October 23, 2026 dependency floors

No exception changed. Four floors were raised under the remediation rule: a reported advisory with a fixed version is fixed at once, at the lowest fixed version, whatever the release's age.

| Dependency | Previously allowed | Required version | Advisories |
| --- | --- | --- | --- |
| pillow | >=12.3.0 | >=13.0.0 | 39 GHSAs fixed only in 13.0.0 (no 12.x patch); 38 carry CVE IDs. Examples: GHSA-8g5g-8vmr-9782 (JPEG heap overflow), GHSA-cp9v-662q-vvx9, GHSA-27h8-gf7j-v5hc |
| rembg (Sprite ML) | >=2.0.60 | >=2.0.86 | rembg 2.0.85 and earlier require `pillow<13`, so the Sprite ML install forced vulnerable Pillow; 2.0.86 allows `<14` |
| anyio | unbounded | >=4.14.2 | CVE-2026-64847, CVE-2026-63374 (critical in Snyk), via httpx |
| fsspec | unbounded | >=2026.6.0 | CVE-2026-104851 (critical in Snyk), via huggingface-hub |

The Pillow, anyio, and fsspec floors are in both `requirements-security.txt` and the Snyk SCM block of `requirements.txt`. The rembg floor is in `requirements-sprite-ml.txt` and in `REMBG_SPEC` (`core/sprite/ml_install.py`), the source of truth for the in-app **Install ML backends** action; a test keeps the two in sync. Fresh installs already resolved past anyio and fsspec, but an existing environment kept 4.10.0 and 2025.9.0 until these floors were added.

Release checks:

- **Pillow 13.0.0.** All 83 files carry Trusted Publisher attestations (`python-pillow/Pillow`, `wheels.yml`, environment `release-pypi`) whose digests match.
- **rembg 2.0.86.** No PyPI attestations; no rembg release has them. Both files match PyPI's digests, and all 36 package `.py` files are byte-identical to GitHub tag `v2.0.86`, released by the maintainer the same minute. The release adds an `atlascloud` remote session that touches the network only when selected; ImageAI's `REMBG_MODELS` allowlist cannot select it.

`tests/test_pillow_dependency_security.py` runs GHSA-cp9v-662q-vvx9 (`Image.merge` with an `I` band 0) and GHSA-27h8-gf7j-v5hc (median filter on an equal-edge crop) in child processes. Both crash the interpreter on 12.3.0 and raise cleanly on 13.0.0. Base, base plus Sprite ML, and local SD resolve on Linux and Windows. Snyk scans pass with nothing open: `requirements.txt` against the maintainer's upgraded environment (106 dependencies, with the policy then in force) and the Sprite ML extras (44 dependencies).

## October 21, 2026 reassessment

The exceptions then in force expired and were renewed on this date. They were removed on 2026-11-18 with the dependency they covered; the transitive floors added the same day remain.

### Transitive dependency floors (same day)

| Dependency | Previously resolved | Required version | Advisories |
| --- | --- | --- | --- |
| filelock | 3.32.7 / 4.1.1 | >=4.2.1 | SNYK-PYTHON-FILELOCK-21280749 through 21280761; upstream GHSA-v4x8-3wr5-3wq8 (high) and 16 other CVE-flagged advisories |

filelock reaches ImageAI through huggingface-hub, which the local SD stack uses. 4.2.1 was published on 2026-10-17, inside the seven-day window. Upstream published every one of these advisories as a CVE-flagged GitHub security advisory patched in 4.2.1, so it qualifies under the documented exception for CVE fixes. Like the other floors, it is repeated in `requirements.txt` for Snyk SCM. Base, local SD, and Sprite ML manifests resolve with it on Linux and Windows. `tests/test_filelock_dependency_security.py` checks GHSA-69hj-f68j-2879 by behaviour: it fails on 4.1.1 and passes on 4.2.1 (POSIX only).

| Dependency | Previously resolved | Required version | Advisories |
| --- | --- | --- | --- |
| certifi | 2026.7.22 | >=2026.10.19 | SNYK-PYTHON-CERTIFI-21280764; upstream GHSA-6q48-6c7w-9gw2 (critical; PYSEC-2026-4320) |

2026.7.22 trusts emSign ECC Root CA - G3, whose intermediates were revoked for key compromise. 2026.10.18 removed every emSign root, and 2026.10.19 restored the three unaffected ones (G1, C1, ECC C3); Snyk tracks the over-removal. requests, httpx, and the Google client libraries verify provider TLS, and therefore API-key traffic, against this bundle.

2026.10.19 is younger than seven days and the advisory has no CVE ID, so the maintainer approved an explicit exception to the package-age rule. The approval depended on an artifact audit, and every check passed:

- **Wheel integrity.** The PyPI wheel's SHA-256 matches PyPI's published digest.
- **Contents.** Compared with 2026.7.22, the only code change is `__version__`; `core.py` and `__main__.py` are byte-identical. Metadata gains one classifier and a newer setuptools generator.
- **CA bundle.** `cacert.pem` drops exactly one root, emSign ECC Root CA - G3, and adds or alters none. That matches upstream PRs #437 (remove all emSign roots) and #440 (restore G1, C1, C3).
- **Provenance.** The wheel's `cacert.pem` is byte-identical to upstream tag `2026.10.19`, and to merge commit `662df63` of #440. PyPI's attestation names Trusted Publisher `certifi/python-certifi`, workflow `release.yml`, environment `release`, and its digest matches the wheel. The Sigstore certificate names `refs/tags/2026.10.19` at `662df63`. The Sigstore signature itself was not verified independently; PyPI checks it on upload.

`tests/test_certifi_dependency_security.py` checks the bundle by fingerprint. It fails on 2026.7.22 (compromised root present) and on 2026.10.18 (unaffected roots missing), and passes on 2026.10.19. All manifests resolve with the floor on Linux and Windows.

## October 13, 2026 reassessment

Fresh CLI scans of main at `410b3d4` under organization `lelandg`, using the
preserved Python 3.12 remediation environment, covered 110 dependencies. The
unfiltered result contained 12 distinct advisories; the policy-filtered result
contained nine. The difference was the three exceptions then in force. Neither
result was a passing scan.

The dependency requirements now address the advisories with published fixes:

| Dependency | Previously scanned | Required version | Advisory suffixes (`SNYK-PYTHON-<PACKAGE>-`) |
| --- | --- | --- | --- |
| urllib3 | 2.7.0 | >=2.8.0 | 20302844, 20302845, 20302846 |
| multidict | 6.8.0 | >=6.9.1 | 20510280 |

These bounds appear in both the base manifest and security constraints because
[Snyk's SCM resolver omits constraint-file directives](https://docs.snyk.io/supported-languages/supported-languages-list/python/scm-integrations-and-python).

The urllib3 response-parsing issues have a relevant application boundary:
provider image URLs and model downloads reach Requests/urllib3. The certificate
finding additionally requires specific HTTPS-proxy TLS configuration; no direct
application configuration was found. The multidict issue concerns C-extension
items-view set operations; application/transitive reachability was not proven.
Both dependencies are upgraded rather than suppressed.

