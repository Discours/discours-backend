database_name="discoursio"

echo "DATABASE MIGRATION STARTED"

echo "Dropping database $database_name"
dropdb $database_name --force
if [ $? -ne 0 ]; then { echo "Failed to drop database, aborting." ; exit 1; } fi
echo "Database $database_name dropped"

echo "Creating database $database_name"
createdb $database_name
if [ $? -ne 0 ]; then { echo "Failed to create database, aborting." ; exit 1; } fi
echo "Database $database_name successfully created"

echo "Start migration"
python3 server.py migrate
if [ $? -ne 0 ]; then { echo "Migration failed, aborting." ; exit 1; } fi
echo 'Done!'

