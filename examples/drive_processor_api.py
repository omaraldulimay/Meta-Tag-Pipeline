from argparse import Namespace
from pathlib import Path
from typing import Optional, Union
from .google_drive_processor import get_drive_service, process_once


def run_processing(
    service_account_file: Union[Path, str] = "google-service-account.json",
    drive_folder_id: Optional[str] = None,
    output_drive_folder_id: Optional[str] = None,
    archive_drive_folder_id: Optional[str] = None,
    incoming: Union[Path, str] = "incoming",
    processed: Union[Path, str] = "processed",
):
    """Convenience wrapper to call the existing processor from other code.

    Returns when processing completes. Raises exceptions from underlying code.
    """
    args = Namespace()
    args.service_account_file = Path(service_account_file)
    args.drive_folder_id = drive_folder_id
    args.output_drive_folder_id = output_drive_folder_id
    args.archive_drive_folder_id = archive_drive_folder_id
    args.incoming = Path(incoming)
    args.processed = Path(processed)

    service = get_drive_service(args.service_account_file)
    process_once(args, service)


__all__ = ["run_processing"]
