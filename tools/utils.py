# encoding: utf-8
from __future__ import print_function
import SimpleITK as sitk
from google_drive_downloader import GoogleDriveDownloader as gdd
import os
import json
from copy import deepcopy, copy
import subprocess
import pydicom
from pathlib import Path
import pydicom
import os
import glob
from natsort import natsorted
import argparse
import pandas as pd
import numpy as np
from multiprocessing import Pool
import SimpleITK as sitk


def fetch_file_from_google_drive(file_map, file_id):
    print(f"###Download {file_map[file_id]}###")
    gdd.download_file_from_google_drive(
        file_id=file_id, dest_path="./lib/tmp.zip", unzip=True
    )
    os.system("rm ./lib/tmp.zip")


def download_dependencies(manifest_path="./gdrive_manifest.json"):
    file_map = json.load(open(manifest_path))

    for file_id in file_map:
        fetch_file_from_google_drive(file_map, file_id)
    # setup for Slicer App
    os.system(f"chmod -R 777 ./lib/Slicer-4.10.2-linux-amd64/Slicer")

    # setup for lib usage
    config_home = os.path.join(str(Path.home()), ".config")
    os.system(
        f"mkdir -p {config_home} && cp -r ./lib/NA-MIC {config_home} && chmod -R 777 {config_home}"
    )


def get_suv_factor(infold):
    res = subprocess.run(
        [
            "./lib/Slicer-4.10.2-linux-amd64/Slicer",
            "--launch",
            "SUVFactorCalculator",
            "-p",
            infold,
            "-r",
            ".",
        ],
        stdout=subprocess.PIPE,
    )
    for line in res.stdout.split(b"\n"):
        if line.startswith(b"saving to"):
            line = line.decode("utf-8")
            break

    res_dcm = line.split()[-1]

    d = pydicom.read_file(res_dcm)
    suv = (
        d.ReferencedImageRealWorldValueMappingSequence[0]
        .RealWorldValueMappingSequence[0]
        .RealWorldValueSlope
    )
    os.remove(res_dcm)

    return suv


def dcm_to_nrrd(folder, to_path, intensity_windowing=True, compression=False):
    """Read a folder with DICOM files and convert to a nrrd file.
    Assumes that there is only one DICOM series in the folder.

    Parameters
    ----------
    folder : string
      Full path to folder with dicom files.
    to_path : string
      Full path to output file (with .nrrd extension). As the file is
      outputted through SimpleITK, any supported format can be selected.
    intensity_windowing: bool
      If True, the dicom tags 'WindowCenter' and 'WindowWidth' are used
      to clip the image, and the resulting image will be rescaled to [0,255]
      and cast as uint8.
    compression : bool
      If True, the output will be compressed.
    """
    reader = sitk.ImageSeriesReader()
    series_ids = reader.GetGDCMSeriesIDs(folder)

    assert len(series_ids) == 1, "Assuming only one series per folder."

    filenames = reader.GetGDCMSeriesFileNames(folder, series_ids[0])
    reader.SetFileNames(filenames)
    image = reader.Execute()

    if intensity_windowing:
        dcm = pydicom.read_file(filenames[0])
        assert hasattr(dcm, "WindowCenter") and hasattr(
            dcm, "WindowWidth"
        ), "when `intensity_windowing=True`, dicom needs to have the `WindowCenter` and `WindowWidth` tags."
        center = dcm.WindowCenter
        width = dcm.WindowWidth

        lower_bound = center - (width - 1) / 2
        upper_bound = center + (width - 1) / 2

        image = sitk.IntensityWindowing(image, lower_bound, upper_bound, 0, 255)
        image = sitk.Cast(
            image, sitk.sitkUInt8
        )  #  after intensity windowing, not necessarily uint8.

    writer = sitk.ImageFileWriter()
    if compression:
        writer.UseCompressionOn()

    writer.SetFileName(to_path)
    writer.Execute(image)


import pandas as pd
import numpy as np
import os
import glob
from natsort import natsorted
import pydicom
import argparse


