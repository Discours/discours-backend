database_name="discoursio"
remote_backup_dir="/var/backups/mongodb"
user="root"
host="v2.discours.io"
server="$user@$host"
dump_dir="./dump"
local_backup_filename="discours-backup.bson.gz.tar"

echo "DATABASE RESET STARTED"
echo "server: $server"
echo "remote backup directory: $remote_backup_dir"

echo "Searching for last backup file..."
last_backup_filename=$(ssh $server "ls -t $remote_backup_dir | head -1")
if [ $? -ne 0 ]; then { echo "Failed to get last backup filename, aborting." ; exit 1; } fi
echo "Last backup file found: $last_backup_filename"

echo "Downloading..."
scp $server:$remote_backup_dir/"$last_backup_filename" "$local_backup_filename"
if [ $? -ne 0 ]; then { echo "Failed to download backup file, aborting." ; exit 1; } fi
echo "Backup file $local_backup_filename downloaded successfully"

echo "Creating dump directory: $dump_dir"
mkdir -p "$dump_dir"
if [ $? -ne 0 ]; then { echo "Failed to create dump directory, aborting." ; exit 1; } fi
echo "$dump_dir directory created"

echo "Unpacking backup file $local_backup_filename to $dump_dir"
tar -xzf "$local_backup_filename" --directory "$dump_dir" --strip-components 1
if [ $? -ne 0 ]; then { echo "Failed to unpack backup, aborting." ; exit 1; } fi
echo "Backup file $local_backup_filename successfully unpacked to $dump_dir"

echo "Removing backup file $local_backup_filename"
rm "$local_backup_filename"
if [ $? -ne 0 ]; then { echo "Failed to remove backup file, aborting." ; exit 1; } fi
echo "Backup file removed"

echo "Dropping database $database_name"
dropdb $database_name --force
if [ $? -ne 0 ]; then { echo "Failed to drop database, aborting." ; exit 1; } fi
echo "Database $database_name dropped"

echo "Creating database $database_name"
createdb $database_name
if [ $? -ne 0 ]; then { echo "Failed to create database, aborting." ; exit 1; } fi
echo "Database $database_name successfully created"

echo "BSON -> JSON"
python3 server.py bson
if [ $? -ne 0 ]; then { echo "BSON -> JSON failed, aborting." ; exit 1; } fi

echo "Start migration"
python3 server.py migrate
if [ $? -ne 0 ]; then { echo "Migration failed, aborting." ; exit 1; } fi
echo 'Done!'

