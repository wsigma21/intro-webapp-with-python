import os
import re
import textwrap
import socket
import traceback
import urllib.parse
from datetime import datetime
from pprint import pformat
from threading import Thread
from typing import Tuple, Optional

class WorkerThread(Thread):
    
    # 実行ファイルのあるディレクトリの指定
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # 静的配信するファイルを置くディレクトリ
    STATIC_ROOT = os.path.join(BASE_DIR, "static")

    MIME_TYPES = {
        "html": "text/html; charset=UTF-8",
        "css": "text/css",
        "png": "image/png",
        "jpg": "image/jpg",
        "gif": "image/gif",
    }
    
    def __init__(self, client_socket: socket, address: Tuple[str, int]):
        # Threadを継承
        super().__init__()

        # インスタンス変数に引数を代入
        self.client_socket = client_socket
        self.client_address = address

    def run(self) -> None:
        """
        クライアントと接続済みのsocketを引数として受け取り、
        リクエストを処理してレスポンスを送信する
        """

        try:
            # クライアントから送られてきたデータを取得する
            request = self.client_socket.recv(4096)

            # クライアントから送られてきたデータをファイルに書き出す
            with open("server_recv.txt", "wb") as f:
                f.write(request)

            # HTTPリクエストをパースする
            method, path, http_version, request_header, request_body = self.parse_http_request(request)

            # 型注釈
            response_body: bytes
            content_type: Optional[str]
            response_line: str
            # pathが/nowの時は、現在時刻を表示するHTMLを生成する
            if path == "/now":
                html = f"""\
                    <html>
                    <body>
                        <h1>Now: {datetime.now()}</h1>
                    </body>
                    </html>
                """
                response_body = textwrap.dedent(html).encode()

                # Content-Typeを指定
                content_type = "text/html; charset=UTF-8"

                # レスポンスラインを生成
                response_line = "HTTP/1.1 200 OK\r\n"

            # pathが/show_requestのときは、HTTPリクエストの内容を表示するHTMLを生成する
            elif path == "/show_request":
                html = f"""\
                    <html>
                    <body>
                        <h1>Request Line:</h1>
                        <p>
                            {method} {path} {http_version}
                        </p>
                        <h1>Headers:</h1>
                        <pre>{pformat(request_header)}</pre>
                        <h1>Body:</h1>
                        <pre>{request_body.decode("utf-8", "ignore")}</pre>
                    </body>
                    </html>
                """
                response_body = textwrap.dedent(html).encode()

                # Content-Typeを指定
                content_type = "text/html; charset=UTF-8"

                # レスポンスラインを生成
                response_line = "HTTP/1.1 200 OK\r\n"

            elif path == "/parameters":
                if method == "GET":
                    response_body = b"<html><body><h1>405 Method Not Allowed</h1></body></html>"
                    content_type = "text/html; charset=UTF-8"
                    response_line = "http/1.1 405 Method Not Allowed\r\n"
                
                elif method == "POST":
                    post_params = urllib.parse.parse_qs(request_body.decode())
                    html = f"""\
                        <html>
                        <body>
                            <h1>Parameters:</h1>
                            <pre>{pformat(post_params)}</pre>
                        </body>
                        </html>
                    """
                    response_body = textwrap.dedent(html).encode()

                    # Content-Typeを指定
                    content_type = "text/html; charset=UTF-8"

                    # レスポンスラインを生成
                    response_line = "HTTP/1.1 200 OK\r\n"
                
            # pathがそれ以外の時は、静的ファイルからレスポンスを生成する
            else:
                try:
                    # ファイルからレスポンスボティを生成
                    response_body = self.get_static_file_content(path)

                    # Content-Typeを指定
                    content_type = None

                    # レスポンラインを生成
                    response_line = "HTTP/1.1 200 OK\r\n"

                except OSError:
                    # ファイルが見つからなかった場合は、ログを出力してから404を返す
                    traceback.print_exc()

                    response_body = b"<html><body><h1>404 Not Found</h1></body></html>"
                    content_type = "text/html; charset=UTF-8"
                    response_line = "HTTP/1.1 404 Not Found\r\n"

            # レスポンスヘッダを生成
            response_header = self.build_response_header(path, response_body, content_type)

            # レスポンス全体を生成する
            response = (response_line + response_header + "\r\n").encode() +  response_body

            # クライアントへレスポンスを送信する
            self.client_socket.send(response)
        
        except Exception:
            # リクエストの処理中に例外が発生したらコンソールにエラーを表示し、処理を続行
            print("=== Worker: リクエストの処理中にエラーが発生しました ===")
            traceback.print_exc()

        finally:
            # 例外の発生有無に関わらずTCP通信をclose
            print(f"=== Worker: クライアントとの接続を終了します remote_address: {self.client_address} ===")
            self.client_socket.close()

    def parse_http_request(self, request: bytes) -> Tuple[str, str, str, dict, bytes]:
        """
        HTTPリクエストを
        1. method: str
        2. path: str
        3. http_version: str
        4. request_header: dict
        5. request_body: bytes
        に分割/変換して返す
        """

        # リクエスト全体を
        # 1. リクエストライン
        # 2. リクエストヘッダ
        # 3. リクエストボディ
        # に分けてパースする
        request_line, remain = request.split(b"\r\n", maxsplit=1)
        request_header, request_body = remain.split(b"\r\n\r\n", maxsplit=1)

        # さらにリクエストラインをパースする
        method, path, http_version = request_line.decode().split(" ")

        # リクエストヘッダを辞書にパースする
        headers = {}
        for header_row in request_header.decode().split("\r\n"):
            key, value = re.split(r": *", header_row, maxsplit=1)
            headers[key] = value

        return method, path, http_version, headers, request_body
    
    def get_static_file_content(self, path: str) -> bytes:
        """
        リクエストpathから、staticファイルの内容を取得する
        """

        # pathの先頭の/を削除し、相対パスにしておく
        relative_path = path.lstrip("/")
        # ファイルのpathを取得
        static_file_path = os.path.join(self.STATIC_ROOT, relative_path)

        # ファイルからレスポンスボティを生成
        with open(static_file_path, "rb") as f:
            return f.read()
    
    def build_response_header(self, path: str, response_body: bytes, content_type: Optional[str]) -> str:
        """
        レスポンスヘッダを構築する
        """

        # Coontent_Typeが指定されていない場合はpathから特定する
        if content_type is None:
            # pathから拡張子を取得
            if "." in path:
                ext = path.rsplit(".", maxsplit=1)[-1]
            else:
                ext = ""
            # 拡張子からMIME Typeを取得
            # 知らない・対応していない拡張子の場合はoctet-streamとする
            content_type = self.MIME_TYPES.get(ext, "application/octet-stream")

        # レスポンスヘッダを生成
        response_header = ""
        response_header += f"Date: {datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n"
        response_header += "HOST: SigmaServer/0.1\r\n"
        response_header += f"Content-Length: {len(response_body)}\r\n"
        response_header += "Connection: Close\r\n"
        response_header += f"Content-Type: {content_type}\r\n"

        return response_header