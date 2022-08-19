import hashlib

import psycopg2
import psycopg2.extras
from pywell.entry_points import run_from_cli, run_from_api_gateway

import validate_key

DESCRIPTION = 'Download RSVPs.'

ARG_DEFINITIONS = {
    'DB_HOST': 'Host for PostgreSQL connection.',
    'DB_NAME': 'Database name.',
    'DB_PASS': 'Pass for database connection.',
    'DB_PORT': 'Port for database connection.',
    'DB_SCHEMA': 'Scheam for database query.',
    'DB_USER': 'Username for database connection.',
    'EXTRA_WHERE': 'Anything to add to the WHERE clause in the RSVP query.',
    'KEY': 'Key to validate.',
    'MAX_AGE': 'Number of days a key should be considered valid.',
    'SECRET': 'Secret to use for validation.',
}

REQUIRED_ARGS = [
    'DB_HOST', 'DB_NAME', 'DB_PASS', 'DB_PORT', 'DB_USER', 'KEY', 'MAX_AGE',
    'SECRET', 
]


def main(args):
    key = validate_key.main(args)
    if key.get('valid', False):
        connection = psycopg2.connect(
            host=args.DB_HOST,
            port=args.DB_PORT,
            user=args.DB_USER,
            password=args.DB_PASS,
            database=args.DB_NAME
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
                    args.DB_SCHEMA,
                    args.DB_SCHEMA,
                    args.DB_SCHEMA,
                    args.DB_SCHEMA,
                    args.DB_SCHEMA,
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
