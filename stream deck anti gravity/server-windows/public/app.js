let configData = null;
let currentProfile = null;
let activePageIndex = 0;
let selectedButton = null;
let availableIcons = [];
let draggedButton = null;

document.addEventListener('DOMContentLoaded', async () => {
  await loadServerInfo();
  await loadIconsCatalog();
  await loadProfiles();

  document.getElementById('btn-save').addEventListener('click', saveAndSync);
  document.getElementById('select-profile').addEventListener('change', onProfileSelectChange);
  document.getElementById('btn-new-profile').addEventListener('click', onCreateNewProfile);
  document.getElementById('select-theme').addEventListener('change', onThemeSelectChange);
});

function onThemeSelectChange(e) {
  const themeClass = e.target.value;
  document.body.className = themeClass;
}

async function loadServerInfo() {
  try {
    const res = await fetch('/api/pairing');
    const data = await res.json();
    document.getElementById('server-info').innerText = `${data.serverName} (${data.ip}:${data.wsPort})`;
    document.getElementById('qr-code-img').src = data.qrCode;
    document.getElementById('qr-ip-text').innerText = `IP: ${data.ip}:${data.wsPort}`;
  } catch (err) {
    document.getElementById('server-info').innerText = 'Erro de Conexão com Servidor';
  }
}

async function loadIconsCatalog() {
  try {
    const res = await fetch('/api/icons-catalog');
    availableIcons = await res.json();
  } catch (err) {
    console.error('Erro ao carregar catálogo de ícones:', err);
  }
}

async function loadProfiles() {
  try {
    const res = await fetch('/api/profiles');
    configData = await res.json();

    const profileSelect = document.getElementById('select-profile');
    profileSelect.innerHTML = '';

    configData.profiles.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.innerText = p.name;
      if (p.id === configData.activeProfileId) opt.selected = true;
      profileSelect.appendChild(opt);
    });

    currentProfile = configData.profiles.find((p) => p.id === configData.activeProfileId) || configData.profiles[0];
    activePageIndex = configData.activePageIndex || 0;

    renderPagesBar();
    renderGrid();
  } catch (err) {
    console.error('Erro ao carregar perfis:', err);
  }
}

async function onProfileSelectChange(e) {
  const profileId = e.target.value;
  try {
    const res = await fetch('/api/profiles/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profileId, pageIndex: 0 })
    });
    const data = await res.json();
    if (data.success) {
      configData = data.config;
      currentProfile = configData.profiles.find((p) => p.id === profileId);
      activePageIndex = 0;
      selectedButton = null;
      renderPagesBar();
      renderGrid();
      renderEditorForm();
    }
  } catch (err) {
    console.error('Erro ao mudar perfil:', err);
  }
}

async function onCreateNewProfile() {
  const name = prompt('Nome do novo perfil:');
  if (!name) return;

  const id = 'prof_' + Date.now();
  try {
    const res = await fetch('/api/profiles/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, name })
    });
    const data = await res.json();
    if (data.success) {
      await loadProfiles();
    }
  } catch (err) {
    alert('Erro ao criar perfil.');
  }
}

function renderPagesBar() {
  const container = document.getElementById('pages-bar');
  container.innerHTML = '';

  if (!currentProfile || !currentProfile.pages) return;

  currentProfile.pages.forEach((p, idx) => {
    const btn = document.createElement('button');
    btn.className = `page-tab ${idx === activePageIndex ? 'active' : ''}`;
    btn.innerText = `Pág ${idx + 1}`;
    btn.addEventListener('click', () => {
      activePageIndex = idx;
      selectedButton = null;
      renderPagesBar();
      renderGrid();
      renderEditorForm();
    });
    container.appendChild(btn);
  });
}

