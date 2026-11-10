// StaxCloud Forms — Studio module: definitions + submissions in the shared kv
// store (form/<slug>, formsub/<slug>/<uuid>), rendered from real records.
//
// Preview renders every block kind the builder can put on a form, with the
// same controls and the same required rules the public form uses (the kind
// semantics mirror the public renderer: config-driven composites, checkbox
// groups, agreement parts). Kinds a test cannot exercise — signatures and
// uploads — render as labeled stand-ins and are exempt from the preview
// required-check, with the reason printed on the stand-in.
'use strict';

/*PURE-BEGIN pvforms*/
// ── Preview field renderer: pure helpers ─────────────────────────────
// A form field carries a coarse fallback `type` (text/email/phone/
// textarea/select) and the real block kind in `stype`, with its full
// definition in `config` — the same shape the public form renders.
function pvCfg(f) { return (f && f.config) || {}; }

var PV_KIND_BY_STYPE = {
  'artist-select': 'artist',
  'booking-form': 'booking', 'booking-gate': 'booking',
  'booking-widget': 'widget', 'customer-service': 'widget',
  'consent-aftercare': 'consent-agree', 'consent-legal': 'consent-agree',
  'consent-touchup': 'consent-agree', 'studio-deposit': 'consent-agree',
  'field-consent': 'agree', 'consent-checkbox': 'agree',
  'consent-client-info': 'composite-info',
  'consent-tattoo-details': 'composite-details',
  'studio-tattoo-desc': 'composite-desc',
  'studio-age-verify': 'composite-age',
  'studio-prev-tattoo': 'composite-prev',
  'consent-medical': 'checks-medical', 'studio-allergy': 'checks-allergy',
  'consent-photo-release': 'checks-photo', 'studio-photo-auth': 'checks-photo-sig',
  'studio-aftercare': 'checks-list',
  'consent-medical-disclosure': 'disclosure',
  'consent-minor-parent': 'minor',
  'consent-signature': 'signature', 'field-signature': 'signature',
  'consent-initials': 'initials', 'field-initials': 'initials',
  'field-file': 'upload', 'studio-ref-images': 'upload',
  'field-heading': 'heading', 'field-paragraph': 'paragraph', 'field-hidden': 'hidden',
  'field-dropdown': 'dropdown', 'field-choice': 'choice', 'field-image-choice': 'image-choice',
  'field-short-text': 'text', 'field-name': 'text',
  'field-email': 'email', 'field-phone': 'phone',
  'field-website': 'website', 'field-number': 'number',
  'field-long-text': 'textarea', 'field-message': 'textarea', 'textarea': 'textarea',
  'scale-number': 'scale-number', 'scale-star': 'scale-star', 'scale-thumbs': 'scale-thumbs'
};
var PV_KIND_BY_TYPE = {
  email: 'email', phone: 'phone', textarea: 'textarea', select: 'dropdown',
  number: 'number', date: 'date', url: 'website', website: 'website', text: 'text'
};
function pvKind(f) {
  if (!f) return 'text';
  var byStype = PV_KIND_BY_STYPE[(f.stype || '').toString().trim()];
  if (byStype) return byStype;
  return PV_KIND_BY_TYPE[(f.type || 'text').toString().trim()] || 'text';
}
function pvInputType(f) {
  var k = pvKind(f);
  if (k === 'phone') return 'tel';
  if (k === 'website') return 'url';
  if (k === 'email' || k === 'number' || k === 'date') return k;
  return 'text';
}

var PV_PHOTO_DEFAULTS = ['Photos may be used on social media', 'Photos may be used in a portfolio', 'My face may be shown', 'Do NOT use my photos'];
var PV_MEDICAL_DEFAULTS = ['Diabetes', 'Hemophilia or bleeding disorder', 'Skin disease or sensitivity', 'Pigment or dye reactions', 'Epilepsy, seizures, fainting, or narcolepsy', 'Anticoagulants or blood thinners', 'Other nonroutine medications', 'Hepatitis', 'HIV', 'High blood pressure or heart disease', 'Pregnancy', 'Contagious disease', 'Immune disorder', 'Other serious physical or mental health condition', 'None apply'];
var PV_ALLERGY_DEFAULTS = ['Latex allergy', 'Metal allergy', 'Eczema / Psoriasis', 'Sensitive skin', 'Keloid scarring', 'None of the above'];
var PV_AFTERCARE_DEFAULTS = ['Keep bandage on for recommended time', 'Wash gently with unscented soap', 'Apply thin layer of recommended ointment', 'Avoid swimming for 2 weeks', 'Avoid direct sunlight for 2 weeks', 'Do not pick or scratch the tattoo'];

function pvOptions(f) {
  var cfg = pvCfg(f);
  var raw = Array.isArray(cfg.options) ? cfg.options : (Array.isArray(f && f.options) ? f.options : []);
  var out = [];
  raw.forEach(function(o) {
    if (typeof o === 'string') { if (o) out.push({ label: o, image: '' }); return; }
    if (o && typeof o === 'object') {
      var label = o.label || o.value || '';
      if (label) out.push({ label: String(label), image: o.image ? String(o.image) : '' });
    }
  });
  var kind = pvKind(f);
  if (!out.length && (kind === 'checks-photo' || kind === 'checks-photo-sig')) {
    return PV_PHOTO_DEFAULTS.map(function(s) { return { label: s, image: '' }; });
  }
  return out;
}
function pvConditions(f) {
  var cfg = pvCfg(f), kind = pvKind(f);
  function strs(list) {
    return (Array.isArray(list) ? list : []).filter(function(x) { return typeof x === 'string' && x; });
  }
  if (kind === 'checks-medical') {
    var conds = strs(cfg.conditions);
    if (!conds.length) return PV_MEDICAL_DEFAULTS.slice();
    if (!conds.some(function(c) { return c.trim().toLowerCase().indexOf('none') === 0; })) conds = conds.concat(['None apply']);
    return conds;
  }
  if (kind === 'checks-allergy') {
    var alg = strs(cfg.conditions);
    return alg.length ? alg : PV_ALLERGY_DEFAULTS.slice();
  }
  if (kind === 'checks-list') {
    var items = strs(cfg.items);
    return items.length ? items : PV_AFTERCARE_DEFAULTS.slice();
  }
  return [];
}
// The checkbox rows a checks-kind field shows (labels only).
function pvChecksItems(f) {
  var kind = pvKind(f);
  if (kind === 'checks-photo' || kind === 'checks-photo-sig') return pvOptions(f).map(function(o) { return o.label; });
  return pvConditions(f);
}

