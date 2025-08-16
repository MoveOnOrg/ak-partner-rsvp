import hashlib

import psycopg2
import psycopg2.extras
import psycopg2.sql
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
        custom_event_ids = []
        if (key.get('export_type') == 'full'):
            # This is a combination export of hosts, signups, and unsourced
            # data that has been split up among partner sources.
            query = psycopg2.sql.SQL("""
                with all_hosts_and_rsvps as (
                    select distinct
                        'rsvp'::text as record_type,
                        e.id || '.' || record_type || '.' || p.user_id as eventid_recordtype_userid,
                        p.user_id,
                        p.created_date,
                        e.id as event_id,
                        e.title as event_title,
                        p.status as rsvp_status,
                        p.user__email_address as email,
                        p.user__given_name as first_name,
                        p.user__family_name as last_name,
                        p.user__phone_number as phone,
                        p.user__postal_code as zip,
                        coalesce(trim(lower(p.referrer__utm_source)),'') as utm_source
                    from {db_schema}.participations p
                    join {db_schema}.events e
                        on (e.id = p.event_id and e.event_campaign_id = %(campaign_id)s)
                    join {db_schema}.organizations o
                        on (o.id = e.organization_id)
                    where
                        date_trunc('day', p.created_date) <= %(event_campaign_end_date)s

                    union all

                    select distinct
                        'host'::text as record_type,
                        e.id || '.' || record_type || '.' || e.owner_id as eventid_recordtype_userid,
                        e.owner_id as user_id,
                        e.created_date,
                        e.id as event_id,
                        e.title as event_title,
                        null as rsvp_status,
                        e.owner__email_address as email,
                        e.owner__given_name as first_name,
                        e.owner__family_name as last_name,
                        e.owner__phone_number as phone,
                        e.owner__postal_code as zip,
                        coalesce(trim(lower(e.referrer__utm_source)),'') as utm_source
                    from {db_schema}.events e
                    join {db_schema}.organizations o
                        on (o.id = e.organization_id)
                    where
                        e.event_campaign_id = %(campaign_id)s
                        and e.deleted_date is null
                        and date_trunc('day', e.created_date) <= %(event_campaign_end_date)s
                )
                select
                    a.record_type,
                    a.event_id,
                    a.event_title,
                    a.created_date,
                    a.rsvp_status,
                    a.email,
                    a.first_name,
                    a.last_name,
                    a.phone,
                    a.zip,
                    a.utm_source
                from all_hosts_and_rsvps a
                left join {unsourced_shares_table} u
                    on (
                        u.eventid_recordtype_userid = a.eventid_recordtype_userid
                        and u.event_campaign_id = %(campaign_id)s
                    )
                where
                    a.utm_source in (
                        select lower(source_code::text)
                        from
                            (select split_to_array(%(source)s, '~') as code) as s,
                            s.code as source_code
                    )
                    or
                    u.shared_with_source in (
                        select lower(source_code::text)
                        from
                            (select split_to_array(%(source)s, '~') as code) as s,
                            s.code as source_code
                    )
                order by a.utm_source desc, u.shared_with_source, a.record_type, a.created_date
            """).format(
                db_schema=psycopg2.sql.Identifier(db_schema),
                unsourced_shares_table=psycopg2.sql.Identifier(
                    script_settings['UNSOURCED_SHARES_SCHEMA'],
                    script_settings['UNSOURCED_SHARES_TABLE'],
                ),
            )

        elif (key.get('export_type') == 'custom_event_signups'):
            # This type is for exporting the signups for a predefined set of
            # event ids, regardless of source code.
            custom_event_ids = [int(num.strip()) for num in script_settings['CUSTOM_EVENT_IDS'].split(',')]
            query = psycopg2.sql.SQL("""
                select distinct
                    e.id as event_id,
                    e.title as event_title,
                    p.created_date as rsvp_date,
                    p.status as rsvp_status,
                    p.user__email_address as email,
                    p.user__given_name as first_name,
                    p.user__family_name as last_name,
                    p.user__phone_number as phone,
                    p.user__postal_code as zip,
                    p.referrer__utm_source as utm_source
                from {db_schema}.participations p
                join {db_schema}.events e
                    on (e.id = p.event_id and e.event_campaign_id = %(campaign_id)s)
                where e.id in %(custom_event_ids)s
                order by 1,3,5
            """).format(db_schema=psycopg2.sql.Identifier(db_schema))

        else:
            return False

        cursor.execute(query, {
            'campaign_id': key.get('campaign_id', ''),
            'custom_event_ids': tuple(custom_event_ids),
            'event_campaign_end_date': script_settings['EVENT_CAMPAIGN_END_DATE'],
            'source': key.get('source', ''),
        })
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
