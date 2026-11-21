// Fail if a production dependency's license doesn't fit the project's own license
// (`license` in package.json). Reads `pnpm licenses list --prod --json`; the same rule as
// backend/scripts/check_licenses.py, which explains it: permissive licenses and LGPL always;
// GPL-3.0, AGPL-3.0 and GPL-2.0 "or later" only in an (A)GPL-3.0 project, which in turn
// rejects GPL-2.0-only, a GPL without a version, EPL-1.0, CDDL and MPL-1.1; never SSPL or
// a package without license information (check it by hand and add it to ALLOW).
// Alternatives ("MIT OR GPL-2.0") pass if one of them does.
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'

const SSPL = /SSPL|Server Side Public/i
const LESSER = /LGPL|Lesser General Public|Library General Public/i
// Whole tokens only, so "LGPL" doesn't count as "GPL".
const GPL = /(?<![A-Za-z])A?GPL|General Public License/i
const V3_OR_LATER = /v3|(?<![\d.])3(\.0)?(?![\d.])|or[- ]later|\+/i
const GPL_INCOMPATIBLE = new RegExp(
  'EPL-1|Eclipse Public License 1|CDDL|Common Development and Distribution|' + 'MPL-1\\.1|Mozilla Public License 1\\.1',
  'i',
)
const NO_LICENSE = /^(|UNKNOWN|UNLICENSED|Unknown|NOASSERTION)$/
// Packages whose metadata is wrong or ambiguous, after checking them by hand:
// { 'package-name': 'reason' }
const ALLOW = {}

const own = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')).license ?? ''
const copyleft = /^A?GPL-3\.0/.test(own)
const strip = (s) => s.replace(/^[()\s]+|[()\s]+$/g, '')
const compatiblePart = (license) => {
  if (NO_LICENSE.test(license) || SSPL.test(license)) return false
  if (LESSER.test(license)) return true
  if (GPL.test(license)) return copyleft && V3_OR_LATER.test(license)
  return !(copyleft && GPL_INCOMPATIBLE.test(license))
}
const compatible = (license) =>
  strip(license)
    .split(/\s+OR\s+|;\s*/i)
    .some((alternative) =>
      strip(alternative)
        .split(/\s+AND\s+/i)
        .every((part) => compatiblePart(strip(part))),
    )

const byLicense = JSON.parse(
  // On Windows pnpm is a .cmd script, which Node starts only through a shell (fixed arguments).
  execFileSync('pnpm', ['licenses', 'list', '--prod', '--json'], {
    encoding: 'utf8',
    shell: process.platform === 'win32',
  }),
)
const bad = []
for (const [license, packages] of Object.entries(byLicense)) {
  if (compatible(license)) continue
  for (const pkg of packages) {
    if (pkg.name in ALLOW) continue
    const versions = pkg.versions?.join(', ') ?? ''
    bad.push(`${pkg.name} ${versions}: ${license || 'no license information'}`)
  }
}
for (const line of bad) console.log(`incompatible license: ${line}`)
if (!bad.length) console.log('licenses ok')
process.exit(bad.length ? 1 : 0)
