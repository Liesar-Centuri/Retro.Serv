(function(){
  // Modern file-listing logic (uses fetch, DOMParser, async/await)
  const BASE = '/Applications/';
  let currentPath = BASE; // current browsing path (always ends with '/')
  const statusEl = document.getElementById('status');
  const table = document.getElementById('files-table');
  const tbody = document.getElementById('files-body');
  const filterInput = document.getElementById('filter');
  const refreshBtn = document.getElementById('refresh');
  const backBtn = document.getElementById('back');
  const browsingEl = document.getElementById('browsing-path');
  const uploadInput = document.getElementById('upload-file');
  const uploadBtn = document.getElementById('upload-btn');
  const uploadCancelBtn = document.getElementById('upload-cancel');
  const mkdirBtn = document.getElementById('mkdir-btn');

  function normalizePath(p){
    if(!p) return '/';
    // ensure leading slash and trailing slash
    let u = p;
    if(!u.startsWith('/')) u = '/' + u;
    if(!u.endsWith('/')) u = u + '/';
    return u;
  }

  function setPath(p){
    currentPath = normalizePath(p);
  if(browsingEl) browsingEl.textContent = currentPath;
    // enable/disable back button (do not go above BASE)
    backBtn.disabled = (currentPath === normalizePath(BASE));
  }

  async function loadList(path){
    setPath(path || currentPath);
    statusEl.textContent = 'Loading...';
    table.style.display = 'none';
    tbody.innerHTML = '';
    try{
      const res = await fetch(currentPath);
      if(!res.ok) throw new Error('HTTP ' + res.status);
      const text = await res.text();
      const doc = new DOMParser().parseFromString(text,'text/html');
      let anchors = [];
      const pre = doc.querySelector('pre');
      if(pre) anchors = Array.from(pre.querySelectorAll('a'));
      else anchors = Array.from(doc.querySelectorAll('a'));
      anchors = anchors.filter(a => a.getAttribute('href') !== '../');

      if(anchors.length === 0){
        statusEl.textContent = 'No files or directories found in /Applications/';
        return;
      }

      const rows = anchors.map(a => {
        const rawHref = a.getAttribute('href');
        const name = a.textContent || rawHref;
        const isDir = rawHref.endsWith('/');
        const absUrl = new URL(rawHref, location.origin + currentPath).href;
        const absPath = new URL(rawHref, location.origin + currentPath).pathname;
        return {name, isDir, url: absUrl, path: absPath, rawHref};
      });

      rows.sort((x,y)=> (x.isDir === y.isDir) ? x.name.localeCompare(y.name) : (x.isDir? -1:1));

      for(const row of rows){
        const tr = document.createElement('tr');
        const nameTd = document.createElement('td');
        const typeTd = document.createElement('td');
        const sizeTd = document.createElement('td');
        sizeTd.className = 'size-cell';
        const linkTd = document.createElement('td');
        const downloadTd = document.createElement('td');

        const link = document.createElement('a');
        link.className = 'file-link';
        link.textContent = row.name;
        link.href = row.url;
        if(row.isDir){
          link.href = '#';
          link.addEventListener('click', (e)=>{
            e.preventDefault();
            loadList(row.path);
          });
        } else {
          link.target = '_blank';
        }

  nameTd.appendChild(link);
  typeTd.innerHTML = row.isDir ? '<span class="type-badge">Directory</span>' : '<span class="type-badge" style="background:#f0fdfa;color:#047857">File</span>';
  sizeTd.textContent = row.isDir ? '-' : '...';
        if(row.isDir){
          linkTd.innerHTML = `<a href="#" data-path="${row.path}">Open</a>`;
          linkTd.querySelector('a').addEventListener('click', (e)=>{ e.preventDefault(); loadList(row.path); });
        } else {
          linkTd.innerHTML = `<a href="${row.url}" target="_blank">Open</a>`;
        }

        const dlBtn = document.createElement('button');
        dlBtn.textContent = 'Download';
        dlBtn.style.padding = '6px 10px';
        dlBtn.style.borderRadius = '6px';
        dlBtn.style.cursor = 'pointer';
        if(row.isDir){
          dlBtn.disabled = true;
          dlBtn.title = 'Cannot download a directory';
        } else {
          dlBtn.addEventListener('click', (e)=>{
            e.preventDefault();
            downloadFile(row.url, row.name);
          });
        }
        downloadTd.appendChild(dlBtn);

        // Delete button
        const deleteTd = document.createElement('td');
        const delBtn = document.createElement('button');
        delBtn.textContent = 'Delete';
        delBtn.style.padding = '6px 10px';
        delBtn.style.borderRadius = '6px';
        delBtn.style.cursor = 'pointer';
        delBtn.style.background = '#ff6666';
        delBtn.style.color = '#fff';
        if(row.name === '..'){
          delBtn.disabled = true;
        } else {
          delBtn.addEventListener('click', async (e)=>{
            e.preventDefault();
            const pretty = row.name + (row.isDir ? ' (directory)' : '');
            const ok = confirm('Delete ' + pretty + '? This cannot be undone.');
            if(!ok) return;
            try{
              statusEl.style.display=''; statusEl.textContent='Deleting...';
              const body = 'path=' + encodeURIComponent(row.path) + '&is_dir=' + (row.isDir? '1':'0');
              const res = await fetch('/delete', { method: 'POST', headers: {'Content-Type':'application/x-www-form-urlencoded'}, body });
              if(!res.ok) throw new Error('HTTP ' + res.status);
              const j = await res.json();
              statusEl.style.display='none';
              loadList(currentPath);
            }catch(err){
              statusEl.textContent = 'Delete failed: ' + err.message;
            }
          });
        }
        deleteTd.appendChild(delBtn);

        tr.appendChild(nameTd);
        tr.appendChild(typeTd);
        tr.appendChild(sizeTd);
        tr.appendChild(linkTd);
        tr.appendChild(downloadTd);
  tr.appendChild(deleteTd);
        tbody.appendChild(tr);

        // fetch file size for files using HEAD (async, best-effort)
        if(!row.isDir){
          (async function(cell, url){
            try{
              const r = await fetch(url, { method: 'HEAD' });
              if(r && r.ok){
                const len = r.headers.get('content-length');
                if(len && !isNaN(len)){
                  cell.textContent = formatBytes(parseInt(len,10));
                } else {
                  cell.textContent = '-';
                }
              } else {
                cell.textContent = '-';
              }
            }catch(e){
              try{
                // fallback: try GET to read headers (may transfer body)
                const r2 = await fetch(url);
                const len2 = r2.headers.get('content-length');
                if(len2 && !isNaN(len2)) cell.textContent = formatBytes(parseInt(len2,10));
                else cell.textContent = '-';
              }catch(_) { cell.textContent = '-'; }
            }
          })(sizeTd, row.url);
        }
      }

  // Ensure the browsing footer reflects the canonical current path
  try{ setPath(currentPath); }catch(e){}
  statusEl.style.display = 'none';
  table.style.display = '';
      applyFilter();
    }catch(err){
      statusEl.textContent = 'Failed to load /Applications/: ' + err.message + '.\nMake sure the server is running and /Applications/ exists.';
    }
  }

  function applyFilter(){
    const q = (filterInput.value || '').toLowerCase();
    Array.from(tbody.querySelectorAll('tr')).forEach(tr=>{
      const name = tr.querySelector('a.file-link').textContent.toLowerCase();
      tr.style.display = name.includes(q) ? '' : 'none';
    });
  }

  async function downloadFile(url, name){
    try{
      statusEl.style.display = '';
      statusEl.textContent = 'Downloading ' + name + ' ...';
      const res = await fetch(url);
      if(!res.ok) throw new Error('HTTP ' + res.status);
      const blob = await res.blob();
      const filename = name.replace(/\/$/,'');
      const objUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objUrl;
      a.download = filename || 'download';
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(()=> URL.revokeObjectURL(objUrl), 5000);
      statusEl.style.display = 'none';
    }catch(err){
      statusEl.textContent = 'Download failed: ' + err.message;
      console.error('download error', err);
    }
  }

  function formatBytes(bytes){
    if(!bytes || bytes === 0) return '0 B';
    const units = ['B','KB','MB','GB','TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    const v = bytes / Math.pow(1024, i);
    return (i === 0) ? bytes + ' B' : v.toFixed(1) + ' ' + units[i];
  }

  filterInput.addEventListener('input', applyFilter);
  refreshBtn.addEventListener('click', ()=>{ statusEl.style.display=''; statusEl.textContent='Refreshing...'; loadList(); });
  backBtn.addEventListener('click', ()=>{
    let p = currentPath.replace(/\/+$/,'');
    const idx = p.lastIndexOf('/');
    if(idx <= 0){
      loadList(BASE);
      return;
    }
    const parent = p.substring(0, idx) + '/';
    if(parent.length < normalizePath(BASE).length) {
      loadList(BASE);
    } else {
      loadList(parent);
    }
  });

  // Upload handling
  if(uploadBtn){
    // track current XHR so cancel can abort
    let currentXhr = null;
    function setCancelEnabled(enabled){
      try{
        if(uploadCancelBtn){
          uploadCancelBtn.disabled = !enabled;
          uploadCancelBtn.style.display = enabled ? '' : 'none';
          uploadCancelBtn.style.opacity = enabled ? '1' : '0.6';
          uploadCancelBtn.style.cursor = enabled ? 'pointer' : 'default';
        }
      }catch(e){}
    }
    setCancelEnabled(false);

    uploadBtn.addEventListener('click', function(){
      const file = uploadInput && uploadInput.files && uploadInput.files[0];
      if(!file){ alert('Select a file first'); return; }
      const form = new FormData();
      // send relative path without leading slash
      const rel = currentPath.replace(/^\//,'');
      form.append('path', rel);
      form.append('file', file, file.name);

      try{
        statusEl.style.display=''; statusEl.textContent='Uploading...';
        const xhr = new XMLHttpRequest();
        currentXhr = xhr;
        setCancelEnabled(true);

        xhr.open('POST', '/upload', true);
        xhr.upload.onprogress = function(evt){
          if(evt.lengthComputable){
            const pct = Math.floor((evt.loaded / evt.total) * 100);
            statusEl.textContent = 'Uploading... ' + pct + '%';
          } else {
            statusEl.textContent = 'Uploading...';
          }
        };
        xhr.onerror = function(){
          currentXhr = null;
          setCancelEnabled(false);
          statusEl.textContent = 'Upload failed: network error';
        };
        xhr.onabort = function(){
          currentXhr = null;
          setCancelEnabled(false);
          statusEl.textContent = 'Upload canceled';
        };
        xhr.onload = function(){
          currentXhr = null;
          setCancelEnabled(false);
          try{
            if(xhr.status >= 200 && xhr.status < 300){
              statusEl.style.display='none';
              loadList(currentPath);
            } else {
              statusEl.textContent = 'Upload failed: HTTP ' + xhr.status;
            }
          }catch(e){
            statusEl.textContent = 'Upload failed: ' + (e.message || 'unknown');
          }
        };

        // wire cancel button
        if(uploadCancelBtn){
          uploadCancelBtn.onclick = function(){
            try{
              if(currentXhr){
                currentXhr.abort();
              }
            }catch(e){}
            setCancelEnabled(false);
          };
        }

        xhr.send(form);
      }catch(err){
        setCancelEnabled(false);
        statusEl.textContent = 'Upload failed: ' + err.message;
      }
    });
  }

  // Create directory handling
  if(mkdirBtn){
    mkdirBtn.addEventListener('click', async function(){
      const name = prompt('Folder name:');
      if(!name) return;
      const rel = currentPath.replace(/^\//,'');
      const body = 'path=' + encodeURIComponent(rel) + '&name=' + encodeURIComponent(name);
      try{
        statusEl.style.display=''; statusEl.textContent='Creating folder...';
        const res = await fetch('/mkdir', { method: 'POST', headers: {'Content-Type':'application/x-www-form-urlencoded'}, body });
        if(!res.ok) throw new Error('HTTP ' + res.status);
        const j = await res.json();
        statusEl.style.display='none';
        loadList(currentPath);
      }catch(err){
        statusEl.textContent = 'Create folder failed: ' + err.message;
      }
    });
  }

  // initial load
  setPath(BASE);
  loadList(BASE);
})();
