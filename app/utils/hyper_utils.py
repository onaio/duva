"""
DEPRECATED: This module is deprecated. It is kept for reference purposes only.
Please utilize core/importer.py instead.
"""
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import pandas as pd
from pandas.errors import EmptyDataError
from rq.job import Job
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm.session import Session
from tableauhyperapi import (
    Connection,
    CreateMode,
    HyperProcess,
    Name,
    SqlType,
    TableDefinition,
    TableName,
    escape_string_literal,
)

from app.common_tags import (
    FAILURE_REASON_METADATA,
    JOB_ID_METADATA,
    SYNC_FAILURES_METADATA,
)
from app.database.session import SessionLocal
from app.jobs.scheduler import cancel_job, schedule_cron_job
from app.libs.s3.client import S3Client
from app.libs.tableau.client import TableauClient
from app.models import Configuration, HyperFile
from app.schemas import FileStatusEnum


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
            Name(name), _pandas_type_to_hyper_sql_type(dtype.kind)()
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
        hyperfile=hyperfile,
    )


def handle_csv_import(
    file_path: str,
    csv_path: Path,
    process: HyperProcess,
    configuration: Optional[Configuration] = None,
    s3_destination: Optional[str] = None,
    hyperfile: Optional[HyperFile] = None,
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
            tableau_client.validate_configuration(configuration)
            tableau_client.publish_hyper(file_path)
            if hyperfile:
                hyperfile.last_synced = datetime.now()

        return import_count


def schedule_hyper_file_cron_job(
    job_func: Callable,
    hyperfile_id: int,
    extra_job_args: list = [],
    job_id_meta_tag: str = JOB_ID_METADATA,
    job_failure_counter_meta_tag: str = SYNC_FAILURES_METADATA,
    db: SessionLocal = SessionLocal(),
) -> Job:
    """
    Schedules a Job that should run on a cron schedule for a particular
    Hyperfile
    """
    hf: HyperFile = HyperFile.get(db, hyperfile_id)
    metadata = hf.meta_data or {}

    job: Job = schedule_cron_job(job_func, [hyperfile_id] + extra_job_args)
    # Set meta tags to help track the started CRON Job
    metadata[job_id_meta_tag] = job.id
    metadata[job_failure_counter_meta_tag] = 0

    hf.meta_data = metadata
    flag_modified(hf, "meta_data")
    db.commit()
    return job


def cancel_hyper_file_job(
    hyperfile_id: int,
    job_id: str,
    db: SessionLocal = SessionLocal(),
    job_name: str = "app.utils.onadata_utils.start_csv_import_to_hyper_job",
    job_id_meta_tag: str = JOB_ID_METADATA,
    job_failure_counter_meta_tag: str = SYNC_FAILURES_METADATA,
) -> None:
    """
    Cancels a scheduler Job related to a Hyper file and resets the job failure
    counter and meta tag
    """
    hf: HyperFile = HyperFile.get(db, hyperfile_id)
    metadata = hf.meta_data or {}

    cancel_job(job_id, [hyperfile_id], job_name)
    if metadata.get(job_id_meta_tag):
        metadata[job_id_meta_tag] = ""
    metadata[job_failure_counter_meta_tag] = 0
    hf.meta_data = metadata
    flag_modified(hf, "meta_data")
    db.commit()


def handle_hyper_file_job_completion(
    hyperfile_id: int,
    db: SessionLocal = SessionLocal(),
    job_succeeded: bool = True,
    object_updated: bool = True,
    file_status: str = FileStatusEnum.file_available.value,
    job_id_meta_tag: str = JOB_ID_METADATA,
    job_failure_counter_meta_tag: str = SYNC_FAILURES_METADATA,
    failure_reason: str = None,
):
    """
    Handles updating a HyperFile according to the outcome of a running Job; Updates
    file status & tracks the jobs current failure counter.
    """
    hf: HyperFile = HyperFile.get(db, hyperfile_id)
    metadata = hf.meta_data or {}

    if job_succeeded:
        if object_updated:
            hf.last_updated = datetime.now()
        metadata[job_failure_counter_meta_tag] = 0
        metadata.pop(FAILURE_REASON_METADATA, None)
    else:
        failure_count = metadata.get(job_failure_counter_meta_tag)
        if isinstance(failure_count, int):
            metadata[job_failure_counter_meta_tag] = failure_count + 1
        else:
            metadata[job_failure_counter_meta_tag] = failure_count = 0

        if failure_reason:
            metadata[FAILURE_REASON_METADATA] = failure_reason

        if failure_count >= 3 and hf.is_active:
            cancel_hyper_file_job(
                hyperfile_id,
                metadata.get(job_id_meta_tag),
                db=db,
                job_id_meta_tag=job_id_meta_tag,
                job_failure_counter_meta_tag=job_failure_counter_meta_tag,
            )
            db.refresh(hf)
            hf.is_active = False

    hf.meta_data = metadata
    hf.file_status = file_status
    flag_modified(hf, "meta_data")
    db.commit()