var PV_AGREE_PARTS = {
  'consent-legal': [{ suffix: '', label: 'I have read and agree to all terms above' }],
  'consent-aftercare': [
    { suffix: '_understand', label: 'I understand the aftercare instructions' },
    { suffix: '_accept', label: 'I accept responsibility for proper aftercare' }],
  'consent-touchup': [
    { suffix: '_timeline', label: 'I understand the touch-up timeline' },
    { suffix: '_exclusions', label: 'I understand exclusions apply' }],
  'studio-deposit': [{ suffix: '', label: 'I agree to the deposit terms' }],
  'field-consent': [{ suffix: '', label: 'I agree' }],
  'consent-checkbox': [{ suffix: '', label: 'I agree' }]
};
function pvAgreeParts(f) { return PV_AGREE_PARTS[(f && f.stype) || ''] || []; }

var PV_TEXT_DEFAULTS = {
  'consent-legal': 'I acknowledge that a tattoo is a permanent change to my body.',
  'consent-aftercare': 'The artist has explained proper aftercare procedures.',
  'consent-touchup': 'Touch-ups are available within the specified window.',
  'studio-deposit': 'Non-refundable deposit required to secure your appointment.',
  'field-consent': 'I agree to the terms and conditions',
  'consent-minor-parent': 'I am the parent or legal guardian of the minor named in this form and give written consent for the described procedure. I will remain physically present during the procedure, have provided proper identification and proof of the minor\u2019s age, understand that body art is permanent, and understand that the practitioner may decline or stop the procedure.'
};
function pvText(f) {
  var cfg = pvCfg(f);
  if (cfg.text) return String(cfg.text);
  return PV_TEXT_DEFAULTS[(f && f.stype) || ''] || '';
}

// Composite blocks: the sub-fields the public form renders, honoring the
// block's show_* toggles (default shown). Sub answers store under
// <field key>_<suffix>, the public form's own naming.
function pvShown(cfg, name) { return cfg[name] !== false; }
function pvSubFields(f) {
  var cfg = pvCfg(f), kind = pvKind(f), out = [];
  function add(toggle, suffix, label, control, placeholder, options) {
    if (toggle && !pvShown(cfg, toggle)) return;
    out.push({ suffix: suffix, label: label, control: control, placeholder: placeholder || '', options: options || null });
  }
  if (kind === 'composite-info') {
    add('show_name', 'name', 'Full Name', 'text', 'Full Name');
    add('show_dob', 'dob', 'Date of Birth', 'date');
    add('show_phone', 'phone', 'Phone', 'tel', 'Phone');
    add('show_email', 'email', 'Email', 'email', 'Email');
    add('show_address', 'address', 'Street Address', 'text', 'Street Address');
    if (pvShown(cfg, 'show_emergency')) {
      out.push({ suffix: 'emergency_name', label: 'Emergency contact name', control: 'text', placeholder: 'Contact Name', options: null });
      out.push({ suffix: 'emergency_phone', label: 'Emergency contact phone', control: 'tel', placeholder: 'Contact Phone', options: null });
    }
  } else if (kind === 'composite-details') {
    add('show_placement', 'placement', 'Placement', 'text', 'Placement (e.g., inner forearm)');
    add('show_size', 'size', 'Approximate size', 'text', 'Approximate size');
    add('show_description', 'desc', 'Description', 'textarea', 'Describe your tattoo idea\u2026');
    add('show_style', 'style', 'Style Preference', 'text', 'e.g. Traditional, Realism');
    add('show_color', 'color', 'Color Preference', 'text', 'Black & Grey / Full Color');
  } else if (kind === 'composite-desc') {
    add('show_style', 'style', 'Style', 'text', 'e.g. Traditional, Realism, Watercolor\u2026');
    add('show_placement', 'placement', 'Placement', 'text', 'e.g. Left forearm');
    add('show_size', 'size', 'Size', 'text', 'e.g. 4 \u00D7 6 inches');
    add('show_description', 'desc', 'Description', 'textarea', 'Describe your tattoo idea in detail\u2026');
  } else if (kind === 'booking') {
    add('show_name', 'name', 'Full Name', 'text', 'Full Name');
    add('show_phone', 'phone', 'Phone', 'tel', 'Phone');
    add('show_email', 'email', 'Email', 'email', 'Email');
    add('show_description', 'desc', 'Description', 'textarea', 'Describe your tattoo idea\u2026');
    add('show_placement', 'placement', 'Placement', 'text', 'Placement (e.g., inner forearm)');
    add('show_size', 'size', 'Approximate size', 'text', 'Approximate size (e.g., 4 inches)');
  } else if (kind === 'composite-age') {
    out.push({ suffix: 'dob', label: 'Date of Birth', control: 'date', placeholder: '', options: null });
    out.push({ suffix: 'id_type', label: 'ID Type', control: 'select', placeholder: '', options: [
      { value: 'drivers_license', label: 'Driver\u2019s License' },
      { value: 'passport', label: 'Passport' },
      { value: 'state_id', label: 'State ID' },
      { value: 'military_id', label: 'Military ID' }] });
  } else if (kind === 'composite-prev') {
    add('show_prevwork', 'has_prev', 'Have you been tattooed before?', 'radio-yn');
    add('show_location', 'location', 'Location of previous work', 'text', 'e.g. Right arm sleeve');
    add('show_reactions', 'reactions', 'Any adverse reactions?', 'textarea', 'Describe any issues with previous tattoos\u2026');
  }
  return out;
}

var PV_MINOR_KEYS = ['minor_name', 'minor_dob', 'parent_name', 'parent_relationship', 'parent_dob', 'parent_phone', 'parent_id_type', 'parent_id_number', 'parent_agree'];
function pvDataKeys(f) {
  var kind = pvKind(f), key = f.key, keys = [key];
  pvAgreeParts(f).forEach(function(p) { if (p.suffix) keys.push(key + p.suffix); });
  pvSubFields(f).forEach(function(s) { keys.push(key + '_' + s.suffix); });
  if (kind === 'checks-medical' || kind === 'checks-allergy') keys.push(key + '_notes');
  if (kind === 'disclosure') { keys.push(key + '_conditions'); keys.push(key + '_details'); }
  if (kind === 'signature') { keys.push(key + '_typed'); keys.push(key + '_typed_agree'); }
  if (kind === 'minor') PV_MINOR_KEYS.forEach(function(s) { keys.push(key + '_' + s); });
  // Captured only on the real (hosted) form, where the pads and the
  // photo picker exist; the preview never fills them.
  if (kind === 'checks-photo-sig') keys.push(key + '_signature');
  if (kind === 'minor') { keys.push(key + '_parent_signature'); keys.push(key + '_minor_signature'); }
  if (kind === 'booking') keys.push(key + '_photos');
  return keys;
}
function pvAgreeKeys(f) {
  var kind = pvKind(f), key = f.key;
  if (kind === 'agree' || kind === 'consent-agree') return pvAgreeParts(f).map(function(p) { return key + p.suffix; });
  if (kind === 'signature') return [key + '_typed_agree'];
  if (kind === 'minor') return [key + '_parent_agree'];
  return [];
}

