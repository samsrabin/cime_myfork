import tempfile
import unittest
from unittest import mock
from pathlib import Path

from CIME import locked_files
from CIME.utils import CIMEError
from CIME.XML.entry_id import EntryID
from CIME.XML.env_batch import EnvBatch
from CIME.XML.files import Files


def create_batch_system(env_batch, batch_submit_value=None):
    batch_system = env_batch.make_child(
        name="batch_system", attributes={"type": "slurm"}
    )
    env_batch.make_child(name="batch_query", attributes={"args": ""}, root=batch_system)
    batch_submit = env_batch.make_child(
        name="batch_submit", root=batch_system, text=batch_submit_value
    )
    env_batch.make_child(name="batch_cancel", root=batch_system)
    env_batch.make_child(name="batch_redirect", root=batch_system)
    env_batch.make_child(name="batch_directive", root=batch_system)
    directives = env_batch.make_child(name="directives", root=batch_system)
    env_batch.make_child(name="directive", root=directives)

    return batch_system


def create_fake_env(tempdir):
    locked_files_dir = Path(tempdir, locked_files.LOCKED_DIR)

    locked_files_dir.mkdir(parents=True)

    locked_file_path = locked_files_dir / "env_batch.xml"

    env_batch = EnvBatch(tempdir)

    env_batch.write(force_write=True)

    batch_system = create_batch_system(env_batch, "sbatch")

    env_batch.write(str(locked_file_path), force_write=True)

    env_batch.remove_child(batch_system)

    batch_system = create_batch_system(env_batch)

    env_batch.write(force_write=True)

    return env_batch


