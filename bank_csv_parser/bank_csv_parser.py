from __future__ import annotations

from dataclasses import dataclass
import datetime
import io
import os
import shutil
from typing import List, Optional, Tuple

import gspread
import numpy as np
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

from .tools import (
    IPrintable,
    check_csv_extra_separators,
    get_header_lines,
    is_date_convertible,
    is_float_convertible,
)


@dataclass
class StatementData:
    dates: pd.core.indexes.datetimes.DatetimeIndex
    money: np.ndarray
    descriptions: np.ndarray
    dframe: pd.dataframe

    @classmethod
    def from_csv(
        self, fname: str, csv_separator: str, filters: List[str]
    ) -> StatementData:
        readlines = np.asarray(open(fname, "r").read().splitlines(), dtype=object)
        header_lines = get_header_lines(readlines)
        buffer = readlines[header_lines:]
        check_csv_extra_separators(buffer, csv_separator)
        date_index, money_index, desc_index = StatementData.extract_column_indices(
            buffer
        )
        dframe = pd.read_csv(
            fname,
            parse_dates=True,
            header=header_lines - 1 if header_lines else None,
            index_col=date_index,
            dayfirst=False,
            keep_date_col=True,
        )
        money = dframe.values[:, money_index - 1]
        dates = dframe.index[:]
        descriptions = dframe.values[:, desc_index - 1]

        # Filter "Payment" entries
        filter_inds = np.where(
            np.logical_not([x.lower() in filters for x in descriptions])
        )
        money = money[filter_inds]
        dates = dates[filter_inds]
        descriptions = descriptions[filter_inds]

        # Some banks have debit negative, some positive
        # Figure it out by looking at the average sign of the money column
        sign = np.mean(np.sign(money))
        print("Sign = ", sign)
        money *= (-1.0) if sign > 0 else 1.0
        return StatementData(
            dates=dates, money=money, descriptions=descriptions, dframe=dframe
        )

    @staticmethod
    def extract_column_indices(buffer: List[str]) -> Tuple[int, int, int]:
        """Process a file buffer and extract the column indices of date,
        money and description. The dates are extracted by checking convertability
        to date format, the money is the column convertible to float that has the
        largest relative standard variation (std/mean). The description is the
        string column that has the largest standard variation.

        Parameters
        ----------
        buffer : List[str]
            Lines read from file

        Returns
        -------
        Tuple[int, int, int]
            Indices of date, money, description

        Raises
        ------
        ValueError
            No data with dates
        ValueError
            No floating point columns
        """
        large_data_sample = np.array([x.rstrip().split(",") for x in buffer])
        data_sample = large_data_sample[0]
        date_indices = np.array([], dtype=int)
        sample_dates = []
        float_cols = []
        string_cols = []
        print("Sample:", data_sample)
        for i in range(len(data_sample)):
            (is_date, x) = is_date_convertible(data_sample[i])
            # check if date
            if is_date:
                date_indices = np.append(date_indices, i)
                sample_dates = sample_dates + [x]
            else:
                # then maybe a float
                (is_float, x) = is_float_convertible(data_sample[i])
                if is_float:
                    if abs(x) < 1e5 and abs(x) > 1e-8:
                        float_cols = float_cols + [i]
                else:
                    # it seems to be a string then
                    string_cols = string_cols + [i]
        if len(date_indices) == 0:
            raise ValueError("Could not find a column with the date.")
        if len(float_cols) == 0:
            raise ValueError("No data columns")
        # Take the earliest transaction date for the reference
        date_index = date_indices[np.argmin(sample_dates)]
        # Get the right description
        data_sample = np.array(data_sample)
        desc_cols = np.array(string_cols)
        # filter everything before the date
        desc_cols = desc_cols[desc_cols > date_index]
        # description is likely to be in the column
        # with longest entries that change (std > 0)
        if large_data_sample.shape[0] > 3:
            f1 = np.vectorize(lambda x: len("".join(filter(lambda y: y.isalpha(), x))))
            means = np.mean(f1(large_data_sample[:, desc_cols]), axis=0)
            stds = np.std(f1(large_data_sample[:, desc_cols]), axis=0)
            pos_std = np.where(stds > 0)
            desc_index = desc_cols[pos_std[0][np.argmax(means[pos_std])]]
        else:
            desc_index = desc_cols[0]

        # Extract the column number with the money amount
        float_sample = large_data_sample[:, float_cols]
        float_sample[np.where(float_sample == "")] = np.nan
        float_sample = float_sample.astype(float)
        means = np.mean(float_sample, axis=0)
        stds = np.std(float_sample, axis=0)
        rel_variation = stds / np.abs(means)
        money_index = float_cols[np.argmax(rel_variation)]
        # self.print("dates [" + str(date_index) + "] (", data_sample[date_index], ")")
        print("money [" + str(money_index) + "] (", data_sample[money_index], ")")
        # self.print("desc  [" + str(desc_index) + "] (", data_sample[desc_index], ")")

        return (date_index, money_index, desc_index)


