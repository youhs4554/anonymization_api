# -*- coding:utf-8 -*-

from flask import (
    Flask,
    request,
    g,
    jsonify,
    Response,
    flash,
    redirect,
    send_from_directory,
)
from werkzeug.utils import secure_filename
import os
from flask_cors import CORS
from datetime import datetime
import subprocess
from tools.annonymizer import Annonymizer
from tools.utils import publish_message
import redis
import json
import random
import string
import subprocess
from flask import _app_ctx_stack
import time
import werkzeug
from werkzeug.exceptions import BadRequest
from natsort import natsorted

app = Flask(__name__)
app.secret_key = "secret"
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


@app.route("/api/v1.0/download/<path:filename>")
def download_file(filename):
    return send_from_directory(ANONY_DIR, filename, as_attachment=True)


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

        mycmd = f"bsdtar -tzf {fname} '*.dcm'"
        output = subprocess.getoutput(mycmd).split("\n")

        if "Not found" in output:
            raise BadRequest("My custom message")

        dname = os.path.dirname(output[0])
        strip_level = dname.count("/")
        cmd = cmd(src=fname, tgt=tgt_dir, strip_level=strip_level)

        # step 1 : unzip file
        os.system(cmd)

        eventId = request.values["eventId"]
        publish_message(r, data={"unzip": True}, event=eventId)

        # TODO.
        # if unzip process ends, write db a flag which menas it is ready to anonymize files.
        # while unzip process, use will see spinning animation which will be used to show server's progress status

        # step 2 : remove original file
        os.system(f"rm {fname}")

        anm_root = os.path.join(ANONY_DIR, os.path.basename(os.path.splitext(fname)[0]))

        # step 3 : run anonymization scripts
        Annonymizer(
            redis=r,
            eventId=eventId,
            root=tgt_dir,
            anm_root=anm_root,
            table_path=os.path.join(anm_root, "Table.xlsx"),
            disable_suv=True,
            verbose=False,
        ).run()

        # step 4 : 분할 압축
        archive_dir = os.path.join(anm_root, "archive")
        if not os.path.exists(archive_dir):
            os.system("mkdir -p {}".format(archive_dir))

        os.system(
            f'tar -cvf - {anm_root} --exclude "archive" | split -b 1536m - {os.path.join(archive_dir, userId)}.tar'
        )

        fileList = natsorted(os.listdir(archive_dir))
        reduced_path = "/".join(archive_dir.split("/")[-2:])
        fileList = [os.path.join(reduced_path, x) for x in fileList]
        publish_message(r, data={"compress": True, "fileList": fileList}, event=eventId)

        # step 5 : forces user to download resulting file

        return "파일 업로드 성공!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)

