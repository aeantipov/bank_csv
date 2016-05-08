import argparse

from bank_csv_parser import BankCSVParser

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="csv statements parser")
    parser.add_argument("files", nargs="*", help="input csv", default=None)
    parser.add_argument("--noupload", dest="upload", action="store_false")
    parser.add_argument("--nobackup", dest="backup", action="store_false")
    parser.add_argument("--spreadsheet_name", type=str, default="tmp_money_import")
    args = parser.parse_args()
    csv_parser = BankCSVParser(args.files)
    csv_parser.parse()
    csv_parser.backup()
    if args.upload:
        csv_parser.upload_gdrive(spreadsheet_name=args.spreadsheet_name)
    else:
        print("Skipping upload")
