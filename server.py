#!/usr/bin/env python3
"""
Simple static file server using Python standard library.
- Serves files from the script directory (d:\\Webserver)
- Redirects root ("/") to FilePage.html if present
- Provides directory listings (including Applications/)
"""
import argparse
import http.server
import socketserver
import os
import sys
from urllib.parse import unquote, urlparse, unquote_plus, parse_qs
import html as html_escape
import shutil


# script directory is the webserver root (HTML/JS/CSS served from here)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

# mount prefix to expose the browse directory (what the FilePage table will request)
MOUNT_PREFIX = '/Applications/'
# filesystem directory exposed under MOUNT_PREFIX (set from CLI)
BROWSE_DIR = None


class Handler(http.server.SimpleHTTPRequestHandler):
    # Force the server to use HTTP/1.0 (rather than HTTP/1.1)
    protocol_version = "HTTP/1.0"
    def end_headers(self):
        # Ensure connection is closed (HTTP/1.0 friendly)
        try:
            self.send_header('Connection', 'close')
        except Exception:
            pass
        super().end_headers()
    def do_GET(self):
        # If the User-Agent looks unknown (not a common browser token), redirect to legacy listing.
        ua = self.headers.get('User-Agent', '') or ''
        ua_l = ua.lower()
        known_tokens = ('mozilla', 'chrome', 'safari', 'opera', 'edge', 'msie', 'trident')
        is_known = any(tok in ua_l for tok in known_tokens)
        # don't redirect for requests already targeting legacy or browse-info or mounted files
        if (not is_known) and (not self.path.startswith('/legacy')) and (not self.path.startswith('/browse-info')):
            # Redirect unknown agents to the legacy plain HTML listing
            self.send_response(302)
            self.send_header('Location', '/legacy/')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        # Provide browse info endpoint for the client
        if self.path.startswith('/browse-info'):
            info = {
                'mount': MOUNT_PREFIX,
                'browse_dir': BROWSE_DIR or '',
                'name': os.path.basename(BROWSE_DIR) if BROWSE_DIR else MOUNT_PREFIX.strip('/')
            }
            data = (bytes(__import__('json').dumps(info), 'utf-8'))
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        # Legacy plain HTML listing for very old browsers (no JS)
        if self.path.startswith('/legacy'):
            # map path after /legacy to the browse directory
            parsed = urlparse(self.path)
            rel = parsed.path[len('/legacy'):]
            if rel.startswith('/'):
                rel = rel[1:]
            rel = unquote(rel)
            target = BROWSE_DIR or SCRIPT_DIR
            full = os.path.join(target, rel) if rel else target
            if os.path.isdir(full):
                entries = sorted(os.listdir(full))
                parts = []
                # Emit a minimal, legacy-friendly HTML document containing ONLY the table
                parts.append('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">')
                parts.append('<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"></head><body>')
                # simple table for legacy browsers: Name | Type | Size | Link
                # Use inline styles and per-row bgcolor to maximize compatibility with old browsers
                parts.append('<table border="0" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;border:4px solid #000;">')
                parts.append('<tr style="background:#ffcc00;">')
                parts.append('<th style="padding:10px;border:3px solid #000;font-family:Courier, monospace;">Name</th>')
                parts.append('<th style="padding:10px;border:3px solid #000;font-family:Courier, monospace;">Type</th>')
                parts.append('<th style="padding:10px;border:3px solid #000;font-family:Courier, monospace;">Size</th>')
                parts.append('<th style="padding:10px;border:3px solid #000;font-family:Courier, monospace;">Link</th>')
                parts.append('<th style="padding:10px;border:3px solid #000;font-family:Courier, monospace;">Download</th>')
                parts.append('<th style="padding:10px;border:3px solid #000;font-family:Courier, monospace;">Delete</th>')
                parts.append('</tr>')
                # Add a Back row to navigate one level up (keeps table-only output)
                if rel:
                    parent_rel = '/'.join([seg for seg in rel.split('/') if seg][:-1])
                    parent_href = ('/legacy/' + parent_rel) if parent_rel else '/legacy/'
                    parts.append(f'<tr style="background:#fff"><td colspan="5" style="padding:10px;border:2px solid #000;text-align:left">')
                    parts.append(f'<a href="{html_escape.escape(parent_href)}" style="display:inline-block;padding:6px 10px;background:#ffcc00;border:2px solid #c68f00;color:#000;text-decoration:none;font-weight:bold;border-radius:6px;">\u2190 Back</a>')
                    parts.append('</td></tr>')
                for idx, e in enumerate(entries):
                    href = (rel + '/' + e) if rel else e
                    fs_path = os.path.join(full, e)
                    is_dir = os.path.isdir(fs_path)
                    # compute size for files
                    try:
                        size = os.path.getsize(fs_path) if not is_dir else None
                    except Exception:
                        size = None
                    size_display = str(size) if size is not None else '-'
                    # alternate row background
                    row_bg = '#fff' if (idx % 2 == 0) else '#fffbde'
                    # link and labels
                    if is_dir:
                        link_href = '/legacy/' + href
                        type_label = 'Directory'
                        link_html = f'<a href="{html_escape.escape(link_href)}" style="color:#0000ff;">Open</a>'
                        download_html = '&nbsp;'
                    else:
                        mount_href = MOUNT_PREFIX + href
                        type_label = 'File'
                        link_html = f'<a href="{html_escape.escape(mount_href)}" style="color:#0000ff;">Open</a>'
                        # download styled as yellow button
                        download_html = f'<a href="{html_escape.escape(mount_href)}" style="display:inline-block;padding:6px 12px;background:#ffcc00;border:2px solid #c68f00;color:#000;text-decoration:none;font-weight:bold;border-radius:6px;">Download</a>'
                    # compute delete link (mount path for both files and directories)
                    mount_href = MOUNT_PREFIX + href
                    parts.append(f'<tr style="background:{row_bg};">')
                    # Name column: make it a link so clicking the name behaves like the modern view
                    if is_dir:
                        display_name = e + '/'
                        name_href = '/legacy/' + href
                    else:
                        display_name = e
                        name_href = MOUNT_PREFIX + href
                    name_html = f'<a href="{html_escape.escape(name_href)}" style="color:#0000ff">{html_escape.escape(display_name)}</a>'
                    parts.append(f'<td style="padding:12px;border:2px solid #000;font-family:Courier, monospace;">{name_html}</td>')
                    parts.append(f'<td style="padding:12px;border:2px solid #000;text-align:center">')
                    # small badge-like box for type
                    parts.append(f'<span style="display:inline-block;padding:4px 8px;border:2px solid #000;background:#fff;font-family:Courier, monospace;">{html_escape.escape(type_label)}</span>')
                    parts.append('</td>')
                    parts.append(f'<td style="padding:12px;border:2px solid #000;text-align:center">{html_escape.escape(size_display)}</td>')
                    parts.append(f'<td style="padding:12px;border:2px solid #000;text-align:center">{link_html}</td>')
                    parts.append(f'<td style="padding:12px;border:2px solid #000;text-align:center">{download_html}</td>')
                    # delete styled as red button, the script will intercept clicks and POST to /delete
                    delete_html = f'<a href="#" data-delete="{html_escape.escape(mount_href)}" style="display:inline-block;padding:6px 12px;background:#ff6666;border:2px solid #cc4444;color:#fff;text-decoration:none;font-weight:bold;border-radius:6px;">Delete</a>'
                    parts.append(f'<td style="padding:12px;border:2px solid #000;text-align:center">{delete_html}</td>')
                    parts.append('</tr>')
                parts.append('</table>')
                # Small ES5-compatible script to enable in-place navigation of the legacy table
                parts.append('<script type="text/javascript">(function(){')
                parts.append('function ajaxGet(url,cb){var xhr=new XMLHttpRequest();xhr.open("GET",url,true);xhr.onreadystatechange=function(){if(xhr.readyState==4){if(xhr.status>=200&&xhr.status<300)cb(null,xhr.responseText);else cb(new Error("HTTP "+xhr.status));}};try{xhr.send(null);}catch(e){cb(e);}}')
                parts.append('function ajaxPost(url,body,cb){var xhr=new XMLHttpRequest();xhr.open("POST",url,true);xhr.setRequestHeader("Content-Type","application/x-www-form-urlencoded");xhr.onreadystatechange=function(){if(xhr.readyState==4){if(xhr.status>=200&&xhr.status<300)cb(null,xhr.responseText);else cb(new Error("HTTP "+xhr.status));}};try{xhr.send(body);}catch(e){cb(e);}}')
                parts.append('function extractTable(html){var low=html.toLowerCase();var si=low.indexOf("<table");if(si===-1) return null;var ei=low.indexOf("</table>",si);if(ei===-1) return null;return html.substring(si,ei+8);}')
                parts.append('function loadTableFromUrl(url,pushHash){ajaxGet(url,function(err,txt){if(err) return;var tbl=extractTable(txt);if(!tbl) return;var old=document.getElementsByTagName("table")[0];if(old&&old.parentNode){var div=document.createElement("div");div.innerHTML=tbl;old.parentNode.replaceChild(div.firstChild,old);}});if(pushHash){try{window.location.hash=encodeURIComponent(url);}catch(e){}}}')
                parts.append("function onClick(e){e=e||window.event;var target=e.target||e.srcElement;while(target&&target.nodeName==='#text')target=target.parentNode;while(target&&target.nodeName!==\"A\")target=target.parentNode;if(!target) return;var href=target.getAttribute(\"href\")||\"\";var deletePath=target.getAttribute(\"data-delete\");if(deletePath){if(e.preventDefault)e.preventDefault();else e.returnValue=false; if(!confirm(\"Delete \" + deletePath + \"? This cannot be undone.\")) return; ajaxPost(\"/delete\",\"path=\"+encodeURIComponent(deletePath),function(err,txt){if(err){try{alert('Delete failed: '+err.message);}catch(e){}return;} var cur=window.location.pathname||'/legacy/'; loadTableFromUrl(cur,false);}); return;}")
                parts.append('if(href.indexOf("/legacy")==0){if(e.preventDefault)e.preventDefault();else e.returnValue=false;loadTableFromUrl(href,true);return;}')
                parts.append('if(href.indexOf("/Applications/")==0 || href.indexOf("/Files/")==0){try{if(e.preventDefault)e.preventDefault();else e.returnValue=false;window.open(href,"_blank");}catch(ex){}return;}')
                parts.append('if(window.addEventListener)window.addEventListener("click",onClick,false);else if(window.attachEvent)window.attachEvent("onclick",onClick);')
                parts.append('var onHash=function(){var h=window.location.hash;if(h&&h.length>1){var url=decodeURIComponent(h.substring(1));loadTableFromUrl(url,false);}};if(window.addEventListener)window.addEventListener("hashchange",onHash,false);else window.onhashchange=onHash;')
                parts.append('})();</script>')
                parts.append('</body></html>')
                body = '\n'.join(parts).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            # if not found, fall through to normal handler which will return 404
        # Redirect root to FilePage.html served from the script directory
        if self.path in ("/", "/index.html"):
            if os.path.exists(os.path.join(SCRIPT_DIR, "FilePage.html")):
                self.path = "/FilePage.html"
        return super().do_GET()

    def do_POST(self):
        """Handle uploads and directory creation.
        POST /upload -> multipart/form-data with fields: path (relative under mount), file (file field)
        POST /mkdir  -> form-encoded with fields: path, name
        """
        parsed = urlparse(self.path)
        if parsed.path == '/upload':
            # parse multipart form
            try:
                # Minimal multipart/form-data parser to avoid requiring the stdlib 'cgi'
                # module (some environments may not provide it). This reads the
                # request body according to Content-Length and splits on the
                # multipart boundary to extract parts.
                content_length = int(self.headers.get('Content-Length', '0'))
                content_type = self.headers.get('Content-Type', '')
                if not content_type.startswith('multipart/form-data'):
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'Expected multipart/form-data')
                    return
                # extract boundary
                import re
                m = re.search(r'boundary=(.+)', content_type)
                if not m:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'Missing multipart boundary')
                    return
                boundary = m.group(1)
                # strip optional quotes
                if boundary.startswith('"') and boundary.endswith('"'):
                    boundary = boundary[1:-1]
                boundary = boundary.encode('utf-8')

                body = b''
                remaining = content_length
                # read the full body
                while remaining > 0:
                    chunk = self.rfile.read(remaining)
                    if not chunk:
                        break
                    body += chunk
                    remaining -= len(chunk)

                delimiter = b'--' + boundary
                parts = body.split(delimiter)
                rel = ''
                filename = None
                file_bytes = None

                for part in parts:
                    if not part or part == b'--' or part == b'--\r\n':
                        continue
                    # strip leading CRLF
                    if part.startswith(b'\r\n'):
                        part = part[2:]
                    hdr_end = part.find(b'\r\n\r\n')
                    if hdr_end == -1:
                        continue
                    headers_block = part[:hdr_end].decode('utf-8', errors='replace')
                    content = part[hdr_end+4:]
                    # strip trailing CRLF
                    if content.endswith(b'\r\n'):
                        content = content[:-2]

                    # find content-disposition header
                    cd = None
                    for hline in headers_block.split('\r\n'):
                        if hline.lower().startswith('content-disposition:'):
                            cd = hline
                            break
                    if not cd:
                        continue
                    name_m = re.search(r'name="([^"]+)"', cd)
                    if not name_m:
                        continue
                    field_name = name_m.group(1)
                    fname_m = re.search(r'filename="([^"]*)"', cd)
                    if fname_m:
                        filename = os.path.basename(fname_m.group(1))
                        file_bytes = content
                    else:
                        value = content.decode('utf-8', errors='replace')
                        if field_name == 'path':
                            rel = value.strip()

                # basic validation
                if not filename or file_bytes is None:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'Missing file')
                    return

                # sanitize rel and resolve target dir
                rel = rel.lstrip('/')
                rel_parts = [p for p in rel.split('/') if p and p != '..']
                # If the client sent the mounted prefix (e.g. 'Applications/...'),
                # strip it so uploads go into the current directory being viewed
                # rather than creating an extra 'Applications' folder inside BROWSE_DIR.
                mount_root = MOUNT_PREFIX.strip('/')
                if rel_parts and rel_parts[0] == mount_root:
                    rel_parts = rel_parts[1:]
                target_dir = BROWSE_DIR or SCRIPT_DIR
                for p in rel_parts:
                    target_dir = os.path.join(target_dir, p)
                os.makedirs(target_dir, exist_ok=True)
                target_path = os.path.join(target_dir, filename)

                # write file bytes to disk (atomic write via temporary file could be added)
                with open(target_path, 'wb') as out:
                    out.write(file_bytes)

                resp = __import__('json').dumps({'status':'ok','path': '/' + '/'.join(rel_parts + [filename])})
                data = resp.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception as e:
                # Log server-side error to stderr to aid debugging (client also receives error text)
                try:
                    print("Error handling /upload:", repr(e), file=sys.stderr)
                except Exception:
                    pass
                self.send_response(500)
                self.end_headers()
                self.wfile.write(bytes(str(e), 'utf-8'))
                return
        elif parsed.path == '/mkdir':
            length = int(self.headers.get('Content-Length', '0'))
            body = self.rfile.read(length).decode('utf-8')
            # parse form-encoded body safely using parse_qs
            qs = parse_qs(body, keep_blank_values=True)
            # parse and percent-decode the submitted path (handle %20 -> space etc.)
            rel_raw = (qs.get('path', [''])[0] or '')
            # Robust decode: handle single- and double-encoded values by decoding up to 3 times
            rel = rel_raw
            try:
                for _ in range(3):
                    decoded = unquote_plus(rel)
                    if decoded == rel:
                        break
                    rel = decoded
            except Exception:
                # fallback to a single decode if something goes wrong
                try:
                    rel = unquote_plus(rel)
                except Exception:
                    pass
            rel = rel.lstrip('/')
            name = (qs.get('name', [''])[0] or '')
            if not name:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Missing name')
                return
            # sanitize
            rel_parts = [p for p in rel.split('/') if p and p != '..']
            # If the client sent the mounted prefix (e.g. 'Applications/...'), strip it so
            # we resolve paths relative to the mounted browse directory rather than
            # creating an extra 'Applications' folder inside BROWSE_DIR.
            mount_root = MOUNT_PREFIX.strip('/')
            if rel_parts and rel_parts[0] == mount_root:
                rel_parts = rel_parts[1:]
            target_dir = BROWSE_DIR or SCRIPT_DIR
            for p in rel_parts:
                target_dir = os.path.join(target_dir, p)
            new_dir = os.path.join(target_dir, name)
            try:
                os.makedirs(new_dir, exist_ok=True)
                resp = __import__('json').dumps({'status':'ok','path': '/' + '/'.join(rel_parts + [name])})
                data = resp.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception as e:
                # Log server-side error to stderr to aid debugging (client also receives error text)
                try:
                    print("Error handling /mkdir:", repr(e), file=sys.stderr)
                except Exception:
                    pass
                self.send_response(500)
                self.end_headers()
                self.wfile.write(bytes(str(e), 'utf-8'))
                return
        elif parsed.path == '/delete':
            # delete a file or directory. Expects form-encoded body: path=<mounted-path>&is_dir=1|0
            length = int(self.headers.get('Content-Length', '0'))
            body = self.rfile.read(length).decode('utf-8')
            # Debug: log incoming delete request body for diagnosis
            try:
                print("[DEBUG] /delete body:", repr(body), file=sys.stderr)
            except Exception:
                pass
            qs = parse_qs(body, keep_blank_values=True)
            rel_raw = (qs.get('path', [''])[0] or '')
            is_dir_flag = qs.get('is_dir', ['0'])[0]
            # Robust percent-decode: handle single- and double-encoded values (e.g. %2520 -> %20 -> space)
            def _decode_multi(s, rounds=3):
                try:
                    for _ in range(rounds):
                        s2 = unquote_plus(s)
                        if s2 == s:
                            break
                        s = s2
                except Exception:
                    try:
                        s = unquote_plus(s)
                    except Exception:
                        pass
                return s

            rel_decoded = _decode_multi(rel_raw)
            # strip leading slash and normalize
            rel_norm = rel_decoded.lstrip('/')
            # split and decode each path segment (defense-in-depth)
            rel_parts = [ _decode_multi(p) for p in rel_norm.split('/') if p and p != '..' ]
            try:
                print("[DEBUG] raw rel:", repr(rel_raw), "decoded:", repr(rel_decoded), "rel_parts:", rel_parts, file=sys.stderr)
            except Exception:
                pass
            mount_root = MOUNT_PREFIX.strip('/')
            if rel_parts and rel_parts[0] == mount_root:
                rel_parts = rel_parts[1:]
            target = BROWSE_DIR or SCRIPT_DIR
            for p in rel_parts:
                target = os.path.join(target, p)
            try:
                print("[DEBUG] resolved target:", target, "abs:", os.path.abspath(target), file=sys.stderr)
                print("[DEBUG] base:", BROWSE_DIR or SCRIPT_DIR, "abs base:", os.path.abspath(BROWSE_DIR or SCRIPT_DIR), file=sys.stderr)
                print("[DEBUG] exists:", os.path.exists(target), file=sys.stderr)
            except Exception:
                pass
            # Ensure target is within allowed base
            base = BROWSE_DIR or SCRIPT_DIR
            try:
                if os.path.commonpath([os.path.abspath(base), os.path.abspath(target)]) != os.path.abspath(base):
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b'Forbidden')
                    return
            except Exception:
                # fallback: deny
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b'Forbidden')
                return
            try:
                if not os.path.exists(target):
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'Not found')
                    return
                if os.path.isdir(target):
                    shutil.rmtree(target)
                else:
                    os.remove(target)
                resp = __import__('json').dumps({'status':'ok','path': '/' + '/'.join(rel_parts)})
                data = resp.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception as e:
                try:
                    print('Error handling /delete:', repr(e), file=sys.stderr)
                except Exception:
                    pass
                self.send_response(500)
                self.end_headers()
                self.wfile.write(bytes(str(e), 'utf-8'))
                return
        else:
            # fallback to default behavior
            return super().do_POST()

    def translate_path(self, path):
        """Map a URL path to a filesystem path.
        If the path begins with MOUNT_PREFIX, map it into BROWSE_DIR.
        Otherwise map into SCRIPT_DIR (webserver folder).
        """
        # strip query/fragment
        parsed = urlparse(path)
        path = parsed.path

        # If request targets the mounted browse prefix, map to BROWSE_DIR
        if BROWSE_DIR and path.startswith(MOUNT_PREFIX):
            rel = path[len(MOUNT_PREFIX):]
            rel = unquote(rel)
            parts = [p for p in rel.split('/') if p and p != '..']
            full = BROWSE_DIR
            for p in parts:
                full = os.path.join(full, p)
            # if path ends with '/', ensure it's returned as a directory path
            return full

        # Fallback: serve from script directory (SCRIPT_DIR)
        # Re-implement SimpleHTTPRequestHandler.translate_path behavior but rooted at SCRIPT_DIR
        path = unquote(parsed.path)
        path = path.split('?',1)[0].split('#',1)[0]
        parts = [p for p in path.split('/') if p and p != '..']
        full = SCRIPT_DIR
        for p in parts:
            full = os.path.join(full, p)
        return full


