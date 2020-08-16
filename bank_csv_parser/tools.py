import datetime
import re
from typing import List, Optional, Tuple
import warnings

import numpy as np


class IPrintable:
    def __init__(self, verbosity: int):
        super().__init__()
        self.verbosity = verbosity

    def print(self, *args, **kwargs):
        verbosity = kwargs.pop("verbosity", self.verbosity)
        print(*args, **kwargs) if verbosity >= self.verbosity else None


def is_date_convertible(in_str: str) -> Tuple[bool, Optional[datetime.datetime]]:
    """Check if the input string is convertible to a date and convert it

    Parameters
    ----------
    in_str : str
        Input

    Returns
    -------
    Tuple[bool, Optional[datetime.datetime]]
        Bool if the date is true, datetime.datetime if the string is a date
    """

    this_is_date = False
    in_str = in_str.strip('"')
    x = None
    fmts = ["%m/%d/%Y", "%m/%d/%y"]
    for fmt in fmts:
        try:
            x = datetime.datetime.strptime(in_str, fmt)
            this_is_date = True
            break
        except ValueError:
            pass
    return (this_is_date, x)


def is_float_convertible(in_str: str) -> Tuple[bool, float]:
    """Check if the input string is convertible to a float and convert it

    Parameters
    ----------
    in_str : str
        Input

    Returns
    -------
    Tuple[bool, float]
        Bool if the date is true, float if the string is a float
    """

    in_str = in_str.strip('"')
    _float_regexp = re.compile(
        r"^[-+]?(?:\b[0-9]+(?:\.[0-9]*)?|\.[0-9]+\b)(?:[eE][-+]?[0-9]+\b)?$"
    )
    is_float = re.match(_float_regexp, in_str)
    return (is_float, float(in_str)) if is_float else (False, None)


def check_csv_extra_separators(buffer: List[str], separator: str = ",") -> bool:
    """Check the csv file for extra separators in its lines

    Parameters
    ----------
    buffer : List[str]
        List of strings of the file
    separator : str
        Separator between columns, default = ","

    Returns
    -------
    bool
        If the file has an equal number of separators in each line

    Raises
    ------
    ValueError
        If the file has an unequal number of separators
    """

    ncommas = np.array([x.count(separator) for x in buffer])
    rightncommas = int(round(np.mean(ncommas), 0))
    wrongstrings = np.where(ncommas != rightncommas)[0]
    if len(wrongstrings) > 0:
        for i in wrongstrings:
            warnings.warn(f"Wrong string {i} : {buffer[i]}")
        raise ValueError
    (f"File has strings with extra separators : {wrongstrings}")
    return True


def get_header_lines(buffer: List[str], separator: str = ",") -> int:
    """Extract the number of header lines by looking if they're convertible to dates

    Parameters
    ----------
    buffer : List[str]
        List of strings of the file

    Returns
    -------
    int
        Number of header lines
    """
    ln = 0
    has_date = False
    for x in buffer:
        has_date = np.sum(
            list(map(lambda x: is_date_convertible(x)[0], x.rstrip().split(separator)))
        )
        if not has_date:
            ln += 1
        else:
            break
    return ln
