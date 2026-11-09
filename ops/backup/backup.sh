#!/bin/sh
# Encrypted, reproducible PostgreSQL backup (C-16, design D8).
#
#   backup.sh backup                 -> /backups/clinica-<UTC>.dump.enc + .sha256
#   backup.sh verify <archivo.enc>   -> checksum + decrypt to `pg_restore --list`
#
# BACKUP_PASSPHRASE is mandatory and has no default. The plain dump never
# survives the command: it is written to a temporary file and removed.

set -eu

DIR_BACKUPS="${BACKUP_DIR:-/backups}"
POSTGRES_HOST="${POSTGRES_HOST:-db}"
POSTGRES_USER="${POSTGRES_USER:-clinica}"
POSTGRES_DB="${POSTGRES_DB:-clinica}"

requerir_passphrase() {
    if [ -z "${BACKUP_PASSPHRASE:-}" ]; then
        echo "BACKUP_PASSPHRASE es obligatoria (sin default, R-08)" >&2
        exit 1
    fi
}

requerir_password() {
    if [ -z "${POSTGRES_PASSWORD:-}" ]; then
        echo "POSTGRES_PASSWORD es obligatoria para pg_dump" >&2
        exit 1
    fi
}

modo="${1:-backup}"

case "$modo" in
    backup)
        requerir_passphrase
        requerir_password
        mkdir -p "$DIR_BACKUPS"
        marca="$(date -u +%Y%m%dT%H%M%SZ)"
        archivo="$DIR_BACKUPS/clinica-$marca.dump.enc"
        temporal="$DIR_BACKUPS/.clinica-$marca.dump"
        trap 'rm -f "$temporal"' EXIT INT TERM

        PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
            -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
            -Fc --no-owner --no-acl > "$temporal"
        openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
            -pass env:BACKUP_PASSPHRASE -in "$temporal" -out "$archivo"
        sha256sum "$archivo" > "$archivo.sha256"
        rm -f "$temporal"
        trap - EXIT INT TERM
        echo "$archivo"
        ;;

    verify)
        requerir_passphrase
        archivo="${2:-}"
        if [ -z "$archivo" ]; then
            echo "Uso: backup.sh verify /backups/<archivo>.dump.enc" >&2
            exit 2
        fi
        if [ ! -f "$archivo" ]; then
            echo "No existe el archivo $archivo" >&2
            exit 1
        fi
        checksum="$archivo.sha256"
        if [ ! -f "$checksum" ]; then
            echo "Falta el checksum $checksum" >&2
            exit 1
        fi

        # The checksum runs before decrypting: a tampered byte fails here.
        ( cd "$(dirname "$archivo")" && sha256sum -c "$(basename "$checksum")" )

        # `pg_restore --list` consumes the stream: no clear-text dump is kept.
        if ! openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -salt \
            -pass env:BACKUP_PASSPHRASE -in "$archivo" \
            | pg_restore --list > /dev/null; then
            echo "Verificación fallida: passphrase incorrecta o archivo dañado" >&2
            exit 1
        fi
        echo "OK $archivo"
        ;;

    *)
        echo "Modo desconocido: $modo (usar backup|verify)" >&2
        exit 2
        ;;
esac
