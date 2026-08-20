#!/bin/bash
# m-agent 안정 코드서명 인증서 생성 + 로그인 키체인 등록.
#
# 왜: ad-hoc 서명 앱은 macOS 권한(TCC)이 바이너리 해시에 묶여, 재빌드할
# 때마다 신원이 바뀌어 화면기록·손쉬운사용·입력모니터링 권한이 깨진다.
# 자체 서명 인증서로 서명하면 신원이 고정돼 재빌드해도 권한이 유지된다.
#
# 한 번만 실행하면 된다. 그 뒤 build-app.sh가 이 인증서(CN "m-agent Local
# Signing")를 자동으로 찾아 서명한다. 없으면 build-app.sh는 ad-hoc으로 떨어진다.
#
# 인증서를 만든 뒤 이미 설치된 앱은 재서명 한 번 필요:
#   codesign -s "m-agent Local Signing" --force --deep /Applications/m-agent.app
# 그리고 권한을 이번 한 번만 새로 받는다(신원이 바뀌었으므로):
#   tccutil reset All com.dayejeong.m-agent   # 옛 항목 정리
#   그다음 앱 재실행 → 시작 → 권한 허용
set -e

NAME="m-agent Local Signing"
PW="tmpimport"                     # p12 임시 암호(등록 후 버려짐). 키체인 암호와 무관.
OSSL="/opt/homebrew/bin/openssl"   # 3.x: -legacy 지원 (macOS security 호환 p12)
D="$(mktemp -d)"
trap 'rm -rf "$D"' EXIT
cd "$D"

if /usr/bin/security find-identity -p codesigning 2>/dev/null | grep -q "${NAME}"; then
    echo "이미 존재: ${NAME}"
    exit 0
fi

cat > cert.cnf <<EOF
[req]
distinguished_name = dn
x509_extensions = v3
prompt = no
[dn]
CN = ${NAME}
[v3]
basicConstraints = critical, CA:false
keyUsage = critical, digitalSignature
extendedKeyUsage = critical, codeSigning
EOF

"${OSSL}" req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem \
    -days 3650 -nodes -config cert.cnf
# -legacy: macOS security가 읽는 구형 PKCS12 암호화/MAC (openssl 3.x 기본은 못 읽음)
"${OSSL}" pkcs12 -export -legacy -inkey key.pem -in cert.pem \
    -out id.p12 -passout "pass:${PW}" -name "${NAME}"

# 로그인 키체인에 등록, codesign이 개인키를 쓰도록 허용(-T).
/usr/bin/security import id.p12 -P "${PW}" -T /usr/bin/codesign

# 자체 서명이라 신뢰(-v valid)엔 안 뜨지만, codesign은 서명에 쓸 수 있다.
if /usr/bin/security find-identity -p codesigning | grep -q "${NAME}"; then
    echo "생성 성공: ${NAME}"
    echo "이제 build-app.sh가 이 인증서로 서명한다."
else
    echo "생성 실패 — 아이덴티티 목록에 없음" >&2
    exit 1
fi
