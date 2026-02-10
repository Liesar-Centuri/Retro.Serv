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
from urllib.parse import unquote, urlparse
import html as html_escape


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
                    parts.append('</tr>')
                parts.append('</table>')
                # Small ES5-compatible script to enable in-place navigation of the legacy table
                parts.append('<script type="text/javascript">(function(){')
                parts.append('function ajaxGet(url,cb){var xhr=new XMLHttpRequest();xhr.open("GET",url,true);xhr.onreadystatechange=function(){if(xhr.readyState==4){if(xhr.status>=200&&xhr.status<300)cb(null,xhr.responseText);else cb(new Error("HTTP "+xhr.status));}};try{xhr.send(null);}catch(e){cb(e);}}')
                parts.append('function extractTable(html){var low=html.toLowerCase();var si=low.indexOf("<table");if(si===-1) return null;var ei=low.indexOf("</table>",si);if(ei===-1) return null;return html.substring(si,ei+8);}')
                parts.append('function loadTableFromUrl(url,pushHash){ajaxGet(url,function(err,txt){if(err) return;var tbl=extractTable(txt);if(!tbl) return;var old=document.getElementsByTagName("table")[0];if(old&&old.parentNode){var div=document.createElement("div");div.innerHTML=tbl;old.parentNode.replaceChild(div.firstChild,old);}});if(pushHash){try{window.location.hash=encodeURIComponent(url);}catch(e){}}}')
                parts.append('function onClick(e){e=e||window.event;var target=e.target||e.srcElement;while(target&&target.nodeName==="#text")target=target.parentNode;while(target&&target.nodeName!=="A")target=target.parentNode;if(!target) return;var href=target.getAttribute("href")||"";')
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

    # Allow address reuse to avoid "address already in use" on quick restarts
    class ReuseTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

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
