#!/bin/bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
package_dir="$(cd "${script_dir}/.." && pwd)"
dist_dir="${package_dir}/dist"
app_path="${dist_dir}/Background Automator.app"
contents_path="${app_path}/Contents"
macos_path="${contents_path}/MacOS"
resources_path="${contents_path}/Resources"
executable_name="BackgroundAutomatorApp"
resource_bundle_name="BackgroundAutomator_BackgroundAutomatorRuntime.bundle"

expected_app_path="${package_dir}/dist/Background Automator.app"
if [[ "${app_path}" != "${expected_app_path}" ]]; then
    echo "Refusing to clean an unexpected app path: ${app_path}" >&2
    exit 1
fi

cd "${package_dir}"
swift build \
    -c release \
    -Xswiftc -warnings-as-errors \
    --product "${executable_name}"

bin_path="$(swift build -c release --show-bin-path)"
source_executable="${bin_path}/${executable_name}"
source_resource_bundle="${bin_path}/${resource_bundle_name}"

test -x "${source_executable}"
test -d "${source_resource_bundle}"
test -f "${source_resource_bundle}/default-rules.json"

/bin/rm -rf -- "${app_path}"
/bin/mkdir -p "${macos_path}" "${resources_path}"
/usr/bin/install -m 755 \
    "${source_executable}" \
    "${macos_path}/${executable_name}"
/usr/bin/install -m 644 \
    "${package_dir}/Resources/Info.plist" \
    "${contents_path}/Info.plist"
/usr/bin/ditto \
    "${source_resource_bundle}" \
    "${resources_path}/${resource_bundle_name}"

echo "Built app: ${app_path}"
