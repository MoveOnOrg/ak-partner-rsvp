import hashlib

import psycopg2
import psycopg2.extras
from pywell.entry_points import run_from_cli, run_from_api_gateway
from pywell.secrets_manager import get_secret

import validate_key

DESCRIPTION = 'Download RSVPs.'

ARG_DEFINITIONS = {
    'EXTRA_WHERE': 'Anything to add to the WHERE clause in the RSVP query.',
    'KEY': 'Key to validate.',
    'MAX_AGE': 'Number of days a key should be considered valid.',
}

REQUIRED_ARGS = [
    'KEY', 'MAX_AGE'
]


def main(args):
    script_settings = get_secret('ak-partner-rsvp')
    db_schema = script_settings['DB_SCHEMA']
    db_settings = get_secret('redshift-admin')

    key = validate_key.main(args)
    if key.get('valid', False):
        connection = psycopg2.connect(
            host=db_settings('host'),
            port=db_settings('port'),
            user=db_settings('username'),
            password=db_settings('password'),
            database='dev'
        )
        cursor = connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        query = """
        SELECT
            u.email, u.first_name, u.middle_name, u.last_name, u.state, u.city,
            u.zip, MIN(a.created_at) AS action_datetime, MAX(s.role) AS role
        FROM %s.core_user u
        JOIN %s.events_eventsignup s ON s.user_id = u.id
        JOIN %s.events_event e ON e.id = s.event_id
        JOIN %s.events_campaign c ON c.id = e.campaign_id
        LEFT JOIN %s.core_action a ON (
            a.page_id = s.page_id
            AND a.user_id = u.id
        )
        WHERE c.name = %s
        %s
        AND a.source = %s
        GROUP BY 1,2,3,4,5,6,7""" % (
                    db_schema,
                    db_schema,
                    db_schema,
                    db_schema,
                    db_schema,
                    '%s',
                    args.EXTRA_WHERE,
                    '%s'
        )
        cursor.execute(query, (key.get('campaign', ''), key.get('source', '')))
        return [dict(row) for row in cursor.fetchall()]
    else:
        return False


def aws_lambda(event, context) -> str:
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    return run_from_api_gateway(
        main, DESCRIPTION, ARG_DEFINITIONS, REQUIRED_ARGS, event,
        format='CSV', filename='moveon_event_signups-%s.csv' % today
    )


if __name__ == '__main__':
    run_from_cli(main, DESCRIPTION, ARG_DEFINITIONS, REQUIRED_ARGS)
