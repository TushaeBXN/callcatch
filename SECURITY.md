# Security Policy — CallCatch

CallCatch is operated by Anthos Intelligence Company. Every call it handles
involves a real person's name, phone number, and home address, so treat
everything in this repo as if a customer could read it.

## Reporting a problem

If you find a security problem (a leaked key, exposed caller data, a way to
make the assistant misbehave), email **[EMAIL]** <!-- TODO(me): set a monitored security address, e.g. security@yourdomain -->.

- Do not open a public GitHub issue for security problems.
- Include what you found, where, and how to reproduce it.
- Do not test on live client phone lines. Use the staging number.

We aim to acknowledge reports within TODO(me): X business days.

## The rules

1. **Never commit secrets.** API keys, passwords, tokens, `.env` files,
   `*.key`, and `*.pem` stay out of git. Put them in your local `.env`, which is
   gitignored. The gitleaks pre-commit hook helps catch mistakes, but you are
   still responsible.
2. **Never commit client data, transcripts, or recordings.** Real client details
   go only in `clients/<name>/private/`, which is gitignored. `transcripts/` and
   `recordings/` are gitignored too. Use obviously fake examples in the repo, such as
   `Acme HVAC` and `+1-555-0100`.
3. **One phone number and one config per client.** Never share a number or a
   config file between two clients. That keeps one client's callers and data
   separate from another's.
4. **All changes go through a pull request.** Nobody pushes directly to `main`.
   See [CONTRIBUTING.md](CONTRIBUTING.md).
5. **Least privilege.** Each person and each piece of software gets only the
   access it needs. The assistant has exactly three tools and no others (see
   `prompts/base_system_prompt.md`).
6. **Use MFA** on GitHub and on every vendor account.

## If a key leaks: rotate first, then clean up

Order matters. Deleting a key from git history does **not** make it safe, because
anyone may already have copied it.

1. **Rotate now.** Log in to the vendor's console, revoke or delete the leaked
   key, and create a new one. Do this before anything else.
2. **Update** your local `.env`, and any deployed secret store, with the new key.
3. **Check for misuse.** Look at the vendor's usage and billing pages for
   activity you don't recognize.
4. **Tell the maintainer** at [EMAIL], and say which key leaked, when, and where.
5. **Clean up.** Remove the key from the code. If it reached GitHub, the
   maintainer decides whether to rewrite history. Rotation is what actually
   protects us; the cleanup is secondary.
6. **Learn from it.** Add a note to the incident log. TODO(me): decide where
   the incident log lives.

## Data retention

- Transcripts and recordings are kept for **TODO(me): N days**, then deleted.
- A client's agreement may set a shorter period. The shorter period wins.
- VERIFY: Retention and recording rules vary by state. See
  `docs/safety-and-compliance.md` (draft, for attorney review).
