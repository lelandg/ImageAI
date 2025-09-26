#!/usr/bin/env bash
set -euo pipefail

log() { echo -e "\n=== $1 ==="; }

# 1. Check node and npm versions
log "Node / npm versions"
node -v || echo "node not found"
npm -v || echo "npm not found"

# 2. Test raw connectivity
log "Ping npm registry"
ping -c 4 registry.npmjs.org || echo "Ping failed"

# 3. DNS resolution
log "DNS resolution"
getent hosts registry.npmjs.org || echo "DNS lookup failed"

# 4. HTTPS test via curl
log "HTTPS fetch test"
curl -I https://registry.npmjs.org/ || echo "curl failed"

# 5. NPM registry test
log "npm ping"
npm ping || echo "npm ping failed"

# 6. Try a trivial install
TESTDIR=$(mktemp -d)
cd "$TESTDIR"
log "npm init + install lodash (test)"
npm init -y >/dev/null 2>&1
npm install lodash --verbose || echo "npm install failed"
cd -
rm -rf "$TESTDIR"

# 7. Disk speed check (to see if BitLocker overhead is issue)
log "Disk speed test"
dd if=/dev/zero of=testfile bs=1M count=256 conv=fdatasync 2>&1 | tee disk_test.log
rm -f testfile

log "Done. Review above output."