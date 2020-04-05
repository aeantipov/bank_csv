import argparse

from bank_csv_parser import BankCSVParser

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="csv statements parser")
    parser.add_argument(
        "files",
        nargs="*",
        help="input csv files, if none - "
        + "all matching files in current directory will be used",
        default=None,
    )
    parser.add_argument(
        "--noupload", dest="upload", action="store_false", help="disable gdrive upload"
    )
    parser.add_argument(
        "--nobackup", dest="backup", action="store_false", help="disable backup"
    )
    parser.add_argument(
        "--spreadsheet_name",
        type=str,
        default="tmp_money_import",
        help="Name of the spreadsheet to upload data",
    )
    parser.add_argument(
        "--sheet_name",
        type=str,
        default="upload",
        help="Name of the sheet within the spreadsheet to upload data",
    )
    parser.add_argument(
        "--gdrive_json",
        type=str,
        default="gdrive.json",
        help="Google Service Account Key file, see "
        + "https://cloud.google.com/iam/docs/creating-managing-service-account-keys",
    )
    args = parser.parse_args()
    csv_parser = BankCSVParser(args.files)
    csv_parser.parse()
    csv_parser.backup()
    if args.upload:
        csv_parser.upload_gdrive(
            spreadsheet_name=args.spreadsheet_name,
            sheet_name=args.sheet_name,
            json_keyfile=args.gdrive_json,
        )
    else:
        print("Skipping upload")