def run(port: int = 8000, browse_dir: str = None):
    global BROWSE_DIR
    if browse_dir:
        browse_dir = os.path.abspath(browse_dir)
        if not os.path.isdir(browse_dir):
            print(f"Error: browse directory does not exist: {browse_dir}")
            sys.exit(2)
        BROWSE_DIR = browse_dir

    # Allow address reuse and serve each request in its own thread so multiple clients
    # can download and interact concurrently.
    class ReuseTCPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        # Make worker threads daemon so they won't block shutdown
        daemon_threads = True

    with ReuseTCPServer(("", port), Handler) as httpd:
        sa = httpd.socket.getsockname()
        host = sa[0] if sa[0] else "0.0.0.0"
        serve_dir = SCRIPT_DIR
        print(f"Serving HTTP on {host} port {sa[1]} (http://localhost:{sa[1]}/) ...")
        print(f"Document root (HTML/JS/CSS): {serve_dir}")
        if BROWSE_DIR:
            print(f"Mounted browse directory {BROWSE_DIR} at {MOUNT_PREFIX}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received, exiting.")
            httpd.server_close()


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Simple static file server (stdlib only)")
    p.add_argument("port", nargs="?", type=int, default=8000, help="port to listen on (default: 8000)")
    p.add_argument("--browse-dir", "-b", dest="browse_dir", help="filesystem directory to expose under /Applications/")
    return p.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    run(port=args.port, browse_dir=args.browse_dir)
