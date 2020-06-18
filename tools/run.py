pass

if __name__ == "__main__":
    INPUT_ROOT = args.INPUT_ROOT
    anm_root = args.anm_root

    # global TARGET_ELEMENTS
    # global meta_data

    TARGET_ELEMENTS = []
    for line in open("target_elements.txt", "r"):
        TARGET_ELEMENTS.append(line.strip())
    print(f"Start anonymization process for {TARGET_ELEMENTS}")

    meta_data = get_table(root=INPUT_ROOT, target_elements=TARGET_ELEMENTS)
    meta_data.to_excel(TABLE_PATH)

    input_folders = natsorted([os.path.join(INPUT_ROOT, x) for x in meta_data.HospNo])
    meta_data.HospNo = np.char.zfill(meta_data.HospNo.values.astype(str), 32)

    # Download dependencies from GoogleDrive
    if (
        not args.disable_suv
        and not os.path.exists("./lib/Slicer-4.10.2-linux-amd64")
        and not os.path.exists("./lib/NA-MIC")
    ):
        download_dependencies()

    if args.debug:
        runner(input_folders[0])
    else:
        pool = Pool(8)
        pool.map(runner, input_folders)
        pool.close()
        pool.join()

    print("Done!")
