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

        query = f"""
            SELECT
                u.email, u.first_name, u.middle_name, u.last_name, u.state, u.city,
                u.zip, MIN(a.created_at) AS action_datetime, MAX(s.role) AS role
            FROM {db_schema}.core_user u
            JOIN {db_schema}.events_eventsignup s ON s.user_id = u.id
            JOIN {db_schema}.events_event e ON e.id = s.event_id
            JOIN {db_schema}.events_campaign c ON c.id = e.campaign_id
            LEFT JOIN {db_schema}.core_action a ON (
                a.page_id = s.page_id
                AND a.user_id = u.id
            )
            WHERE c.name = '{key.get('campaign', '')}'
            {args.EXTRA_WHERE or ''}
            AND a.source = '{key.get('source', '')}'
            GROUP BY 1,2,3,4,5,6,7
        """

        cursor.execute(query)
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
