#!/bin/sh
# Writes nginx's list of the proxies whose X-Forwarded-For it believes (docker/nginx.conf) from
# TRUSTED_PROXIES: addresses or CIDR ranges, separated by commas or spaces; "none" for only the
# container itself. Default: the private networks, where a proxy in front usually is.
set -e

conf="${1:-/etc/nginx/trusted-proxies.conf}"
proxies="${TRUSTED_PROXIES:-10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 fc00::/7}"
[ "$proxies" = "none" ] && proxies=""

# Checked first, then written at once: the container's user may write the file, not its directory.
lines="set_real_ip_from 127.0.0.0/8;
set_real_ip_from ::1/128;"
for proxy in $(echo "$proxies" | tr ',' ' '); do
    case "$proxy" in
        *[!0-9a-fA-F.:/]*)
            echo "TRUSTED_PROXIES: not an address or CIDR range: $proxy" >&2
            exit 1
            ;;
    esac
    lines="$lines
set_real_ip_from $proxy;"
done
echo "$lines" > "$conf"
