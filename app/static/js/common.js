/* 公共工具：请求封装、提示、弹窗、学科 tab、格式化。 */
(function () {
  'use strict';

  const CC = (window.CC = window.CC || {});

  CC.skillLabels = {
    tutor_hint: '解题引导',
    homework_grade: '作业批改',
    wrong_explain: '错题讲解',
    care_chat: '关怀式对话',
    learning_profile: '学习画像',
    grade_override: '教师改分',
    mark_wrong: '标记判错',
    undo_mark_wrong: '撤销判错'
  };

  CC.skillLabel = function (key) {
    if (!key) return '—';
    return CC.skillLabels[key] || key;
  };

  CC.escape = function (value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };

  CC.api = async function (path, options) {
    const opts = Object.assign({ method: 'GET', credentials: 'same-origin' }, options || {});
    if (opts.body && typeof opts.body !== 'string') {
      opts.headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
      opts.body = JSON.stringify(opts.body);
    }
    const response = await fetch(path, opts);
    let data = {};
    try {
      data = await response.json();
    } catch (error) {
      data = {};
    }
    if (!response.ok) {
      if (response.status === 401 && window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
      const err = new Error(data.error || '请求失败，请稍后重试');
      err.status = response.status;
      err.code = data.error_code;
      err.data = data;
      throw err;
    }
    return data;
  };

  CC.toast = function (message, type) {
    const root = document.getElementById('toast-root');
    if (!root) return;
    const node = document.createElement('div');
    node.className = 'toast' + (type ? ' ' + type : '');
    node.textContent = message;
    root.appendChild(node);
    setTimeout(function () {
      node.remove();
    }, 2600);
  };

  CC.openModal = function (id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove('hidden');
  };

  CC.closeModal = function (id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add('hidden');
  };

  document.addEventListener('click', function (event) {
    const closer = event.target.closest('[data-close]');
    if (closer) {
      CC.closeModal(closer.getAttribute('data-close'));
    }
  });

  CC.setSubjectTabs = function (containerId, initial, onChange) {
    const container = document.getElementById(containerId);
    if (!container) return { get: function () { return initial; } };
    let current = initial;
    const tabs = Array.prototype.slice.call(container.querySelectorAll('.subject-tab'));
    if (!tabs.some(function (tab) { return tab.dataset.subject === current; }) && tabs.length) {
      current = tabs[0].dataset.subject;
    }
    tabs.forEach(function (tab) {
      tab.classList.toggle('active', tab.dataset.subject === current);
      tab.addEventListener('click', function () {
        if (tab.dataset.subject === current) return;
        current = tab.dataset.subject;
        tabs.forEach(function (other) {
          other.classList.toggle('active', other === tab);
        });
        onChange(current);
      });
    });
    return {
      get: function () { return current; },
      set: function (value) {
        current = value;
        tabs.forEach(function (tab) {
          tab.classList.toggle('active', tab.dataset.subject === value);
        });
      }
    };
  };

  CC.pad = function (value) {
    return String(value).padStart(2, '0');
  };

  CC.fmtDate = function (iso) {
    if (!iso) return '—';
    const moment = new Date(iso);
    if (Number.isNaN(moment.getTime())) return '—';
    return moment.getFullYear() + '-' + CC.pad(moment.getMonth() + 1) + '-' + CC.pad(moment.getDate()) +
      ' ' + CC.pad(moment.getHours()) + ':' + CC.pad(moment.getMinutes());
  };

  CC.fmtShortDate = function (iso) {
    if (!iso) return '—';
    const moment = new Date(iso);
    if (Number.isNaN(moment.getTime())) return '—';
    return CC.pad(moment.getMonth() + 1) + '-' + CC.pad(moment.getDate());
  };

  CC.fmtScore = function (value) {
    return value == null ? '—' : String(value);
  };

  CC.fmtRate = function (value) {
    if (value == null) return '暂无数据';
    return Math.round(value * 1000) / 10 + '%';
  };

  CC.statusMeta = function (status) {
    const table = {
      pending: { label: '排队中', cls: 'badge-warn' },
      grading: { label: '批改中', cls: 'badge-info' },
      graded: { label: '已完成', cls: 'badge-ok' },
      failed: { label: '批改失败', cls: 'badge-danger' }
    };
    return table[status] || { label: status || '未知', cls: 'badge-neutral' };
  };

  CC.statusBadge = function (status) {
    const meta = CC.statusMeta(status);
    return '<span class="badge ' + meta.cls + '">' + CC.escape(meta.label) + '</span>';
  };

  CC.truncate = function (value, length) {
    const text = String(value == null ? '' : value);
    return text.length > length ? text.slice(0, length) + '…' : text;
  };

  CC.emptyRow = function (text) {
    return '<div class="empty"><div class="empty-icon">📭</div><div class="empty-title">' +
      CC.escape(text) + '</div></div>';
  };

  CC.newKey = function () {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    return 'k-' + Date.now() + '-' + Math.random().toString(16).slice(2, 10);
  };

  CC.scrollToBottom = function (element) {
    if (element) element.scrollTop = element.scrollHeight;
  };

  CC.readStream = async function (response, onEvent) {
    if (!response.body || !response.body.getReader) {
      const text = await response.text();
      text.split('\n\n').forEach(function (block) {
        CC.parseBlock(block, onEvent);
      });
      return;
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true }).replace(/\r/g, '');
      let index = buffer.indexOf('\n\n');
      while (index >= 0) {
        const block = buffer.slice(0, index);
        buffer = buffer.slice(index + 2);
        CC.parseBlock(block, onEvent);
        index = buffer.indexOf('\n\n');
      }
    }
  };

  CC.parseBlock = function (block, onEvent) {
    let eventName = 'message';
    let data = '';
    block.split('\n').forEach(function (line) {
      if (!line || line.startsWith(':')) return;
      if (line.startsWith('event:')) eventName = line.slice(6).trim();
      else if (line.startsWith('data:')) data += line.slice(5).trim();
    });
    if (!data) return;
    let payload;
    try {
      payload = JSON.parse(data);
    } catch (error) {
      return;
    }
    onEvent(eventName, payload);
  };
})();
