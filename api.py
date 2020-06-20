# -*- coding:utf-8 -*-

from flask import Flask, request, g, jsonify, Response
from werkzeug.utils import secure_filename
import os
from flask_cors import CORS
from datetime import datetime
import subprocess
from tools.annonymizer import Annonymizer
import redis
import json
import random
import string
import subprocess
from flask import _app_ctx_stack

app = Flask(__name__)
CORS(app)

r = redis.StrictRedis(host="0.0.0.0", port=6379)  # Connect to local Redis instance

EXTS = [".zip", ".tar", ".tar.gz", ".gz", ".tgz"]

UNCOMPRESS_COMMNADS_DICT = {
    ".zip": lambda src, tgt, strip_level: f'bsdtar --strip-components={strip_level} -xvf {src} -C "{tgt}"',
    ".tar": lambda src, tgt, strip_level: f'tar -xvf {src} -C "{tgt}" --strip-components={strip_level}',
    ".gz": lambda src, tgt, strip_level: f'tar -xvzf {src} -C "{tgt}" --strip-components={strip_level}',
}
ORIGIN_DIR = "upload/origin"
ANONY_DIR = "upload/anonymous"

for x in [ORIGIN_DIR, ANONY_DIR]:
    os.system(f"mkdir -p {x}")


def event_stream():
    pub = r.pubsub()
    pub.subscribe("sse_example_channel")
    for msg in pub.listen():
        if msg["type"] != "subscribe":
            event, data = json.loads(msg["data"])
            data = json.dumps(data)
            yield "event: {0}\ndata: {1}\n\n".format(event, data)
        else:
            yield "data: {0}\n\n".format(msg["data"])


@app.route("/api/v1.0/stream")
def get_pushes():
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/v1.0/anonymization", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        f = request.files["file"]

        # generate random text
        char_set = string.ascii_lowercase + string.digits
        userId = "".join(random.sample(char_set * 8, 8))

        ext = os.path.splitext(f.filename)[-1]

        fname = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + userId + ext
        fname = os.path.join(ORIGIN_DIR, fname)
        f.save(fname)
        ext = os.path.splitext(fname)[1]
        if ext in [".gz", ".tar.gz", ".tgz"]:
            ext = ".gz"

        cmd = UNCOMPRESS_COMMNADS_DICT.get(ext)
        tgt_dir = os.path.join(ORIGIN_DIR, os.path.basename(os.path.splitext(fname)[0]))
        os.system(f'mkdir -p "{tgt_dir}"')

        mycmd = f"bsdtar -tvzf {fname}"
        output = subprocess.getoutput(mycmd)
        output = [line.split(" ")[-1] for line in output.split("\n")]
        output = list(filter(lambda line: line.endswith(".dcm"), output))
        dname = os.path.dirname(output[0].split(" ")[-1])
        strip_level = dname.count("/")
        cmd = cmd(src=fname, tgt=tgt_dir, strip_level=strip_level)

        event = "myevent"  # unused
        data = {"unzip": None}
        r.publish("sse_example_channel", json.dumps([event, data]))

        # step 1 : unzip file
        os.system(cmd)

        # TODO.
        # if unzip process ends, write db a flag which menas it is ready to anonymize files.
        # while unzip process, use will see spinning animation which will be used to show server's progress status

        # step 2 : remove original file
        os.system(f"rm {fname}")

        anm_root = os.path.join(ANONY_DIR, os.path.basename(os.path.splitext(fname)[0]))

        # step 3 : run anonymization scripts
        Annonymizer(
            redis=r,
            root=tgt_dir,
            anm_root=anm_root,
            table_path=os.path.join(anm_root, "Table.xlsx"),
            disable_suv=True,
            verbose=False,
        ).run()

        # step 4 : 분할 압축

        # step 5 : forces user to download resulting file

        return "파일 업로드 성공!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)

