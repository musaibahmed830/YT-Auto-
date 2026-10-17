// AutoTube AI Studio - Modern Frontend Engine

let currentSeriesState = null;
let taskPollInterval = null;

document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  loadAllData();

  // Check URL params for oauth return
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("connected") === "1") {
    showToast("🎉 YouTube Channel successfully connected!", "success");
    // Clear URL query
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  // Periodic health & background poll
  setInterval(pollTaskStatus, 3000);
});

// ── Tab Navigation ─────────────────────────────────────────────────────────────
function setupNavigation() {
  const navItems = document.querySelectorAll(".nav-item");
  const tabContents = document.querySelectorAll(".tab-content");

  const tabHeadings = {
    "tab-channels": {
      title: "Connected YouTube Channels",
      sub: "Manage your channel portfolio, upload schedules, and OAuth tokens."
    },
    "tab-studio": {
      title: "Story Series Studio",
      sub: "Plan multi-episode suspense series with synchronized 60s Main Videos and 20s Shorts."
    },
    "tab-preview": {
      title: "Video Previews",
      sub: "Inspect and play freshly rendered 16:9 Long-Form and 9:16 Shorts."
    },
    "tab-history": {
      title: "Upload & Performance History",
      sub: "Track all published videos and Shorts across all connected channels."
    },
    "tab-health": {
      title: "System & API Health",
      sub: "Real-time connectivity status of Gemini, Groq, Pexels, and Edge-TTS."
    }
  };

  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const targetTab = item.getAttribute("data-tab");

      navItems.forEach(i => i.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));

      item.classList.add("active");
      const content = document.getElementById(targetTab);
      if (content) content.classList.add("active");

      if (tabHeadings[targetTab]) {
        document.getElementById("page-heading").innerText = tabHeadings[targetTab].title;
        document.getElementById("page-subheading").innerText = tabHeadings[targetTab].sub;
      }

      // Tab specific refresh
      if (targetTab === "tab-channels") loadChannels();
      if (targetTab === "tab-studio") loadSeries();
      if (targetTab === "tab-preview") refreshVideoPlayerList();
      if (targetTab === "tab-history") loadHistory();
      if (targetTab === "tab-health") loadHealth();
    });
  });
}

function loadAllData() {
  loadChannels();
  loadSeries();
  loadHistory();
  loadHealth();
}

