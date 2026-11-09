# Encrypted backup tools (C-16, design D8).
# `postgres:16-alpine` ships pg_dump/pg_restore; Alpine's openssl CLI is added
# here because the API image has openssl but no pg_dump.
FROM postgres:16-alpine

RUN apk add --no-cache openssl

WORKDIR /opt/backup
COPY backup.sh /opt/backup/backup.sh
RUN chmod 0755 /opt/backup/backup.sh

ENTRYPOINT ["/opt/backup/backup.sh"]
CMD ["backup"]
