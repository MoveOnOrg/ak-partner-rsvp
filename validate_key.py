from datetime import datetime, timedelta
import hashlib

from pywell.entry_points import run_from_cli, run_from_api_gateway
from pywell.secrets_manager import get_secret

DESCRIPTION = 'Validate a download key.'

ARG_DEFINITIONS = {
    'KEY': 'Key to validate.',
    'MAX_AGE': 'Number of days a key should be considered valid.'
}

REQUIRED_ARGS = ['KEY', 'MAX_AGE']


def main(args, script_settings={}):
    if not script_settings:
        script_settings = get_secret('ak-partner-rsvp')
    secret = script_settings['SECRET']

    # If key doesn't have enough parts, it's invalid.
    if len(args.KEY.split('.')) != 5:
        return {'valid': False}
    [key_created, age, source, campaign, hash] = args.KEY.split('.')
    m = hashlib.sha256()

    m.update(
        (
            '%s.%s.%s.%s.%s' % (key_created, age, source, campaign, secret)
        ).encode('utf-8')
    )
    hash_check = m.hexdigest()
    # If key hash doesn't match prefix, it's invalid.
    if hash_check != hash:
        return {'valid': False}
    # If key age is too big, it's invalid.
    if int(age) > int(args.MAX_AGE):
        return {'valid': False}
    # If key was created more than age days ago, it's invalid.
    key_created_min = (datetime.now() - timedelta(days=int(age))).strftime('%Y-%m-%d')
    if key_created_min > key_created:
        return {'valid': False}
    # Otherwise, it's a valid key. Note: valid doesn't mean it will have any
    # results for the source and campaign. We don't check that until export.
    return {
        'valid': True,
        'date': key_created,
        'age': age,
        'source': source,
        'campaign': campaign
    }


def aws_lambda(event, context) -> str:
    return run_from_api_gateway(main, DESCRIPTION, ARG_DEFINITIONS, REQUIRED_ARGS, event)


if __name__ == '__main__':
    run_from_cli(main, DESCRIPTION, ARG_DEFINITIONS, REQUIRED_ARGS)