def file_sanity_check(filename, data_elements, replacement_str="anonymous"):
    try:
        dataset = pydicom.dcmread(filename)
    except:
        print(f"{filename} is not valid dicom file!")
        return False

    return True


def get_table(root, target_elements):
    input_folders = glob.glob(root + "/*")
    filename_list = natsorted(glob.glob(root + "/*/*"))

    names = []  # valid names

    # empty folder
    empty_folders = list(
        set(input_folders) - set([os.path.dirname(p) for p in filename_list])
    )

    for i in range(len(filename_list)):
        filename = filename_list[i]
        valid = file_sanity_check(filename, target_elements)
        if valid:
            names.append(os.path.basename(os.path.dirname(filename)))

    names = list(set(names))

    # save .xlsx to anonymize
    df = pd.DataFrame({"No": np.arange(len(names)), "HospNo": names})

    return df


def pid2ixs(df, pid):
    return str(df[df.HospNo == str(pid).zfill(32)].No.values[0])


def anonymize(dataset, data_elements, replacement_str="anonymous"):
    for de in data_elements:
        try:
            ret = dataset.data_element(de)
        except KeyError:
            # skip non-existing key
            continue
        if ret is None:
            # exception handling
            raise Exception(f"Unkown element '{de}'")
        ret.value = replacement_str

    return dataset


def runner(
    infold,
    redis,
    root,
    anm_root,
    target_elements,
    meta_data,
    disable_suv=True,
    verbose=True,
    global_step=[0],
):
    filename_list = natsorted(glob.glob(infold + "/*"))
    # run SUVFactorCalculator
    if not disable_suv:
        suv = get_suv_factor(infold)
        suv_slices = []

    # anonymize and save as .dcm
    tot = len(glob.glob(os.path.join(root, "*", "*")))

    try:
        for i in range(len(filename_list)):
            import time

            t0 = time.time()

            filename = filename_list[i]
            try:
                dataset = pydicom.dcmread(filename)
            except:
                continue

            dataset = anonymize(dataset, target_elements)

            # save resulting dataset
            pid = os.path.basename(infold)
            cvt_ix = pid2ixs(meta_data, pid=pid)

            anm_dir = infold.replace(root, anm_root)
            anm_dir_splits = os.path.split(anm_dir)
            anm_dir = os.path.join(anm_dir_splits[0], cvt_ix)

            anm_dir_raw = anm_dir
            if not disable_suv:
                anm_dir_raw = os.path.join(anm_dir, "raw")

            # directory for raw anonymized dcms
            if not os.path.exists(anm_dir_raw):
                print(f"create directory at {anm_dir_raw}")
                os.system(f"mkdir -p {anm_dir_raw}")

            _, ext = os.path.splitext(os.path.basename(filename))
            anm_path = os.path.join(anm_dir_raw, f"Slice{i:04}" + ext)
            dataset.save_as(anm_path)  # 1 : save original pixel data

            # multiply with SUV-ScaleFactor
            img = sitk.GetArrayFromImage(sitk.ReadImage(anm_path))  # (1,h,w)
            # anm_suv_path = os.path.join(anm_dir_suv, f'PET{i:04}'+'.nrrd')

            if not disable_suv:
                suv_slices.append(suv * img)
                suv_img = sitk.GetImageFromArray(suv * img)

            if verbose:
                for de in target_elements:
                    print(filename, dataset.data_element(de))

            elapsed_time = time.time() - t0
            remaining_time = (tot - global_step[0]) * elapsed_time
            percent = min(100.0, 100 * float(global_step[0] / tot))

            event = "myevent"  # unused
            data = {"remaining_time": remaining_time, "percent": percent}
            redis.publish("sse_example_channel", json.dumps([event, data]))

            global_step[0] += 1

        if not disable_suv:
            suv_volume = sitk.GetImageFromArray(np.vstack(suv_slices)[::-1])
            suv_volume = sitk.Cast(suv_volume, sitk.sitkFloat64)

            # write a resulting volume as .nrrd file
            sitk.WriteImage(suv_volume, os.path.join(anm_dir, "SUV.nrrd"))

    except KeyboardInterrupt:
        raise Exception("User Interrupt")
