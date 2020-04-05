# bank_csv
Python module and script to parse bank csv files and collect them in a common database.
For a given list of files this code:
- Parses every statement 
- Collects them all into date/value/description table
- Makes a copy of statements locally 
- (Optional) Uploads into a google drive spreadsheet. For this you need a key, see https://cloud.google.com/iam/docs/creating-managing-service-account-keys

## Usage 
```
usage: parse_money.py [-h] [--noupload] [--nobackup] [--spreadsheet_name SPREADSHEET_NAME] [--sheet_name SHEET_NAME] [--gdrive_json GDRIVE_JSON] [files [files ...]]

csv statements parser

positional arguments:
  files                 input csv files, if none - all matching files in current directory will be used

optional arguments:
  -h, --help            show this help message and exit
  --noupload            disable gdrive upload
  --nobackup            disable backup
  --spreadsheet_name SPREADSHEET_NAME
                        Name of the spreadsheet to upload data
  --sheet_name SHEET_NAME
                        Name of the sheet within the spreadsheet to upload data
  --gdrive_json GDRIVE_JSON
                        Google Service Account Key file, see https://cloud.google.com/iam/docs/creating-managing-service-account-keys
```
