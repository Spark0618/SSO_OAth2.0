import http.server
import ssl
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Simple HTTPS Server")
    parser.add_argument(
        "--ssl-cert", 
        required=True,
        help="Path to SSL certificate file (.crt or .pem)"
    )
    parser.add_argument(
        "--ssl-key",
        required=True,
        help="Path to SSL private key file (.key or .pem)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=4173,
        help="Port to listen on (default: 4173)"
    )

    args = parser.parse_args()

    # 设置 handler（默认提供静态文件服务）
    handler = http.server.SimpleHTTPRequestHandler
    httpd = http.server.HTTPServer(("localhost", args.port), handler)

    # 创建 SSL 上下文
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=args.ssl_cert, keyfile=args.ssl_key)

    # 启用 HTTPS
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    print(f"Serving HTTPS on https://localhost:{args.port}")
    print(f"Using cert: {args.ssl_cert}")
    print(f"Using key : {args.ssl_key}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
