#!/bin/sh
# Starts an image with an empty library, logs in and opens every page in every language.
# Fails on any page that does not answer 200 and on any error in the server log.
#   tests/smoke.sh <image>
set -eu
IMAGE=$1
NAME=gamedock-smoke
PORT=18465
docker rm -f $NAME >/dev/null 2>&1 || true
docker run -d --name $NAME -p $PORT:8465 \
    -e USER_ADMIN_NAME=admin -e USER_ADMIN_PASSWORD=smoke-test-123 "$IMAGE" >/dev/null
trap 'docker rm -f $NAME >/dev/null 2>&1 || true' EXIT

for i in $(seq 1 60); do
    curl -fs -o /dev/null "http://127.0.0.1:$PORT/login" && break
    sleep 2
done

JAR=$(mktemp)
curl -fs -o /dev/null -c "$JAR" -b "$JAR" -d "user=admin&password=smoke-test-123" "http://127.0.0.1:$PORT/login"

failed=0
for lang in en pt-BR es; do
    curl -fs -o /dev/null -c "$JAR" -b "$JAR" "http://127.0.0.1:$PORT/language/$lang"
    for page in / /setup /admin /admin/files /admin/settings; do
        code=$(curl -s -o /tmp/page.html -w "%{http_code}" -b "$JAR" "http://127.0.0.1:$PORT$page")
        if [ "$code" != 200 ] || ! grep -q "<html lang=\"$lang\"" /tmp/page.html; then
            echo "FAIL $lang $page -> $code"
            failed=1
        else
            echo "ok   $lang $page"
        fi
    done
done

for api in /api/settings /api/users; do
    code=$(curl -s -o /dev/null -w "%{http_code}" -b "$JAR" "http://127.0.0.1:$PORT$api")
    [ "$code" = 200 ] && echo "ok   $api" || { echo "FAIL $api -> $code"; failed=1; }
done

if docker logs $NAME 2>&1 | grep -E "Traceback|ERROR" ; then
    echo "FAIL errors in the server log"
    failed=1
fi
exit $failed
