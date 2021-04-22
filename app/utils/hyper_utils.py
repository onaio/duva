# Utility functions file
from typing import List
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError
from sqlalchemy.orm.session import Session
from tableauhyperapi import (
    SqlType,
    Connection,
    HyperProcess,
    TableName,
    escape_string_literal,
    TableDefinition,
    CreateMode,
)

from app.libs.s3.client import S3Client
from app.libs.tableau.client import TableauClient
from app.models import HyperFile, Configuration


def element_type_to_hyper_sql_type(elem_type: str) -> SqlType:
    type_map = {
        "integer": SqlType.big_int,
        "decimal": SqlType.double,
        "text": SqlType.text,
    }
    return type_map.get(elem_type)


def _pandas_type_to_hyper_sql_type(_type: str) -> SqlType:
    # Only supports text and numeric fields, more may be added later
    type_map = {  # noqa
        "b": SqlType.text,
        "i": SqlType.big_int,
        "u": SqlType.text,
        "f": SqlType.double,
        "c": SqlType.text,
        "O": SqlType.text,
        "S": SqlType.text,
        "a": SqlType.text,
        "U": SqlType.text,
    }
    return type_map.get(_type)


def _import_csv_to_hyperfile(
    path: str,
    csv_path: str,
    process: HyperProcess,
    table_name: TableName = TableName("Extract", "Extract"),
    null_field: str = "NULL",
    delimiter: str = ",",
) -> int:
    """
    Imports CSV data into a HyperFile
    """
    with Connection(endpoint=process.endpoint, database=path) as connection:
        command = (
            f"COPY {table_name} from {escape_string_literal(csv_path)} with "
            f"(format csv, NULL '{null_field}', delimiter '{delimiter}', header)"
        )
        count = connection.execute_command(command=command)
        return count


def _prep_csv_for_import(csv_path: Path) -> List[TableDefinition.Column]:
    """
    Creates a schema definition from an Onadata CSV Export
    DISCLAIMER: This function doesn't actually try to derive the columns
    type. It returns every column as a string column
    """
    columns: List[SqlType] = []
    df = pd.read_csv(csv_path, na_values=["n/a", ""])
    df = df.convert_dtypes()
    for name, dtype in df.dtypes.iteritems():
        column = TableDefinition.Column(
            name, _pandas_type_to_hyper_sql_type(dtype.kind)()
        )
        columns.append(column)
    # Save dataframe to CSV as the dataframe is more cleaner
    # in most cases. We also don't want the headers to be within
    # the CSV as Hyper picks the header as a value
    with open(csv_path, "w") as f:
        f.truncate(0)
    df.to_csv(csv_path, na_rep="NULL", header=True, index=False)
    return columns


def handle_csv_import_to_hyperfile(
    hyperfile: HyperFile, csv_path: str, process: HyperProcess, db: Session
) -> int:
    file_path = hyperfile.retrieve_latest_file(db)
    s3_destination = hyperfile.get_file_path(db)
    configuration = hyperfile.configuration

    return handle_csv_import(
        file_path=file_path,
        csv_path=csv_path,
        process=process,
        configuration=configuration,
        s3_destination=s3_destination,
    )


def handle_csv_import(
    file_path: str,
    csv_path: Path,
    process: HyperProcess,
    configuration: Configuration = None,
    s3_destination: str = None,
) -> int:
    """
    Handles CSV Import to Hyperfile
    """
    table_name = TableName("Extract", "Extract")
    try:
        columns = _prep_csv_for_import(csv_path=csv_path)
    except EmptyDataError:
        return 0
    else:
        with Connection(
            endpoint=process.endpoint,
            database=file_path,
            create_mode=CreateMode.CREATE_AND_REPLACE,
        ) as connection:
            connection.catalog.create_schema("Extract")
            extract_table = TableDefinition(table_name, columns=columns)
            connection.catalog.create_table(extract_table)

        import_count = _import_csv_to_hyperfile(
            path=file_path,
            csv_path=str(csv_path),
            table_name=table_name,
            process=process,
        )

        # Store hyper file in S3 Storage
        s3_client = S3Client()
        s3_client.upload(file_path, s3_destination or Path(file_path).name)

        if configuration:
            tableau_client = TableauClient(configuration=configuration)
            tableau_client.publish_hyper(file_path)

        return import_count
