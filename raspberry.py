

import io
import logging
import socketserver
from threading import Condition
from http import server
import picamera

PAGE = """
<html>
<head>
<title>Raspberry Pi IP Camera</title>
</head>
<body>
<h1>Live Stream</h1>
<img src="stream.mjpg" width="{width}" height="{height}" />
</body>
</html>
"""

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.format(width=WIDTH, height=HEIGHT).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning('Streaming client disconnected: %s', str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == '__main__':
    WIDTH, HEIGHT, FRAMERATE = 1280, 720, 24
    PORT = 8000

    with picamera.PiCamera(resolution=f'{WIDTH}x{HEIGHT}', framerate=FRAMERATE) as camera:
        output = StreamingOutput()
        camera.start_recording(output, format='mjpeg')
        try:
            address = ('', PORT)
            server = StreamingServer(address, StreamingHandler)
            print(f'Streaming on http://<Raspberry Pi IP>:{PORT}')
            server.serve_forever()
        finally:
            camera.stop_recording()
