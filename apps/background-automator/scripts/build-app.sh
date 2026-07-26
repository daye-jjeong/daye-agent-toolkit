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

bundle_identifier="$(
    /usr/bin/plutil -extract CFBundleIdentifier raw -o - \
        "${contents_path}/Info.plist"
)"
if [[ "${bundle_identifier}" != "com.dayejeong.background-automator" ]]; then
    echo "Unexpected bundle identifier: ${bundle_identifier}" >&2
    exit 1
fi

# 자체 서명 코드사인 인증서로 서명하면 코드가 바뀌어도 지정 요구사항
# (designated requirement)이 인증서 기준으로 동일해 macOS 권한(TCC)이
# 유지된다. 인증서가 없으면 ad-hoc(-)으로 폴백하되, 이 경우 재빌드마다
# 화면 기록·손쉬운 사용·입력 모니터링 권한을 다시 허용해야 한다.
sign_identity="Background Automator Local Signing"
if ! /usr/bin/security find-certificate -c "${sign_identity}" \
    >/dev/null 2>&1; then
    echo "Self-signed identity not found; falling back to ad-hoc signing." >&2
    sign_identity="-"
fi

/usr/bin/codesign \
    --force \
    --sign "${sign_identity}" \
    --identifier "${bundle_identifier}" \
    --timestamp=none \
    "${macos_path}/${executable_name}"
/usr/bin/codesign \
    --force \
    --sign "${sign_identity}" \
    --identifier "${bundle_identifier}" \
    --timestamp=none \
    "${app_path}"
/usr/bin/codesign \
    --verify \
    --deep \
    --strict \
    --verbose=2 \
    "${app_path}"

echo "Built app: ${app_path}"
