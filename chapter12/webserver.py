import os
import socket
import traceback
from datetime import datetime

class WebServer:
    """
    Webサーバを表すクラス
    """

    # 実行ファイルのあるディレクトリの指定
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # 静的配信するファイルを置くディレクトリ
    STATIC_ROOT = os.path.join(BASE_DIR, "static")

    MIME_TYPES = {
        "html": "text/html",
        "css": "text/css",
        "png": "image/png",
        "jpg": "image/jpg",
        "gif": "image/gif",
    }

    def serve(self):
        """
        サーバを起動する
        """

        print("=== サーバを起動します ===")

        try:
            # socketを生成
            server_socket = socket.socket()
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # socketをlocalhostのポート8080に紐付け
            server_socket.bind(("localhost", 8080))
            server_socket.listen(10)

            while True:
            
                # 外部からの接続を待ち、接続があったらコネクションを確立
                print("=== クライアントからの接続を待ちます ===")
                (client_socket, address) = server_socket.accept()
                print(f"=== クライアントとの接続が完了しました remote_address: {address} ===")

                try:
                
                    # クライアントから送られてきたデータを取得する
                    request = client_socket.recv(4096)

                    # クライアントから送られてきたデータをファイルに書き出す
                    with open("server_recv.txt", "wb") as f:
                        f.write(request)

                    # リクエスト全体を
                    # 1. リクエストライン
                    # 2. リクエストヘッダ
                    # 3. リクエストボディ
                    # に分けてパースする
                    request_line, remain = request.split(b"\r\n", maxsplit=1)
                    request_header, request_body = remain.split(b"\r\n\r\n", maxsplit=1)

                    # さらにリクエストラインをパースする
                    method, path, http_version = request_line.decode().split(" ")
                    
                    # pathの先頭の/を削除し、相対パスにしておく
                    relative_path = path.lstrip("/")
                    # ファイルのpathを取得
                    static_file_path = os.path.join(self.STATIC_ROOT, relative_path)

                    # ファイルからレスポンスボティを生成
                    try:
                        with open(static_file_path, "rb") as f:
                            response_body = f.read()

                        # レスポンラインを生成
                        response_line = "HTTP/1.1 200 OK\r\n"

                    except OSError:
                        # ファイルが見つからなかった場合は404を返す
                        response_body = b"<html><body><h1>404 Not Found</h1></body></html>"
                        response_line = "HTTP/1.1 404 Not Found\r\n"

                    # ヘッダ生成のためにContent-Typeを取得しておく
                    # pathから拡張子を取得
                    if "." in path:
                        ext = path.rsplit(".", maxsplit = 1)[-1]
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

                    # ヘッダとボディを空行でくっつけた上でbytesに変換し、レスポンス全体を生成する
                    response = (response_line + response_header + "\r\n").encode() +  response_body

                    # クライアントへレスポンスを送信する
                    client_socket.send(response)

                except Exception:
                    # リクエストの処理中に例外が発生した場合はコンソールにエラーを出し、処理を続行する
                    print("=== リクエストの処理中にエラーが発生しました ===")
                    traceback.print_exc()
                
                finally:
                    # 例外の発生有無に関わらずTCP通信をcloseする
                    client_socket.close()

        finally:
            print("=== サーバを停止します ===")


if __name__ == '__main__':
    server = WebServer()
    server.serve()