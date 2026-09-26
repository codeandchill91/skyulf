# Databricks notebook source
"""Create or append the bounded SM-34B fixture; never replace an existing table."""

import json
from datetime import datetime, timedelta

spark = globals()["spark"]
dbutils = globals()["dbutils"]
TABLE = "workspace.skyulf_lifecycle_test.sm34b_20260926_r1_source"
action = dbutils.widgets.get("fixture_action")
schema = "record_id long, x double, z double, target double, label long, observed_at string, confirmed_at string"


def row(index):
    """Include missing numeric features and delayed per-row result availability."""
    observed = datetime(2026, 6, 1, 10) + timedelta(hours=12 * index)
    confirmed = observed + timedelta(days=3)
    if index % 11 == 0:
        confirmed = datetime(2026, 12, 1)
    x = float(index % 10)
    z = float(index % 3)
    return (
        index,
        None if index % 13 == 0 else x,
        z,
        3 * x + z + 10,
        int(x >= 5),
        observed.strftime("%d/%m/%Y %H:%M"),
        confirmed.strftime("%Y-%m-%d"),
    )


if action == "create":
    assert not spark.catalog.tableExists(TABLE), "Fixture exists; inspect before retrying."
    spark.createDataFrame([row(i) for i in range(240)], schema).write.format("delta").option(
        "delta.enableChangeDataFeed", "true"
    ).mode("error").saveAsTable(TABLE)
elif action == "append":
    assert spark.table(TABLE).count() == 240, "Append requires the original fixture."
    spark.createDataFrame([row(i) for i in range(240, 243)], schema).write.format("delta").mode(
        "append"
    ).saveAsTable(TABLE)
else:
    raise ValueError(action)
dbutils.notebook.exit(
    json.dumps({"action": action, "table": TABLE, "rows": spark.table(TABLE).count()})
)
