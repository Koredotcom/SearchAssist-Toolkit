from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import cgi
import os

UPLOAD_DIR = "outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        ctype, pdict = cgi.parse_header(self.headers.get("Content-Type"))

        if ctype != "multipart/form-data":
            self.send_response(415)
            self.end_headers()
            self.wfile.write(b"Only file upload (multipart/form-data) is supported")
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST",
                     "CONTENT_TYPE": self.headers["Content-Type"]}
        )

        if "file" not in form:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing 'file' field in upload")
            return

        uploaded_file = form["file"]

        if not uploaded_file.filename:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Uploaded file has no filename")
            return

        try:
            file_content = uploaded_file.file.read().decode("utf-8")
            xo10_data = json.loads(file_content)
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Uploaded file must be valid JSON")
            return

        if "faqs" not in xo10_data:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing 'faqs' in uploaded JSON")
            return

        xo11_data = []
        for faq in xo10_data["faqs"]:
            source = faq.get("_source", {})
            question = source.get("faq_question", "")

            answer_text = ""
            for ans in source.get("faq_answer", []):
                if isinstance(ans, dict):
                    answer_text += ans.get("text", "") + " "

            cond_answer_texts = []
            for cond in source.get("faq_cond_answers", []):
                for ans in cond.get("answers", []):
                    if isinstance(ans, dict):
                        cond_text = ans.get("text", "")
                        if cond_text:
                            cond_answer_texts.append(cond_text)

            alt_questions = source.get("faq_alt_questions", [])
            if not isinstance(alt_questions, list):
                alt_questions = []

            res = {
                "chunkText": answer_text.strip(),
                "recordUrl": "faq",
                "chunkTitle": question,
            }

            if cond_answer_texts:
                res["cfa1"] = cond_answer_texts
            if alt_questions:
                res["cfa2"] = alt_questions

            xo11_data.append(res)

        base_name = os.path.splitext(uploaded_file.filename)[0]
        output_filename = f"{base_name}-converted.json"
        output_path = os.path.join(UPLOAD_DIR, output_filename)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(xo11_data, f, indent=2, ensure_ascii=False)

        host = self.headers.get(
            "Host",
            f"{self.server.server_address[0]}:{self.server.server_address[1]}"
        )
        url = f"http://{host}/{UPLOAD_DIR}/{output_filename}"

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"url": url}).encode("utf-8"))

    def do_GET(self):
        if self.path.startswith(f"/{UPLOAD_DIR}/"):
            filepath = self.path.lstrip("/")
            if os.path.exists(filepath):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                with open(filepath, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"File not found")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Invalid endpoint")

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 5000), SimpleHandler)
    print("Server running at http://localhost:5000")
    server.serve_forever()
