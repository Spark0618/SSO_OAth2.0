import argparse
import hashlib
import http.server
import ssl
import sys
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urljoin, urlparse


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
    parser.add_argument(
        "--client-ca",
        help="Path to client CA for mTLS (enables mutual TLS verification if provided)"
    )
    parser.add_argument(
        "--require-client-cert",
        action="store_true",
        help="Require client certificate (implies --client-ca)"
    )
    parser.add_argument(
        "--upstream",
        help="If set, acts as a tiny reverse proxy to this upstream (e.g. https://auth.localhost:5000) and injects client fingerprint header"
    )
    parser.add_argument(
        "--proxy-prefix",
        default="/",
        help="Only proxy paths starting with this prefix (default: '/' means proxy all when --upstream is set)"
    )
    parser.add_argument(
        "--proxy-exclude",
        default="",
        help="Comma-separated path whitelist that will NOT be proxied (e.g. '/academic.html,/favicon.ico')"
    )
    parser.add_argument(
        "--insecure-upstream",
        action="store_true",
        help="Skip upstream TLS verification (for self-signed lab certs)"
    )

    args = parser.parse_args()
    exclude_paths = {p.strip() for p in args.proxy_exclude.split(",") if p.strip()}

    # 设置 handler（默认提供静态文件服务）
    class TLSRequestHandler(http.server.SimpleHTTPRequestHandler):
        """扩展 handler，记录并打印客户端证书指纹，支持简单反向代理注入指纹。"""

        def setup(self):
            super().setup()
            self.client_fingerprint = None
            try:
                cert_bin = self.connection.getpeercert(binary_form=True)
                if cert_bin:
                    self.client_fingerprint = hashlib.sha256(cert_bin).hexdigest()
            except ssl.SSLError:
                # 握手失败会被上层断开，这里不再处理
                pass

        def log_message(self, fmt, *args):
            suffix = f" fp={self.client_fingerprint}" if self.client_fingerprint else ""
            sys.stderr.write("%s - - [%s] %s%s\n" % (
                self.client_address[0],
                self.log_date_time_string(),
                fmt % args,
                suffix,
            ))

        def _proxy_request(self):
            if not args.upstream:
                return False
            if exclude_paths and self.path.split("?", 1)[0] in exclude_paths:
                return False
            # 仅当请求路径匹配前缀时才代理，其余仍走本地静态文件
            if args.proxy_prefix and not self.path.startswith(args.proxy_prefix):
                return False

            parsed = urlparse(args.upstream)
            scheme = parsed.scheme or "http"
            upstream_host = parsed.hostname
            upstream_port = parsed.port or (443 if scheme == "https" else 80)
            target_path = urljoin(parsed.path or "/", self.path)

            # 复制请求头
            headers = {k: v for k, v in self.headers.items()}
            headers["Host"] = parsed.netloc
            if self.client_fingerprint:
                headers["X-Client-Cert-Fingerprint"] = self.client_fingerprint

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length else None

            if scheme == "https":
                if args.insecure_upstream:
                    ctx = ssl._create_unverified_context()
                else:
                    ctx = ssl.create_default_context()
                conn = HTTPSConnection(upstream_host, upstream_port, context=ctx)
            else:
                conn = HTTPConnection(upstream_host, upstream_port)

            conn.request(self.command, target_path, body=body, headers=headers)
            resp = conn.getresponse()
            resp_body = resp.read()

            self.send_response(resp.status, resp.reason)
            # 过滤 hop-by-hop 头
            hop_by_hop = {"Connection", "Keep-Alive", "Proxy-Authenticate", "Proxy-Authorization", "TE", "Trailers", "Transfer-Encoding", "Upgrade"}
            for k, v in resp.getheaders():
                if k in hop_by_hop:
                    continue
                self.send_header(k, v)
            self.end_headers()
            if resp_body:
                self.wfile.write(resp_body)
            conn.close()
            return True

        def do_GET(self):
            if self._proxy_request():
                return
            super().do_GET()

        def do_POST(self):
            if self._proxy_request():
                return
            super().do_POST()

        def do_PUT(self):
            if self._proxy_request():
                return
            super().do_PUT()

        def do_DELETE(self):
            if self._proxy_request():
                return
            super().do_DELETE()

        def do_OPTIONS(self):
            if self._proxy_request():
                return
            super().do_OPTIONS()

    httpd = http.server.HTTPServer(("localhost", args.port), TLSRequestHandler)

    # 创建 SSL 上下文
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=args.ssl_cert, keyfile=args.ssl_key)
    if args.client_ca:
        context.load_verify_locations(cafile=args.client_ca)
    if args.client_ca or args.require_client_cert:
        # 启用客户端证书校验（双向认证）
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = False  # 只校验证书链，不检查主机名

    # 启用 HTTPS
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    print(f"Serving HTTPS on https://localhost:{args.port}")
    print(f"Using cert: {args.ssl_cert}")
    print(f"Using key : {args.ssl_key}")
    if context.verify_mode == ssl.CERT_REQUIRED:
        print("mTLS: client certificate is REQUIRED")
        if args.client_ca:
            print(f"Trusted client CA: {args.client_ca}")
        else:
            print("Trusted client CA: system default")
    else:
        print("mTLS: client certificate is NOT required (one-way TLS)")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
