import os

from flask import Flask, request, jsonify, render_template, Response
import requests

app = Flask(__name__)


@app.route("/proxy")
def proxy():
    url = request.args.get("url")
    if not url:
        return {"error": "No URL provided"}, 400

    try:
        # Если это локальный файл
        if url.startswith("file:///"):
            file_path = url.replace("file:///", "")
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    data = f.read()
                return Response(data, status=200, headers={
                    "Access-Control-Allow-Origin": "*",
                    "Content-Type": "application/octet-stream"
                })
            else:
                return {"error": "File not found"}, 404

        # Если это обычный HTTP/HTTPS запрос
        r = requests.get(url, timeout=10)
        return Response(r.content, status=r.status_code, headers={
            "Access-Control-Allow-Origin": "*",
            "Content-Type": r.headers.get("Content-Type", "application/octet-stream")
        })

    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
