from datetime import datetime
import hashlib
import logging

from pywell.secrets_manager import get_secret
from pywell.entry_points import run_from_cli

from parsons.etl.table import Table  # noqa: E402
from parsons.utilities.api_connector import APIConnector  # noqa: E402
from parsons.airtable import Airtable  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(
    handlers=[logging.StreamHandler()],
    format="%(levelname)s %(message)s",
    level="INFO",
)

DESCRIPTION = "Generate export keys for partners listed in Airtable, create Onetime Secret url, and update Airtable with the url"
ARG_DEFINITIONS = {}
REQUIRED_ARGS = []

"""
This script gets a list of partners stored in Airtable, and for each one
does the following:
* Generates an export key for each partner.
* Creates a Onetime Secret link for the key, using the partner's official
    source code as the passphrase.
* Writes the Onetime Secret link to back to Airtable.

The following keys should be set in Secrets Manager:
    AIRTABLE_BASE_KEY - The key/ID of the Airtable Base.
    AIRTABLE_TABLE - The key/ID or name of the table in the Base.
    AIRTABLE_PAT - The Airtable Personal Access Token.
    AIRTABLE_COLUMN_ORG_NAME - The column that contains the partner's name.
    AIRTABLE_COLUMN_SOURCE_CODE - The column that contains the official source code.
    AIRTABLE_COLUMN_ADDITIONAL_CODES - The column that contains any additional (comma-separated) source codes.
    AIRTABLE_COLUMN_OTS_URL - The column that will contain the OneTimeSecret URL.
    AIRTABLE_GET_RECORDS_FORMULA - The formula to use when retrieving records from Airtable.
        Formula reference: https://support.airtable.com/v1/docs/formula-field-reference
"""
settings = get_secret("ak-partner-rsvp")

# Airtable column names
COLUMN_ORG_NAME = settings["AIRTABLE_COLUMN_ORG_NAME"]
COLUMN_SOURCE_CODE = settings["AIRTABLE_COLUMN_SOURCE_CODE"]
COLUMN_ADDITIONAL_CODES = settings["AIRTABLE_COLUMN_ADDITIONAL_CODES"]
COLUMN_OTS_URL = settings["AIRTABLE_COLUMN_OTS_URL"]

# OneTimeSecret API URL
OTS_DEFAULT_URI = "https://us.onetimesecret.com/api/v2/"


class OneTimeSecret(object):
    """
    A class to interact with the OneTimeSecret API. Leverages the Parsons
    APIConnector class.

    For more information, see the `Onetime Secret API documentation
    <https://docs.onetimesecret.com/en/rest-api/>`_.
    """

    def __init__(self):
        self.client = APIConnector(OTS_DEFAULT_URI)
        self.client.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def create_secret(self, keys, passphrase=None, ttl=259200) -> Table:
        data = {
            "secret": {
                "secret": keys,
                "passphrase": passphrase,
                "ttl": ttl,     # Defaults to 72 hours.
            },
        }
        response = self.client.post_request(url="secret/conceal", json=data)
        return (
            f"https://us.onetimesecret.com/secret/{response['record']['secret']['key']}"
        )


def create_onetimesecret(onetimesecret, partner, passphrase=None, ttl=259200):
    logger.info(f"Creating export keys and Onetime Secret for {partner[COLUMN_ORG_NAME]}...")

    additional_codes = partner[COLUMN_ADDITIONAL_CODES] or ""
    prefix = (
        datetime.now().strftime("%Y%m%d")
        + f".{settings['MAX_AGE']}.{partner[COLUMN_SOURCE_CODE]}{additional_codes}.{settings['EVENT_CAMPAIGN_ID']}.full."
    )

    key = hashlib.sha256()
    key.update(("%s%s" % (prefix, settings["KEY_HASH_SECRET"])).encode("utf-8"))

    keys = f"""
Your download key:

{prefix}{key.hexdigest()}
"""

    return onetimesecret.create_secret(keys, passphrase, ttl)


def main(args):
    airtable = Airtable(
        settings["AIRTABLE_BASE_KEY"],
        settings["AIRTABLE_TABLE"],
        personal_access_token=settings["AIRTABLE_PAT"],
    )
    onetimesecret = OneTimeSecret()

    partners = airtable.get_records(
        fields=[COLUMN_ORG_NAME, COLUMN_SOURCE_CODE, COLUMN_ADDITIONAL_CODES],
        formula=(settings["AIRTABLE_GET_RECORDS_FORMULA"] or f"{{{COLUMN_OTS_URL}}}=''"),
    )

    if partners.num_rows:
        logger.info(f"Found {partners.num_rows} partners to update in Airtable")

        partners.add_column(
            "onetimesecret url",
            lambda rec: create_onetimesecret(
                onetimesecret, rec, passphrase=rec[COLUMN_SOURCE_CODE], ttl=259200
            ),
        )

        # This will run the create_onetimesecret() function for each partner.
        partners.materialize()

        # Remove columns that we don't want to sync back to Airtable.
        partners.remove_column("createdTime", COLUMN_ORG_NAME, COLUMN_SOURCE_CODE, COLUMN_ADDITIONAL_CODES)

        logger.info("Updating Airtable...")
        airtable.update_records(partners)
        logger.info("Done")


if __name__ == "__main__":
    run_from_cli(main, DESCRIPTION, ARG_DEFINITIONS, REQUIRED_ARGS)