// ── Channels Management ────────────────────────────────────────────────────────
async function loadChannels() {
  const container = document.getElementById("channels-container");
  const selectChannel = document.getElementById("select-target-channel");
  try {
    const res = await fetch("/api/channels");
    const data = await res.json();
    const channels = data.channels || [];

    document.getElementById("stat-channels-count").innerText = channels.length;

    // Update target select in task modal
    if (selectChannel) {
      selectChannel.innerHTML = "";
      if (channels.length === 0) {
        selectChannel.innerHTML = `<option value="">No connected channel (Local Render Only)</option>`;
      } else {
        channels.forEach(ch => {
          const opt = document.createElement("option");
          opt.value = ch.id;
          opt.innerText = `${ch.channel_title} (${ch.is_active ? 'Active' : 'Paused'})`;
          selectChannel.appendChild(opt);
        });
      }
    }

    if (channels.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 48px; background: rgba(255,255,255,0.02); border-radius: 12px; border: 1px dashed var(--border-color);">
          <div style="font-size: 40px; margin-bottom: 12px;">📡</div>
          <h3 style="font-size: 18px; margin-bottom: 8px;">No Channels Connected Yet</h3>
          <p style="color: var(--text-muted); font-size: 14px; max-width: 460px; margin: 0 auto 18px auto;">
            Connect your YouTube channel to enable 100% automated uploads for scheduled story episodes and Shorts.
          </p>
          <button class="btn btn-primary" onclick="openConnectModal()"><span>➕</span> Connect Channel</button>
        </div>
      `;
      return;
    }

    container.innerHTML = channels.map(ch => `
      <div class="channel-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px;">
          <div>
            <h3 style="font-size: 17px; font-weight: 700; color: #fff;">${escapeHtml(ch.channel_title)}</h3>
            <span style="font-size: 12px; color: var(--accent); background: rgba(99, 102, 241, 0.15); padding: 2px 8px; border-radius: 99px; margin-top: 4px; display: inline-block;">
              ${escapeHtml(ch.niche || 'Story Series')}
            </span>
          </div>
          <span class="badge ${ch.is_active ? 'badge-success' : 'badge-warning'}">
            ${ch.is_active ? '● Active' : '○ Paused'}
          </span>
        </div>

        <div style="font-size: 13px; color: var(--text-muted); display: flex; flex-direction: column; gap: 6px; margin-bottom: 18px;">
          <div>⏰ Schedule: <strong style="color: var(--text-main);">${escapeHtml(ch.schedule_times || '06:00,18:00')}</strong></div>
          <div>🔒 Privacy: <strong style="color: var(--text-main); text-transform: capitalize;">${escapeHtml(ch.privacy_status || 'public')}</strong></div>
          <div>🆔 Channel ID: <span style="font-family: monospace; font-size: 11px; color: var(--text-dim);">${ch.id.slice(0, 14)}...</span></div>
        </div>

        <div style="display: flex; gap: 8px; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-color); padding-top: 12px;">
          <button class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;" onclick="toggleChannel('${ch.id}', ${!ch.is_active})">
            ${ch.is_active ? '⏸ Pause' : '▶ Activate'}
          </button>
          <button class="btn" style="background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 6px 12px; font-size: 12px;" onclick="deleteChannel('${ch.id}')">
            🗑 Remove
          </button>
        </div>
      </div>
    `).join("");

  } catch (err) {
    console.error("Error loading channels:", err);
    container.innerHTML = `<p style="color: #ef4444;">Failed to load channels: ${err.message}</p>`;
  }
}

async function toggleChannel(channelId, newStatus) {
  try {
    await fetch(`/api/channels/${channelId}/toggle?active=${newStatus}`, { method: "POST" });
    showToast(`Channel ${newStatus ? 'activated' : 'paused'}`, "info");
    loadChannels();
  } catch (err) {
    showToast("Failed to toggle channel status", "error");
  }
}

async function deleteChannel(channelId) {
  if (!confirm("Are you sure you want to remove this channel connection?")) return;
  try {
    await fetch(`/api/channels/${channelId}`, { method: "DELETE" });
    showToast("Channel removed successfully", "info");
    loadChannels();
  } catch (err) {
    showToast("Failed to remove channel", "error");
  }
}

// ── Connect Modal & OAuth ──────────────────────────────────────────────────────
function openConnectModal() {
  document.getElementById("modal-connect-channel").classList.add("active");
}

function closeConnectModal() {
  document.getElementById("modal-connect-channel").classList.remove("active");
}

async function redirectToGoogleAuth() {
  try {
    const res = await fetch("/api/auth/google-url");
    const data = await res.json();
    if (data.auth_url) {
      window.location.href = data.auth_url;
    } else {
      showToast(data.detail || "Google OAuth client is not configured in .env", "error");
    }
  } catch (err) {
    showToast("Failed to initiate Google OAuth: " + err.message, "error");
  }
}

async function handleManualChannelSubmit(e) {
  e.preventDefault();
  const payload = {
    channel_title: document.getElementById("manual-channel-title").value.trim(),
    client_id: document.getElementById("manual-client-id").value.trim(),
    client_secret: document.getElementById("manual-client-secret").value.trim(),
    refresh_token: document.getElementById("manual-refresh-token").value.trim(),
    niche: "Story & Shorts",
    privacy_status: "public"
  };

  try {
    const res = await fetch("/api/channels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to add channel");

    showToast("Channel connected successfully!", "success");
    closeConnectModal();
    document.getElementById("form-manual-channel").reset();
    loadChannels();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ── Story Series Studio ────────────────────────────────────────────────────────
async function loadSeries() {
  const container = document.getElementById("episodes-container");
  const seriesTitleEl = document.getElementById("current-series-title");
  try {
    const res = await fetch("/api/series/status");
    const data = await res.json();
    currentSeriesState = data.state;

    if (!currentSeriesState || !currentSeriesState.episodes || currentSeriesState.episodes.length === 0) {
      seriesTitleEl.innerText = "No Series Planned Yet";
      document.getElementById("stat-series-progress").innerText = "0 / 0";
      container.innerHTML = `
        <div style="text-align: center; padding: 40px; background: rgba(255,255,255,0.02); border-radius: 12px; border: 1px dashed var(--border-color);">
          <p style="color: var(--text-muted); font-size: 14px;">Enter a story prompt above and click "Plan Multi-Episode Series" to get started.</p>
        </div>
      `;
      return;
    }

    const total = currentSeriesState.total_episodes || currentSeriesState.episodes.length;
    const completed = currentSeriesState.completed_episodes || 0;
    document.getElementById("stat-series-progress").innerText = `${completed} / ${total} Eps`;
    seriesTitleEl.innerText = `Active Series: "${currentSeriesState.topic || 'Custom Story'}"`;

    container.innerHTML = currentSeriesState.episodes.map(ep => {
      const isDone = ep.completed;
      const scenesCount = ep.full_script && ep.full_script.scenes ? ep.full_script.scenes.length : 0;
      return `
        <div class="episode-card ${isDone ? 'episode-completed' : ''}">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <span style="background: var(--accent); color: #fff; font-weight: 700; font-size: 12px; padding: 3px 10px; border-radius: 99px;">
                Episode ${ep.episode_number}
              </span>
              <h4 style="font-size: 16px; font-weight: 600; color: #fff;">${escapeHtml(ep.episode_title)}</h4>
            </div>
            <span class="badge ${isDone ? 'badge-success' : 'badge-warning'}">
              ${isDone ? '✓ Uploaded / Ready' : '⏳ Pending'}
            </span>
          </div>

          <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px; line-height: 1.5;">
            <strong>Hook / Cliffhanger:</strong> ${escapeHtml(ep.cliffhanger_hook || 'Dramatic suspense ending')}
          </p>

          <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.25); padding: 8px 14px; border-radius: 8px; font-size: 12px; color: var(--text-dim);">
            <div>🎬 <strong>${scenesCount} Synced Scenes</strong> (60s Main + 20s Short)</div>
            <div style="display: flex; gap: 8px;">
              <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 12px;" onclick="toggleSceneViewer(${ep.episode_number})">
                👁️ View Scenes
              </button>
              ${!isDone ? `
                <button class="btn btn-primary" style="padding: 4px 12px; font-size: 12px;" onclick="runSingleEpisode(${ep.episode_number})">
                  ▶ Render & Upload
                </button>
              ` : `
                <button class="btn btn-secondary" style="padding: 4px 12px; font-size: 12px;" onclick="previewEpisodeVideos(${ep.episode_number})">
                  📺 Watch Preview
                </button>
              `}
            </div>
          </div>

          <!-- Collapsible Scenes List -->
          <div id="scenes-detail-${ep.episode_number}" style="display: none; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border-color);">
            <h5 style="font-size: 13px; margin-bottom: 8px; color: var(--accent);">Synchronized Scenes Breakdown:</h5>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${(ep.full_script && ep.full_script.scenes ? ep.full_script.scenes : []).map((sc, sIdx) => `
                <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-radius: 6px; padding: 8px 12px; font-size: 12px;">
                  <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <strong style="color: #fff;">Scene ${sIdx + 1}</strong>
                    <span style="color: var(--accent); font-family: monospace;">🔎 Pexels query: "${escapeHtml(sc.visual_search_query || '')}"</span>
                  </div>
                  <div style="color: var(--text-muted);">🗣️ Narration: "${escapeHtml(sc.narration || '')}"</div>
                </div>
              `).join("")}
            </div>
          </div>
        </div>
      `;
    }).join("");

  } catch (err) {
    console.error("Error loading series:", err);
  }
}

function toggleSceneViewer(epNum) {
  const el = document.getElementById(`scenes-detail-${epNum}`);
  if (el) {
    el.style.display = el.style.display === "none" ? "block" : "none";
  }
}

async function generateStoryPlan() {
  const promptInput = document.getElementById("story-prompt-input");
  const countSelect = document.getElementById("story-episodes-count");
  const btn = document.getElementById("btn-generate-plan");

  const prompt = promptInput.value.trim();
  if (!prompt) {
    showToast("Please enter a story concept prompt first!", "error");
    return;
  }

  btn.disabled = true;
  btn.innerText = "⏳ Planning Series...";

  try {
    const res = await fetch("/api/series/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: prompt, episodes: parseInt(countSelect.value) })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to start series planning");

    showToast("Planning initiated! Watching progress...", "info");
    openTaskModal();
    pollTaskStatus();
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>✨</span> Plan Multi-Episode Series`;
  }
}

