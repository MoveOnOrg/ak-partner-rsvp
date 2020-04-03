from datetime import datetime, timedelta
import hashlib

import pytest

import validate_key


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)


class Test:
    def test_valid_key(self):
        yesterday = (datetime.now() - timedelta(days=int(1))).strftime('%Y-%m-%d')
        m = hashlib.sha256()
        prefix = '%s.2.asource.acampaign' % yesterday
        m.update((prefix + '.secret').encode('utf-8'))
        hash = m.hexdigest()
        args = {
            'KEY': prefix + '.' + hash,
            'MAX_AGE': 2,
            'SECRET': 'secret'
        }
        args_struct = Struct(**args)
        result = validate_key.main(args_struct)
        assert result.get('valid') == True

    def test_bad_format_key(self):
        args = {
            'KEY': 'invalidkey',
            'MAX_AGE': 2,
            'SECRET': 'secret'
        }
        args_struct = Struct(**args)
        result = validate_key.main(args_struct)
        assert result.get('valid') == False

    def test_old_key(self):
        last_week = (datetime.now() - timedelta(days=int(7))).strftime('%Y-%m-%d')
        m = hashlib.sha256()
        prefix = '%s.2.asource.acampaign' % last_week
        m.update((prefix + '.secret').encode('utf-8'))
        hash = m.hexdigest()
        args = {
            'KEY': prefix + '.' + hash,
            'MAX_AGE': 2,
            'SECRET': 'secret'
        }
        args_struct = Struct(**args)
        result = validate_key.main(args_struct)
        assert result.get('valid') == False

    def test_wrong_secret(self):
        yesterday = (datetime.now() - timedelta(days=int(1))).strftime('%Y-%m-%d')
        m = hashlib.sha256()
        prefix = '%s.2.asource.acampaign' % yesterday
        m.update((prefix + '.wrongsecret').encode('utf-8'))
        hash = m.hexdigest()
        args = {
            'KEY': prefix + '.' + hash,
            'MAX_AGE': 2,
            'SECRET': 'secret'
        }
        args_struct = Struct(**args)
        result = validate_key.main(args_struct)
        assert result.get('valid') == False

    def test_max_age_too_high(self):
        yesterday = (datetime.now() - timedelta(days=int(1))).strftime('%Y-%m-%d')
        m = hashlib.sha256()
        prefix = '%s.3.asource.acampaign' % yesterday
        m.update((prefix + '.secret').encode('utf-8'))
        hash = m.hexdigest()
        args = {
            'KEY': prefix + '.' + hash,
            'MAX_AGE': 2,
            'SECRET': 'secret'
        }
        args_struct = Struct(**args)
        result = validate_key.main(args_struct)
        assert result.get('valid') == False
