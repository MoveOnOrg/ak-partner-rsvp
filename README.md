# Mobilize America Partner Data Export

This is a tool to allow partners to export their own sourced RSVPs from Mobilize America event campaigns. It has two parts: a static site and an API.

## Static site

The static site in the repo is MoveOn-specific. If you're using this with a different Mobilize America instance, you'd of course want to change the HTML and CSS to match your organization's brand, and also edit the apiRoot value at the top of static/index.js.

### Deploy

To deploy the static site, simply put the files on any web host. At MoveOn, we use S3 for this.

## API

The API is a Python 3.12 app designed to run on AWS Lambda. It can be used with any Mobilize America instance by changing the settings to point to your Mobilize America database (copy settings.py.template to settings.py). Each individual script (validate_key.py and export_rsvps.py) can also be run from the command line for testing.

The scripts use AWS Secrets Manager, with a record called `ak-partner-rsvp` to store and call the `KEY_HASH_SECRET`, `MAX_AGE`, `EXTRA_WHERE`, and `DB_SCHEMA` variables unique to this deployment, and a `redshift-admin` configuration for database access.

### Deploy

The API can be deployed using [Zappa](https://github.com/Miserlou/Zappa) with the provided zappa_settings.yml.template (copied to zappa_settings.yml).

Each individual script has its own zappa_settings.py file, named zappa_settings_export.py and zappa_settings_validate.py. You'll most likely need to rename these to deploy.