class TestLockedFiles(unittest.TestCase):
    def test_check_diff_rebuild_trigger(self):
        case = mock.MagicMock()

        case.get_values.side_effect = (("CPL", "ATM"), (), ("NTASKS",))

        diff = {
            "NTASKS": ("32", "16"),
        }

        with self.assertRaisesRegex(
            CIMEError, "ERROR: A rebuild is required, please run:.*"
        ):
            locked_files.check_diff(case, "env_mach_pes.xml", "env_mach_pes", diff)

    def test_check_diff_other_env(self):
        case = mock.MagicMock()

        diff = {
            "some_key": ("value1", "value2"),
        }

        with self.assertRaises(CIMEError):
            locked_files.check_diff(case, "env_mach_pes.xml", "env_mach_pes", diff)

    def test_check_diff_env_build_no_diff(self):
        case = mock.MagicMock()

        diff = {}

        locked_files.check_diff(case, "env_build.xml", "env_build", diff)

        case.set_value.assert_not_called()

    def test_check_diff_env_build_pio_version(self):
        case = mock.MagicMock()

        diff = {
            "some_key": ("value1", "value2"),
            "PIO_VERSION": ("1", "2"),
        }

        locked_files.check_diff(case, "env_build.xml", "env_build", diff)

        case.set_value.assert_any_call("BUILD_COMPLETE", False)
        case.set_value.assert_any_call("BUILD_STATUS", 2)

    def test_check_diff_env_build(self):
        case = mock.MagicMock()

        diff = {
            "some_key": ("value1", "value2"),
        }

        locked_files.check_diff(case, "env_build.xml", "env_build", diff)

        case.set_value.assert_any_call("BUILD_COMPLETE", False)
        case.set_value.assert_any_call("BUILD_STATUS", 1)

    def test_check_diff_env_batch(self):
        case = mock.MagicMock()

        diff = {
            "some_key": ("value1", "value2"),
        }

        with self.assertRaises(CIMEError):
            locked_files.check_diff(case, "env_batch.xml", "env_batch", diff)

    def test_check_diff_env_case(self):
        case = mock.MagicMock()

        diff = {
            "some_key": ("value1", "value2"),
        }

        with self.assertRaises(CIMEError):
            locked_files.check_diff(case, "env_case.xml", "env_case", diff)

    def test_diff_lockedfile_detect_difference(self):
        case = mock.MagicMock()

        with tempfile.TemporaryDirectory() as tempdir:
            case.get_value.side_effect = (tempdir,)

            env_batch = create_fake_env(tempdir)

            case.get_env.return_value = env_batch

            _, diff = locked_files.diff_lockedfile(case, tempdir, "env_batch.xml")

            assert diff
            assert diff["batch_submit"] == [None, "sbatch"]

    def test_diff_lockedfile_not_supported(self):
        case = mock.MagicMock()

        with tempfile.TemporaryDirectory() as tempdir:
            case.get_value.side_effect = (tempdir,)

            locked_file_path = Path(tempdir, locked_files.LOCKED_DIR, "env_new.xml")

            locked_file_path.parent.mkdir(parents=True)

            locked_file_path.touch()

            _, diff = locked_files.diff_lockedfile(case, tempdir, "env_new.xml")

            assert not diff

    def test_diff_lockedfile_does_not_exist(self):
        case = mock.MagicMock()

        with tempfile.TemporaryDirectory() as tempdir:
            case.get_value.side_effect = (tempdir,)

            locked_files.diff_lockedfile(case, tempdir, "env_batch.xml")

    def test_diff_lockedfile(self):
        case = mock.MagicMock()

        with tempfile.TemporaryDirectory() as tempdir:
            case.get_value.side_effect = (tempdir,)

            create_fake_env(tempdir)

            locked_files.diff_lockedfile(case, tempdir, "env_batch.xml")

    def test_check_lockedfile(self):
        case = mock.MagicMock()

        with tempfile.TemporaryDirectory() as tempdir:
            case.get_value.side_effect = (tempdir,)

            create_fake_env(tempdir)

            with self.assertRaises(CIMEError):
                locked_files.check_lockedfile(case, "env_batch.xml")

    def test_check_lockedfiles_skip(self):
        case = mock.MagicMock()

        with tempfile.TemporaryDirectory() as tempdir:
            case.get_value.side_effect = (tempdir,)

            create_fake_env(tempdir)

            locked_files.check_lockedfiles(case, skip="env_batch.xml")

    def test_check_lockedfiles(self):
        case = mock.MagicMock()

        with tempfile.TemporaryDirectory() as tempdir:
            case.get_value.side_effect = (tempdir,)

            create_fake_env(tempdir)

            with self.assertRaises(CIMEError):
                locked_files.check_lockedfiles(case)

    def test_is_locked(self):
        with tempfile.TemporaryDirectory() as tempdir:
            src_path = Path(tempdir, locked_files.LOCKED_DIR, "env_case.xml")

            src_path.parent.mkdir(parents=True)

            src_path.touch()

            assert locked_files.is_locked("env_case.xml", tempdir)

            src_path.unlink()

            assert not locked_files.is_locked("env_case.xml", tempdir)

    def test_unlock_file_error_path(self):
        with tempfile.TemporaryDirectory() as tempdir:
            src_path = Path(tempdir, locked_files.LOCKED_DIR, "env_case.xml")

            src_path.parent.mkdir(parents=True)

            src_path.touch()

            with self.assertRaises(CIMEError):
                locked_files.unlock_file("/env_case.xml", tempdir)

    def test_unlock_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            src_path = Path(tempdir, locked_files.LOCKED_DIR, "env_case.xml")

            src_path.parent.mkdir(parents=True)

            src_path.touch()

            locked_files.unlock_file("env_case.xml", tempdir)

            assert not src_path.exists()

    def test_lock_file_newname(self):
        with tempfile.TemporaryDirectory() as tempdir:
            src_path = Path(tempdir, "env_case.xml")

            src_path.touch()

            locked_files.lock_file("env_case.xml", tempdir, newname="env_case-old.xml")

            dst_path = Path(tempdir, locked_files.LOCKED_DIR, "env_case-old.xml")

            assert dst_path.exists()

    def test_lock_file_error_path(self):
        with tempfile.TemporaryDirectory() as tempdir:
            src_path = Path(tempdir, "env_case.xml")

            src_path.touch()

            with self.assertRaises(CIMEError):
                locked_files.lock_file("/env_case.xml", tempdir)

    def test_lock_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            src_path = Path(tempdir, "env_case.xml")

            src_path.touch()

            locked_files.lock_file("env_case.xml", tempdir)

            dst_path = Path(tempdir, locked_files.LOCKED_DIR, "env_case.xml")

            assert dst_path.exists()
