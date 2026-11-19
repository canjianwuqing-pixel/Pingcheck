#!/bin/sh
set -eu

CONFIG_PATH="${SS_CONFIG_PATH:-/pingcheck-data/ss-client/config.json}"
POLL_INTERVAL="${SS_POLL_INTERVAL:-2}"
CURRENT_HASH=""
CHILD_PID=""

stop_client() {
    if [ -n "$CHILD_PID" ] && kill -0 "$CHILD_PID" 2>/dev/null; then
        kill -TERM "$CHILD_PID" 2>/dev/null || true
        wait "$CHILD_PID" 2>/dev/null || true
    fi
    CHILD_PID=""
}

start_client() {
    echo "Shadowsocks client configuration activated"
    sslocal --log-without-time -c "$CONFIG_PATH" &
    CHILD_PID="$!"
}

shutdown() {
    stop_client
    exit 0
}

trap shutdown INT TERM

while true; do
    if [ -s "$CONFIG_PATH" ]; then
        NEXT_HASH="$(sha256sum "$CONFIG_PATH" | cut -d ' ' -f 1)"
        if [ "$NEXT_HASH" != "$CURRENT_HASH" ]; then
            stop_client
            start_client
            CURRENT_HASH="$NEXT_HASH"
        elif [ -z "$CHILD_PID" ] || ! kill -0 "$CHILD_PID" 2>/dev/null; then
            if [ -n "$CHILD_PID" ]; then
                wait "$CHILD_PID" 2>/dev/null || true
            fi
            echo "Shadowsocks client stopped; restarting"
            start_client
        fi
    else
        if [ -n "$CHILD_PID" ]; then
            stop_client
            echo "Shadowsocks client waiting for configuration"
        fi
        CURRENT_HASH=""
    fi
    sleep "$POLL_INTERVAL" &
    wait "$!"
done