function renderGrid() {
  const container = document.getElementById('deck-grid');
  container.innerHTML = '';

  if (!currentProfile || !currentProfile.pages) return;

  const page = currentProfile.pages[activePageIndex] || currentProfile.pages[0];
  const gridConfig = currentProfile.gridConfig || { rows: 3, cols: 4 };

  container.style.gridTemplateColumns = `repeat(${gridConfig.cols}, 1fr)`;

  const buttonsMap = new Map();
  if (page && page.buttons) {
    page.buttons.forEach((b) => buttonsMap.set(`${b.row}_${b.col}`, b));
  }

  for (let r = 0; r < gridConfig.rows; r++) {
    for (let c = 0; c < gridConfig.cols; c++) {
      const key = `${r}_${c}`;
      let btn = buttonsMap.get(key);

      if (!btn) {
        btn = {
          id: `btn_${activePageIndex}_${r}_${c}`,
          row: r,
          col: c,
          rowSpan: 1,
          colSpan: 1,
          label: 'Novo Botão',
          backgroundColor: '#1E1E2E',
          labelColor: '#FFFFFF',
          actionType: 'NONE'
        };
      }

      const btnEl = document.createElement('div');
      btnEl.className = 'grid-button';
      btnEl.draggable = true;

      if (selectedButton && selectedButton.id === btn.id) {
        btnEl.classList.add('selected');
      }
      btnEl.style.backgroundColor = btn.backgroundColor || '#1E1E2E';
      if (btn.colSpan && btn.colSpan > 1) {
        btnEl.style.gridColumn = `span ${btn.colSpan}`;
      }

      if (btn.iconUrl) {
        const img = document.createElement('img');
        img.src = btn.iconUrl;
        btnEl.appendChild(img);
      }

      const span = document.createElement('span');
      span.innerText = btn.label;
      span.style.color = btn.labelColor || '#FFFFFF';
      btnEl.appendChild(span);

      // Eventos Drag & Drop
      btnEl.addEventListener('dragstart', (e) => {
        draggedButton = btn;
        btnEl.classList.add('dragging');
        e.dataTransfer.setData('text/plain', btn.id);
      });

      btnEl.addEventListener('dragend', () => {
        btnEl.classList.remove('dragging');
        draggedButton = null;
      });

      btnEl.addEventListener('dragover', (e) => {
        e.preventDefault();
        btnEl.classList.add('drag-over');
      });

      btnEl.addEventListener('dragleave', () => {
        btnEl.classList.remove('drag-over');
      });

      btnEl.addEventListener('drop', (e) => {
        e.preventDefault();
        btnEl.classList.remove('drag-over');
        if (draggedButton && draggedButton.id !== btn.id) {
          swapButtons(draggedButton, btn);
        }
      });

      btnEl.addEventListener('click', () => selectButton(btn));
      container.appendChild(btnEl);
    }
  }
}

function swapButtons(btnA, btnB) {
  const tempRow = btnA.row;
  const tempCol = btnA.col;

  btnA.row = btnB.row;
  btnA.col = btnB.col;

  btnB.row = tempRow;
  btnB.col = tempCol;

  const page = currentProfile.pages[activePageIndex] || currentProfile.pages[0];
  const idxA = page.buttons.findIndex((b) => b.id === btnA.id);
  if (idxA < 0) page.buttons.push(btnA);

  const idxB = page.buttons.findIndex((b) => b.id === btnB.id);
  if (idxB < 0) page.buttons.push(btnB);

  renderGrid();
}

function selectButton(btn) {
  selectedButton = btn;
  renderGrid();
  renderEditorForm();
}

