import os
import re
import socket
import traceback
from datetime import datetime
from threading import Thread
from typing import Tuple

import settings
from henango.http.request import HTTPRequest
from henango.http.response import HTTPResponse
from henango.urls.resolver import URLResolver

class Worker(Thread):

    # 拡張子とMIME Typeの対応
    MIME_TYPES = {
        "html": "text/html; charset=UTF-8",
        "css": "text/css",
        "png": "image/png",
        "jpg": "image/jpg",
        "gif": "image/gif",
    }
    
    # ステータスコードとステータスラインの対応
    STATUS_LINES = {
        200: "200 OK",
        404: "404 Not Found",
        405: "405 Method Not Allowd",
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
            request_bytes = self.client_socket.recv(4096)

            # クライアントから送られてきたデータをファイルに書き出す
            with open("server_recv.txt", "wb") as f:
                f.write(request_bytes)

            # HTTPリクエストをパースする
            request = self.parse_http_request(request_bytes)

            # URL解決を試みる
            view = URLResolver().resolve(request)

            # レスポンスを生成する
            response = view(request)

            # レスポンスラインを生成
            response_line = self.build_response_line(response)
            
            response_header = self.build_response_header(response, request)

            # レスポンス全体を生成する
            response_bytes = (response_line + response_header + "\r\n").encode() +  response.body

            # クライアントへレスポンスを送信する
            self.client_socket.send(response_bytes)
        
        except Exception:
            # リクエストの処理中に例外が発生したらコンソールにエラーを表示し、処理を続行
            print("=== Worker: リクエストの処理中にエラーが発生しました ===")
            traceback.print_exc()

        finally:
            # 例外の発生有無に関わらずTCP通信をclose
            print(f"=== Worker: クライアントとの接続を終了します remote_address: {self.client_address} ===")
            self.client_socket.close()

    def parse_http_request(self, request: bytes) -> HTTPRequest:
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

        return HTTPRequest(method=method, path=path, http_version=http_version, headers=headers, body=request_body)
    
    def get_static_file_content(self, path: str) -> bytes:
        """
        リクエストpathから、staticファイルの内容を取得する
        """
        default_static_root = os.path.join(os.path.dirname(__file__), "../../static")
        static_root = getattr(settings, "STATIC_ROOT", default_static_root)

        # pathの先頭の/を削除し、相対パスにしておく
        relative_path = path.lstrip("/")
        # ファイルのpathを取得
        static_file_path = os.path.join(static_root, relative_path)

        # ファイルからレスポンスボティを生成
        with open(static_file_path, "rb") as f:
            return f.read()
        
    def build_response_line(self, response: HTTPResponse) -> str:
        """
        レスポンスラインを構築する
        """
        status_line = self.STATUS_LINES[response.status_code]
        return f"HTTP/1.1 {status_line}"
    
    def build_response_header(self, response: HTTPResponse, request: HTTPRequest) -> str:
        """
        レスポンスヘッダを構築する
        """

        # Coontent_Typeが指定されていない場合はpathから特定する
        if response.content_type is None:
            # pathから拡張子を取得
            if "." in request.path:
                ext = request.path.rsplit(".", maxsplit=1)[-1]
            else:
                ext = ""
            # 拡張子からMIME Typeを取得
            # 知らない・対応していない拡張子の場合はoctet-streamとする
            response.content_type = self.MIME_TYPES.get(ext, "application/octet-stream")

        # レスポンスヘッダを生成
        response_header = ""
        response_header += f"Date: {datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n"
        response_header += "HOST: SigmaServer/0.1\r\n"
        response_header += f"Content-Length: {len(response.body)}\r\n"
        response_header += "Connection: Close\r\n"
        response_header += f"Content-Type: {response.content_type}\r\n"

        return response_header
    