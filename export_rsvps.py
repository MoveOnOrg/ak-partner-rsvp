import hashlib

import psycopg2
import psycopg2.extras
from pywell.entry_points import run_from_cli, run_from_api_gateway
from pywell.secrets_manager import get_secret

import validate_key

DESCRIPTION = 'Download RSVPs.'

ARG_DEFINITIONS = {
    'KEY': 'Key to validate.'
}

REQUIRED_ARGS = ['KEY']


def main(args):
    script_settings = get_secret('ak-partner-rsvp')
    db_settings = get_secret('redshift-admin')
    db_schema = script_settings['DB_SCHEMA']
    extra_where = script_settings['EXTRA_WHERE'] or ''

    key = validate_key.main(args, script_settings)

    if key.get('valid', False):
        connection = psycopg2.connect(
            host=db_settings['host'],
            port=db_settings['port'],
            user=db_settings['username'],
            password=db_settings['password'],
            database=db_settings['dbName']
        )
        cursor = connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        query = None
        if (key.get('export_type') == 'signups'):
            query = """
            SELECT DISTINCT
                e.id AS event_id,
                e.title AS event_title,
                p.created_date AS rsvp_date,
                p.status AS rsvp_status,
                p.user__email_address AS email,
                p.user__given_name AS first_name,
                p.user__family_name AS last_name,
                p.user__phone_number AS phone,
                p.user__postal_code AS zip,
                p.referrer__utm_source AS utm_source
            FROM %s.participations p
            JOIN %s.events e ON (e.id = p.event_id AND e.event_campaign_id = %s)
            WHERE
                LOWER(p.referrer__utm_source) IN (
                    SELECT LOWER(source_code::TEXT)
                    FROM
                        (SELECT SPLIT_TO_ARRAY(%s, '~') AS code) AS s,
                        s.code AS source_code
                )
                %s
            ORDER BY 1,3,5""" % (
                db_schema,
                db_schema,
                '%s',
                '%s',
                extra_where
            )
        elif (key.get('export_type') == 'hosts'):
            query = """
            SELECT DISTINCT
                e.id AS event_id,
                e.title AS event_title,
                e.created_date,
                e.owner__email_address AS email,
                e.owner__given_name AS first_name,
                e.owner__family_name AS last_name,
                e.owner__phone_number AS phone,
                e.owner__postal_code AS zip,
                e.referrer__utm_source AS utm_source
            FROM %s.events e
            WHERE
                e.event_campaign_id = %s
                AND LOWER(e.referrer__utm_source) IN (
                    SELECT LOWER(source_code::TEXT)
                    FROM
                        (SELECT SPLIT_TO_ARRAY(%s, '~') AS code) AS s,
                        s.code AS source_code
                )
                AND e.deleted_date IS NULL
                %s
            ORDER BY 1,3,5""" % (
                db_schema,
                '%s',
                '%s',
                extra_where
            )
        elif (key.get('export_type') == 'custom_event_signups'):
            # This type is for exporting the signups for a predefined set of
            # event ids, regardless of source code.
            query = """
                SELECT DISTINCT
                    e.id AS event_id,
                    e.title AS event_title,
                    p.created_date AS rsvp_date,
                    p.status AS rsvp_status,
                    p.user__email_address AS email,
                    p.user__given_name AS first_name,
                    p.user__family_name AS last_name,
                    p.user__phone_number AS phone,
                    p.user__postal_code AS zip,
                    p.referrer__utm_source AS utm_source
                FROM %s.participations p
                JOIN %s.events e on (e.id = p.event_id AND e.event_campaign_id = %s)
                WHERE
                    e.id IN (%s)
                    AND %s = '%s'
                order by 1,3,5""" % (
                    db_schema,
                    db_schema,
                    '%s',
                    script_settings['CUSTOM_EVENT_IDS'],
                    '%s',
                    key.get('source', '')
                )
        else:
            return False

        # return query
        cursor.execute(query, (key.get('campaign_id', ''), key.get('source', '')))
        return [dict(row) for row in cursor.fetchall()]
    else:
        return False


def aws_lambda(event, context) -> str:
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')

    # Get the export_type from the key (if valid) so we can name the file appropriately.
    export_type = 'signups'
    if event.get('body', False):
        # event['body'] will be 'KEY=<the download key>'
        key_string = event.get('body', 'KEY=invalid_key').split('=')[1]
        key = validate_key.main(
            # validate_key expects an object with a "KEY" attribute.
            # https://www.hydrogen18.com/blog/python-anonymous-objects.html
            type('', (object,), {"KEY": key_string})(),
            get_secret('ak-partner-rsvp')
        )
        if key.get('valid', False):
            export_type = key.get('export_type', export_type)

    return run_from_api_gateway(
        main, DESCRIPTION, ARG_DEFINITIONS, REQUIRED_ARGS, event,
        format='CSV', filename='moveon_event_%s-%s.csv' % (export_type, today)
    )


if __name__ == '__main__':
    run_from_cli(main, DESCRIPTION, ARG_DEFINITIONS, REQUIRED_ARGS)