// Stand-in kinds: the real control cannot be exercised by a test, so the
// preview required-check exempts them (the reason prints on the stand-in).
var PV_EXEMPT_KINDS = { signature: 1, upload: 1, widget: 1, heading: 1, paragraph: 1, hidden: 1 };
function pvExempt(f) { return !!PV_EXEMPT_KINDS[pvKind(f)]; }

function pvHas(data, key) {
  var v = data ? data[key] : undefined;
  if (v === undefined || v === null) return false;
  if (typeof v === 'string') return v.trim() !== '';
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === 'boolean') return v;
  return true;
}
// '' when the field's required rule is satisfied, else the field's label —
// the public form's required semantics, read over preview state (where
// agreement checkboxes hold booleans and stand-in kinds are exempt).
function pvMissing(f, data) {
  if (!f || !f.required) return '';
  var kind = pvKind(f);
  if (PV_EXEMPT_KINDS[kind]) return '';
  var key = f.key, label = f.label || f.key;
  switch (kind) {
    case 'agree':
    case 'consent-agree':
      return pvAgreeParts(f).every(function(p) { return !!data && data[key + p.suffix] === true; }) ? '' : label;
    case 'checks-medical':
    case 'checks-allergy':
      return (pvHas(data, key) || pvHas(data, key + '_notes')) ? '' : label;
    case 'disclosure':
      return (pvHas(data, key + '_conditions') || pvHas(data, key + '_details')) ? '' : label;
    case 'checks-photo':
    case 'checks-photo-sig':
      return pvHas(data, key) ? '' : label;
    case 'checks-list': {
      var items = pvConditions(f);
      var sel = (data && Array.isArray(data[key])) ? data[key] : [];
      if (!items.length) return pvHas(data, key) ? '' : label;
      return items.every(function(it) { return sel.indexOf(it) >= 0; }) ? '' : label;
    }
    case 'composite-info':
    case 'composite-details':
    case 'composite-desc':
    case 'booking':
    case 'composite-age':
      return pvSubFields(f).every(function(s) { return pvHas(data, key + '_' + s.suffix); }) ? '' : label;
    case 'composite-prev': {
      if (!pvHas(data, key + '_has_prev')) return label;
      if (String(data[key + '_has_prev']) === 'yes') {
        return pvSubFields(f).every(function(s) { return s.suffix === 'has_prev' || pvHas(data, key + '_' + s.suffix); }) ? '' : label;
      }
      return '';
    }
    case 'minor': {
      var subs = PV_MINOR_KEYS.filter(function(s) { return s !== 'parent_agree'; });
      var okAll = subs.every(function(s) { return pvHas(data, key + '_' + s); });
      return (okAll && !!data && data[key + '_parent_agree'] === true) ? '' : label;
    }
    default:
      return pvHas(data, key) ? '' : label;
  }
}

// The starting preview state for a form: checkbox groups as arrays,
// agreement checkboxes as booleans, a fixed artist pre-chosen.
function pvSeed(def, artists) {
  var data = {};
  ((def && def.fields) || []).forEach(function(f) {
    var kind = pvKind(f), cfg = pvCfg(f), key = f.key;
    if (kind === 'checks-medical' || kind === 'checks-allergy' || kind === 'checks-photo' ||
        kind === 'checks-photo-sig' || kind === 'checks-list') data[key] = [];
    else if (kind === 'disclosure') data[key + '_conditions'] = [];
    else if (kind === 'choice' && cfg.allow_multiple) data[key] = [];
    if (kind === 'agree' || kind === 'consent-agree') {
      pvAgreeParts(f).forEach(function(p) { data[key + p.suffix] = false; });
    }
    if (kind === 'signature') data[key + '_typed_agree'] = false;
    if (kind === 'minor') data[key + '_parent_agree'] = false;
    if (kind === 'dropdown') data[key] = '';
    if (kind === 'artist' && cfg.assignment_mode === 'fixed_artist' && cfg.fixed_artist_id) {
      if ((artists || []).some(function(a) { return a.id === cfg.fixed_artist_id; })) data[key] = cfg.fixed_artist_id;
    }
  });
  return data;
}
// The test-submission record's data: only keys this form's fields own,
// with agreement booleans written the way the public form writes them.
function pvCompose(def, data) {
  var out = {};
  ((def && def.fields) || []).forEach(function(f) {
    var agree = {};
    pvAgreeKeys(f).forEach(function(k) { agree[k] = 1; });
    pvDataKeys(f).forEach(function(k) {
      if (!data || !(k in data)) return;
      var v = data[k];
      if (v === undefined) return;
      if (agree[k]) { if (v === true) out[k] = 'agreed'; return; }
      out[k] = v;
    });
  });
  return out;
}

// Preview opens on the shop's real consent form when there is one — not
// on whatever record sorts first.
function pvDefaultSlug(defs) {
  var list = (defs || []).filter(function(d) { return d && d.slug; });
  if (!list.length) return '';
  var consent = list.filter(function(d) { return /consent/i.test(d.slug) || /consent/i.test(d.title || ''); });
  var pool = consent.length ? consent : list;
  var withFields = pool.filter(function(d) { return (d.fields || []).length > 0; });
  var ranked = (withFields.length ? withFields : pool).slice().sort(function(a, b) {
    var pa = a.published ? 1 : 0, pb = b.published ? 1 : 0;
    if (pb !== pa) return pb - pa;
    return (b.fields || []).length - (a.fields || []).length;
  });
  return ranked[0].slug;
}

