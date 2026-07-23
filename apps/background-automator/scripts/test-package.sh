#!/bin/bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
package_dir="$(cd "${script_dir}/.." && pwd)"
app_path="${package_dir}/dist/Background Automator.app"
contents_path="${app_path}/Contents"
executable_path="${contents_path}/MacOS/BackgroundAutomatorApp"
plist_path="${contents_path}/Info.plist"
resource_bundle_path="${contents_path}/Resources/BackgroundAutomator_BackgroundAutomatorRuntime.bundle"
rules_path="${resource_bundle_path}/default-rules.json"

"${script_dir}/build-app.sh"

test -d "${app_path}"
test -x "${executable_path}"
test -f "${plist_path}"
/usr/bin/plutil -lint "${plist_path}"

test "$(/usr/bin/plutil -extract CFBundleExecutable raw -o - "${plist_path}")" = "BackgroundAutomatorApp"
test "$(/usr/bin/plutil -extract CFBundleIdentifier raw -o - "${plist_path}")" = "com.dayejeong.background-automator"
test "$(/usr/bin/plutil -extract CFBundleDisplayName raw -o - "${plist_path}")" = "Background Automator"
test "$(/usr/bin/plutil -extract CFBundlePackageType raw -o - "${plist_path}")" = "APPL"
test "$(/usr/bin/plutil -extract LSUIElement raw -o - "${plist_path}")" = "true"
test "$(/usr/bin/plutil -extract LSMinimumSystemVersion raw -o - "${plist_path}")" = "14.0"

test -d "${resource_bundle_path}"
test -f "${rules_path}"
/usr/bin/cmp -s \
    "${package_dir}/Sources/BackgroundAutomatorRuntime/Resources/default-rules.json" \
    "${rules_path}"
json_check='import Foundation; let url = URL(fileURLWithPath: CommandLine.arguments[1]); let value = try JSONSerialization.jsonObject(with: Data(contentsOf: url)); guard value is [String: Any] else { fatalError("rules must be an object") }'
swift -e "${json_check}" "${rules_path}"

echo "Packaging smoke test passed: ${app_path}"
