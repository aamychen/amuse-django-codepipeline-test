import json
import logging
import dateutil.parser
from datetime import datetime


logger = logging.getLogger(__name__)


def transform_data(data):
    transactions = data.get("transactions")

    if transactions:
        for transaction in transactions:
            if transaction["type"] == "deposit":
                for deposit in transaction["deposits"]:
                    if not "isrc" in deposit:
                        deposit["isrc"] = ""
                    if not "licensed" in deposit:
                        deposit["licensed"] = False
                    if not "stores" in deposit:
                        deposit["stores"] = []

                    for store in deposit["stores"]:
                        store["id"] = int(store["id"])

    return data
