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

# 빌드 도장: 어느 빌드가 남긴 기록인지 로그에서 바로 갈라 보기 위한 것이다.
# 시각으로 자르면 '빌드했지만 앱을 다시 켜지 않은' 구간을 새 빌드로 잘못
# 집계한다(2026-07-26 실측). 커밋하지 않고 빌드하는 일이 잦아 해시만으로는
# 빌드끼리 구분되지 않으므로 빌드 시각을 함께 붙인다. 연도를 빼도 되는 건
# builds.jsonl이 첫 실행 시각을 온전한 날짜로 따로 남기기 때문이다.
last_sha_file="${dist_dir}/.last-build-sha"
head_sha="$(git -C "${package_dir}" rev-parse --short HEAD)"
dirty_mark=""
if [[ -n "$(git -C "${package_dir}" status --porcelain)" ]]; then
    dirty_mark="+dirty"
fi
build_identifier="${head_sha}${dirty_mark}-$(date +%m%dT%H%M)"

# 직전 빌드 이후로 들어간 커밋 제목 = 이 빌드가 무엇을 바꿨는지.
build_summary=""
if [[ -f "${last_sha_file}" ]]; then
    last_sha="$(cat "${last_sha_file}")"
    if git -C "${package_dir}" cat-file -e "${last_sha}^{commit}" 2>/dev/null
    then
        build_summary="$(
            git -C "${package_dir}" log --format=%s "${last_sha}..HEAD" \
                | awk 'NR>1 { printf "; " } { printf "%s", $0 } END { print "" }'
        )"
    fi
fi
if [[ -z "${build_summary}" ]]; then
    # 첫 빌드이거나, 직전 해시가 rebase·squash로 사라진 경우.
    build_summary="$(git -C "${package_dir}" log -1 --format=%s)"
fi
if [[ -n "${dirty_mark}" ]]; then
    build_summary="커밋 안 한 변경 포함 — ${build_summary}"
fi

/usr/bin/plutil -replace BABuildIdentifier \
    -string "${build_identifier}" "${contents_path}/Info.plist"
/usr/bin/plutil -replace BABuildSummary \
    -string "${build_summary}" "${contents_path}/Info.plist"

stamped="$(
    /usr/bin/plutil -extract BABuildIdentifier raw -o - \
        "${contents_path}/Info.plist"
)"
if [[ "${stamped}" != "${build_identifier}" ]]; then
    echo "Build stamp did not survive: ${stamped}" >&2
    exit 1
fi
printf '%s\n' "${head_sha}" > "${last_sha_file}"

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
