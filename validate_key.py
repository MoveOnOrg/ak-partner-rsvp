from datetime import datetime, timedelta
import hashlib
from pywell.entry_points import run_from_cli, run_from_api_gateway
from pywell.secrets_manager import get_secret

DESCRIPTION = 'Validate a download key.'

ARG_DEFINITIONS = {
    'KEY': 'Key to validate.'
}

REQUIRED_ARGS = ['KEY']


def main(args, script_settings={}):
    if not script_settings:
        script_settings = get_secret('ak-partner-rsvp')
    key_hash_secret = script_settings['KEY_HASH_SECRET']
    max_age = int(script_settings['MAX_AGE'] or 14)

    # If key doesn't have enough parts, it's invalid.
    if len(args.KEY.split('.')) != 6:
        return {'valid': False}
    [key_created, age, source, campaign_id, export_type, hash] = args.KEY.split('.')
    m = hashlib.sha256()

    m.update(
        (
            f'{key_created}.{age}.{source}.{campaign_id}.{export_type}.{key_hash_secret}'
        ).encode('utf-8')
    )
    hash_check = m.hexdigest()
    # If key hash doesn't match prefix, it's invalid.
    if hash_check != hash:
        return {'valid': False}
    # If key age is too big, it's invalid.
    if int(age) > max_age:
        return {'valid': False}
    # If key was created more than age days ago, it's invalid.
    key_created_min = (datetime.now() - timedelta(days=int(age))).strftime('%Y%m%d')
    if key_created_min > key_created:
        return {'valid': False}
    # Otherwise, it's a valid key. Note: valid doesn't mean it will have any
    # results for the source and campaign id. We don't check that until export.
    return {
        'valid': True,
        'date': key_created,
        'age': age,
        'source': source,   # Multiple source codes can be joined with a tilde (~).
        'campaign_id': campaign_id,
        'export_type': export_type
    }


def aws_lambda(event, context) -> str:
    return run_from_api_gateway(main, DESCRIPTION, ARG_DEFINITIONS, REQUIRED_ARGS, event)


if __name__ == '__main__':
    run_from_cli(main, DESCRIPTION, ARG_DEFINITIONS, REQUIRED_ARGS)