// Rich-text blocks (consent terms, paragraphs) carry HTML the client
// reads formatted. Render it through the same allowlist the public form
// sanitizes with — formatting tags only, no attributes but a safe href.
var PV_RICH_ALLOW = { p: 1, br: 1, strong: 1, b: 1, em: 1, i: 1, u: 1, s: 1, a: 1, ul: 1, ol: 1, li: 1, h1: 1, h2: 1, h3: 1, h4: 1, h5: 1, h6: 1, span: 1, blockquote: 1, sub: 1, sup: 1, hr: 1 };
function pvRich(html) {
  var s = String(html === null || html === undefined ? '' : html);
  s = s.replace(/<(script|style|iframe|object|title)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, '');
  s = s.replace(/<!--[\s\S]*?-->/g, '');
  return s.replace(/<\/?([a-zA-Z][a-zA-Z0-9]*)((?:[^>"']|"[^"]*"|'[^']*')*)>/g, function(m, tag, attrs) {
    var t = tag.toLowerCase();
    if (!PV_RICH_ALLOW[t]) return '';
    if (m.charAt(1) === '/') return '</' + t + '>';
    if (t === 'a') {
      var hm = attrs.match(/href\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+))/i);
      var href = hm ? (hm[2] || hm[3] || hm[4] || '') : '';
      if (/^(https?:|mailto:)/i.test(href)) return '<a href="' + href.replace(/"/g, '&quot;') + '">';
      return '<a>';
    }
    return '<' + t + '>';
  });
}

// ── Small read helpers the Preview template calls ────────────────────
function pvHelp(f) { return pvCfg(f).help || ''; }
function pvPlaceholder(f) { return pvCfg(f).placeholder || ''; }
function pvTitle(f) { return pvKind(f) === 'disclosure' ? (pvCfg(f).title || f.label || '') : (f.label || ''); }
function pvSigMode(f) { var cfg = pvCfg(f); return cfg.signature_mode || cfg.mode || 'dual'; }
function pvStandinNote(f) {
  if (pvKind(f) === 'signature') return 'Signs on the real form \u2014 you don\u2019t need it for a test send.';
  if ((f.stype || '') === 'studio-ref-images' || pvCfg(f).accept === 'images') return 'Clients upload photos on the real form \u2014 you don\u2019t need it for a test send.';
  return 'Clients upload a file on the real form \u2014 you don\u2019t need it for a test send.';
}
var PV_DISCLOSURE_DEFAULTS = ['Diabetes', 'History of hemophilia or bleeding disorders', 'History of skin diseases, skin lesions, or severe skin sensitivities (including sensitivity to soap, disinfectants, etc.)', 'History of allergies or adverse reactions to pigments, dyes, or topical products', 'History of epilepsy, seizures, fainting, or narcolepsy', 'Hepatitis', 'HIV Positive', 'High blood pressure or heart disease', 'Immune system disorder', 'Contagious or infectious diseases', 'Current pregnancy or nursing', 'Any other serious physical or mental health conditions'];
function pvSec1(f) {
  var cfg = pvCfg(f);
  var list = (Array.isArray(cfg.sec1_conditions) ? cfg.sec1_conditions : []).filter(function(x) { return typeof x === 'string' && x; });
  if (!list.length) return PV_DISCLOSURE_DEFAULTS.slice();
  if (!list.some(function(c) { return c.trim().toLowerCase().indexOf('none') === 0; })) list = list.concat(['None apply']);
  return list;
}
function pvSec2(f) {
  var cfg = pvCfg(f);
  var items = Array.isArray(cfg.sec2_items) ? cfg.sec2_items : [
    'Anticoagulants / Blood Thinners: Medications that thin the blood or interfere with blood clotting.',
    'Other Non-Routine Medications: Any medications other than routine antibiotics, allergy medication, or birth control pills.'];
  return items.filter(function(x) { return typeof x === 'string' && x; }).map(function(raw) {
    var i = raw.indexOf(':');
    if (i > 0) return { head: raw.slice(0, i).trim(), body: raw.slice(i + 1).trim() };
    return { head: '', body: raw };
  });
}
function pvScaleOpts(f) {
  var cfg = pvCfg(f), kind = pvKind(f), out = [];
  if (kind === 'scale-number') {
    var min = parseInt(cfg.min, 10) || 1, max = parseInt(cfg.max, 10) || 10;
    for (var i = min; i <= max; i++) out.push({ value: String(i), label: String(i) });
  } else if (kind === 'scale-star') {
    var smax = parseInt(cfg.max, 10) || 5;
    for (var j = 1; j <= smax; j++) out.push({ value: String(j), label: '\u2605' });
  } else if (kind === 'scale-thumbs') {
    out.push({ value: 'up', label: 'Thumbs up' });
    out.push({ value: 'down', label: 'Thumbs down' });
  }
  return out;
}
function pvWidgetLine(f) {
  if ((f.stype || '') === 'customer-service') {
    var g = pvCfg(f).greeting;
    return g ? 'Chat box \u2014 ' + g : 'Chat box \u2014 on the real form, clients can message the shop here.';
  }
  return 'Appointment picker \u2014 on the real form, clients pick a day and time here.';
}
function pvArtistFixed(f, artists) {
  var cfg = pvCfg(f);
  if (cfg.assignment_mode !== 'fixed_artist') return null;
  return (artists || []).filter(function(a) { return a.id === cfg.fixed_artist_id; })[0] || null;
}
function pvAgeNote(f) { return 'Must be ' + (pvCfg(f).min_age || 18) + ' or older'; }
function pvMinorCfg(f) {
  var cfg = pvCfg(f);
  return {
    minAge: cfg.min_age || 16, maxAge: cfg.max_age || 17,
    requireParentId: cfg.require_parent_id !== false,
    requireBothSigs: cfg.require_both_sigs !== false,
    help: cfg.help || ''
  };
}
// Labels for every answer key a form can store, sub-answers included:
// "Your details — Email", "I have read and agree…", "Signature (typed)".
function pvAnswerLabels(def) {
  var map = {};
  ((def && def.fields) || []).forEach(function(f) {
    if (!f || !f.key) return;
    var kind = pvKind(f), key = f.key, label = pvTitle(f) || f.label || '';
    map[key] = label;
    if (kind === 'agree' || kind === 'consent-agree') pvAgreeParts(f).forEach(function(p) { if (p.suffix) map[key + p.suffix] = label + ' — ' + p.label; });
    if (kind.indexOf('composite') === 0 || kind === 'booking') pvSubFields(f).forEach(function(s) { map[key + '_' + s.suffix] = label + ' — ' + s.label; });
    if (kind === 'checks-medical' || kind === 'checks-allergy') map[key + '_notes'] = label + ' — notes';
    if (kind === 'disclosure') { map[key + '_conditions'] = label; map[key + '_details'] = label + ' — details'; }
    if (kind === 'signature') { map[key + '_typed'] = label + ' (typed name)'; map[key + '_typed_agree'] = label + ' — typed name is my signature'; }
    if (kind === 'checks-photo-sig') map[key + '_signature'] = label + ' — signature';
    if (kind === 'booking') map[key + '_photos'] = label + ' — reference photos';
    if (kind === 'minor') {
      [['minor_name', 'minor’s name'], ['minor_dob', 'minor’s date of birth'], ['parent_name', 'parent or guardian'], ['parent_relationship', 'relationship'], ['parent_dob', 'parent date of birth'], ['parent_phone', 'parent phone'], ['parent_id_type', 'parent ID type'], ['parent_id_number', 'parent ID number'], ['parent_agree', 'parent consents'], ['parent_signature', 'parent signature'], ['minor_signature', 'minor’s signature']]
        .forEach(function(p) { map[key + '_' + p[0]] = label + ' — ' + p[1]; });
    }
  });
  return map;
}
/*PURE-END pvforms*/


/*PURE-BEGIN fbbuilder*/
// ── Form builder: the blocks an owner can add, and their settings ────
// Each palette entry is the block's stored shape: `stype` is the real
// kind, `type` the coarse fallback older readers understand.
var FB_PALETTE = [
  { group: 'Basics', items: [
    { stype: 'field-heading', type: 'text', name: 'Heading', label: 'Section heading' },
    { stype: 'field-paragraph', type: 'text', name: 'Text', label: 'Text', config: { text: 'Write something for the client to read.' } },
    { stype: 'field-name', type: 'text', name: 'Name', label: 'Your name', required: true },
    { stype: 'field-email', type: 'email', name: 'Email', label: 'Email', required: true },
    { stype: 'field-phone', type: 'phone', name: 'Phone', label: 'Phone' },
    { stype: 'field-short-text', type: 'text', name: 'Short answer', label: 'Short answer' },
    { stype: 'field-long-text', type: 'textarea', name: 'Long answer', label: 'Tell us more' },
    { stype: '', type: 'date', name: 'Date', label: 'Date' },
    { stype: 'field-number', type: 'number', name: 'Number', label: 'Number' },
    { stype: 'field-dropdown', type: 'select', name: 'Dropdown', label: 'Choose one', config: { options: ['Option 1', 'Option 2'] } },
    { stype: 'field-choice', type: 'select', name: 'Choices', label: 'Pick what applies', config: { options: ['Option 1', 'Option 2'], allow_multiple: true } },
    { stype: 'field-consent', type: 'text', name: 'Agree box', label: 'Agreement', config: { text: 'I agree to the terms and conditions' }, required: true }
  ] },
  { group: 'Tattoo', items: [
    { stype: 'consent-client-info', type: 'text', name: 'Client details', label: 'Your details', required: true },
    { stype: 'consent-tattoo-details', type: 'text', name: 'Tattoo details', label: 'About the tattoo' },
    { stype: 'artist-select', type: 'select', name: 'Artist', label: 'Which artist?' },
    { stype: 'studio-ref-images', type: 'text', name: 'Reference photos', label: 'Reference photos' },
    { stype: 'studio-age-verify', type: 'text', name: 'Age check', label: 'Age verification', required: true },
    { stype: 'studio-prev-tattoo', type: 'text', name: 'Previous tattoos', label: 'Previous tattoos' }
  ] },
  { group: 'Consent', items: [
    { stype: 'consent-legal', type: 'text', name: 'Terms', label: 'Consent and release', required: true },
    { stype: 'consent-medical-disclosure', type: 'text', name: 'Medical disclosure', label: 'Medical disclosure', required: true },
    { stype: 'consent-medical', type: 'text', name: 'Medical checklist', label: 'Medical conditions' },
    { stype: 'studio-allergy', type: 'text', name: 'Allergies', label: 'Allergies and skin' },
    { stype: 'consent-aftercare', type: 'text', name: 'Aftercare', label: 'Aftercare', required: true },
    { stype: 'consent-photo-release', type: 'text', name: 'Photo release', label: 'Photo release' },
    { stype: 'studio-deposit', type: 'text', name: 'Deposit terms', label: 'Deposit', required: true },
    { stype: 'consent-touchup', type: 'text', name: 'Touch-up policy', label: 'Touch-ups' },
    { stype: 'consent-minor-parent', type: 'text', name: 'Parent consent', label: 'Parent or guardian consent', required: true },
    { stype: 'consent-initials', type: 'text', name: 'Initials', label: 'Initials', required: true },
    { stype: 'consent-signature', type: 'text', name: 'Signature', label: 'Signature', required: true }
  ] }
];
function fbPaletteEntry(stype, type) {
  for (var g = 0; g < FB_PALETTE.length; g++) {
    for (var i = 0; i < FB_PALETTE[g].items.length; i++) {
      var it = FB_PALETTE[g].items[i];
      if (it.stype === (stype || '') && (it.stype || it.type === type)) return it;
    }
  }
  return null;
}
// What a block is called in the builder — its palette name, else its kind.
function fbBlockName(f) {
  var it = fbPaletteEntry(f.stype, f.type);
  if (it) return it.name;
  var k = pvKind(f);
  return k.charAt(0).toUpperCase() + k.slice(1).replace(/-/g, ' ');
}
function fbSlug(text) {
  return String(text || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 48);
}
// A key no other field uses. Keys never change once a block exists:
// stored submissions are read back by them.
function fbUniqueKey(base, fields) {
  var stem = fbSlug(base).replace(/-/g, '_') || 'field';
  var taken = {};
  (fields || []).forEach(function(f) { if (f && f.key) taken[f.key] = 1; });
  // A key must not be another key's "<key>_" prefix either: sub-answers
  // are stored as <key>_<suffix>.
  function clash(k) {
    if (taken[k]) return true;
    return Object.keys(taken).some(function(t) { return t.indexOf(k + '_') === 0 || k.indexOf(t + '_') === 0; });
  }
  if (!clash(stem)) return stem;
  for (var n = 2; n < 500; n++) { if (!clash(stem + n)) return stem + n; }
  return stem + Date.now();
}
function fbNewBlock(entry, fields) {
  var f = { key: fbUniqueKey(entry.name, fields), label: entry.label, type: entry.type, required: !!entry.required };
  if (entry.stype) f.stype = entry.stype;
  if (entry.config) f.config = JSON.parse(JSON.stringify(entry.config));
  // Health checklists get a way to say "none": a required list must be
  // answerable by someone with nothing to declare.
  var none = 'None of the above';
  if (entry.stype === 'consent-medical-disclosure') f.config = { sec1_conditions: PV_DISCLOSURE_DEFAULTS.concat([none]) };
  if (entry.stype === 'consent-medical') f.config = { conditions: PV_MEDICAL_DEFAULTS.concat([none]) };
  if (entry.stype === 'studio-allergy') f.config = { conditions: PV_ALLERGY_DEFAULTS.concat([none]) };
  return f;
}
function fbUniqueSlug(title, taken) {
  var stem = fbSlug(title) || 'form';
  if (!taken[stem]) return stem;
  for (var n = 2; n < 500; n++) { if (!taken[stem + '-' + n]) return stem + '-' + n; }
  return stem + '-' + Date.now();
}
// Plain typed text becomes paragraphs; text that already carries real
// formatting tags is kept. A stray "<" in typed text is not a tag.
var FB_HTML_TAG = /<\/?(p|br|strong|em|b|i|u|ul|ol|li|h[1-6]|div|span|a)\b[^>]*>/i;
function fbTextToHtml(text) {
  var t = String(text || '');
  if (FB_HTML_TAG.test(t)) return t;
  return t.split(/\n{2,}/).map(function(p) { return p.trim(); }).filter(Boolean).map(function(p) {
    return '<p>' + p.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/\n/g, '<br>') + '</p>';
  }).join('');
}
function fbHtmlToText(html) {
  var t = String(html || '');
  if (!FB_HTML_TAG.test(t)) return t;
  return t.replace(/<\/p>\s*<p[^>]*>/gi, '\n\n').replace(/<br\s*\/?>/gi, '\n').replace(/<\/(h[1-6]|li|div)>/gi, '\n')
    .replace(/<[^>]+>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').trim();
}
function fbLines(text) {
  return String(text || '').split('\n').map(function(x) { return x.trim(); }).filter(Boolean);
}
var FB_TOGGLES = {
  'composite-info': [['show_name', 'Full name'], ['show_dob', 'Date of birth'], ['show_phone', 'Phone'], ['show_email', 'Email'], ['show_address', 'Street address'], ['show_emergency', 'Emergency contact']],
  'composite-details': [['show_placement', 'Placement'], ['show_size', 'Size'], ['show_description', 'Description'], ['show_style', 'Style'], ['show_color', 'Color']],
  'composite-desc': [['show_style', 'Style'], ['show_placement', 'Placement'], ['show_size', 'Size'], ['show_description', 'Description']],
  'composite-prev': [['show_prevwork', 'Tattooed before?'], ['show_location', 'Where'], ['show_reactions', 'Reactions']]
};
// The settings a block offers, as rows the builder draws: each row reads
// and writes the block itself.
function fbSettings(f) {
  var kind = pvKind(f), rows = [];
  function cfg() { if (!f.config) f.config = {}; return f.config; }
  function row(type, label, get, set, extra) {
    var r = { type: type, label: label, get: get, set: set };
    if (extra) Object.keys(extra).forEach(function(k) { r[k] = extra[k]; });
    rows.push(r);
  }
  function linesRow(label, prop, fallback) {
    row('lines', label, function() {
      var list = Array.isArray(cfg()[prop]) && cfg()[prop].length ? cfg()[prop] : fallback;
      return list.map(function(o) { return typeof o === 'string' ? o : (o && (o.label || o.value)) || ''; }).join('\n');
    }, function(v) { cfg()[prop] = fbLines(v); }, { hint: 'One per line' });
  }
  if (kind === 'heading') {
    row('text', 'Heading', function() { return f.label || ''; }, function(v) { f.label = v; });
    return rows;
  }
  if (kind === 'paragraph') {
    row('textarea', 'Text', function() { return fbHtmlToText(cfg().text || ''); }, function(v) { cfg().text = fbTextToHtml(v); });
    return rows;
  }
  row('text', kind === 'disclosure' ? 'Title' : 'Question', function() { return (kind === 'disclosure' && cfg().title) || f.label || ''; },
    function(v) { f.label = v; if (kind === 'disclosure') cfg().title = v; });
  if (kind !== 'widget') row('toggle', 'Required', function() { return !!f.required; }, function(v) { f.required = !!v; });
  if (['text', 'email', 'phone', 'website', 'number', 'date', 'textarea', 'dropdown', 'choice', 'upload', 'initials', 'artist'].indexOf(kind) >= 0) {
    row('text', 'Help text', function() { return cfg().help || ''; }, function(v) { cfg().help = v; });
  }
  if (['text', 'email', 'phone', 'website', 'number', 'textarea'].indexOf(kind) >= 0) {
    row('text', 'Placeholder', function() { return cfg().placeholder || ''; }, function(v) { cfg().placeholder = v; });
  }
  if (kind === 'dropdown' || kind === 'choice') linesRow('Options', 'options', []);
  if (kind === 'choice') row('toggle', 'Allow more than one', function() { return !!cfg().allow_multiple; }, function(v) { cfg().allow_multiple = !!v; });
  if (kind === 'agree' || kind === 'consent-agree' || kind === 'minor') {
    row('textarea', 'Terms the client reads', function() { return fbHtmlToText(cfg().text || pvText(f)); }, function(v) { cfg().text = fbTextToHtml(v); });
  }
  if (kind === 'checks-medical') linesRow('Conditions', 'conditions', PV_MEDICAL_DEFAULTS);
  if (kind === 'checks-allergy') linesRow('Conditions', 'conditions', PV_ALLERGY_DEFAULTS);
  if (kind === 'checks-list') linesRow('Items', 'items', PV_AFTERCARE_DEFAULTS);
  if (kind === 'checks-photo' || kind === 'checks-photo-sig') linesRow('Choices', 'options', PV_PHOTO_DEFAULTS);
  if (kind === 'disclosure') linesRow('Conditions', 'sec1_conditions', PV_DISCLOSURE_DEFAULTS);
  (FB_TOGGLES[kind] || []).forEach(function(t) {
    row('toggle', 'Ask for: ' + t[1], function() { return cfg()[t[0]] !== false; }, function(v) { cfg()[t[0]] = !!v; });
  });
  if (kind === 'composite-age') {
    row('number', 'Minimum age', function() { return cfg().min_age || 18; }, function(v) { cfg().min_age = Math.max(1, parseInt(v, 10) || 18); });
  }
  if (kind === 'signature') {
    row('select', 'How they sign', function() { return pvSigMode(f); }, function(v) { cfg().signature_mode = v; },
      { options: [['dual', 'Draw or type'], ['draw', 'Draw only'], ['typed', 'Type only']] });
  }
  return rows;
}
// Starting points for a new form.
function fbTemplate(name) {
  var fields = [];
  function add(stype, type, over) {
    var entry = fbPaletteEntry(stype, type);
    var f = fbNewBlock(entry, fields);
    if (over) Object.keys(over).forEach(function(k) { f[k] = over[k]; });
    fields.push(f);
  }
  if (name === 'contact') {
    add('field-name'); add('field-email'); add('field-phone');
    add('field-long-text', 'textarea', { label: 'How can we help?', required: true });
    return { title: 'Contact us', fields: fields };
  }
  if (name === 'booking') {
    add('consent-client-info', 'text', { config: { show_dob: false, show_address: false, show_emergency: false } });
    add('consent-tattoo-details');
    add('artist-select');
    add('studio-ref-images');
    return { title: 'Booking request', fields: fields };
  }
  if (name === 'consent') {
    add('consent-client-info');
    add('consent-tattoo-details', 'text', { config: { show_style: false, show_color: false } });
    add('studio-age-verify');
    add('consent-medical-disclosure');
    add('consent-legal');
    add('consent-aftercare');
    add('consent-photo-release');
    add('consent-signature');
    return { title: 'Tattoo consent', fields: fields };
  }
  return { title: 'New form', fields: fields };
}
// What stops a draft from being saved or published, in plain words ('' = fine).
function fbProblems(draft) {
  if (!String(draft.title || '').trim()) return 'Give the form a name.';
  var fields = draft.fields || [];
  if (!fields.length) return 'Add at least one block.';
  var seen = {};
  for (var i = 0; i < fields.length; i++) {
    var f = fields[i], kind = pvKind(f);
    if (!f.key || seen[f.key]) return 'Two blocks share a name inside the form — remove one and add it again.';
    seen[f.key] = 1;
    if (kind !== 'paragraph' && !String(f.label || '').trim()) return 'Block ' + (i + 1) + ' needs a question or heading.';
    if ((kind === 'dropdown' || kind === 'choice') && !pvOptions(f).length) return '"' + f.label + '" needs at least one option.';
  }
  return '';
}
/*PURE-END fbbuilder*/

function formsPage() {
  return {
    defs: [],
    subs: [],
    loading: true,
    loadError: '',
    previewSlug: '',
    previewData: {},
    submitting: false,
    submitted: false,
    contactNames: {},
    labelMap: {},
    artists: [],
    // Builder state: the working copy of the form being edited.
    draft: null,
    draftRaw: null,
    draftDirty: false,
    openBlock: -1,
    adding: false,
    addAt: -1,
    saving: false,
    showTemplates: false,
    palette: FB_PALETTE,
    fbBlockName: fbBlockName,
    raws: {},

    // Renderer helpers, exposed to the Preview template.
    pvKind: pvKind, pvInputType: pvInputType, pvOptions: pvOptions, pvCfg: pvCfg,
    pvChecksItems: pvChecksItems, pvAgreeParts: pvAgreeParts, pvText: pvText,
    pvSubFields: pvSubFields, pvHelp: pvHelp, pvPlaceholder: pvPlaceholder,
    pvTitle: pvTitle, pvSigMode: pvSigMode, pvStandinNote: pvStandinNote,
    pvSec2: pvSec2, pvSec1: pvSec1, pvScaleOpts: pvScaleOpts, pvWidgetLine: pvWidgetLine,
    pvArtistFixed: pvArtistFixed, pvAgeNote: pvAgeNote, pvMinorCfg: pvMinorCfg,
    pvRich: pvRich, pvExempt: pvExempt,

    async loadData() {
      this.loading = true;
      this.loadError = '';
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var data = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv');
        var pairs = data.kv_pairs || [];
        var defs = [];
        var subs = [];
        var contactNames = {};
        var labelMap = {};
        var artistRecs = {};
        var artistOrder = [];
        var raws = {};
        pairs.forEach(function(pr) {
          if (!pr.key) return;
          var v = pr.value;
          if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
          if (!v) return;
          if (pr.key.indexOf('contact/') === 0) {
            if (v.name) contactNames[pr.key] = v.name;
          } else if (pr.key.indexOf('formsub/') === 0) {
            subs.push({ key: pr.key, form: v.form || '', uuid: v.uuid || '', ts: v.ts || '', source: v.source || '', test: !!v.test, processed: !!v.processed, contact: v.contact || '', data: v.data || {} });
          } else if (pr.key.indexOf('form/') === 0) {
            (Array.isArray(v.fields) ? v.fields : []).forEach(function(f) {
              if (f && f.key && f.label && !labelMap[f.key]) labelMap[f.key] = f.label;
            });
            raws[pr.key.slice(5)] = v;
            if (!v.deleted) defs.push({ slug: pr.key.slice(5), title: v.title || pr.key.slice(5), fields: Array.isArray(v.fields) ? v.fields : [], public_url: v.public_url || '', published: !!v.published, by_stax: v.drafted_by === 'stax' && !v.published });
          } else if (pr.key === 'artist/index') {
            if (Array.isArray(v.artists)) artistOrder = v.artists.slice();
          } else if (pr.key.indexOf('artist/') === 0) {
            artistRecs[pr.key.slice(7)] = v.display_name || v.name || pr.key.slice(7);
          }
        });
        defs.sort(function(a, b) { return a.title.localeCompare(b.title); });
        subs.sort(function(a, b) { return new Date(b.ts || 0) - new Date(a.ts || 0); });
        this.defs = defs;
        this.raws = raws;
        // The Build view only exists while a form is open in it.
        if (Alpine.store('app').formsTab === 'build' && !this.draft) Alpine.store('app').formsTab = 'forms';
        this.subs = subs;
        this.contactNames = contactNames;
        this.labelMap = labelMap;
        var order = artistOrder.length ? artistOrder : Object.keys(artistRecs);
        this.artists = order.filter(function(id) { return artistRecs[id]; }).map(function(id) { return { id: id, name: artistRecs[id] }; });
        Alpine.store('app').formsNewCount = subs.filter(function(s) { return !s.processed; }).length;
        if (!this.previewSlug && defs.length) this.setPreview(pvDefaultSlug(defs));
      } catch(e) {
        this.loadError = e.message || 'Could not load forms.';
      }
      this.loading = false;
    },

    get tab() { return Alpine.store('app').formsTab; },

    defOf(slug) {
      return this.defs.find(function(d) { return d.slug === slug; }) || null;
    },

    subsOf(slug) {
      return this.subs.filter(function(s) { return s.form === slug; });
    },

    // While building, the preview pane shows the working copy.
    get previewDef() { return this.tab === 'build' && this.draft ? this.draft : this.defOf(this.previewSlug); },

    setPreview(slug) {
      this.previewSlug = slug;
      this.submitted = false;
      var def = this.defOf(slug);
      this.previewData = def ? pvSeed(def, this.artists) : {};
    },

    // ── Builder ──────────────────────────────────────────────────────
    get building() { return this.tab === 'build' && !!this.draft; },
    formLink(slug) { return window.location.origin + '/f/' + slug; },
    draftProblem() { return this.draft ? fbProblems(this.draft) : ''; },
    settingsOf(f) { return fbSettings(f); },

    reseed() { if (this.draft) this.previewData = pvSeed(this.draft, this.artists); this.submitted = false; },
    touch() { this.draftDirty = true; },

    startNew(template) {
      var t = fbTemplate(template);
      var taken = {};
      Object.keys(this.raws).forEach(function(k) { taken[k] = 1; });
      this.draft = { slug: fbUniqueSlug(t.title, taken), title: t.title, fields: t.fields, published: false, public_url: '', isNew: true };
      this.draftRaw = {};
      this.draftDirty = true;
      this.openBlock = -1; this.adding = false; this.showTemplates = false;
      Alpine.store('app').formsTab = 'build';
      this.reseed();
    },

    editForm(slug) {
      if (this.draft && this.draft.slug === slug && this.draftDirty) { Alpine.store('app').formsTab = 'build'; return; }
      var d = this.defOf(slug);
      if (!d) return;
      this.draftRaw = JSON.parse(JSON.stringify(this.raws[slug] || {}));
      this.draft = { slug: slug, title: d.title, fields: JSON.parse(JSON.stringify(d.fields)), published: d.published, public_url: d.public_url, isNew: false };
      this.draftDirty = false;
      this.openBlock = -1; this.adding = false;
      Alpine.store('app').formsTab = 'build';
      this.reseed();
    },

    leaveBuilder() { Alpine.store('app').formsTab = 'forms'; },
    async discardDraft() {
      if (this.draft && (this.draftDirty || this.draft.isNew)) {
        var ok = await StaxUI.confirm({
          title: 'Discard your changes?',
          message: 'The edits to \u201c' + (this.draft.title || 'this form') + '\u201d since you last saved are thrown away. The saved form stays as it was.',
          confirmLabel: 'Discard', danger: true
        });
        if (!ok) return;
      }
      this.draft = null; this.draftRaw = null; this.draftDirty = false; Alpine.store('app').formsTab = 'forms';
    },

    openAdd(at) { this.adding = true; this.addAt = at; this.openBlock = -1; },
    addBlock(entry) {
      var f = fbNewBlock(entry, this.draft.fields);
      var at = this.addAt < 0 || this.addAt > this.draft.fields.length ? this.draft.fields.length : this.addAt;
      this.draft.fields.splice(at, 0, f);
      this.adding = false;
      this.openBlock = at;
      this.touch(); this.reseed();
      var self = this;
      this.$nextTick(function() {
        var el = self.$root.querySelector('[data-fb-index="' + at + '"]');
        if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      });
    },
    removeBlock(i) {
      var self = this;
      var draft = this.draft;
      var removed = draft.fields.splice(i, 1)[0];
      this.openBlock = -1;
      this.touch(); this.reseed();
      if (!removed) return;
      StaxUI.undo('Removed \u201c' + (fbBlockName(removed) || 'block') + '\u201d', function() {
        // Only into the same form, still open: never into a different draft.
        if (self.draft !== draft) return;
        draft.fields.splice(Math.min(i, draft.fields.length), 0, removed);
        self.touch(); self.reseed();
      });
    },
    moveBlock(i, by) {
      var j = i + by;
      if (j < 0 || j >= this.draft.fields.length) return;
      var f = this.draft.fields.splice(i, 1)[0];
      this.draft.fields.splice(j, 0, f);
      if (this.openBlock === i) this.openBlock = j;
      this.touch();
    },
    setSetting(row, value) { row.set(value); this.touch(); },

    // The stored record: everything the form already carried (older
    // fields this builder does not edit) plus what the builder owns.
    draftRecord(published) {
      var rec = JSON.parse(JSON.stringify(this.draftRaw || {}));
      rec.title = String(this.draft.title || '').trim();
      rec.fields = JSON.parse(JSON.stringify(this.draft.fields));
      rec.published = !!published;
      rec.updated = new Date().toISOString();
      delete rec.deleted;
      return rec;
    },

    async saveDraft(publish) {
      if (!this.draft || this.saving) return false;
      if (publish === false) {
        var down = await StaxUI.confirm({
          title: 'Take this form down?',
          message: 'The link stops working for anyone who has it. You can publish it again later.',
          confirmLabel: 'Take down', danger: true
        });
        if (!down) return false;
      }
      var problem = fbProblems(this.draft);
      if (problem) { OpenFangToast.error(problem); return false; }
      var published = publish === undefined ? !!this.draft.published : !!publish;
      this.saving = true;
      var ok = false;
      try {
        var rec = this.draftRecord(published);
        var slug = this.draft.slug;
        var path = '/api/memory/agents/shared/kv/' + encodeURIComponent('form/' + slug);
        await OpenFangAPI.put(path, { value: rec });
        // Read it back: "saved" is only said about a record that is there.
        var back = await OpenFangAPI.get(path);
        var stored = back && back.value;
        if (typeof stored === 'string') { try { stored = JSON.parse(stored); } catch(e) { stored = null; } }
        if (!stored || stored.title !== rec.title || (stored.fields || []).length !== rec.fields.length || !!stored.published !== published) {
          throw new Error('The form did not save. Nothing was changed — try again.');
        }
        this.draftRaw = rec;
        this.draft.published = published;
        this.draft.isNew = false;
        this.draftDirty = false;
        ok = true;
        OpenFangToast.success(publish === true ? 'Published — the link is live' : publish === false ? 'Taken down — the link no longer works' : 'Saved');
        await this.loadData();
      } catch(e) {
        OpenFangToast.error(e.message || 'The form did not save.');
      }
      this.saving = false;
      return ok;
    },

    async copyLink(slug) {
      var link = this.formLink(slug);
      try { await navigator.clipboard.writeText(link); OpenFangToast.success('Link copied'); }
      catch(e) { OpenFangToast.error('Copy did not work here — the link is ' + link); }
    },

    async deleteForm(slug) {
      var def = this.defOf(slug) || {};
      var ok = await StaxUI.confirm({
        title: 'Remove this form?',
        message: '\u201c' + (def.title || slug) + '\u201d comes off your list and its link stops working. Submissions already sent are kept.',
        confirmLabel: 'Remove', danger: true
      });
      if (!ok) return;
      try {
        var rec = JSON.parse(JSON.stringify(this.raws[slug] || {}));
        rec.deleted = true; rec.published = false; rec.updated = new Date().toISOString();
        await OpenFangAPI.put('/api/memory/agents/shared/kv/' + encodeURIComponent('form/' + slug), { value: rec });
        if (this.draft && this.draft.slug === slug) { this.draft = null; this.draftDirty = false; }
        OpenFangToast.success('Form removed. Its submissions are kept.');
        await this.loadData();
      } catch(e) { OpenFangToast.error(e.message || 'The form could not be removed.'); }
    },

    fieldLabel(slug, key) {
      var d = this.defOf(slug);
      if (d) {
        var f = d.fields.find(function(x) { return x.key === key; });
        if (f && f.label) return f.label;
      }
      return this.labelMap[key] || staxHumanKey(key);
    },

    // Answers render through the one shared helper (app.js) — the
    // same rows Contacts shows on the person.
    answerRows(s) {
      var d = this.defOf(s.form);
      return staxAnswerRows(s.data, d ? d.fields : [], this.labelMap);
    },

    // The card footer names the person, never their record key;
    // when the pointer does not resolve, the footer stays off.
    contactName(s) {
      if (s.contact && this.contactNames[s.contact]) return this.contactNames[s.contact];
      var e = ((s.data || {}).email || '').toLowerCase();
      if (e && this.contactNames['contact/' + e]) return this.contactNames['contact/' + e];
      return '';
    },

    fmtTs(ts) {
      if (!ts) return '';
      var d = new Date(ts);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    },

    async submitPreview() {
      var def = this.previewDef;
      if (!def || this.submitting) return;
      if (this.building && (this.draftDirty || this.draft.isNew)) {
        OpenFangToast.error('Save the form first, then send a test.');
        return;
      }
      if (!def.fields.length) {
        OpenFangToast.error('This form has no fields to test yet.');
        return;
      }
      // Required check with the public form's rules; stand-in kinds
      // (signature, uploads) are exempt — see pvMissing.
      for (var i = 0; i < def.fields.length; i++) {
        var missing = pvMissing(def.fields[i], this.previewData);
        if (missing) {
          OpenFangToast.error('Please fill in: ' + missing);
          return;
        }
      }
      this.submitting = true;
      try {
        var uuid = (crypto.randomUUID ? crypto.randomUUID() : 'test-' + Date.now());
        var rec = {
          form: def.slug,
          uuid: uuid,
          ts: new Date().toISOString(),
          source: 'preview',
          test: true,
          data: pvCompose(def, this.previewData)
        };
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        await OpenFangAPI.put('/api/memory/agents/' + agentId + '/kv/' + encodeURIComponent('formsub/' + def.slug + '/' + uuid), { value: rec });
        this.submitted = true;
        this.previewData = pvSeed(def, this.artists);
        OpenFangToast.success('Test submission saved — see Submissions');
        await this.loadData();
      } catch(e) {
        OpenFangToast.error(e.message);
      }
      this.submitting = false;
    }
  };
}