function renderEditorForm() {
  const container = document.getElementById('editor-form');
  if (!selectedButton) {
    container.innerHTML = '<p class="placeholder-text">Clique em um botão da grade para editá-lo.</p>';
    return;
  }

  let iconOptionsHtml = '<option value="">Sem Ícone</option>';
  availableIcons.forEach((icon) => {
    const isSel = selectedButton.iconUrl === icon.url ? 'selected' : '';
    iconOptionsHtml += `<option value="${icon.url}" ${isSel}>${icon.name} (${icon.type})</option>`;
  });

  const payload = selectedButton.actionPayload || {};
  let actionParamValue = payload.keys || payload.path || payload.url || payload.pageIndex || payload.profileId || payload.sceneName || '';
  if (selectedButton.actionType === 'MULTI_ACTION' && payload.actions) {
    actionParamValue = JSON.stringify(payload.actions);
  }

  container.innerHTML = `
    <div class="form-group">
      <label>Rótulo do Botão:</label>
      <input type="text" id="edit-label" value="${selectedButton.label || ''}">
    </div>

    <div class="color-picker-row">
      <div class="form-group" style="flex:1;">
        <label>Largura (ColSpan):</label>
        <select id="edit-colspan">
          <option value="1" ${(selectedButton.colSpan || 1) === 1 ? 'selected' : ''}>1x (Normal)</option>
          <option value="2" ${(selectedButton.colSpan || 1) === 2 ? 'selected' : ''}>2x (Duplo)</option>
        </select>
      </div>
      <div class="form-group" style="flex:1;">
        <label>Cor de Fundo:</label>
        <input type="color" id="edit-bg-color" value="${selectedButton.backgroundColor || '#1e1e2e'}">
      </div>
    </div>

    <div class="form-group">
      <label>Cor do Texto:</label>
      <input type="color" id="edit-text-color" value="${selectedButton.labelColor || '#ffffff'}">
    </div>

    <div class="form-group">
      <label>Ícone:</label>
      <select id="edit-icon">${iconOptionsHtml}</select>
    </div>

    <div class="form-group">
      <label>Tipo de Ação:</label>
      <select id="edit-action-type">
        <option value="NONE" ${selectedButton.actionType === 'NONE' ? 'selected' : ''}>Nenhuma</option>
        <option value="TOGGLE_MUTE" ${selectedButton.actionType === 'TOGGLE_MUTE' ? 'selected' : ''}>Mutar / Desmutar Som Windows</option>
        <option value="VOLUME_UP" ${selectedButton.actionType === 'VOLUME_UP' ? 'selected' : ''}>Aumentar Volume</option>
        <option value="VOLUME_DOWN" ${selectedButton.actionType === 'VOLUME_DOWN' ? 'selected' : ''}>Diminuir Volume</option>
        <option value="MEDIA_PLAY_PAUSE" ${selectedButton.actionType === 'MEDIA_PLAY_PAUSE' ? 'selected' : ''}>Play / Pause Mídia</option>
        <option value="HOTKEY" ${selectedButton.actionType === 'HOTKEY' ? 'selected' : ''}>Atalho de Teclado (Hotkey)</option>
        <option value="OPEN_APP" ${selectedButton.actionType === 'OPEN_APP' ? 'selected' : ''}>Abrir Programa / Arquivo</option>
        <option value="OPEN_URL" ${selectedButton.actionType === 'OPEN_URL' ? 'selected' : ''}>Abrir URL</option>
        <option value="SWITCH_PAGE" ${selectedButton.actionType === 'SWITCH_PAGE' ? 'selected' : ''}>Mudar Página</option>
        <option value="SWITCH_PROFILE" ${selectedButton.actionType === 'SWITCH_PROFILE' ? 'selected' : ''}>Mudar Perfil</option>
        <option value="OBS_SCENE" ${selectedButton.actionType === 'OBS_SCENE' ? 'selected' : ''}>Mudar Cena no OBS</option>
        <option value="OBS_TOGGLE_STREAM" ${selectedButton.actionType === 'OBS_TOGGLE_STREAM' ? 'selected' : ''}>Iniciar / Parar Live OBS</option>
        <option value="OBS_TOGGLE_RECORD" ${selectedButton.actionType === 'OBS_TOGGLE_RECORD' ? 'selected' : ''}>Iniciar / Parar Gravação OBS</option>
        <option value="OPEN_FOLDER" ${selectedButton.actionType === 'OPEN_FOLDER' ? 'selected' : ''}>Abrir Pasta (Sub-Deck)</option>
        <option value="HW_CPU" ${selectedButton.actionType === 'HW_CPU' ? 'selected' : ''}>Monitor de CPU (%)</option>
        <option value="HW_RAM" ${selectedButton.actionType === 'HW_RAM' ? 'selected' : ''}>Monitor de RAM (%)</option>
        <option value="HW_GPU" ${selectedButton.actionType === 'HW_GPU' ? 'selected' : ''}>Monitor de GPU (%)</option>
        <option value="SPOTIFY_TRACK" ${selectedButton.actionType === 'SPOTIFY_TRACK' ? 'selected' : ''}>Spotify (Música & Artista)</option>
        <option value="DISCORD_TOGGLE_MUTE" ${selectedButton.actionType === 'DISCORD_TOGGLE_MUTE' ? 'selected' : ''}>Discord: Mutar Microfone</option>
        <option value="DISCORD_TOGGLE_DEAFEN" ${selectedButton.actionType === 'DISCORD_TOGGLE_DEAFEN' ? 'selected' : ''}>Discord: Mutar Áudio (Deafen)</option>
        <option value="MULTI_ACTION" ${selectedButton.actionType === 'MULTI_ACTION' ? 'selected' : ''}>Macro em Cadeia (Multi-Actions)</option>
      </select>
    </div>

    <div class="form-group" id="action-param-group">
      <label id="action-param-label">Parâmetro da Ação:</label>
      <input type="text" id="edit-action-param" value='${actionParamValue}'>
    </div>
  `;

  document.getElementById('edit-colspan').addEventListener('change', (e) => {
    selectedButton.colSpan = parseInt(e.target.value, 10) || 1;
    renderGrid();
  });

  document.getElementById('edit-label').addEventListener('input', (e) => {
    selectedButton.label = e.target.value;
    renderGrid();
  });

  document.getElementById('edit-bg-color').addEventListener('input', (e) => {
    selectedButton.backgroundColor = e.target.value;
    renderGrid();
  });

  document.getElementById('edit-text-color').addEventListener('input', (e) => {
    selectedButton.labelColor = e.target.value;
    renderGrid();
  });

  document.getElementById('edit-icon').addEventListener('change', (e) => {
    selectedButton.iconUrl = e.target.value;
    renderGrid();
  });

  document.getElementById('edit-action-type').addEventListener('change', (e) => {
    selectedButton.actionType = e.target.value;
  });

  document.getElementById('edit-action-param').addEventListener('input', (e) => {
    const val = e.target.value;
    if (selectedButton.actionType === 'HOTKEY') {
      selectedButton.actionPayload = { keys: val };
    } else if (selectedButton.actionType === 'OPEN_APP') {
      selectedButton.actionPayload = { path: val };
    } else if (selectedButton.actionType === 'OPEN_URL') {
      selectedButton.actionPayload = { url: val };
    } else if (selectedButton.actionType === 'SWITCH_PAGE') {
      selectedButton.actionPayload = { pageIndex: parseInt(val, 10) || 0 };
    } else if (selectedButton.actionType === 'SWITCH_PROFILE') {
      selectedButton.actionPayload = { profileId: val };
    } else if (selectedButton.actionType === 'OBS_SCENE') {
      selectedButton.actionPayload = { sceneName: val };
    } else if (selectedButton.actionType === 'MULTI_ACTION') {
      try {
        selectedButton.actionPayload = { actions: JSON.parse(val) };
      } catch (_err) {}
    }
  });
}

async function saveAndSync() {
  if (!currentProfile) return;

  const page = currentProfile.pages[activePageIndex] || { pageIndex: activePageIndex, buttons: [] };
  const idx = page.buttons.findIndex((b) => b.id === selectedButton.id);
  if (idx >= 0) {
    page.buttons[idx] = selectedButton;
  } else if (selectedButton) {
    page.buttons.push(selectedButton);
  }

  try {
    const res = await fetch('/api/profiles/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profileId: currentProfile.id,
        pageIndex: activePageIndex,
        buttons: page.buttons
      })
    });

    const data = await res.json();
    if (data.success) {
      alert('Configuração salva e sincronizada!');
    }
  } catch (err) {
    alert('Erro ao salvar no servidor.');
  }
}
