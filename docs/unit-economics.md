# Unit Economics

> **Every cost in this document and in `unit_economics.py` is a FAKE
> placeholder.** The numbers are round examples chosen to show how the math
> works. They are **not** vendor prices. VERIFY every cost input against the
> vendor's current pricing page before using any result for pricing or quotes.

Calculator: [`docs/unit_economics.py`](unit_economics.py). It uses only Python's
standard library, so there's nothing to install.

## How to run it

```bash
python docs/unit_economics.py
```
Runs the worked example below, using the fake defaults.

```bash
python docs/unit_economics.py --calls-per-week 60 --avg-job-value 250
```
Changes any input. Every input has a `--flag`. Run `--help` for the full list.

## Inputs

| Input | Flag | Meaning | Status |
|---|---|---|---|
| Calls per week | `--calls-per-week` | Forwarded calls CallCatch answers | Ask the owner (onboarding 1.1) |
| Average minutes per call | `--avg-minutes-per-call` | Length of a typical call | Estimate, then measure |
| Telephony cost per minute | `--telephony-per-min` | Inbound minutes, including forwarding legs | **FAKE, VERIFY** |
| Speech-to-text per minute | `--stt-per-min` | Turning the caller's speech into text | **FAKE, VERIFY** |
| Text-to-speech per minute | `--tts-per-min` | Turning the assistant's replies into speech | **FAKE, VERIFY** |
| LLM cost per call | `--llm-per-call` | Model cost for one whole conversation | **FAKE, VERIFY**. Estimate from test-run token counts. |
| Cost per notification | `--notification-cost` | One SMS or email | **FAKE, VERIFY** |
| Notifications per call | `--notifications-per-call` | For example, 2 = a text plus an email | Example |
| Number rental, monitoring, tools (monthly) | `--number-rental-monthly`, `--monitoring-monthly`, `--tools-monthly` | Fixed cost per client per month | **FAKE, VERIFY** |
| Setup fee | `--setup-fee` | One-time charge to the client | TODO(me) |
| Monthly retainer | `--monthly-retainer` | Monthly charge to the client | TODO(me) |
| Minimum acceptable margin | `--min-margin-pct` | The lowest monthly margin we accept before a cap or overage applies | TODO(me) |
| Setup amortization months | `--setup-amortize-months` | Spreads the setup fee for the "including setup" view | Example: 12 |
| Client's average job value | `--avg-job-value` | Optional. Shows how many extra jobs pay for the retainer (onboarding 1.2) | Ask the owner |

**Simplifying assumption:** speech-to-text and text-to-speech are both billed on
the full call length. That's conservative, since in reality each side speaks for
only part of the call. VERIFY how each vendor actually bills: by the second, by
the minute, or with a minimum charge.

## Formulas

- **Cost per call** = minutes × (telephony + STT + TTS per minute) + LLM per call + notifications × cost per notification
- **Calls per month** = calls per week × 52 ÷ 12
- **Monthly cost per client** = fixed monthly + cost per call × calls per month
- **Monthly margin** = retainer − monthly cost (shown in dollars and as a percentage of the retainer)
- **Break-even volume** = (retainer − fixed) ÷ cost per call. Above this many calls per month, the client costs more than they pay.
- **Usage-cap point** = (retainer × (1 − minimum margin) − fixed) ÷ cost per call. Above this many calls, margin drops below the minimum, so pricing needs a cap, an overage charge, or a higher retainer.

## Worked example (FAKE numbers)

This is the real output of `python docs/unit_economics.py`:

