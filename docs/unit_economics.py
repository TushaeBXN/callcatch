"""
CallCatch unit-economics calculator. Standard library only, no installs.

    python docs/unit_economics.py                       # the worked example (FAKE numbers)
    python docs/unit_economics.py --calls-per-week 60   # change any input
    python docs/unit_economics.py --help                # list every input

EVERY cost below is a FAKE placeholder. VERIFY each one against current
vendor pricing before using any result. The script never looks up real prices,
and its defaults are round example numbers, not vendor quotes.

Read docs/unit-economics.md for what each output means, and why the
"usage cap" output must NOT be read as "turn off emergency paging".
"""

import argparse
import sys
from dataclasses import dataclass, fields

WEEKS_PER_MONTH = 52 / 12   # about 4.33


@dataclass
class Inputs:
    # --- volume ---
    calls_per_week: float = 25            # EXAMPLE. Ask the owner at onboarding (docs/onboarding.md step 1.1).
    avg_minutes_per_call: float = 3.0     # EXAMPLE.
    # --- variable costs (all FAKE, VERIFY) ---
    telephony_per_min: float = 0.05       # FAKE, VERIFY: inbound minutes plus forwarding
    stt_per_min: float = 0.05             # FAKE, VERIFY: speech-to-text
    tts_per_min: float = 0.05             # FAKE, VERIFY: text-to-speech
    llm_per_call: float = 0.10            # FAKE, VERIFY: model cost for one whole call
    notification_cost: float = 0.05       # FAKE, VERIFY: one SMS or email
    notifications_per_call: float = 2     # EXAMPLE: one text plus one email per call
    # --- fixed monthly costs per client (all FAKE, VERIFY) ---
    number_rental_monthly: float = 5.00   # FAKE, VERIFY
    monitoring_monthly: float = 10.00     # FAKE, VERIFY
    tools_monthly: float = 20.00          # FAKE, VERIFY: share of tooling or hosting
    # --- what we charge (TODO(me): real pricing decision) ---
    setup_fee: float = 500.00             # EXAMPLE, TODO(me)
    monthly_retainer: float = 300.00      # EXAMPLE, TODO(me)
    # --- policy knobs ---
    min_margin_pct: float = 40.0          # EXAMPLE, TODO(me): lowest monthly margin we accept before a cap or overage kicks in
    setup_amortize_months: float = 12     # spread the setup fee over this many months for the first-year view
    avg_job_value: float = 0.0            # optional: the client's average job value, for their break-even (0 = skip)


class InputError(ValueError):
    pass


def validate(i: Inputs):
    problems = []
    for f in fields(i):
        v = getattr(i, f.name)
        if not isinstance(v, (int, float)) or v != v:   # v != v catches NaN
            problems.append(f"{f.name} must be a number")
        elif v < 0:
            problems.append(f"{f.name} can't be negative (got {v})")
    if i.calls_per_week <= 0:
        problems.append("calls_per_week must be greater than 0")
    if i.avg_minutes_per_call <= 0:
        problems.append("avg_minutes_per_call must be greater than 0")
    if not (0 <= i.min_margin_pct < 100):
        problems.append("min_margin_pct must be at least 0 and less than 100")
    if i.setup_amortize_months <= 0:
        problems.append("setup_amortize_months must be greater than 0")
    if problems:
        raise InputError("Invalid inputs:\n  - " + "\n  - ".join(problems))


def calculate(i: Inputs) -> dict:
    validate(i)
    per_min = i.telephony_per_min + i.stt_per_min + i.tts_per_min
    cost_per_call = i.avg_minutes_per_call * per_min + i.llm_per_call + i.notifications_per_call * i.notification_cost
    calls_per_month = i.calls_per_week * WEEKS_PER_MONTH
    fixed = i.number_rental_monthly + i.monitoring_monthly + i.tools_monthly
    variable = cost_per_call * calls_per_month
    monthly_cost = fixed + variable
    margin = i.monthly_retainer - monthly_cost
    margin_pct = (margin / i.monthly_retainer * 100) if i.monthly_retainer > 0 else None

    # Break-even: retainer = fixed + cost_per_call * n
    if cost_per_call > 0:
        break_even = (i.monthly_retainer - fixed) / cost_per_call
        # Cap point: margin falls to min_margin_pct: retainer*(1 - m) = fixed + cost_per_call * n
        cap_point = (i.monthly_retainer * (1 - i.min_margin_pct / 100) - fixed) / cost_per_call
    else:
        break_even = cap_point = float("inf")

    first_year_revenue = i.monthly_retainer * 12 + i.setup_fee
    first_year_margin = first_year_revenue - monthly_cost * 12
    amortized_margin = margin + i.setup_fee / i.setup_amortize_months

    return {
        "cost_per_min": per_min,
        "cost_per_call": cost_per_call,
        "calls_per_month": calls_per_month,
        "fixed_monthly": fixed,
        "variable_monthly": variable,
        "monthly_cost": monthly_cost,
        "monthly_margin": margin,
        "monthly_margin_pct": margin_pct,
        "amortized_margin": amortized_margin,
        "first_year_margin": first_year_margin,
        "break_even_calls_per_month": break_even,
        "cap_point_calls_per_month": cap_point,
        "client_jobs_to_cover_retainer": (i.monthly_retainer / i.avg_job_value) if i.avg_job_value > 0 else None,
    }


