from multiprocessing.pool import ThreadPool
from functools import partial
from .utils import runner, get_table
import os
from natsort import natsorted
import numpy as np
from tqdm import tqdm
import json


class Annonymizer:
    TARGET_ELEMENTS = ["PatientAge", "PatientBirthDate", "PatientID", "PatientName"]

    def __init__(
        self, redis, root, anm_root, table_path=None, disable_suv=True, verbose=True,
    ):
        self.redis = redis
        self.root = root
        self.anm_root = anm_root
        # directory for raw anonymized dcms
        if not os.path.exists(anm_root):
            os.makedirs(anm_root, exist_ok=True)  # cretae a new dir

        self.disable_suv = disable_suv
        self.verbose = verbose
        # sanity check for given Dicoms and return
        meta_data = get_table(root=root, target_elements=self.TARGET_ELEMENTS)
        meta_data.to_excel(table_path)
        self.input_folders = natsorted(
            [os.path.join(root, x) for x in meta_data.HospNo]
        )
        meta_data.HospNo = np.char.zfill(meta_data.HospNo.values.astype(str), 32)

        self.meta_data = meta_data
        self.global_step = [1]

    def run(self):
        pool = ThreadPool(8)
        nfolders = len(self.input_folders)

        from glob import glob
        from functools import reduce
        import time

        nslices_tot = reduce(
            lambda x, y: x + y,
            [len(glob(infold + "/*")) for infold in self.input_folders],
        )

        with tqdm(total=nfolders) as pbar:
            for i in range(nfolders):
                infold = self.input_folders[i]
                nslices_current = len(glob(infold + "/*"))

                runner(
                    infold,
                    redis=self.redis,
                    root=self.root,
                    anm_root=self.anm_root,
                    target_elements=self.TARGET_ELEMENTS,
                    meta_data=self.meta_data,
                    disable_suv=self.disable_suv,
                    verbose=self.verbose,
                    global_step=self.global_step,
                )
                pbar.update()

                remaining_time = (nfolders - i) * pbar.avg_time
                event = "myevent"  # unused

                data = {"unzip": None, "remaining_time": remaining_time}
                self.redis.publish("sse_example_channel", json.dumps([event, data]))

                print(f"{i+1}/{nfolders}, remainTime : {remaining_time}")

                # write on db
                ### will be db exec code!

            pool.close()
            pool.join()

        print("Done!")