```
CallCatch unit economics: ALL COSTS ARE FAKE PLACEHOLDERS. VERIFY before use.

INPUTS
  Calls per week .................. 25  (108.3/month)
  Avg minutes per call ............ 3
  Telephony / STT / TTS per min ... $0.0500 / $0.0500 / $0.0500   [FAKE, VERIFY]
  LLM per call .................... $0.1000   [FAKE, VERIFY]
  Notifications ................... 2 x $0.0500   [FAKE, VERIFY]
  Fixed monthly ................... $35.00 (number $5.00, monitoring $10.00, tools $20.00)   [FAKE, VERIFY]
  Setup fee / monthly retainer .... $500.00 / $300.00   [EXAMPLE, TODO(me)]
  Minimum acceptable margin ....... 40%   [EXAMPLE, TODO(me)]

OUTPUTS
  Cost per call ................... $0.6500
  Monthly cost per client ......... $105.42  (fixed $35.00 + variable $70.42)
  Monthly margin .................. $194.58  (64.9% of retainer)
  Margin incl. setup fee (amortized over 12 mo) $236.25/month
  First-year margin incl. setup ... $2,835.00
  Break-even (margin = $0) ........ 408 calls/month (~94/week)
  Usage-cap point ................. 223 calls/month (~51/week)  (margin falls to 40%)

  REMINDER: the usage-cap point is a PRICING signal. It doesn't answer what happens
  to emergency detection and paging at the cap. That is still an open question: see
  docs/service-agreement-outline.md section 6 (attorney item 2) and section 10a (item 1).

SENSITIVITY (same costs, different volumes)
  calls/week   monthly cost   margin      margin %
          10         $63.17     $236.83      78.9%
          25        $105.42     $194.58      64.9%
          50        $175.83     $124.17      41.4%
         100        $316.67     -$16.67      -5.6%
         200        $598.33    -$298.33     -99.4%
```

**Reading it:** at 25 calls a week, this fake client costs about $105 a month
against a $300 retainer, a 64.9% margin. Margin falls to the 40% minimum at
about 51 calls a week, and to zero at about 94 calls a week. The sensitivity
table shows the same thing: by 100 calls a week, this fake client loses money.

### Same example, higher volume (above the cap point)

`python docs/unit_economics.py --calls-per-week 60 --avg-job-value 250`, outputs section:

```
OUTPUTS
  Cost per call ................... $0.6500
  Monthly cost per client ......... $204.00  (fixed $35.00 + variable $169.00)
  Monthly margin .................. $96.00  (32.0% of retainer)
  Margin incl. setup fee (amortized over 12 mo) $137.67/month
  First-year margin incl. setup ... $1,652.00
  Break-even (margin = $0) ........ 408 calls/month (~94/week)
  Usage-cap point ................. 223 calls/month (~51/week)  (margin falls to 40%)
  Client break-even ............... 1.2 extra jobs/month at $250.00 per job

  NOTE: this client's volume is ABOVE the usage-cap point. Pricing needs a cap or overage (see REMINDER).

  REMINDER: the usage-cap point is a PRICING signal. It doesn't answer what happens
  to emergency detection and paging at the cap. That is still an open question: see
  docs/service-agreement-outline.md section 6 (attorney item 2) and section 10a (item 1).
```

### Invalid inputs are rejected, not calculated

`python docs/unit_economics.py --calls-per-week 0 --telephony-per-min -0.01`:

```
Invalid inputs:
  - telephony_per_min can't be negative (got -0.01)
  - calls_per_week must be greater than 0
```
The script exits with code 1. It also rejects a minimum margin of 100% or more,
and non-number inputs. It never divides by zero: with no per-call cost, break-even
shows as "never".

## The usage-cap output is NOT a decision about emergencies

The usage-cap point tells us **when pricing needs to change**. It doesn't say
**what the service should do** when a client passes that volume.

In particular, **a usage cap must not silently disable emergency detection or
paging.** Whether emergency handling keeps working after a cap is reached is an
**open product and legal decision**, recorded in:

- **`docs/service-agreement-outline.md` section 6 ("Usage caps and overage")**:
  the open question of whether emergency detection and paging keep working after
  a cap is reached. It's **item 2** on that document's attorney question list
  (section 15).
- **`docs/service-agreement-outline.md` section 10a ("Emergency paging —
  separate open question for the attorney")**: the liability question for the
  paging function, which a cap that turned paging off would directly affect.
  It's **item 1** on the attorney list.

Until those are decided, this calculator assumes nothing. It flags the volume and
prints the reminder every time. TODO(me): once decided, record the answer here
and in the agreement. Any cap should then be built so that emergency detection
and paging are handled exactly as decided, never as a side effect of a spend
limit.

The same applies to our internal spend caps in `.env` (`SPEND_CAP_MONTHLY_USD`,
`SPEND_CAP_DAILY_USD`). What happens to emergency calls when one of those
triggers is part of the same open decision. TODO(me).

## Getting real numbers

1. Look up each vendor's current pricing and note the date you checked. VERIFY.
2. Measure real call length and LLM tokens per call. The scenario runner prints
   token totals, but pilot calls are better.
3. Rerun the calculator with the real inputs, and keep the run with its date in
   your pricing notes. Don't commit vendor quotes that are under an NDA
   (a non-disclosure agreement).
