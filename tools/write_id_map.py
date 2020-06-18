import pandas as pd
import numpy as np
import os
import glob
from natsort import natsorted
from tqdm import tqdm
import pydicom
import argparse


def file_sanity_check(filename, data_elements, replacement_str="anonymous"):
    try:
        dataset = pydicom.dcmread(filename)
    except:
        print(f"{filename} is not valid dicom file!")
        return False

    return True


def main(args):
    input_folders = glob.glob(args.INFOLD + "/*")
    filename_list = natsorted(glob.glob(args.INFOLD + "/*/*"))

    names = []
    invalid_names = []

    # empty folder
    empty_folders = list(
        set(input_folders) - set([os.path.dirname(p) for p in filename_list])
    )
    invalid_names += [os.path.basename(p) for p in empty_folders]

    for i in tqdm(range(len(filename_list)), desc="check validity..."):
        filename = filename_list[i]
        valid = file_sanity_check(filename, args.GET_ELEMENTS)
        if valid:
            names.append(os.path.basename(os.path.dirname(filename)))
        else:
            invalid_names.append(os.path.basename(os.path.dirname(filename)))

    names = list(set(names))
    invalid_names = list(set(invalid_names))

    # save invalid_list
    with open("invalid_list.txt", "w") as outfile:
        outfile.writelines([line + "\n" for line in invalid_names])

    # save .xlsx to anonymize
    df = pd.DataFrame({"No": np.arange(len(names)), "HospNo": names})
    df.to_excel("output.xlsx")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--INFOLD", type=str, default="./DCMs", help="path to dicom roopt directory"
    )
    args = parser.parse_args()
    args.TARGET_ELEMENTS = [line.rstrip("\n") for line in open("./target_elements.txt")]