// ── Video Execution & Task Runner ──────────────────────────────────────────────
function triggerEpisodeModal() {
  openTaskModal();
}

function openTaskModal() {
  document.getElementById("modal-task-runner").classList.add("active");
  startLiveLogPolling();
}

function closeTaskModal() {
  document.getElementById("modal-task-runner").classList.remove("active");
}

async function runSingleEpisode(epNum) {
  openTaskModal();
  const selectCh = document.getElementById("select-target-channel");
  const chId = selectCh ? selectCh.value : null;

  try {
    const res = await fetch("/api/series/run-episode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel_id: chId || null, episode_number: epNum })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to start episode");
    showToast(`Episode ${epNum} execution started!`, "success");
    startLiveLogPolling();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function startEpisodeExecution() {
  const selectCh = document.getElementById("select-target-channel");
  const chId = selectCh ? selectCh.value : null;

  try {
    const res = await fetch("/api/series/run-episode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel_id: chId || null, episode_number: null })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to start episode execution");
    showToast("Video automation launched!", "success");
    startLiveLogPolling();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function startLiveLogPolling() {
  if (taskPollInterval) clearInterval(taskPollInterval);
  taskPollInterval = setInterval(pollTaskStatus, 1500);
  pollTaskStatus();
}

async function pollTaskStatus() {
  try {
    const res = await fetch("/api/task-status");
    const data = await res.json();

    const indicator = document.getElementById("system-status-indicator");
    if (indicator) {
      indicator.innerText = data.is_running ? `Busy: ${data.current_action.slice(0, 24)}...` : "All Engines Ready";
    }

    const logBox = document.getElementById("live-task-log");
    if (logBox && data.log_messages && data.log_messages.length > 0) {
      logBox.innerHTML = data.log_messages.map(m => `<div>${escapeHtml(m)}</div>`).join("");
      logBox.scrollTop = logBox.scrollHeight;
    }

    if (!data.is_running && taskPollInterval) {
      clearInterval(taskPollInterval);
      taskPollInterval = null;
      loadSeries();
      loadHistory();
      refreshVideoPlayerList();
    }
  } catch (err) {
    console.error("Status poll error:", err);
  }
}

// ── Video Previews ─────────────────────────────────────────────────────────────
function previewEpisodeVideos(epNum) {
  // Switch to preview tab
  const previewTab = document.querySelector('[data-tab="tab-preview"]');
  if (previewTab) previewTab.click();

  const mainVideo = document.getElementById("player-main");
  const shortVideo = document.getElementById("player-short");

  if (mainVideo) {
    mainVideo.src = `/api/video-stream/ep${epNum}_main.mp4`;
    mainVideo.load();
  }
  if (shortVideo) {
    shortVideo.src = `/api/video-stream/ep${epNum}_short.mp4`;
    shortVideo.load();
  }
}

function refreshVideoPlayerList() {
  if (!currentSeriesState || !currentSeriesState.episodes) return;
  const completed = currentSeriesState.episodes.filter(e => e.completed);
  if (completed.length > 0) {
    const latest = completed[completed.length - 1];
    previewEpisodeVideos(latest.episode_number);
  }
}

// ── Upload History ─────────────────────────────────────────────────────────────
async function loadHistory() {
  const tbody = document.getElementById("history-table-body");
  try {
    const res = await fetch("/api/history");
    const data = await res.json();
    const history = data.history || [];

    document.getElementById("stat-total-uploads").innerText = history.length;

    if (history.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; color: var(--text-dim); padding: 32px;">
            No uploads recorded yet. Trigger an episode execution above to upload your first video!
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = history.map(item => `
      <tr>
        <td><strong>${escapeHtml(item.channel_title || 'YouTube Channel')}</strong></td>
        <td>
          <div style="font-weight: 600; color: #fff;">${escapeHtml(item.title)}</div>
          <span style="font-size: 11px; color: var(--text-dim);">Episode ${item.episode_number || '1'}</span>
        </td>
        <td>
          <span class="badge ${item.is_short ? 'badge-info' : 'badge-success'}">
            ${item.is_short ? '📱 Short (9:16)' : '🎬 Main Video (16:9)'}
          </span>
        </td>
        <td style="color: var(--text-muted); font-size: 12px;">${escapeHtml(item.uploaded_at || 'Just now')}</td>
        <td>
          ${item.video_id && !item.video_id.startsWith('local') ? `
            <a href="https://youtu.be/${item.video_id}" target="_blank" style="color: var(--accent); text-decoration: none; font-weight: 600; font-size: 13px;">
              Watch on YouTube ↗
            </a>
          ` : `
            <span style="color: var(--text-dim); font-size: 12px;">Rendered Locally</span>
          `}
        </td>
      </tr>
    `).join("");

  } catch (err) {
    console.error("Error loading history:", err);
  }
}

// ── System Health ──────────────────────────────────────────────────────────────
async function loadHealth() {
  const container = document.getElementById("health-grid");
  try {
    const res = await fetch("/api/system-health");
    const data = await res.json();

    container.innerHTML = `
      <div class="health-card">
        <div>
          <h4 style="font-size: 15px; margin-bottom: 4px; color: #fff;">Google Gemini AI</h4>
          <p style="font-size: 13px; color: var(--text-muted);">Free LLM scriptwriter and scene generator (gemini-2.5-flash / gemini-1.5-flash)</p>
        </div>
        <span class="badge ${data.gemini_api_key ? 'badge-success' : 'badge-warning'}">
          ${data.gemini_api_key ? '✓ Configured' : '⚠ Missing GEMINI_API_KEY'}
        </span>
      </div>

      <div class="health-card">
        <div>
          <h4 style="font-size: 15px; margin-bottom: 4px; color: #fff;">Groq Free Fallback Engine</h4>
          <p style="font-size: 13px; color: var(--text-muted);">Instant failover LLM (llama-3.3-70b-versatile)</p>
        </div>
        <span class="badge ${data.groq_api_key ? 'badge-success' : 'badge-warning'}">
          ${data.groq_api_key ? '✓ Configured' : '○ Optional Fallback'}
        </span>
      </div>

      <div class="health-card">
        <div>
          <h4 style="font-size: 15px; margin-bottom: 4px; color: #fff;">Pexels Stock Video API</h4>
          <p style="font-size: 13px; color: var(--text-muted);">Free HD footage matching visual keywords (Orientation-aware for horizontal & vertical)</p>
        </div>
        <span class="badge ${data.pexels_api_key ? 'badge-success' : 'badge-warning'}">
          ${data.pexels_api_key ? '✓ Configured' : '⚠ Missing PEXELS_API_KEY'}
        </span>
      </div>

      <div class="health-card">
        <div>
          <h4 style="font-size: 15px; margin-bottom: 4px; color: #fff;">Microsoft Edge-TTS Voiceover</h4>
          <p style="font-size: 13px; color: var(--text-muted);">100% Free natural neural voices (en-US-ChristopherNeural)</p>
        </div>
        <span class="badge badge-success">✓ Active & Ready</span>
      </div>

      <div class="health-card">
        <div>
          <h4 style="font-size: 15px; margin-bottom: 4px; color: #fff;">Connected Channels Database</h4>
          <p style="font-size: 13px; color: var(--text-muted);">SQLite multi-channel credential vault (data/channels.db)</p>
        </div>
        <span class="badge badge-success">✓ ${data.connected_channels} Channel(s)</span>
      </div>
    `;
  } catch (err) {
    console.error("Health check error:", err);
  }
}

// ── Utility Toast & Escapes ────────────────────────────────────────────────────
function showToast(msg, type = "info") {
  const existing = document.getElementById("toast-banner");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.id = "toast-banner";
  toast.style.position = "fixed";
  toast.style.bottom = "24px";
  toast.style.right = "24px";
  toast.style.padding = "12px 20px";
  toast.style.borderRadius = "8px";
  toast.style.fontSize = "14px";
  toast.style.fontWeight = "600";
  toast.style.zIndex = "9999";
  toast.style.boxShadow = "0 8px 32px rgba(0,0,0,0.4)";
  toast.style.transition = "all 0.3s ease";

  if (type === "success") {
    toast.style.background = "#10b981";
    toast.style.color = "#fff";
  } else if (type === "error") {
    toast.style.background = "#ef4444";
    toast.style.color = "#fff";
  } else {
    toast.style.background = "#6366f1";
    toast.style.color = "#fff";
  }

  toast.innerText = msg;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
