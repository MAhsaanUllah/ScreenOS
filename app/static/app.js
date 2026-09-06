const $ = id => document.getElementById(id);
let token = null;
let record = null;

function status(text, isError = false) {
  const el = $('status');
  el.textContent = text;
  el.classList.toggle('error', isError);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'X-Screenos': '1',
      ...(options.headers || {})
    }
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed. Please check inputs.');
  }
  return data;
}

// Drag & Drop Handling
const dropzone = $('dropzone');
const fileInput = $('file-input');
const fileNameDisplay = $('file-name-display');

if (dropzone && fileInput) {
  dropzone.addEventListener('click', () => fileInput.click());
  
  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, e => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, e => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', e => {
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      updateFileName();
    }
  });

  fileInput.addEventListener('change', updateFileName);
}

function updateFileName() {
  if (fileInput.files.length) {
    fileNameDisplay.textContent = `Selected: ${fileInput.files[0].name}`;
    fileNameDisplay.style.color = '#0f172a';
    fileNameDisplay.style.fontWeight = '500';
  } else {
    fileNameDisplay.textContent = 'No file selected';
    fileNameDisplay.style.color = '';
  }
}

// Sample Loader
const sampleBtn = $('load-sample-btn');
if (sampleBtn) {
  sampleBtn.onclick = () => {
    const sampleText = `FICTIONAL SAMPLE - not a real applicant
Amina Example
AI Engineer at Example Studio
Built automated invoice review with a human approval step.
Built a Python FastAPI service with validated requests and helpful errors.
Created document search that returned exact source quotes with each answer.
Designed a database with separate customer access and tested access checks.
Added 32 automated tests and deployed the service with failure alerts.`;

    const file = new File([sampleText], "01_strong.txt", { type: "text/plain" });
    const container = new DataTransfer();
    container.items.add(file);
    fileInput.files = container.files;
    updateFileName();
    $('name-input').value = 'Amina Example';
    status('Sample CV loaded: 01_strong.txt. Click "Prepare & Clean Resume".');
  };
}

// Consent and Textarea Sync
$('consent').onchange = () => {
  $('score').disabled = !$('consent').checked;
};

$('cleaned').oninput = () => {
  $('consent').checked = false;
  $('score').disabled = true;
};

// Upload & Preview Form
$('upload').onsubmit = async (e) => {
  e.preventDefault();
  $('preview').disabled = true;
  token = null;
  $('preview-area').hidden = true;
  $('result').hidden = true;
  $('empty').hidden = false;
  $('saved').textContent = '';
  status('Extracting text and applying PII guardrails...');

  try {
    const data = await api('/api/preview', {
      method: 'POST',
      body: new FormData(e.target)
    });
    token = data.review_id;
    $('cleaned').value = data.cleaned_text;
    $('cleaned').disabled = false;
    $('consent').checked = false;
    $('consent').disabled = false;
    $('score').disabled = true;
    $('preview-area').hidden = false;
    status('PII sanitized and candidate hash generated. Review text and authorize scoring.');
  } catch (err) {
    status(err.message, true);
  } finally {
    $('preview').disabled = false;
  }
};

// Score Trigger
$('score').onclick = async () => {
  if (!token || !$('consent').checked) return;
  
  $('score').disabled = true;
  $('preview').disabled = true;
  $('cleaned').disabled = true;
  $('consent').disabled = true;
  status('Evaluating candidate against job rubric... Please wait a few moments.');

  try {
    const d = await api(`/api/reviews/${token}/score`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cleaned_text: $('cleaned').value })
    });

    $('empty').hidden = true;
    $('result').hidden = false;
    $('total').innerHTML = `${d.overall_score}<small>/100</small>`;
    
    // Verdict Badge
    const verdictEl = $('verdict');
    verdictEl.textContent = d.verdict.replaceAll('_', ' ');
    verdictEl.className = 'verdict-badge ' + (
      d.overall_score >= 75 ? 'verdict-strong' :
      d.overall_score >= 50 ? 'verdict-possible' : 'verdict-weak'
    );

    // Criteria Cards
    const criteriaEl = $('criteria');
    criteriaEl.replaceChildren();

    for (const c of d.criteria) {
      const card = document.createElement('article');
      const isMet = c.status === 'MET';
      const isPartial = c.status === 'PARTIALLY_MET';
      card.className = 'criterion-card ' + (isMet ? 'met' : isPartial ? 'partial' : 'notfound');

      const header = document.createElement('div');
      header.className = 'criterion-header';

      const title = document.createElement('span');
      title.className = 'criterion-title';
      title.textContent = c.criterion;

      const badge = document.createElement('span');
      badge.className = 'criterion-badge ' + (isMet ? 'pill-green' : isPartial ? 'verdict-possible' : 'verdict-weak');
      badge.textContent = `${c.status.replaceAll('_', ' ')} · ${c.score}/${c.weight} Pts`;

      header.append(title, badge);

      const quote = document.createElement('div');
      quote.className = 'quote-block';
      quote.textContent = c.evidence_quote ? `“${c.evidence_quote}”` : '— No direct evidence found in candidate text.';

      card.append(header, quote);
      criteriaEl.append(card);
    }

    $('notes').textContent = d.notes || 'Automated rubric evaluation completed.';
    $('saved').textContent = '';
    $('review-notes').value = '';
    $('review-notes').disabled = false;
    $('approve').disabled = false;
    $('reject').disabled = false;
    $('download').hidden = true;
    status('Evidence card ready. Review supporting quotes and make your screening decision.');
  } catch (err) {
    status(err.message, true);
    $('score').disabled = false;
    $('cleaned').disabled = false;
    $('consent').disabled = false;
  } finally {
    $('preview').disabled = false;
  }
};

// Decision Actions
async function decide(decision) {
  $('approve').disabled = true;
  $('reject').disabled = true;
  try {
    record = await api(`/api/reviews/${token}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        decision,
        notes: $('review-notes').value
      })
    });
    $('review-notes').disabled = true;
    $('saved').textContent = `✓ ${decision === 'APPROVE' ? 'Approved for Interview' : 'Rejected'} (Saved locally)`;
    $('download').hidden = false;
    status('Decision recorded. You may download the audit JSON or screen another candidate.');
  } catch (err) {
    status(err.message, true);
    $('approve').disabled = false;
    $('reject').disabled = false;
  }
}

$('approve').onclick = () => decide('APPROVE');
$('reject').onclick = () => decide('REJECT');

$('download').onclick = () => {
  if (!record) return;
  const blob = new Blob([JSON.stringify(record, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `screenos-review-${token.slice(0, 8)}.json`;
  a.click();
  URL.revokeObjectURL(url);
};

// Keyboard Shortcuts
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
  if (!$('approve').disabled && (e.key === 'Enter' || e.key === 'a')) {
    decide('APPROVE');
  } else if (!$('reject').disabled && (e.key === 'Escape' || e.key === 'r')) {
    decide('REJECT');
  }
});
