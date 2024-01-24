#!/bin/bash
# This version is a2.1 because have update in postgres dsn to ip adress

export PATH="$PATH:/usr/local/sbin:/usr/sbin:/sbin"

APP="discoursio-api"
SSH_KEY="/root/.ssh/id_rsa"
YMD=$(date "+%Y-%m-%d")
DUMP_PATH="/var/lib/dokku/data/storage/discoursio-api/migration/dump"
DATA_PATH="/var/lib/dokku/data/storage/discoursio-api/migration/data"
SCRIPT_PATH="/root/robo_script"
MONGO_DB_PATH="/var/backups/mongodb"
POSTGRES_DB_PATH="/var/backups/postgres"
CONTAINER_ID=$(docker ps | grep "$APP" | /bin/awk '{print $1}')
OLD_DB=$(dokku postgres:app-links "$APP")
NEW_DB="discoursio-db-$YMD"
DSN_OLD_DB=$(dokku config:get "$APP" DATABASE_URL)
LAST_DB_MONGO=$(find "$MONGO_DB_PATH" -printf '%T@ %p\n' | sort -nk1 | grep discours | tail -n 1 | /bin/awk '{print $2}')
LAST_DB_POSTGRES=$(find "$POSTGRES_DB_PATH" -printf '%T@ %p\n' | sort -nk1 | grep discours | tail -n 1 | /bin/awk '{print $2}')
NEW_HOST="testapi.discours.io"
NEW_PATH="/root/."

increase_swap() {
  echo "Make Swap 6GB"
  swapoff -a
  dd if=/dev/zero of=/swap_file bs=1M count=6144
  chmod 600 /swap_file
  mkswap /swap_file
  swapon /swap_file
}

check_container() {
  if [ -z "$CONTAINER_ID" ]; then
    echo "Container $APP is not Running"
    exit 1
  fi
  echo "Container $APP is running"
}

check_dump_dir() {
    if [ ! -d $DUMP_PATH ]; then
        echo "$DUMP_PATH dosn't exist"
        exit 1
    else
        echo "$DUMP_PATH exist (^.-)"
    fi
    if [ ! -d $DATA_PATH ]; then
        echo "$DATA_PATH dosn't exist"
        exit 1
    else
        echo "$DATA_PATH exist (-.^)"
    fi
}

check_old_db() {
  if [ -z "$OLD_DB" ]; then
    echo "DB postgres is not set"
    exit 1
  fi
  echo "DB postgres is set"
}

check_app_config() {
  if $(dokku docker-options:report $APP | grep -q $DUMP_PATH) && $(dokku docker-options:report $APP | grep -q $DATA_PATH); then
    echo "DUMP_PATH and DATA_PATH exist in $APP config"
  else
    echo "DUMP_PATH or DATA_PATH does not exist in $APP config"
    exit 1
  fi
}


untar_mongo_db() {
  if [ -d "$DUMP_PATH/discours" ]; then
    echo "$DUMP_PATH/discours File exists"
  else
   tar xzf $LAST_DB_MONGO && mv *.bson/discours $DUMP_PATH/ && rm -R *.bson
  fi
  echo "Untar Bson from mongoDB"
}

bson_mode() {
  CONTAINER_ID=$(docker ps | grep "$APP" | /bin/awk '{print $1}')

   if [ -z "$CONTAINER_ID" ]; then
    echo "Container $APP is not Running"
    exit 1
  fi

  docker exec -t "$CONTAINER_ID" rm -rf dump
  docker exec -t "$CONTAINER_ID" ln -s /migration/dump dump

  docker exec -t "$CONTAINER_ID" rm -rf migration/data
  docker exec -t "$CONTAINER_ID" ln -s /migration/data migration/data

  docker exec -t "$CONTAINER_ID" python3 server.py bson
}

create_new_postgres_db() {
  echo "Create NEW postgres DB"
  dokku postgres:create "$NEW_DB"

  # Get the internal IP address
  INTERNAL_IP=$(dokku postgres:info "$NEW_DB" | grep 'Internal ip:' | awk '{print $3}')

  # Get the DSN without the hostname
  DSN=$(dokku postgres:info "$NEW_DB" --dsn | sed 's/postgres/postgresql/')

  # Replace the hostname with the internal IP address
  DSN_NEW_DB=$(echo "$DSN" | sed "s@dokku-postgres-$NEW_DB@$INTERNAL_IP@")

  echo "$DSN_NEW_DB"
  dokku postgres:link "$NEW_DB" "$APP" -a "MIGRATION_DATABASE"
  dokku config:set "$APP" MIGRATION_DATABASE_URL="$DSN_NEW_DB" --no-restart

  # Wait for 120 seconds
  echo "Waiting for 120 seconds..."
  for i in {1..120}; do
    sleep 1
    echo -n "(^.^') "
  done
}

migrate_jsons() {

CONTAINER_ID=$(docker ps | grep $APP | /bin/awk '{print $1}')

 if [ -z "$CONTAINER_ID" ]; then
    echo "Container $APP is not Running"
    exit 1
  fi

docker exec -t "$CONTAINER_ID" rm -rf dump
docker exec -t "$CONTAINER_ID" ln -s /migration/dump dump

docker exec -t "$CONTAINER_ID" rm -rf migration/data
docker exec -t "$CONTAINER_ID" ln -s /migration/data migration/data

docker exec -t --env DATABASE_URL="$DSN_NEW_DB" "$CONTAINER_ID" python3 server.py migrate
}

restart_and_clean() {
dokku ps:stop "$APP"
dokku config:unset "$APP" MIGRATION_DATABASE_URL --no-restart
dokku config:unset "$APP" DATABASE_URL --no-restart
dokku config:set "$APP" DATABASE_URL="$DSN_NEW_DB" --no-restart
dokku postgres:unlink "$OLD_DB" "$APP"
dokku ps:start "$APP"
}

send_postgres_dump() {
echo "send postgres.dump to $NEW_HOST"
scp -i "$SSH_KEY" -r "$LAST_DB_POSTGRES" "root@$NEW_HOST:$NEW_PATH"
}

delete_files() {
rm -rf $DUMP_PATH/*
rm -rf $DATA_PATH/*
}

configure_pgweb() {
echo "config PGWEB"
dokku ps:stop pgweb
dokku config:unset pgweb DATABASE_URL --no-restart
dokku postgres:unlink "$OLD_DB" pgweb
dokku postgres:link "$NEW_DB" pgweb -a "DATABASE"
dokku postgres:destroy "$OLD_DB" -f
dokku ps:start pgweb
}

rm_old_db() {
  echo "remove old DB"
  dokku postgres:destroy "$OLD_DB" -f
}

decrease_swap() {
echo "make swap 2gb again"
swapoff -a
dd if=/dev/zero of=/swap_file bs=1M count=2048
chmod 600 /swap_file
mkswap /swap_file
swapon /swap_file
}

# Main script flow
increase_swap
check_container
check_dump_dir
check_old_db
check_app_config
untar_mongo_db

if bson_mode; then
  create_new_postgres_db
else
  echo "BSON move didn't work well! ERROR!"

  decrease_swap
  delete_files

  exit 1
fi

if migrate_jsons; then
  restart_and_clean
else
  echo "MIGRATE move didn't work well! ERROR!"

  delete_files
  rm_old_db
  decrease_swap

  exit 1
fi

send_postgres_dump
delete_files
#configure_pgweb
rm_old_db
decrease_swap