class BankCSVParser(IPrintable):
    def __init__(
        self,
        filenames: Optional[List[str]] = None,
        csv_separator: str = ",",
        verbosity: int = 1,
    ):
        """Class to loop over a list of bank statements in CSV files,
        read them in and convert to a common table. Results are backed up and
        uploaded to google drive if asked.

        Parameters
        ----------
        filenames : List[str]
            List of files
        csv_separator : str, optional
            CSV separator, by default ","
        verbosity : int, optional
            Level of verbosity, by default 1

        Raises
        ------
        FileExistsError
            File not found
        """
        super().__init__(verbosity=verbosity)
        if filenames is None or not len(filenames):
            self.filenames = np.array(
                list(filter(lambda x: x.lower().find(".csv") != -1, os.listdir()))
            )
        else:
            self.filenames = filenames
        for fname in self.filenames:
            if not os.path.exists(fname):
                raise FileExistsError(fname + " not found")

        self.csv_separator = csv_separator
        self.data = {}
        self.money_sorted = {}
        self.desc_sorted = {}

        # Filters for payments in bank statements
        self.filters = [
            "ONLINE PAYMENT - THANK YOU",
            "PAYMENT - THANK YOU",
            "Payment Thank You - Web",
            "Payment Thank You-Mobile",
            "PAYMENT RECEIVED - THANK YOU",
            "PAYMENT THANK YOU",
            "ONLINE PAYMENT, THANK YOU",
            "ONLINE PAYMENT THANK YOU",
            "INTERNET PAYMENT THANK YOU",
            "Payment Received",
            "Topped up balance",
            "MOBILE PAYMENT - THANK YOU",
        ]
        self.filters = [x.lower() for x in self.filters]

    def parse(self):
        """Loop through a list of files and create a database
        """
        for fname in self.filenames:
            self.print("-->", fname)
            statement_data = StatementData.from_csv(
                fname, self.csv_separator, self.filters
            )
            self.data[fname] = statement_data
            self.print(self.data[fname].dframe.head())
            self.print("---------------------------------------------------")
            self.update(statement_data)

    def update(self, st_data: StatementData):
        """Update data with the new statement

        Parameters
        ----------
        st_data : StatementData
            Statement data
        """
        dates, money, descriptions = st_data.dates, st_data.money, st_data.descriptions
        date_min = dates.min().date()
        date_max = dates.max().date()
        date_range = pd.date_range(date_min, date_max)

        for date in date_range:
            date1 = date.date().isoformat()
            self.money_sorted[date1] = self.money_sorted.get(date1, [])
            self.desc_sorted[date1] = self.desc_sorted.get(date1, [])

        for (x, m, desc) in zip(dates, money, descriptions):
            if desc not in self.filters:
                date1 = x.date().isoformat()
                self.money_sorted[date1] = self.money_sorted.get(date1, []) + [
                    -round(m, 2)
                ]
                self.desc_sorted[date1] = self.desc_sorted.get(date1, []) + [desc]
            else:
                raise ValueError("Filter didn't work")

    def data_stack(self):
        """Stack dates, values and descriptions to an array

        Returns
        -------
        np.ndarray
            Array with 3 columns: dates, values, descriptions
        """
        return np.vstack(
            [
                list(self.money_sorted.keys()),
                list(self.money_sorted.values()),
                list(self.desc_sorted.values()),
            ]
        ).transpose()[np.argsort(list(self.money_sorted.keys()))]

    def snapshot(self, output: Optional[io.TextIOBase] = None) -> io.TextIOBase:
        """Convert the data in BankCSVParser to a human-readable table and
        print it either in a StringIO or given file stream.

        Parameters
        ----------
        output : Optional[io.TextIOBase], optional
            File stream, by default None

        Returns
        -------
        io.TextIOBase
            Stream with results
        """
        all_data = self.data_stack()
        output = output or io.StringIO()
        for x in all_data:
            (date, vals, descs) = x
            values_str = "+".join([str(x) for x in vals]) if len(vals) > 0 else ""
            desc_str = "; ".join([str(x) for x in descs]) if len(descs) > 0 else ""
            output.write(f"{date}  : {values_str}; {desc_str}\n")
        return output

    def backup(self):
        """Copy all input files to a backup dir with current date
        """
        backup_dir = "backup_" + datetime.datetime.now().date().strftime("%Y.%m.%d")
        os.mkdir(backup_dir) if not os.path.exists(backup_dir) else None
        for fname in self.filenames:
            shutil.copy(fname, backup_dir)
            self.print(f"Backed {fname} -> {backup_dir}")
        self.snapshot(open("snapshot.txt", "w"))
        shutil.copy("snapshot.txt", backup_dir)

    def upload_gdrive(
        self,
        spreadsheet_name: str = "tmp_money_import",
        sheet_name: str = "upload",
        json_keyfile: str = "gdrive.json",
    ):
        """Upload data (table of dates/values/descriptions) to google drive

        Parameters
        ----------
        spreadsheet_name : str, optional
            Name of the spreadsheet to uplaod, by default "tmp_money_import"
        sheet_name : str, optional
            Name of the sheet in the spreadsheet to uplaod
        json_keyfile : str, optional
            JSON credentials for , by default "gdrive.json".
            See https://cloud.google.com/iam/docs/creating-managing-service-account-keys
        """
        all_data = self.data_stack()
        self.print("Uploading data to Google Drive")
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ]
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            json_keyfile, scope
        )
        gc = gspread.authorize(credentials)
        spreadsheet = gc.open(spreadsheet_name)
        wsh = spreadsheet.worksheet(sheet_name)
        wsh.resize(all_data.shape[0] + 1, all_data.shape[1])
        # write titles
        wsh.update_acell("A1", "Date")
        wsh.update_acell("B1", "Money")
        wsh.update_acell("C1", "Description")

        cell_list_date = wsh.range("A2:A{}".format(all_data.shape[0]))
        cell_list_money = wsh.range("B2:B{}".format(all_data.shape[0]))
        cell_list_desc = wsh.range("C2:C{}".format(all_data.shape[0]))

        for cdate, cmoney, cdesc, x in zip(
            cell_list_date, cell_list_money, cell_list_desc, all_data
        ):
            (date, vals, descs) = x
            cdate.value = date
            values_str = "+".join([str(x) for x in vals])
            desc_str = "; ".join([str(x) for x in descs])
            cmoney.value = "=" + values_str if len(vals) else ""
            cdesc.value = desc_str

        wsh.update_cells(cell_list_date, "USER_ENTERED")
        wsh.update_cells(cell_list_money, "USER_ENTERED")
        wsh.update_cells(cell_list_desc, "USER_ENTERED")

        self.print("Done.")
