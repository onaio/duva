# Module containing the Importer class
# Used to import CSV Data into a Hyper Database
import logging
import os
from pathlib import Path
from typing import List

import pandas as pd
from pandas.errors import EmptyDataError
from requests.exceptions import RetryError
from sqlalchemy.orm.session import Session
from tableauhyperapi import (
    Connection,
    CreateMode,
    HyperException,
    HyperProcess,
    Name,
    SqlType,
    TableDefinition,
    TableName,
    Telemetry,
    escape_string_literal,
)

from app import crud
from app.common_tags import JOB_ID_METADATA, SYNC_FAILURES_METADATA
from app.core.exceptions import FailedExternalRequest
from app.core.onadata import OnaDataAPIClient
from app.core.security import fernet_decrypt
from app.database.session import SessionLocal
from app.jobs.scheduler import schedule_cron_job
from app.models import HyperFile
from app.schemas import FileStatusEnum

logger = logging.getLogger("importer")


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


def _prep_csv_for_import(csv_path: Path) -> List[TableDefinition.Column]:
    """
    Creates a schema definition from an Onadata CSV Export
    DISCLAIMER: This function doesn't actually try to derive the columns
    type. It returns every column as a string column
    """
    columns: List[SqlType] = []
    df = pd.read_csv(csv_path, na_values=["n/a", ""])
    df = df.convert_dtypes()
    for i, dtype in enumerate(df.dtypes):
        column = TableDefinition.Column(
            Name(df.dtypes.index[i]), _pandas_type_to_hyper_sql_type(dtype.kind)()
        )
        columns.append(column)
    # Save dataframe to CSV as the dataframe is more cleaner
    # in most cases. We also don't want the headers to be within
    # the CSV as Hyper picks the header as a value
    with open(csv_path, "w") as f:
        f.truncate(0)
    df.to_csv(csv_path, na_rep="NULL", header=True, index=False)
    return columns


def schedule_import_to_hyper_job(db: Session, hyperfile: HyperFile):
    """
    Schedule a job to import CSV Data into a Tableau Hyper database
    """
    job = schedule_cron_job(import_to_hyper, [hyperfile.id, False])
    hyperfile = crud.hyperfile.update(
        db,
        db_obj=hyperfile,
        obj_in={"meta_data": {JOB_ID_METADATA: job.id, SYNC_FAILURES_METADATA: 0}},
    )
    return hyperfile


def import_to_hyper(hyperfile_id: int, schedule_cron: bool = True):
    """
    Start process to import CSV Data into a Tableau Hyper database
    """
    db = SessionLocal()
    hyperfile = crud.hyperfile.get(db, id=hyperfile_id)
    if not hyperfile:
        logger.info(f"Hyperfile with id {hyperfile_id} does not exist!!!")
        return

    if schedule_cron and not hyperfile.meta_data.get(JOB_ID_METADATA):
        hyperfile = schedule_import_to_hyper_job(db, hyperfile)

    with Importer(hyperfile=hyperfile, db=db) as importer:
        success = importer.import_csv()
        if not success:
            sync_meta = hyperfile.meta_data.get(SYNC_FAILURES_METADATA, 0) + 1
            hyperfile = crud.hyperfile.update(
                db,
                db_obj=hyperfile,
                obj_in={"meta_data": {SYNC_FAILURES_METADATA: sync_meta}},
            )


class Importer:
    """
    Class used to import CSV Data from Onadata into a Tableau Hyper database.
    """

    def __init__(self, hyperfile: HyperFile, db: Session):
        self.hyperfile = hyperfile
        self.db = db
        self.unique_id = f"{self.hyperfile.id}-{self.hyperfile.filename}"

    def __enter__(self):
        return self.start_import()

    def start_import(self):
        self.process = HyperProcess(
            telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU
        )
        return self

    def import_csv(self):
        logger.info(f"{self.unique_id} - Importing CSV for Hyper File")

        self.hyperfile = crud.hyperfile.update_status(
            self.db, obj=self.hyperfile, status=FileStatusEnum.syncing
        )
        client = OnaDataAPIClient(
            self.hyperfile.user.server.url,
            fernet_decrypt(self.hyperfile.user.access_token),
            user=self.hyperfile.user,
        )
        logger.info(f"{self.unique_id} - Downloading Export")
        try:
            export_path = client.download_export(self.hyperfile)
            logger.info(f"{self.unique_id} - Export downloaded")
        except RetryError as e:
            logger.info(f"{self.unique_id} - Retry Error: {e}")
            self.hyperfile = crud.hyperfile.update_status(
                self.db,
                obj=self.hyperfile,
                status=FileStatusEnum.latest_sync_failed,
            )
            return False
        except FailedExternalRequest as e:
            logger.error(f"{self.unique_id} - CSV export download failed: {e}")
            self.hyperfile = crud.hyperfile.update_status(
                self.db,
                obj=self.hyperfile,
                status=FileStatusEnum.latest_sync_failed,
            )
            return False

        if export_path:
            logger.info(f"{self.unique_id} - Importing CSV to Hyper")
            file_path = crud.hyperfile.get_latest_file(obj=self.hyperfile)
            try:
                count = self._import_csv_to_hyper(
                    hyper_path=file_path, export_path=export_path
                )
            except HyperException as e:
                logger.error(
                    f"{self.unique_id} - Creating HyperFile from CSV Failed: {e}"
                )
                exists = os.path.exists(file_path)
                logger.error(f"{self.unique_id} - HyperFile: {file_path} - {exists}")
            else:
                if count:
                    logger.info(f"{self.unique_id} - CSV imported to Hyper")
                    # Update HyperFile
                    logger.info(
                        f"{self.unique_id} - Syncing HyperFile to S3 and Tableau"
                    )
                    self.hyperfile = crud.hyperfile.sync_upstreams(
                        db=self.db, obj=self.hyperfile
                    )
                    logger.info(
                        f"{self.unique_id} - Synced HyperFile to S3 and Tableau"
                    )
                    self.hyperfile = crud.hyperfile.update_status(
                        self.db,
                        obj=self.hyperfile,
                        status=FileStatusEnum.file_available,
                    )
                    logger.info(f"{self.unique_id} - Imported and synced successfully")
                    return True

        logger.info(f"{self.unique_id} - CSV import failed")
        return False

    def _import_csv_to_hyper(
        self,
        hyper_path: str,
        export_path: Path,
        null_field: str = "NULL",
        delimiter: str = ",",
    ):
        table_name = TableName("Extract", "Extract")
        try:
            columns = _prep_csv_for_import(csv_path=export_path)
        except EmptyDataError:
            # If the CSV is empty, we don't want to create a table
            # with no columns
            return

        with Connection(
            endpoint=self.process.endpoint,
            database=hyper_path,
            create_mode=CreateMode.CREATE_AND_REPLACE,
        ) as connection:
            connection.catalog.create_schema("Extract")
            extract_table = TableDefinition(table_name, columns=columns)
            connection.catalog.create_table(extract_table)

            command = (
                f"COPY {table_name} FROM {escape_string_literal(str(export_path))} WITH"
                f"(format csv, NULL '{null_field}', delimiter '{delimiter}', header)"
            )
            count = connection.execute_command(command=command)
            return count

    def __exit__(self, *args):
        self.stop_process()

    def stop_process(self):
        self.process.close()
