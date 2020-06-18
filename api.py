from flask import Flask, request, g, jsonify, Response
from werkzeug.utils import secure_filename
import os
from flask_cors import CORS
from datetime import datetime
import subprocess
from tools.annonymizer import Annonymizer
import redis
import json

app = Flask(__name__)
CORS(app)

r = redis.StrictRedis(host="0.0.0.0", port=6379)  # Connect to local Redis instance

EXTS = [".zip", ".tar", ".tar.gz", ".gz", ".tgz"]

UNCOMPRESS_COMMNADS_DICT = {
    ".zip": lambda src, tgt: f'bsdtar --strip-components=1 -xvf {src} -C "{tgt}"',
    ".tar": lambda src, tgt: f'tar -xvf {src} -C "{tgt}" --strip-components=2',
    ".gz": lambda src, tgt: f'tar -xvzf {src} -C "{tgt}" --strip-components=2',
}
SAVE_DIR = "upload"


def event_stream():
    pub = r.pubsub()
    pub.subscribe("sse_example_channel")
    for msg in pub.listen():
        if msg["type"] != "subscribe":
            event, data = json.loads(msg["data"])
            yield "event: {0}\ndata: {1}\n\n".format(event, data)
        else:
            yield "data: {0}\n\n".format(msg["data"])


@app.route("/api/v1.0/stream")
def get_pushes():
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/v1.0/publish")
def publish_data():
    event = "myevent"  # unused
    data = "1234"  # TDOO. retrieve current status & remaining time
    r.publish("sse_example_channel", json.dumps([event, data]))

    return "Published"


@app.route("/api/v1.0/anonymization", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        f = request.files["file"]
        fname = os.path.join(SAVE_DIR, secure_filename(f.filename))
        f.save(fname)
        ext = os.path.splitext(fname)[1]
        if ext in [".gz", ".tar.gz", ".tgz"]:
            ext = ".gz"

        cmd = UNCOMPRESS_COMMNADS_DICT.get(ext)
        tgt_dir = os.path.join(SAVE_DIR, datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.system(f'mkdir -p "{tgt_dir}"')

        cmd = cmd(src=fname, tgt=tgt_dir)
        # step 1 : unzip file
        os.system(cmd)

        # TODO.
        # if unzip process ends, write db a flag which menas it is ready to anonymize files.
        # while unzip process, use will see spinning animation which will be used to show server's progress status

        # step 2 : remove original file
        os.system(f"rm {fname}")

        tgt_dir = os.path.abspath(tgt_dir)

        # step 3 : run anonymization scripts
        Annonymizer(
            root=tgt_dir,
            anm_root=tgt_dir + "_process",
            table_path=os.path.join(tgt_dir + "_process", "Table.xlsx"),
            disable_suv=True,
            verbose=False,
        ).run()

        return "파일 업로드 성공!"


if __name__ == "__main__":
    if not os.path.exists("upload"):
        os.system("mkdir -p upload")

    app.run(host="0.0.0.0", debug=True)

