#!/usr/bin/env bash

##########################################################################
# restore_rds_instance.sh
#
# Usage:
#   ./restore_rds_instance.sh [instance_name]
#
# Creates a new RDS instance from the latest production snapshot.
# More specifically, the following steps are performed:
#   - Determine the snapshot ID to use (the latest production snapshot)
#   - Delete the new DB instance if it exists
#   - Create the new DB instance
#   - Make necessary modifications to the new instance (disable backups,
#     anonymize etc)
##########################################################################

set -e

instance_identifier=$1
instance_class=db.t2.micro
availability_zone=eu-west-1a
prod_instance_identifier=amuse
db_name=amuse
db_user=postgres
db_password=postgres
new_db_user=amuse
new_db_password=blarg123
# it's blarg123
anon_user_password='pbkdf2_sha256$24000$v40VLX6GmcEH$SIAtdvlzjELbM/DukU5ag45E7N15ejIP/zWqN1OxyG4='

export AWS_DEFAULT_OUTPUT=text

function say {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $*"
}

if [[ "$instance_identifier" = "$prod_instance_identifier" ]]; then
    say "Instance identifier is the same as prod instance identifier. That seems bad. Exiting."
    exit 7
fi

security_group=sg-3ba36d43
subnet_group=default
parameter_group=dev94

# TODO: shape up VPCs/Subnets etc
#elif [[ "$instance_identifier" = dev* ]]; then
#    security_group=sg-xxxxxx # dev-db
#    subnet_group=dev-subnets
#elif [[ "$instance_identifier" = staging* ]]; then
#    security_group=sg-xxxxxx # staging-db
#    subnet_group=staging-subnets
#fi

function wait-for-status {
    instance=$1
    target_status=$2
    status=unknown
    # Initial long sleep because RDS needs a bit of time to react
    sleep 30
    while [[ "$status" != "$target_status" ]]; do
        sleep 10
        status=`aws rds describe-db-instances \
            --db-instance-identifier "$instance" | head -n 1 \
            | awk -F \  '{print $11}'`
    done
}

function wait-until-deleted {
    instance=$1
    count=1
    while [[ "$count" != "0" ]]; do
        sleep 10
        count=`aws rds describe-db-instances \
            --db-instance-identifier "$instance" 2>/dev/null \
            | grep DBINSTANCES \
            | wc -l \
            | tr -d ' '`
      done
}

# Fetch snapshot ID
snapshot_id=`aws rds describe-db-snapshots \
    --db-instance-identifier "$prod_instance_identifier" \
    | tail -n 1 \
    | grep -oe "arn:aws:rds:[^:]\+:[0-9]\+:snapshot:rds:amuse-[0-9-]\+"`

say "Snapshot Id: $snapshot_id"
say "Deleting database (if exists): $instance_identifier"
# Delete the existing instance
aws rds delete-db-instance \
    --db-instance-identifier "$instance_identifier" \
    --skip-final-snapshot > /dev/null 2>&1 || true

wait-until-deleted "$instance_identifier"

say "Creating new database: $instance_identifier"
# Create the new instance
aws rds restore-db-instance-from-db-snapshot \
    --db-instance-identifier "$instance_identifier" \
    --db-snapshot-identifier "$snapshot_id" \
    --db-instance-class "$instance_class" \
    --availability-zone "$availability_zone" \
    --publicly-accessible \
    --no-multi-az \
    --no-auto-minor-version-upgrade \
    --db-subnet-group-name $subnet_group #> /dev/null

say "Waiting for new DB instance to be available..."
wait-for-status "$instance_identifier" available
say "New instance is available"

say "Modifying new instace:
* Setting VPC security group
* Disabling automatic backups"
aws rds modify-db-instance \
    --db-instance-identifier "$instance_identifier" \
    --vpc-security-group-ids "$security_group" \
    --backup-retention-period 0 \
    --db-parameter-group-name "$parameter_group" \
    --apply-immediately

say "Waiting for DB instance to be available..."
wait-for-status "$instance_identifier" available
say "Instance is available"

# Get new host
new_db_host=$(aws rds describe-db-instances --db-instance-identifier "$instance_identifier" | grep ENDPOINT | awk -F \  '{print $2}')

export PGUSER=$db_user
export PGPASSWORD="$db_password"
export PGHOST=$new_db_host
export PGDATABASE=$db_name

if [ "$db_user" != "$new_db_user" ]; then
    # If a new user is defined - create it and change ownership of database + all tables
    say "Migrating to new user: $new_db_user..."
    psql -c "CREATE USER $new_db_user WITH PASSWORD '$new_db_password'; ALTER DATABASE $db_name OWNER TO $new_db_user"
    for tbl in `psql -qAt -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"`; do
        psql -c "ALTER TABLE \"$tbl\" OWNER TO $new_db_user"
    done
    # Use this user for the remaining operations
    export PGUSER=$new_db_user
    export PGPASSWORD="$new_db_password"
elif [ "$db_password" != "$new_db_password" ]; then
    # If a new password is defined - change the password
    say "Changing password for user $db_user"
    psql -c "ALTER ROLE $db_user PASSWORD '$new_db_password'"
fi

say "Purging and anonymizing..."
time psql -c "
  TRUNCATE
    django_admin_log,
    drflog_entry,
    stats_spotifystream,
    rest_framework_tracking_apirequestlog,
    stats_spotifyuser,
    stats_songdaily,
    stats_isrcdaily,
    stats_userdaily
    RESTART IDENTITY;
    UPDATE users_user
      SET
        password = '$anon_user_password',
        artist_name = 'Artist' || users_user.id,
        email = users_user.id || '@example.com',
        phone = users_user.id,
        facebook_id = 'fb' || users_user.id,
        google_id = 'goo' || users_user.id,
        profile_link = 'http://www.facebook.com',
        firebase_token = 'firebasetoken' || users_user.id,
        first_name = 'firstname' || users_user.id,
        last_name = 'lastname' || users_user.id,
        facebook_page = 'fbpage' || users_user.id,
        instagram_name = 'instaname' || users_user.id,
        soundcloud_page = 'soundcloudpage' || users_user.id,
        spotify_page = 'spotifypage' || users_user.id,
        twitter_name = 'twittername' || users_user.id,
        youtube_channel = 'youtubechannel' || users_user.id,
        apple_id = users_user.id
      WHERE is_admin IS FALSE;
"

# TODO: when to do this etc
#if [[ "$instance_identifier" = dev* ]]; then
#    say "Deleting all but the 10k latest rows in ***"
#    time psql -c "DELETE FROM some_table WHERE id NOT IN ( SELECT id FROM some_table ORDER BY id DESC LIMIT 10000 )"
#fi

say "Modifying new instace:
* Changing storage type to standard (magnetic)"
aws rds modify-db-instance \
    --db-instance-identifier "$instance_identifier" \
    --storage-type standard \
    --iops 0 \
    --apply-immediately

say "Waiting for DB instance to be available..."
wait-for-status "$instance_identifier" available
say "Instance is available"

say "All done"
