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
    browsingEl.textContent = currentPath;
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

        tr.appendChild(nameTd);
        tr.appendChild(typeTd);
        tr.appendChild(sizeTd);
        tr.appendChild(linkTd);
        tr.appendChild(downloadTd);
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

  // initial load
  setPath(BASE);
  loadList(BASE);
})();
