/* 学生端页面交互。 */
(function () {
  'use strict';

  const page = document.body.dataset.page;
  const state = {
    knowledgeSubject: '数学',
    chatSubject: '数学',
    submitSubject: '数学',
    mistakeSubject: '数学',
    assignments: [],
    watching: new Map()
  };

  function init() {
    if (page === 'student-dashboard') initDashboard();
    else if (page === 'student-knowledge') initKnowledge();
    else if (page === 'student-chat') initChat();
    else if (page === 'student-submit') initSubmit();
    else if (page === 'student-mistakes') initMistakes();
    else if (page === 'student-care') initCare();
    else if (page === 'student-analytics') initAnalytics();
  }

  /* ===== 本班首页 ===== */
  async function initDashboard() {
    try {
      const data = await CC.api('/api/student/dashboard');
      const stats = data.stats || {};
      setText('stat-unsubmitted', stats.unsubmitted);
      setText('stat-graded', stats.graded);
      setText('stat-wrong', stats.wrong);
      setText('stat-questions', stats.questions);
      const list = document.getElementById('upcoming-list');
      if (!list) return;
      if (!data.upcoming.length) {
        list.innerHTML = CC.emptyRow('暂无进行中的作业');
        return;
      }
      list.innerHTML = data.upcoming.map(function (item) {
        const status = item.submission_status === 'unsubmitted'
          ? '<span class="badge badge-warn">待提交</span>'
          : CC.statusBadge(item.submission_status);
        return '<div class="list-row">' +
          '<div><div class="list-title">' + CC.escape(item.title) + '</div>' +
          '<div class="list-desc">' + CC.escape(item.subject) + ' · ' + CC.escape(CC.truncate(item.description, 60)) + '</div>' +
          '<div class="meta">截止 ' + CC.fmtDate(item.deadline) + '</div></div>' +
          '<div class="row gap-8">' + status +
          '<a class="btn btn-outline btn-sm" href="/student/submit">去提交</a></div></div>';
      }).join('');
    } catch (error) {
      CC.toast(error.message, 'error');
    }
  }

  /* ===== 讲义与检索 ===== */
  function initKnowledge() {
    const tabs = CC.setSubjectTabs('knowledge-tabs', state.knowledgeSubject, function (subject) {
      state.knowledgeSubject = subject;
      resetSearch();
      loadMaterials();
    });
    state.knowledgeSubject = tabs.get();
    loadMaterials();

    const searchBtn = document.getElementById('knowledge-search-btn');
    const searchInput = document.getElementById('knowledge-search-input');
    if (searchBtn) searchBtn.addEventListener('click', doSearch);
    if (searchInput) {
      searchInput.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') doSearch();
      });
    }
  }

  function resetSearch() {
    document.getElementById('knowledge-search-input').value = '';
    document.getElementById('search-results').innerHTML = '';
    document.getElementById('search-empty').classList.add('hidden');
  }

  async function doSearch() {
    const input = document.getElementById('knowledge-search-input');
    const query = input.value.trim();
    const results = document.getElementById('search-results');
    const empty = document.getElementById('search-empty');
    if (!query) {
      results.innerHTML = '';
      empty.classList.add('hidden');
      return;
    }
    results.innerHTML = '<div class="muted small">检索中…</div>';
    empty.classList.add('hidden');
    try {
      const data = await CC.api('/api/materials/search?subject=' +
        encodeURIComponent(state.knowledgeSubject) + '&q=' + encodeURIComponent(query));
      if (!data.items.length) {
        results.innerHTML = '';
        empty.classList.remove('hidden');
        return;
      }
      results.innerHTML = data.items.map(function (hit) {
        return '<div class="list-row">' +
          '<div><div class="list-title">' + CC.escape(hit.text) + '</div>' +
          '<div class="meta">来源：《' + CC.escape(hit.material_title) + '》 · 第 ' + hit.chunk_no +
          ' 段 · 相关度 ' + hit.relevance + '</div></div>' +
          '<button class="btn btn-outline btn-sm" data-open-material="' + hit.material_id + '">查看讲义</button>' +
          '</div>';
      }).join('');
      bindMaterialButtons(results);
    } catch (error) {
      results.innerHTML = '<div class="muted small">' + CC.escape(error.message) + '</div>';
    }
  }

  async function loadMaterials() {
    const list = document.getElementById('knowledge-material-list');
    const empty = document.getElementById('knowledge-material-empty');
    const total = document.getElementById('material-total');
    if (!list) return;
    list.innerHTML = '<div class="muted small">加载中…</div>';
    try {
      const data = await CC.api('/api/materials?subject=' + encodeURIComponent(state.knowledgeSubject));
      if (total) total.textContent = '共 ' + data.total + ' 份';
      if (!data.items.length) {
        list.innerHTML = '';
        empty.classList.remove('hidden');
        return;
      }
      empty.classList.add('hidden');
      list.innerHTML = data.items.map(function (item) {
        return '<div class="list-row">' +
          '<div><div class="list-title">' + CC.escape(item.title) + '</div>' +
          '<div class="meta">' + CC.escape(item.subject) + ' · ' + item.chunk_count +
          ' 个片段 · ' + CC.fmtDate(item.created_at) + '</div></div>' +
          '<button class="btn btn-outline btn-sm" data-open-material="' + item.id + '">查看讲义</button>' +
          '</div>';
      }).join('');
      bindMaterialButtons(list);
    } catch (error) {
      list.innerHTML = '<div class="muted small">' + CC.escape(error.message) + '</div>';
    }
  }

  function bindMaterialButtons(container) {
    container.querySelectorAll('[data-open-material]').forEach(function (button) {
      button.addEventListener('click', function () {
        openMaterial(Number(button.dataset.openMaterial));
      });
    });
  }

  async function openMaterial(id) {
    try {
      const data = await CC.api('/api/materials/' + id);
      const material = data.material;
      document.getElementById('material-view-title').textContent = material.title;
      document.getElementById('material-view-body').innerHTML =
        '<div class="muted small">' + CC.escape(material.subject) + ' · ' + material.chunk_count +
        ' 个知识库片段 · ' + CC.fmtDate(material.created_at) + '</div>' +
        '<div class="divider"></div>' +
        '<div class="list-stack">' + material.chunks.map(function (chunk) {
          return '<div class="list-row"><div><div class="list-title">片段 ' + chunk.chunk_no + '</div>' +
            '<div class="list-desc">' + CC.escape(chunk.text) + '</div></div></div>';
        }).join('') + '</div>';
      CC.openModal('material-view-modal');
    } catch (error) {
      CC.toast(error.message, 'error');
    }
  }

  /* ===== 助手对话 ===== */
  function initChat() {
    const tabs = CC.setSubjectTabs('chat-tabs', state.chatSubject, function (subject) {
      state.chatSubject = subject;
      loadChatHistory();
    });
    state.chatSubject = tabs.get();
    loadChatSkillStatus();
    loadChatHistory();

    const sendBtn = document.getElementById('chat-send');
    const input = document.getElementById('chat-input');
    if (sendBtn) sendBtn.addEventListener('click', sendChat);
    if (input) {
      input.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault();
          sendChat();
        }
      });
    }
  }

  async function loadChatSkillStatus() {
    const badge = document.getElementById('chat-skill-status');
    try {
      const data = await CC.api('/api/skills');
      const tutor = (data.items || []).find(function (item) { return item.skill_key === 'tutor_hint'; });
      if (tutor) {
        badge.textContent = tutor.name + ' · ' + (tutor.enabled ? '已开启' : '已关闭');
        badge.className = 'badge ' + (tutor.enabled ? 'badge-ok' : 'badge-neutral');
      } else {
        badge.textContent = '未配置解题引导技能';
        badge.className = 'badge badge-neutral';
      }
    } catch (error) {
      badge.textContent = '技能状态加载失败';
      badge.className = 'badge badge-danger';
    }
  }

  async function loadChatHistory() {
    const box = document.getElementById('chat-messages');
    if (!box) return;
    box.innerHTML = '<div class="muted small">加载中…</div>';
    try {
      const data = await CC.api('/api/chat?subject=' + encodeURIComponent(state.chatSubject));
      if (!data.items.length) {
        renderChatWelcome();
        return;
      }
      box.innerHTML = '';
      data.items.forEach(function (message) {
        if (message.role === 'user') {
          appendChatBubble('user', message.content, {});
        } else {
          appendChatBubble('assistant', message.content, {
            trace: message.trace,
            sources: message.sources,
            skill: message.skill_key
          });
        }
      });
      CC.scrollToBottom(box);
    } catch (error) {
      box.innerHTML = '<div class="muted small">' + CC.escape(error.message) + '</div>';
    }
  }

  function renderChatWelcome() {
    const box = document.getElementById('chat-messages');
    box.innerHTML = '<div class="chat-welcome">' +
      '<div style="font-size:34px">💬</div>' +
      '<div class="section-title" style="justify-content:center;margin-top:10px">向 ' +
      CC.escape(state.chatSubject) + ' 助手提问</div>' +
      '<div class="muted small">回答会标注本班讲义来源；未命中时会明确说明，不伪造来源。</div>' +
      '<div class="chat-suggests">' +
      '<button class="chat-suggest" data-suggest="求根公式怎么推导？有什么使用条件？">求根公式怎么推导？有什么使用条件？</button>' +
      '<button class="chat-suggest" data-suggest="怎么判断一元二次方程的判别式符号？">怎么判断一元二次方程的判别式符号？</button>' +
      '<button class="chat-suggest" data-suggest="帮我梳理这一章的常见易错点。">帮我梳理这一章的常见易错点。</button>' +
      '</div></div>';
    box.querySelectorAll('[data-suggest]').forEach(function (button) {
      button.addEventListener('click', function () {
        document.getElementById('chat-input').value = button.dataset.suggest;
        sendChat();
      });
    });
  }

  function appendChatBubble(role, content, options) {
    const box = document.getElementById('chat-messages');
    if (box.querySelector('.chat-welcome')) box.innerHTML = '';
    const row = document.createElement('div');
    row.className = 'bubble-row ' + role;
    row.innerHTML = '<div class="bubble-avatar">' + (role === 'user' ? '🧑‍🎓' : '🤖') + '</div>' +
      '<div class="bubble"><div class="trace-slot"></div><div class="bubble-content"></div>' +
      '<div class="sources-slot"></div></div>';
    const bubble = row.querySelector('.bubble');
    const contentNode = row.querySelector('.bubble-content');
    contentNode.textContent = content || '';
    if (options.trace && options.trace.length) {
      row.querySelector('.trace-slot').innerHTML = traceHtml(options.trace, true);
    }
    if (options.sources && options.sources.length) {
      row.querySelector('.sources-slot').innerHTML = sourcesHtml(options.sources);
    }
    box.appendChild(row);
    CC.scrollToBottom(box);
    return { row: row, bubble: bubble, content: contentNode };
  }

  function traceHtml(steps, finished) {
    const list = steps.map(function (step, index) {
      const done = step.done || (finished && index === steps.length - 1);
      return '<div class="trace-step' + (done ? ' done' : '') + '">' +
        '<span class="trace-ic">' + (done ? '✓' : '…') + '</span>' +
        '<div><div class="trace-label">' + CC.escape(step.label) + '</div>' +
        '<div class="trace-detail">' + CC.escape(step.detail) + '</div></div></div>';
    }).join('');
    return '<div class="trace"><div class="trace-head">' +
      '<span class="trace-title">执行过程</span>' +
      '<span class="trace-status' + (finished ? ' done' : '') + '">' +
      (finished ? '完成' : '执行中…') + '</span></div>' +
      '<div class="trace-steps">' + list + '</div></div>';
  }

  function sourcesHtml(sources) {
    return '<div class="bubble-sources"><span class="muted">来源：</span>' +
      sources.map(function (hit) {
        return '<span class="source-chip" data-source-material="' + hit.material_id +
          '" data-source-chunk="' + hit.chunk_no + '">《' + CC.escape(hit.material_title) +
          '》段' + hit.chunk_no + '</span>';
      }).join('') + '</div>';
  }

  async function sendChat() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');
    const box = document.getElementById('chat-messages');
    const message = input.value.trim();
    if (!message) return;
    if (message.length > 2000) {
      CC.toast('提问必须为 1—2000 字符', 'error');
      return;
    }
    input.value = '';
    sendBtn.disabled = true;
    appendChatBubble('user', message, {});
    const placeholder = appendChatBubble('assistant', '', {});
    placeholder.content.innerHTML = '<span class="cursor">▍</span>';
    let accumulated = '';
    let sources = [];

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject: state.chatSubject, message: message })
      });
      if (!response.ok) {
        const data = await response.json().catch(function () { return {}; });
        throw new Error(data.error || '助手暂时无法回答，请稍后再试');
      }
      await CC.readStream(response, function (event, payload) {
        if (event === 'trace') {
          placeholder.row.querySelector('.trace-slot').innerHTML = traceHtml(payload.steps || [], false);
        } else if (event === 'sources') {
          sources = payload || [];
        } else if (event === 'delta') {
          accumulated += payload.text || '';
          placeholder.content.textContent = accumulated;
          CC.scrollToBottom(box);
        } else if (event === 'done') {
          placeholder.row.querySelector('.trace-slot').innerHTML =
            traceHtml(payload.trace || [], false) === '' ? '' : placeholder.row.querySelector('.trace-slot').innerHTML;
          const status = placeholder.row.querySelector('.trace-status');
          if (status) {
            status.classList.add('done');
            status.textContent = '完成';
          }
          placeholder.row.querySelectorAll('.trace-step').forEach(function (step) {
            step.classList.add('done');
            const mark = step.querySelector('.trace-ic');
            if (mark) mark.textContent = '✓';
          });
          placeholder.row.querySelector('.sources-slot').innerHTML = sources.length ? sourcesHtml(sources) : '';
          if (payload.matched === false && !accumulated) {
            placeholder.content.textContent = '本班知识库未命中相关讲义。';
          }
        }
      });
      bindSourceChips(placeholder.row);
      CC.scrollToBottom(box);
    } catch (error) {
      placeholder.content.textContent = '抱歉，助手暂时无法回答。请稍后再试，或先查阅本班讲义。';
      CC.toast(error.message, 'error');
    } finally {
      sendBtn.disabled = false;
    }
  }

  function bindSourceChips(container) {
    container.querySelectorAll('.source-chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        showChunk(Number(chip.dataset.sourceMaterial), Number(chip.dataset.sourceChunk));
      });
    });
  }

  async function showChunk(materialId, chunkNo) {
    try {
      const data = await CC.api('/api/materials/' + materialId);
      const chunk = (data.material.chunks || []).find(function (item) { return item.chunk_no === chunkNo; });
      const title = document.getElementById('source-modal-title');
      const body = document.getElementById('source-modal-body');
      if (!title || !body) {
        CC.toast('《' + data.material.title + '》第 ' + chunkNo + ' 段：' + ((chunk && chunk.text) || ''), 'ok');
        return;
      }
      title.textContent = '《' + data.material.title + '》第 ' + chunkNo + ' 段';
      body.innerHTML = '<div class="graded-answer">' +
        CC.escape(chunk ? chunk.text : '该片段不存在') + '</div>' +
        '<div class="muted small mt-12">来源为该讲义的真实切片，助手不会跨班或凭空引用。</div>';
      CC.openModal('source-modal');
    } catch (error) {
      CC.toast(error.message, 'error');
    }
  }

  /* ===== 交作业 ===== */
  function initSubmit() {
    const tabs = CC.setSubjectTabs('submit-tabs', state.submitSubject, function (subject) {
      state.submitSubject = subject;
      loadAssignments();
    });
    state.submitSubject = tabs.get();
    loadAssignments();

    const confirmBtn = document.getElementById('submit-confirm');
    if (confirmBtn) confirmBtn.addEventListener('click', confirmSubmit);
  }

  async function loadAssignments() {
    const list = document.getElementById('assignment-list');
    const empty = document.getElementById('submit-empty');
    if (!list) return;
    list.innerHTML = '<div class="muted small">加载中…</div>';
    try {
      const data = await CC.api('/api/assignments?subject=' + encodeURIComponent(state.submitSubject));
      state.assignments = data.items || [];
      if (!state.assignments.length) {
        list.innerHTML = '';
        empty.classList.remove('hidden');
        return;
      }
      empty.classList.add('hidden');
      renderAssignments();
    } catch (error) {
      list.innerHTML = '<div class="muted small">' + CC.escape(error.message) + '</div>';
    }
  }

  function renderAssignments() {
    stopAllWatching();
    const list = document.getElementById('assignment-list');
    list.innerHTML = state.assignments.map(assignmentCard).join('');

    list.querySelectorAll('[data-submit]').forEach(function (button) {
      button.addEventListener('click', function () { openSubmit(button.dataset.submit); });
    });
    list.querySelectorAll('[data-retry-submit]').forEach(function (button) {
      button.addEventListener('click', function () { retrySubmission(button.dataset.retrySubmit); });
    });
    bindEvidenceButtons(list);
    bindSourceChips(list);

    state.assignments.forEach(function (assignment) {
      if (assignment.submission && ['pending', 'grading'].indexOf(assignment.submission.status) >= 0) {
        watchSubmission(assignment.id, assignment.submission.id);
      }
    });
  }

  function assignmentCard(item) {
    const submission = item.submission;
    const statusBadge = submission
      ? CC.statusBadge(submission.status)
      : '<span class="badge ' + (item.closed ? 'badge-neutral' : 'badge-warn') + '">' +
        (item.closed ? '已截止' : '待提交') + '</span>';
    const action = submission || item.closed
      ? ''
      : '<button class="btn btn-primary btn-sm" data-submit="' + item.id + '">提交作答</button>';
    return '<div class="assignment-card" data-assignment-id="' + item.id + '">' +
      '<div class="assignment-head">' +
      '<div><div class="assignment-title">' + CC.escape(item.title) + '</div>' +
      '<div class="assignment-desc">' + CC.escape(item.description) + '</div>' +
      '<div class="assignment-meta"><span>截止 ' + CC.fmtDate(item.deadline) + '</span>' +
      '<span data-status-slot>' + statusBadge + '</span></div></div>' +
      '<div>' + action + '</div></div>' +
      '<div class="assignment-body">' + submissionBody(submission, item) + '</div></div>';
  }

  function submissionBody(submission) {
    if (!submission) return '';
    if (submission.status === 'pending' || submission.status === 'grading') {
      return '<div class="grading-box"><span class="spinner"></span>' +
        (submission.status === 'pending' ? '已进入批改队列，等待助手开始…' : '助手正在批改你的作答…') +
        '</div><div class="muted small mt-8">状态会实时更新，刷新页面也不会丢失。</div>';
    }
    if (submission.status === 'failed') {
      return '<div class="notice notice-danger">' + CC.escape(submission.error_message || '批改失败') + '</div>' +
        '<div class="mt-12"><button class="btn btn-outline btn-sm" data-retry-submit="' + submission.id +
        '">重新批改</button></div>';
    }
    const teacher = submission.teacher_score != null;
    const comment = teacher ? submission.teacher_comment : submission.ai_comment;
    const evidence = submission.ai_evidence || [];
    return '<div class="grade-row">' +
      '<div class="score">' + CC.fmtScore(submission.final_score) + '</div>' +
      '<div style="flex:1;min-width:220px">' +
      '<span class="badge badge-brand">' + (teacher ? '教师终评' : 'AI 初评') + '</span>' +
      '<div class="muted small mt-8">AI 初评：' + CC.fmtScore(submission.ai_score) + ' 分' +
      (teacher ? ' · 教师终评：' + submission.teacher_score + ' 分' : '') + '</div>' +
      '<div class="graded-comment mt-8">' + CC.escape(comment || '暂无评语') + '</div>' +
      '<div class="evidence-row">' + (evidence.length
        ? evidence.map(function (hit, index) {
          return '<span class="tag" data-evidence="' + index + '" data-assignment="' +
            submission.assignment_id + '">《' + CC.escape(hit.material_title) + '》段' + hit.chunk_no + '</span>';
        }).join('')
        : '<span class="muted small">本班知识库未命中讲义，评语未引用来源。</span>') +
      '</div></div></div>' +
      '<div class="divider"></div>' +
      '<div class="muted small">我的作答</div>' +
      '<div class="graded-answer mt-8">' + CC.escape(submission.content) + '</div>';
  }

  function bindEvidenceButtons(container) {
    container.querySelectorAll('[data-evidence]').forEach(function (chip) {
      chip.addEventListener('click', function () {
        const assignment = state.assignments.find(function (item) {
          return String(item.id) === String(chip.dataset.assignment) ||
            (item.submission && String(item.submission.assignment_id) === String(chip.dataset.assignment));
        });
        if (!assignment || !assignment.submission) return;
        const hit = (assignment.submission.ai_evidence || [])[Number(chip.dataset.evidence)];
        if (hit) showChunk(hit.material_id, hit.chunk_no);
      });
    });
  }

  function watchSubmission(assignmentId, submissionId) {
    if (state.watching.has(String(submissionId))) return;
    const es = new EventSource('/api/submissions/' + submissionId + '/stream');
    const entry = { es: es, timer: null };
    state.watching.set(String(submissionId), entry);
    es.addEventListener('status', function (event) {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch (error) {
        return;
      }
      applySubmissionStatus(assignmentId, payload, submissionId);
    });
    es.onerror = function () {
      es.close();
      startPolling(assignmentId, submissionId);
    };
  }

  function startPolling(assignmentId, submissionId) {
    const entry = state.watching.get(String(submissionId)) || {};
    if (entry.timer) return;
    if (entry.es) entry.es.close();
    entry.timer = setInterval(async function () {
      try {
        const data = await CC.api('/api/submissions/' + submissionId);
        applySubmissionStatus(assignmentId, data.submission, submissionId);
      } catch (error) {
        stopWatching(submissionId);
      }
    }, 3000);
    state.watching.set(String(submissionId), entry);
  }

  function applySubmissionStatus(assignmentId, submission, submissionId) {
    const assignment = state.assignments.find(function (item) { return String(item.id) === String(assignmentId); });
    if (!assignment) return;
    assignment.submission = submission;
    if (['graded', 'failed'].indexOf(submission.status) >= 0) {
      stopWatching(submissionId);
      renderAssignments();
      CC.toast(submission.status === 'graded' ? '批改完成，可查看到评分与评语' :
        '批改失败，可点击重新批改', submission.status === 'graded' ? 'ok' : 'error');
      return;
    }
    const card = document.querySelector('.assignment-card[data-assignment-id="' + assignmentId + '"]');
    if (!card) return;
    const slot = card.querySelector('[data-status-slot]');
    if (slot) slot.innerHTML = CC.statusBadge(submission.status);
    const body = card.querySelector('.assignment-body');
    if (body) body.innerHTML = submissionBody(submission);
    bindEvidenceButtons(card);
    bindSourceChips(card);
  }

  function stopWatching(submissionId) {
    const entry = state.watching.get(String(submissionId));
    if (!entry) return;
    if (entry.es) entry.es.close();
    if (entry.timer) clearInterval(entry.timer);
    state.watching.delete(String(submissionId));
  }

  function stopAllWatching() {
    state.watching.forEach(function (entry) {
      if (entry.es) entry.es.close();
      if (entry.timer) clearInterval(entry.timer);
    });
    state.watching.clear();
  }

  function openSubmit(id) {
    const assignment = state.assignments.find(function (item) { return String(item.id) === String(id); });
    if (!assignment) return;
    document.getElementById('submit-assignment-id').value = assignment.id;
    document.getElementById('submit-modal-title').textContent = '提交作业 · ' + assignment.title;
    document.getElementById('submit-assignment-desc').textContent = assignment.description || '（无题目描述）';
    document.getElementById('submit-content').value = '';
    document.getElementById('submit-error').classList.add('hidden');
    CC.openModal('submit-modal');
  }

  async function confirmSubmit() {
    const id = document.getElementById('submit-assignment-id').value;
    const content = document.getElementById('submit-content').value.trim();
    const errorBox = document.getElementById('submit-error');
    if (!content || content.length > 5000) {
      errorBox.textContent = '作答内容必须为 1—5000 字符';
      errorBox.classList.remove('hidden');
      return;
    }
    const button = document.getElementById('submit-confirm');
    button.disabled = true;
    try {
      await CC.api('/api/assignments/' + id + '/submit', {
        method: 'POST',
        body: { content: content, idempotency_key: CC.newKey() }
      });
      CC.closeModal('submit-modal');
      CC.toast('提交成功，已进入异步批改队列', 'ok');
      loadAssignments();
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.classList.remove('hidden');
    } finally {
      button.disabled = false;
    }
  }

  async function retrySubmission(id) {
    try {
      await CC.api('/api/submissions/' + id + '/retry', { method: 'POST' });
      CC.toast('已重新加入批改队列', 'ok');
      loadAssignments();
    } catch (error) {
      CC.toast(error.message, 'error');
    }
  }

  /* ===== 错题 ===== */
  function initMistakes() {
    const tabs = CC.setSubjectTabs('mistake-tabs', state.mistakeSubject, function (subject) {
      state.mistakeSubject = subject;
      loadWrongQuestions();
    });
    state.mistakeSubject = tabs.get();
    loadWrongQuestions();
  }

  async function loadWrongQuestions() {
    const list = document.getElementById('wrong-list');
    const empty = document.getElementById('wrong-empty');
    if (!list) return;
    list.innerHTML = '<div class="muted small">加载中…</div>';
    try {
      const data = await CC.api('/api/wrong-questions?subject=' + encodeURIComponent(state.mistakeSubject));
      if (!data.items.length) {
        list.innerHTML = '';
        empty.classList.remove('hidden');
        return;
      }
      empty.classList.add('hidden');
      list.innerHTML = data.items.map(wrongCard).join('');
      list.querySelectorAll('[data-explain]').forEach(function (button) {
        button.addEventListener('click', function () { explainWrong(button.dataset.explain, button); });
      });
      bindSourceChips(list);
    } catch (error) {
      list.innerHTML = '<div class="muted small">' + CC.escape(error.message) + '</div>';
    }
  }

  function wrongCard(item) {
    return '<div class="assignment-card" data-wrong-id="' + item.id + '">' +
      '<div class="assignment-head">' +
      '<div><div class="assignment-title wrong-question">' + CC.escape(item.question_text) + '</div>' +
      '<div class="assignment-desc">我的作答：' + CC.escape(item.my_answer) + '</div>' +
      '<div class="assignment-meta"><span>错因：' + CC.escape(item.error_reason) + '</span>' +
      '<span>' + CC.fmtDate(item.created_at) + '</span></div></div>' +
      '<button class="btn btn-primary btn-sm" data-explain="' + item.id + '">' +
      (item.explanation ? '重新讲解' : '请助手讲解') + '</button></div>' +
      '<div class="assignment-body">' + (item.explanation ? explanationHtml(item.explanation) : '') + '</div>' +
      '</div>';
  }

  function explanationHtml(explanation) {
    const points = explanation.knowledge_points || [];
    return '<div class="explain-section">' +
      '<div class="explain-title">错因分析</div>' +
      '<div class="explain-body">' + CC.escape(explanation.error_analysis) + '</div></div>' +
      '<div class="explain-section">' +
      '<div class="explain-title">相关知识点</div>' +
      '<div class="explain-body">' + (points.length
        ? points.map(function (point) {
          return '<div>· ' + CC.escape(point.title || point) +
            (point.material_title ? ' <span class="tag">《' + CC.escape(point.material_title) +
              '》段' + point.chunk_no + '</span>' : '') + '</div>';
        }).join('')
        : '<div class="muted small">本班知识库未命中相关讲义，未引用来源。</div>') +
      '</div></div>' +
      '<div class="explain-section">' +
      '<div class="explain-title">修正建议</div>' +
      '<div class="explain-body">' + CC.escape(explanation.advice) + '</div></div>' +
      (explanation.no_hit
        ? '<div class="notice notice-warn mt-12">本次讲解未命中本班讲义，仅依据题目与错因给出引导，不引用来源。</div>'
        : '');
  }

  async function explainWrong(id, button) {
    button.disabled = true;
    const original = button.textContent;
    button.textContent = '讲解生成中…';
    try {
      const data = await CC.api('/api/wrong-questions/' + id + '/explain', { method: 'POST' });
      const card = document.querySelector('.assignment-card[data-wrong-id="' + id + '"]');
      if (card) {
        card.querySelector('.assignment-body').innerHTML = explanationHtml(data.explanation);
        button.textContent = '重新讲解';
      }
      CC.toast(data.cached ? '已读取已有讲解' : '讲解已生成', 'ok');
    } catch (error) {
      button.textContent = original;
      CC.toast(error.message, 'error');
    } finally {
      button.disabled = false;
    }
  }

  /* ===== 关怀式对话 ===== */
  function initCare() {
    loadCareHistory();
    const sendBtn = document.getElementById('care-send');
    const input = document.getElementById('care-input');
    if (sendBtn) sendBtn.addEventListener('click', sendCare);
    if (input) {
      input.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault();
          sendCare();
        }
      });
    }
  }

  function disableCare() {
    const notice = document.getElementById('care-disabled');
    if (notice) notice.classList.remove('hidden');
    const input = document.getElementById('care-input');
    const send = document.getElementById('care-send');
    if (input) input.disabled = true;
    if (send) send.disabled = true;
  }

  async function loadCareHistory() {
    const box = document.getElementById('care-messages');
    if (!box) return;
    box.innerHTML = '<div class="muted small">加载中…</div>';
    try {
      const data = await CC.api('/api/care/history');
      if (!data.items.length) {
        box.innerHTML = '<div class="chat-welcome"><div style="font-size:34px">🤗</div>' +
          '<div class="section-title" style="justify-content:center;margin-top:10px">今天想聊点什么？</div>' +
          '<div class="muted small">这里不聊学科题目，只关注你的情绪与学习状态，内容仅本人可见。</div></div>';
        return;
      }
      box.innerHTML = '';
      data.items.forEach(function (message) {
        appendCareBubble(message.role, message.content, message.safety);
      });
      CC.scrollToBottom(box);
    } catch (error) {
      if (error.code === 'skill_disabled') {
        box.innerHTML = '<div class="empty"><div class="empty-icon">🔒</div>' +
          '<div class="empty-title">该能力已被教师关闭</div></div>';
        disableCare();
      } else {
        box.innerHTML = '<div class="muted small">' + CC.escape(error.message) + '</div>';
      }
    }
  }

  function appendCareBubble(role, content, safety) {
    const box = document.getElementById('care-messages');
    if (box.querySelector('.chat-welcome')) box.innerHTML = '';
    const row = document.createElement('div');
    row.className = 'bubble-row ' + role;
    row.innerHTML = '<div class="bubble-avatar">' + (role === 'user' ? '🧑‍🎓' : '🤗') + '</div>' +
      '<div class="bubble"><div class="bubble-content"></div></div>';
    row.querySelector('.bubble-content').textContent = content;
    if (safety && role === 'assistant') {
      const notice = document.createElement('div');
      notice.className = 'notice notice-warn mt-8';
      notice.textContent = '已触发安全提示：请优先保证自身安全，及时联系信任的人或专业求助渠道。';
      row.querySelector('.bubble').appendChild(notice);
    }
    box.appendChild(row);
    CC.scrollToBottom(box);
    return row;
  }

  async function sendCare() {
    const input = document.getElementById('care-input');
    const sendBtn = document.getElementById('care-send');
    const message = input.value.trim();
    if (!message) return;
    if (message.length > 1000) {
      CC.toast('消息必须为 1—1000 字符', 'error');
      return;
    }
    input.value = '';
    sendBtn.disabled = true;
    appendCareBubble('user', message, false);
    try {
      const data = await CC.api('/api/care/chat', {
        method: 'POST',
        body: { message: message }
      });
      appendCareBubble('assistant', data.reply.content, data.risk);
    } catch (error) {
      if (error.code === 'skill_disabled') {
        disableCare();
      }
      CC.toast(error.message, 'error');
    } finally {
      sendBtn.disabled = false;
    }
  }

  /* ===== 学情分析 ===== */
  async function initAnalytics() {
    try {
      const data = await CC.api('/api/analytics/me');
      const metrics = data.metrics || {};
      setText('stat-questions', metrics.questions);
      setText('stat-submissions', metrics.submissions);
      setText('stat-correct', metrics.correct_rate == null ? '暂无数据' : CC.fmtRate(metrics.correct_rate));
      setText('stat-wrong', metrics.wrong_questions);

      renderRadar(data.mastery || {});
      renderTrend(data.trend || []);
      renderHeat(data.heat || {});
      renderProfile(data);
    } catch (error) {
      CC.toast(error.message, 'error');
    }
  }

  function renderRadar(mastery) {
    const subjects = Object.keys(mastery);
    const cx = 160;
    const cy = 140;
    const radius = 95;
    let svg = '<svg class="radar" width="320" height="280" viewBox="0 0 320 280">';

    [0.33, 0.66, 1].forEach(function (ratio) {
      const points = subjects.map(function (_, index) {
        const angle = (-90 + index * (360 / subjects.length)) * Math.PI / 180;
        return (cx + Math.cos(angle) * radius * ratio) + ',' + (cy + Math.sin(angle) * radius * ratio);
      }).join(' ');
      svg += '<polygon class="radar-ring" points="' + points + '"></polygon>';
    });

    subjects.forEach(function (subject, index) {
      const angle = (-90 + index * (360 / subjects.length)) * Math.PI / 180;
      svg += '<line class="radar-axis" x1="' + cx + '" y1="' + cy + '" x2="' +
        (cx + Math.cos(angle) * radius) + '" y2="' + (cy + Math.sin(angle) * radius) + '"></line>';
      const lx = cx + Math.cos(angle) * (radius + 28);
      const ly = cy + Math.sin(angle) * (radius + 28);
      const anchor = Math.cos(angle) > 0.25 ? 'start' : (Math.cos(angle) < -0.25 ? 'end' : 'middle');
      svg += '<text class="radar-label" x="' + lx + '" y="' + (ly + 4) + '" text-anchor="' + anchor + '">' +
        CC.escape(subject) + '</text>';
    });

    const dataPoints = [];
    subjects.forEach(function (subject, index) {
      const value = mastery[subject];
      if (value == null) return;
      const angle = (-90 + index * (360 / subjects.length)) * Math.PI / 180;
      const ratio = Math.max(0, Math.min(100, value)) / 100;
      dataPoints.push({
        x: cx + Math.cos(angle) * radius * ratio,
        y: cy + Math.sin(angle) * radius * ratio,
        subject: subject,
        value: value
      });
    });

    if (dataPoints.length >= 3) {
      svg += '<polygon class="radar-area" points="' +
        dataPoints.map(function (point) { return point.x + ',' + point.y; }).join(' ') + '"></polygon>';
    }
    dataPoints.forEach(function (point) {
      svg += '<circle class="radar-dot" cx="' + point.x + '" cy="' + point.y + '" r="4"></circle>';
    });
    svg += '</svg>';
    document.getElementById('radar-container').innerHTML = svg;

    document.getElementById('mastery-legend').innerHTML = subjects.map(function (subject) {
      const value = mastery[subject];
      return '<div class="mastery-row"><span>' + CC.escape(subject) + '</span>' +
        '<span class="mastery-value">' + (value == null ? '暂无数据' : value + ' 分') + '</span></div>';
    }).join('') + '<div class="muted small mt-8">无数据学科留空，不补 0。</div>';
  }

  function renderTrend(trend) {
    const container = document.getElementById('trend-container');
    const empty = document.getElementById('trend-empty');
    const points = trend.filter(function (item) { return item.score != null; });
    if (!points.length) {
      container.innerHTML = '';
      empty.classList.remove('hidden');
      return;
    }
    empty.classList.add('hidden');
    const width = 520;
    const height = 220;
    const padL = 40;
    const padR = 18;
    const padT = 18;
    const padB = 34;
    const plotW = width - padL - padR;
    const plotH = height - padT - padB;
    const xOf = function (index) {
      if (points.length === 1) return padL + plotW / 2;
      return padL + (index / (points.length - 1)) * plotW;
    };
    const yOf = function (score) {
      return padT + (1 - Math.max(0, Math.min(100, score)) / 100) * plotH;
    };

    let svg = '<svg class="spark" width="' + width + '" height="' + height + '" viewBox="0 0 ' +
      width + ' ' + height + '">';
    [0, 25, 50, 75, 100].forEach(function (value) {
      const y = yOf(value);
      svg += '<line x1="' + padL + '" y1="' + y + '" x2="' + (width - padR) + '" y2="' + y +
        '" stroke="var(--border)" stroke-width="1"></line>';
      svg += '<text x="' + (padL - 8) + '" y="' + (y + 4) + '" text-anchor="end" font-size="11" fill="var(--text-3)">' +
        value + '</text>';
    });
    const linePoints = points.map(function (item, index) {
      return xOf(index) + ',' + yOf(item.score);
    }).join(' ');
    svg += '<polyline class="spark-line" points="' + linePoints + '"></polyline>';
    points.forEach(function (item, index) {
      svg += '<circle class="spark-dot" cx="' + xOf(index) + '" cy="' + yOf(item.score) + '" r="4"></circle>';
      svg += '<text x="' + xOf(index) + '" y="' + (yOf(item.score) - 12) + '" text-anchor="middle" ' +
        'font-size="12" font-weight="700" fill="var(--brand)">' + item.score + '</text>';
    });
    points.forEach(function (item, index) {
      if (points.length > 6 && index % 2 === 1 && index !== points.length - 1) return;
      svg += '<text x="' + xOf(index) + '" y="' + (height - 10) + '" text-anchor="middle" ' +
        'font-size="11" fill="var(--text-3)">' + CC.fmtShortDate(item.date) + '</text>';
    });
    svg += '</svg>';
    container.innerHTML = svg;
  }

  function renderHeat(heat) {
    const container = document.getElementById('heat-container');
    const empty = document.getElementById('heat-empty');
    const weeks = heat.weeks || [];
    const matrix = heat.matrix || {};
    const subjects = Object.keys(matrix);
    let total = 0;
    subjects.forEach(function (subject) {
      (matrix[subject] || []).forEach(function (count) { total += count; });
    });
    if (!total) {
      container.innerHTML = '';
      empty.classList.remove('hidden');
      return;
    }
    empty.classList.add('hidden');
    let table = '<table class="heat-table"><thead><tr><th>学科</th>' +
      weeks.map(function (week) { return '<th>' + CC.escape(week) + '</th>'; }).join('') +
      '</tr></thead><tbody>';
    subjects.forEach(function (subject) {
      table += '<tr><th>' + CC.escape(subject) + '</th>';
      (matrix[subject] || []).forEach(function (count) {
        let cls = 'heat-cell';
        if (count === 0) cls += ' empty-cell';
        else if (count <= 2) cls += ' light';
        else if (count <= 4) cls += ' mid';
        else cls += ' has-data';
        table += '<td class="' + cls + '">' + count + '</td>';
      });
      table += '</tr>';
    });
    table += '</tbody></table>';
    container.innerHTML = table;
  }

  function renderProfile(data) {
    const content = document.getElementById('profile-content');
    const empty = document.getElementById('profile-empty');
    const profile = data.profile;
    if (profile) {
      empty.classList.add('hidden');
      content.innerHTML = '<div class="profile-grid">' +
        '<div><div class="profile-style">学习风格：<strong>' + CC.escape(profile.style || '稳健型') + '</strong></div>' +
        '<div class="profile-suggest mt-16"><div class="profile-suggest-title">学习建议</div>' +
        CC.escape(profile.advice || '保持当前节奏，优先复盘错题。') + '</div>' +
        '<div class="muted small mt-8">画像依据：已批改提交 ' + data.graded_count + ' 次 · 模式 ' +
        CC.escape(data.mode) + '</div></div>' +
        '<div class="profile-side">' +
        '<div class="profile-block"><div class="profile-block-title ok">优势学科</div><ul>' +
        (profile.strengths && profile.strengths.length
          ? profile.strengths.map(function (item) { return '<li>' + CC.escape(item) + '</li>'; }).join('')
          : '<li class="muted small">暂无明显优势学科</li>') +
        '</ul></div>' +
        '<div class="profile-block"><div class="profile-block-title warn">待提升</div><ul>' +
        (profile.weaknesses && profile.weaknesses.length
          ? profile.weaknesses.map(function (item) { return '<li>' + CC.escape(item) + '</li>'; }).join('')
          : '<li class="muted small">暂无明显短板</li>') +
        '</ul></div></div></div>';
      return;
    }
    content.innerHTML = '';
    empty.classList.remove('hidden');
    if (data.profile_error) {
      content.innerHTML = '<div class="notice notice-danger">画像生成失败，数字统计仍可正常使用。</div>';
      empty.classList.add('hidden');
    }
  }

  function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value == null ? '—' : String(value);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