def _money(x, places=2):
    return f"${x:,.{places}f}" if x >= 0 else f"-${-x:,.{places}f}"


def _volume(n):
    if n == float("inf"):
        return "never (no per-call cost)"
    if n <= 0:
        return "already past it at ANY volume (fixed costs alone exceed the target)"
    return f"{n:,.0f} calls/month (~{n / WEEKS_PER_MONTH:,.0f}/week)"


def report(i: Inputs) -> str:
    r = calculate(i)
    lines = [
        "CallCatch unit economics: ALL COSTS ARE FAKE PLACEHOLDERS. VERIFY before use.",
        "",
        "INPUTS",
        f"  Calls per week .................. {i.calls_per_week:g}  ({r['calls_per_month']:.1f}/month)",
        f"  Avg minutes per call ............ {i.avg_minutes_per_call:g}",
        f"  Telephony / STT / TTS per min ... {_money(i.telephony_per_min, 4)} / {_money(i.stt_per_min, 4)} / {_money(i.tts_per_min, 4)}   [FAKE, VERIFY]",
        f"  LLM per call .................... {_money(i.llm_per_call, 4)}   [FAKE, VERIFY]",
        f"  Notifications ................... {i.notifications_per_call:g} x {_money(i.notification_cost, 4)}   [FAKE, VERIFY]",
        f"  Fixed monthly ................... {_money(r['fixed_monthly'])} (number {_money(i.number_rental_monthly)}, monitoring {_money(i.monitoring_monthly)}, tools {_money(i.tools_monthly)})   [FAKE, VERIFY]",
        f"  Setup fee / monthly retainer .... {_money(i.setup_fee)} / {_money(i.monthly_retainer)}   [EXAMPLE, TODO(me)]",
        f"  Minimum acceptable margin ....... {i.min_margin_pct:g}%   [EXAMPLE, TODO(me)]",
        "",
        "OUTPUTS",
        f"  Cost per call ................... {_money(r['cost_per_call'], 4)}",
        f"  Monthly cost per client ......... {_money(r['monthly_cost'])}  (fixed {_money(r['fixed_monthly'])} + variable {_money(r['variable_monthly'])})",
    ]
    if r["monthly_margin_pct"] is None:
        lines.append(f"  Monthly margin .................. {_money(r['monthly_margin'])}  (no retainer, so % is undefined)")
    else:
        lines.append(f"  Monthly margin .................. {_money(r['monthly_margin'])}  ({r['monthly_margin_pct']:.1f}% of retainer)")
    lines += [
        f"  Margin incl. setup fee (amortized over {i.setup_amortize_months:g} mo) {_money(r['amortized_margin'])}/month",
        f"  First-year margin incl. setup ... {_money(r['first_year_margin'])}",
        f"  Break-even (margin = $0) ........ {_volume(r['break_even_calls_per_month'])}",
        f"  Usage-cap point ................. {_volume(r['cap_point_calls_per_month'])}  (margin falls to {i.min_margin_pct:g}%)",
    ]
    if r["client_jobs_to_cover_retainer"] is not None:
        lines.append(f"  Client break-even ............... {r['client_jobs_to_cover_retainer']:.1f} extra jobs/month at {_money(i.avg_job_value)} per job")

    cap = r["cap_point_calls_per_month"]
    if 0 < cap < float("inf") and r["calls_per_month"] > cap:
        lines += ["", "  NOTE: this client's volume is ABOVE the usage-cap point. Pricing needs a cap or overage (see REMINDER)."]
    elif cap <= 0:
        lines += ["", "  NOTE: the retainer can't meet the minimum margin even at zero calls. Revisit pricing."]
    lines += [
        "",
        "  REMINDER: the usage-cap point is a PRICING signal. It doesn't answer what happens",
        "  to emergency detection and paging at the cap. That is still an open question: see",
        "  docs/service-agreement-outline.md section 6 (attorney item 2) and section 10a (item 1).",
    ]

    # sensitivity table
    lines += ["", "SENSITIVITY (same costs, different volumes)",
              "  calls/week   monthly cost   margin      margin %"]
    for cpw in (10, 25, 50, 100, 200):
        rr = calculate(Inputs(**{**i.__dict__, "calls_per_week": cpw}))
        pct = f"{rr['monthly_margin_pct']:.1f}%" if rr["monthly_margin_pct"] is not None else "n/a"
        lines.append(f"  {cpw:>10}   {_money(rr['monthly_cost']):>12}   {_money(rr['monthly_margin']):>9}   {pct:>8}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="CallCatch unit economics. All defaults are FAKE examples; VERIFY every cost.")
    for f in fields(Inputs):
        parser.add_argument("--" + f.name.replace("_", "-"), type=float, default=f.default, dest=f.name,
                            help=f"(default {f.default:g})")
    args = parser.parse_args(argv)
    try:
        print(report(Inputs(**vars(args))))
    except InputError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
