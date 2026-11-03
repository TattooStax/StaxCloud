# Gate-2 bridge — status: STAGED, not live

File: `bridge-gate2-staged.py` (sha256 1d16b29a…)

## What it adds over the live Fix-2 bridge
- Content binding: before sending, the bridge verifies the live approval's
  description contains the outbox record's exact recipient string and exact
  full body text — an approval id alone no longer authorizes arbitrary content.
- Single-use: a kv ledger (`approvalused/<approval_id>`) is written at the
  'sent' transition; an already-spent approval id is refused as consumed.
  The ledger read fails closed on transport error.

## Why it is staged, not live
It was deployed to the Dell on 2026-11-02 but its acceptance proofs were never
run: the proof step (fabricated forgery/reuse test records) was refused by a
safety policy and was not retried or routed around. Unproven code does not stay
on the send path, so the bridge was rolled back to the proven Fix-2 build
(sha256 a93b1456…) on the Dell and in the VM master on 2026-11-02.

## Proofs it still needs before it may go live
1. Forgery-with-real-id: an outbox record carrying a genuine approved id but
   altered body (and a variant with altered recipient) is refused, thread
   count unchanged, nothing sent.
2. Reuse: a second outbox record presenting an already-consumed approval id
   is refused as spent.
3. Legit path: one genuinely approved reply sends exactly once and the
   consumption ledger entry is written and read back.

Until all three are observed at the receiving end, the Fix-2 bridge remains
the live build.
