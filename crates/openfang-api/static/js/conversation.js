// StaxCloud conversations — the shared conversation view for the
// Channels surfaces. Team and Texts instantiate it; Email takes the
// grammar only. The component renders a head, a scrolling message
// region, and a composer — and it NEVER sends anything. It emits
// the composer's text to a handler the host surface must supply as
// onDraft(body); there is no default handler and no flag. Team's
// handler writes the team record; Texts' handler holds the reply
// for approval. A surface that forgets the handler cannot send —
// the submit simply refuses.
'use strict';

/*PURE-BEGIN conv*/
var CONV_EVERYONE = 'everyone';
var CONV_READ_CAP = 200;

// A person's conversation-safe slug: lowercase, runs of anything
// non-alphanumeric become one dash, no edge dashes.
function convSlug(name) {
  return (name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

// The 1:1 conversation id for two people: deterministic from the
// sorted member pair, so both directions name the same conversation
// and no creation record is needed.
function convPairId(a, b) {
  var s = [convSlug(a), convSlug(b)].sort();
  return 'dm:' + s[0] + '+' + s[1];
}

// The conversation a stored message belongs to: its conv field, or
// Everyone for records written before conversations existed.
function convOf(v) {
  return (v && typeof v.conv === 'string' && v.conv) ? v.conv : CONV_EVERYONE;
}

// The 1:1 conversations a viewer can open: one per other person on
// the roster, keyed by the other person's name. Stax is never a 1:1
// target — he is a member of Everyone only until he can be woken
// inside a conversation — and nobody has a 1:1 with themselves.
function convPairIdsFor(people, viewer) {
  var out = {};
  (people || []).forEach(function(p) {
    if (!p || !p.name) return;
    if (p.name === viewer || p.name === 'Stax') return;
    out[p.name] = convPairId(viewer, p.name);
  });
  return out;
}

// Every 1:1 id derivable from the roster (any pair, either order) —
// the resolution set: a message in one of these conversations has a
// home even when the signed-in viewer is not one of its members.
function convAllPairIds(people) {
  var out = {};
  var names = (people || []).map(function(p) { return p && p.name; }).filter(Boolean);
  for (var i = 0; i < names.length; i++)
    for (var j = i + 1; j < names.length; j++)
      out[convPairId(names[i], names[j])] = true;
  return out;
}

// Group messages (already sorted oldest to newest) by conversation,
// keeping at most CONV_READ_CAP per conversation — the cap is per
// conversation, so a busy room cannot starve a quiet one. A message
// whose conversation is not in `known` (a group record that never
// landed, a name that left the roster) lands in Everyone rather
// than being lost.
function groupByConv(msgs, known) {
  var out = {};
  (msgs || []).forEach(function(m) {
    var id = convOf(m);
    if (id !== CONV_EVERYONE && !(known && known[id])) id = CONV_EVERYONE;
    (out[id] || (out[id] = [])).push(m);
  });
  Object.keys(out).forEach(function(id) {
    if (out[id].length > CONV_READ_CAP) out[id] = out[id].slice(-CONV_READ_CAP);
  });
  return out;
}
/*PURE-END conv*/

// The shared conversation-view state and behavior. Hosts compose it
// into their page component with staxWithConversationView and MUST
// define onDraft(body) — the one and only way anything leaves the
// composer.
/*PURE-BEGIN compose*/
function staxConversationView() {
  return {
    convDraft: '',
    convSending: false,

    async convSubmit() {
      var body = (this.convDraft || '').trim();
      if (!body || this.convSending) return false;
      if (typeof this.onDraft !== 'function') {
        if (window.OpenFangToast) OpenFangToast.error('This conversation is not set up to send.');
        return false;
      }
      this.convSending = true;
      var ok = false;
      try {
        await this.onDraft(body);
        this.convDraft = '';
        ok = true;
      } catch (e) {
        if (window.OpenFangToast) OpenFangToast.error((e && e.message) || 'Could not send. Try again.');
      }
      this.convSending = false;
      if (ok) this.convScrollToNewest();
      return ok;
    },

    // Land on the newest message: on open the fetched rows paint
    // after this runs, so keep setting the scroll each frame until
    // the content height is stable across consecutive frames AND
    // the scroll verifies at the bottom. The frame bound is the
    // fallback exit for a list with no overflow.
    convScrollToNewest() {
      var self = this;
      this.$nextTick(function() {
        var tries = 0, lastHeight = -1, stableFrames = 0;
        var go = function() {
          var el = self.$refs.convScroll;
          if (!el) return;
          var h = el.scrollHeight;
          el.scrollTop = h;
          var overflows = h > el.clientHeight;
          if (overflows && h === lastHeight) stableFrames++;
          else stableFrames = 0;
          lastHeight = h;
          var atBottom = (h - el.clientHeight - el.scrollTop) <= 2;
          if (overflows && stableFrames >= 2 && atBottom) return;
          if (++tries < 45) requestAnimationFrame(go);
        };
        go();
      });
    }
  };
}

// Compose the conversation view into a host page object. Plain
// property copy, never Object.assign onto the page: a host page may
// define getters (Texts' selected thread is one), and assigning
// through them would freeze the getter's current value into a
// static property. Host-defined properties win.
function staxWithConversationView(page) {
  var view = staxConversationView();
  Object.keys(view).forEach(function(k) {
    if (!(k in page)) page[k] = view[k];
  });
  return page;
}
/*PURE-END compose*/
