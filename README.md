# Mobilize America Partner Data Export

This is a tool to allow partners to export their own sourced RSVPs from Mobilize America event campaigns. It has two parts: a static site and an API.

## Static site

The static site in the repo is MoveOn-specific. If you're using this with a different Mobilize America instance, you'd of course want to change the HTML and CSS to match your organization's brand, and also edit the apiRoot value at the top of static/index.js.

### Deploy

To deploy the static site, simply put the files on any web host. At MoveOn, we use S3 for this.

## API

The API is a Python 3.9 app designed to run on AWS Lambda. It can be used with any Mobilize America instance by changing the settings to point to your Mobilize America database (copy settings.py.template to settings.py). Each individual script (validate_key.py and export_rsvps.py) can also be run from the command line for testing.

The scripts use AWS Secrets Manager, with a record called `ak-partner-rsvp` to store and call the variables below unique to this deployment, and a `redshift-admin` configuration for database access.

* `KEY_HASH_SECRET` - This is the secret that is used for generating the export key.
* `MAX_AGE` - The maximum allowed age of the export key.
* `DB_SCHEMA` - The database schema that holds the Mobilize America tables.
* `EVENT_CAMPAIGN_ID` - The numeric event campaign id in Mobilize America.
* `EVENT_CAMPAIGN_END_DATE` - The last day of the event campaign. The export will include only records where the creation date is less than or equal to this value. For hosts, it is the `created_date` of the event in the `events` table; for attendees, it is the `created_date` of the RSVP in the `participations` table.
* `UNSOURCED_SHARED_SCHEMA`, `UNSOURCED_SHARED_TABLE` - The database schema and table that holds the allocation of unsourced hosts/RSVPs to each partner source. This table can be empty, but it must exist. Expected columns:
  * `event_campaign_id` - The numeric event campaign id in Mobilize America.
  * `eventid_recordtype_userid` - A unique key containing the Mobilize America event id, the record type (`host` or `rsvp`), and the Mobilize America user id of the participant or host, separated by `.`. E.g., `123456.rsvp.24680`
  * `shared_with_source` - The partner source code that this contact has been allocated to.
* `CUSTOM_EVENT_IDS` - The list of Mobilize America event ids to use for the `custom_event_signups` export type.

### Deploy

The API can be deployed using [Zappa](https://github.com/Miserlou/Zappa) with the provided zappa_settings.yml.template (copied to zappa_settings.yml).

Each individual script has its own zappa_settings.py file, named zappa_settings_export.py and zappa_settings_validate.py. You'll most likely need to rename these to deploy.

## Airtable/Onetime Secret integration script

Given an Airtable base containing a list of partners, the included `gen_secrets_for_airtable.py` does the following:

* Retrieves the list of partners from Airtable.
* Generates an export key for each partner.
* Creates a Onetime Secret link for the key, using the partner's official source code as the passphrase.
* Writes the Onetime Secret link to back to Airtable.

An automation can be set up in Airtable to send an email to the partner when the column containing their Onetime Secret link is filled in by the script.

The script uses AWS Secrets Manager for the Airtable configuration (see the comments in the script for the list of expected keys) and [Parsons](https://www.parsonsproject.org/) for connecting to the Airtable and Onetime Secret APIs.
