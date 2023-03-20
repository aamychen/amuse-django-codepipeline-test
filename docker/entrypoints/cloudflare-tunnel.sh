#!/bin/ash

set -e
cloudflared service install $CLOUDFLARE_TUNNEL || true
/etc/init.d/cloudflared stop
rm -f /var/run/cloudflared.pid
/etc/init.d/cloudflared start

exec "$@"
