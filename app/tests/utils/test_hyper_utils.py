"""
TEsts for the hyper_utils module
"""
from unittest.mock import patch, MagicMock
from sqlalchemy.orm.attributes import flag_modified

from app.common_tags import JOB_ID_METADATA, SYNC_FAILURES_METADATA
from app.models import HyperFile
from app.schemas import FileCreate, FileStatusEnum
from app.settings import settings
from app.tests.test_base import TestBase
from app.utils.hyper_utils import (
    schedule_hyper_file_cron_job,
    cancel_hyper_file_job,
    handle_hyper_file_job_completion,
)


class TestHyperUtils(TestBase):
    @patch("app.utils.hyper_utils.schedule_cron_job")
    def _schedule_hyper_file_cron_job(
        self, mock_schedule_cron_job, user, job_mock: MagicMock = MagicMock
    ):
        def dummy_func(a: str):
            print(a)

        mock_schedule_cron_job.side_effect = job_mock

        hyperfile = HyperFile.create(
            self.db,
            FileCreate(
                user=user.id, filename="test.hyper", is_active=True, form_id="111"
            ),
        )

        schedule_hyper_file_cron_job(dummy_func, hyperfile.id, db=self.db)
        self.db.refresh(hyperfile)

        assert mock_schedule_cron_job.called is True
        return hyperfile

    def test_schedule_hyper_file_cron_job(self, create_user_and_login):
        user, _ = create_user_and_login
        job_mock = MagicMock
        job_mock.id = "some_id"
        hyperfile = self._schedule_hyper_file_cron_job(user=user, job_mock=job_mock)
        expected_metadata = {JOB_ID_METADATA: job_mock.id, SYNC_FAILURES_METADATA: 0}
        # Ensure that the HyperFiles' metadata is updated accordingly
        assert hyperfile.meta_data == expected_metadata
        # Clean up created hyper file
        self.db.query(HyperFile).delete()
        self.db.commit()

    @patch("app.utils.hyper_utils.cancel_job")
    def test_cancel_hyper_file_job(self, mock_cancel_job, create_user_and_login):
        user, _ = create_user_and_login
        job_mock = MagicMock
        job_mock.id = "some_id"
        hyperfile = self._schedule_hyper_file_cron_job(user=user, job_mock=job_mock)
        self.db.refresh(hyperfile)
        hyperfile.meta_data[SYNC_FAILURES_METADATA] = 4
        flag_modified(hyperfile, "meta_data")
        self.db.commit()
        self.db.refresh(hyperfile)

        assert hyperfile.meta_data == {
            JOB_ID_METADATA: job_mock.id,
            SYNC_FAILURES_METADATA: 4,
        }
        # Ensure that cancelling a hyper file job updates it's metadata
        cancel_hyper_file_job(hyperfile.id, job_mock.id, db=self.db)
        self.db.refresh(hyperfile)
        expected_metadata = {JOB_ID_METADATA: "", SYNC_FAILURES_METADATA: 0}
        assert hyperfile.meta_data == expected_metadata
        assert mock_cancel_job.called is True
        self.db.query(HyperFile).delete()
        self.db.commit()

    @patch("app.utils.hyper_utils.cancel_job")
    def test_handle_hyper_file_job_completion(
        self, mock_cancel_job, create_user_and_login
    ):
        user, _ = create_user_and_login
        job_mock = MagicMock
        job_mock.id = "some_id"
        hyperfile = self._schedule_hyper_file_cron_job(user=user, job_mock=job_mock)
        self.db.refresh(hyperfile)
        failure_count = hyperfile.meta_data[SYNC_FAILURES_METADATA]

        # Test that the failure count is updated on job failure
        handle_hyper_file_job_completion(
            hyperfile.id,
            self.db,
            job_succeeded=False,
            file_status=FileStatusEnum.latest_sync_failed,
        )
        self.db.refresh(hyperfile)
        assert hyperfile.meta_data[SYNC_FAILURES_METADATA] == failure_count + 1
        assert hyperfile.file_status == FileStatusEnum.latest_sync_failed
        assert mock_cancel_job.called is False

        # Test job is cancelled once job failure limit is reached
        hyperfile.meta_data[SYNC_FAILURES_METADATA] = settings.job_failure_limit
        flag_modified(hyperfile, "meta_data")
        self.db.commit()

        handle_hyper_file_job_completion(
            hyperfile.id,
            self.db,
            job_succeeded=False,
            file_status=FileStatusEnum.latest_sync_failed,
        )
        self.db.refresh(hyperfile)
        assert hyperfile.meta_data == {JOB_ID_METADATA: "", SYNC_FAILURES_METADATA: 0}
        assert mock_cancel_job.called is True
        self.db.query(HyperFile).delete()
        self.db.commit()
