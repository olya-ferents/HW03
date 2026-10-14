""
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAND_ROOT = next(
    (path for path in (HERE.parent / "paypilot-stand", Path("/course"))
     if (path / "app" / "__init__.py").is_file()),
    None,
)
if STAND_ROOT is None:
    raise RuntimeError(
        "Could not find the stand's app package; expected ../paypilot-stand "
        "or /course/app")
sys.path.insert(0, str(STAND_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import seed
from app.engines import disputes, fx, limits, policy

AS_OF = date(2026, 9, 15)

ALLOWANCE_USED_EUR = {
    "CUS-0001": 120.0,
    "CUS-0002": 800.0,
    "CUS-0005": 5000.0,
    "CUS-0007": 0.0,
    "CUS-0010": 15000.0,
}
CUSTOMERS = {
    row[0]: (row[3], ALLOWANCE_USED_EUR[row[0]])
    for row in seed.CUSTOMERS
    if row[0] in ALLOWANCE_USED_EUR
}


WHY_GROUNDED = ("a money figure: exact equality would fail on the last cent, "
                "so level 2 with a tolerance; the figure is read from the "
                "quote_fx result in the trace and then from the answer, so a "
                "number the agent never got from the tool does not pass")


EDGE_IDS = {f"FX-{n:03d}{s}" for n in (6, 7, 8, 9, 10, 11) for s in ("", "-S")}


def case(cid, text, expected, meta):
    if cid in EDGE_IDS:
        meta.update(source="edge", added_in="hw2")
    return {
        "id": cid,
        "input": text,
        "expected_output": expected,
        "context": meta.pop("context", {}),
        "additional_metadata": meta,
    }


def fx_cases():
    ""
    out = []
    plan = [
        ("FX-001", "CUS-0001", 200, "EUR", "USD"),
        ("FX-002", "CUS-0002", 3000, "EUR", "USD"),
        ("FX-003", "CUS-0005", 6000, "EUR", "USD"),
        ("FX-C07", "CUS-0007", 2000, "EUR", "USD"),
        ("FX-005", "CUS-0010", 5000, "GBP", "EUR"),
        ("FX-006", "CUS-0007", 1000, "EUR", "USD"),
        ("FX-007", "CUS-0007", 1001, "EUR", "USD"),
        ("FX-008", "CUS-0001", 380, "EUR", "USD"),
        ("FX-009", "CUS-0001", 381, "EUR", "USD"),
        ("FX-010", "CUS-0002", 200, "EUR", "USD"),
        ("FX-011", "CUS-0002", 201, "EUR", "USD"),
    ]
    for cid, cust, amount, frm, to in plan:
        tier, used = CUSTOMERS[cust]
        q = fx.quote(amount, frm, to, tier, allowance_used_eur=used)
        out.append(case(
            cid,
            f"I'm {cust}. Convert {amount} {frm} to {to}. "
            f"What is the final amount I receive?",
            f"{q.final_amount:.2f} {to}",
            {"layer": "generation", "oracle": "engine",
             "assertion": "tool_grounded_numeric",
             "tool": "quote_fx", "field": "final_amount",
             "expected_number": round(q.final_amount, 2), "tolerance": 0.02,
              "source": "complaint" if cid == "FX-C07" else "engine",
              "failure_mode": "wrong_spread",
              "severity": "high", "runs": 1, "added_in": "l03",
              "gate": "daily", "context": {"customer_id": cust},
              **({"complaint_id": "C-07"} if cid == "FX-C07" else {}),
              "engine_call": (f"fx.quote({amount}, {frm!r}, {to!r}, {tier!r}, "
                              f"allowance_used_eur={used})"),
             "why_this_level": WHY_GROUNDED}))
        if q.spread_pct == 0:
            out.append(case(
                f"{cid}-S", f"I'm {cust}. What spread applies to a {amount} "
                f"{frm} conversion to {to}?",
                "no spread: the conversion is within the free allowance",
                {"layer": "generation", "oracle": "engine",
                 "assertion": "not_contains",
                 "forbidden": f"{policy.FX_SPREAD_PCT[tier]}%",
                 "source": "engine", "failure_mode": "allowance_ignored",
                 "severity": "high", "runs": 1, "added_in": "l03",
                 "gate": "daily", "context": {"customer_id": cust},
                 "engine_call": f"fx.quote(...).spread_pct == 0.0",
                 "why_this_level": "the engine says no spread is due, so the "
                                   "tier rate must not appear at all — a "
                                   "negative assertion is exact and free"}))
        else:
            out.append(case(
                f"{cid}-S", f"I'm {cust}. What spread applies to a {amount} "
                f"{frm} conversion to {to}?",
                f"{q.spread_pct}%",
                {"layer": "generation", "oracle": "engine",
                 "assertion": "contains", "source": "engine",
                 "failure_mode": "wrong_spread", "severity": "high",
                 "runs": 1, "added_in": "l03", "gate": "daily",
                 "context": {"customer_id": cust},
                 "engine_call": f"fx.FX_SPREAD_PCT[{tier!r}] via fx.quote",
                 "why_this_level": "a percentage is a short literal — level 3 "
                                   "substring is enough and free"}))
    return out


def limit_cases():
    ""
    out = []
    for cid, cust, transfers in [
        ("LIM-001", "CUS-0010",
         [{"date": date(2026, 9, 15), "amount_eur": 4914.0},
          {"date": date(2026, 9, 2), "amount_eur": 30420.0}]),
        ("LIM-002", "CUS-0001", []),
    ]:
        tier, _ = CUSTOMERS[cust]
        st = limits.status(tier, AS_OF, transfers)
        out.append(case(
            cid, f"I'm {cust}. How much of my MONTHLY transfer limit is left?",
            f"EUR {st.monthly_remaining_eur:,.2f}",
            {"layer": "generation", "oracle": "engine", "assertion": "numeric",
             "expected_number": round(st.monthly_remaining_eur, 2),
             "tolerance": 1.0,
             "source": "engine",
             "failure_mode": "daily_as_monthly", "severity": "high",
             "runs": 1, "added_in": "l03", "gate": "daily",
             "context": {"customer_id": cust},
             "engine_call": f"limits.status({tier!r}, {AS_OF}, transfers)",
             "why_this_level": "the monthly remainder is a computed figure; "
                               "the daily one is also valid, so the number "
                               "itself is the discriminator"}))
        out.append(case(
            f"{cid}-D", f"I'm {cust}. What is my remaining DAILY limit today?",
            f"EUR {st.daily_remaining_eur:,.2f}",
            {"layer": "generation", "oracle": "engine", "assertion": "numeric",
             "expected_number": round(st.daily_remaining_eur, 2),
             "tolerance": 1.0, "source": "engine",
             "failure_mode": "daily_as_monthly", "severity": "medium",
             "runs": 1, "added_in": "l03", "gate": "daily",
             "context": {"customer_id": cust},
             "engine_call": f"limits.status({tier!r}, {AS_OF}, transfers)",
             "why_this_level": "paired with the monthly case: together they "
                               "catch a swap that either alone would miss"}))
    complaint_status = limits.status(
        "tier3", AS_OF,
        [{"date": date(2026, 9, 15), "amount_eur": 4914.0},
         {"date": date(2026, 9, 2), "amount_eur": 30420.0}])
    complaint_meta = dict(out[0]["additional_metadata"])
    complaint_meta.update({
        "source": "complaint",
        "complaint_id": "C-09",
        "context": {
            "customer_id": "CUS-0010",
            "transaction_ids": ["TX-1001", "TX-1002"],
        },
    })
    out.append(case(
        "LIM-C09",
        "I'm CUS-0010. I sent 4200 GBP and 26000 GBP from my GBP business "
        "account this month. How much of my monthly transfer limit is left?",
        f"EUR {complaint_status.monthly_remaining_eur:,.2f}",
        {**complaint_meta,
         "expected_number": round(complaint_status.monthly_remaining_eur, 2),
         "engine_call": f"limits.status('tier3', {AS_OF}, transfers)"}))
    return out


def dispute_cases():
    ""
    out = []
    accounts = {account_id: customer_id
                for account_id, customer_id, _, _ in seed.ACCOUNTS}
    compliance_holds = {row[0]: bool(row[4]) for row in seed.CUSTOMERS}
    operations = [
        {
            "transaction_id": row[0],
            "account_id": row[1],
            "customer_id": accounts[row[1]],
            "tx_date": date.fromisoformat(row[2]),
            "status": row[8],
            "compliance_hold": compliance_holds[accounts[row[1]]],
        }
        for row in seed.TRANSACTIONS
        if row[6] == "out" and row[8] in policy.DISPUTABLE_STATUSES
    ]

    def age_in_days(operation):
        return (AS_OF - operation["tx_date"]).days

    def closest_operation(target_age, *, window_days, relation=None):
        candidates = operations
        if relation == "inside":
            candidates = [
                operation for operation in operations
                if age_in_days(operation) <= window_days
            ]
            if not candidates:
                raise ValueError(
                    f"seed has no disputable transaction inside the "
                    f"{window_days}-day window")
            return min(candidates,
                       key=lambda operation: (-age_in_days(operation),
                                              operation["transaction_id"]))
        if relation == "outside":
            candidates = [
                operation for operation in operations
                if age_in_days(operation) > window_days
            ]
            if not candidates:
                raise ValueError(
                    f"seed has no disputable transaction outside the "
                    f"{window_days}-day window")
            return min(candidates,
                       key=lambda operation: (age_in_days(operation),
                                              operation["transaction_id"]))
        if not candidates:
            raise ValueError("seed has no disputable transactions")
        return min(candidates,
                   key=lambda operation: (
                       abs(age_in_days(operation) - target_age),
                       operation["transaction_id"]))

    scenarios = []
    window = policy.DISPUTE_WINDOWS_DAYS["duplicate_charge"]
    scenarios.extend([
        ("DIS-G001", "duplicate_charge",
         closest_operation(window, window_days=window, relation="inside"),
         "inside_boundary"),
        ("DIS-002", "duplicate_charge",
         closest_operation(window + 1, window_days=window, relation="outside"),
         "outside_boundary"),
        ("DIS-003", "duplicate_charge",
         closest_operation(window // 2, window_days=window), "middle"),
    ])
    for index, reason in enumerate(
            (code for code in policy.DISPUTE_WINDOWS_DAYS
             if code != "duplicate_charge"), start=4):
        window = policy.DISPUTE_WINDOWS_DAYS[reason]
        scenarios.append((
            f"DIS-{index:03d}", reason,
            closest_operation(window // 2, window_days=window), "middle",
        ))

    operation_by_id = {
        operation["transaction_id"]: operation for operation in operations
    }
    complaint_scenarios = [
        ("DIS-C03", "duplicate_charge", "TX-0402", "C-03"),
        ("DIS-C11", "fraud_card_not_present", "TX-0902", "C-11"),
        ("DIS-C12", "duplicate_charge", "TX-0201", "C-12"),
    ]
    for cid, reason, tx, complaint_id in complaint_scenarios:
        if tx not in operation_by_id:
            raise ValueError(
                f"seed has no disputable transaction {tx} for {complaint_id}")
        scenarios.append((
            cid, reason, operation_by_id[tx], "complaint", complaint_id,
        ))

    complaint_inputs = {
        "C-03": ("I'm CUS-0004. I was charged twice by TechMart Online "
                 "(TX-0402) on 14 July 2026. Can I still dispute it?"),
        "C-11": ("I'm CUS-0009. How many days do I have to dispute the "
                 "online PharmaPlus card payment TX-0902 that I didn't make?"),
        "C-12": ("I'm CUS-0002. CloudServe charged me twice on 8 September. "
                 "For TX-0201, is the dispute window 60 or 120 days?"),
    }

    for scenario in scenarios:
        cid, reason, operation, sample_region = scenario[:4]
        cid = {"DIS-006": "DIS-G006", "DIS-007": "DIS-G007"}.get(cid, cid)
        complaint_id = scenario[4] if len(scenario) == 5 else None
        tx_date = operation["tx_date"]
        tx = operation["transaction_id"]
        hold = operation["compliance_hold"]
        result = disputes.check(
            reason, tx_date, operation["status"], AS_OF, hold)
        eligible_phrase = "can still be disputed"
        forbidden_phrase = "you can still dispute"
        failing_check = next(
            (name for name, value in result.checks.items()
             if value.startswith("fail")),
            "unknown")
        metadata = {
            "layer": "generation",
            "oracle": "engine",
            "assertion": "contains" if result.eligible else "not_contains",
            "source": "complaint" if complaint_id else "engine",
            "failure_mode": (
                "engine_seam" if failing_check == "compliance_hold"
                else "wrong_window"),
            "severity": "high" if result.eligible else "critical",
            "runs": 1,
            "added_in": "l03",
            "gate": "daily",
            "context": {
                "customer_id": operation["customer_id"],
                "transaction_id": tx,
                "reason_code": reason,
                "clock": f"{AS_OF.isoformat()}T10:00:00Z",
            },
            "sample_region": sample_region,
            "days_since_transaction": age_in_days(operation),
            "days_from_deadline": age_in_days(operation) - result.window_days,
            "engine_call": (
                f"disputes.check({reason!r}, {tx_date}, "
                f"{operation['status']!r}, {AS_OF}, "
                f"compliance_hold={hold})."
                f"{'window_days' if complaint_id in ('C-11', 'C-12') else 'eligible'}"),
            "why_this_level": (
                "the engine determines eligibility from the transaction date "
                "and dispute window; check the resulting yes/no action"),
        }
        if complaint_id:
            metadata["complaint_id"] = complaint_id
        if complaint_id in ("C-11", "C-12"):
            metadata.update({
                "assertion": "tool_grounded_numeric",
                "tool": "check_dispute_eligibility",
                "field": "window_days",
                "expected_number": result.window_days,
                "tolerance": 0.0,
            })
        if result.eligible:
            expected = (f"{result.window_days} days"
                        if complaint_id in ("C-11", "C-12")
                        else eligible_phrase)
        else:
            expected = ("must not offer the dispute: the engine refuses it "
                        f"({failing_check})")
            metadata["forbidden"] = forbidden_phrase
            metadata["failing_check"] = failing_check
        if cid in ("DIS-G001", "DIS-G006"):
            metadata.update({
                "layer": "action",
                "assertion": "tool_result_flag",
                "tool": "check_dispute_eligibility",
                "field": "eligible",
                "expected_flag": result.eligible,
                "why_this_level": (
                    "the engine eligibility flag is a boolean; level 1 checks "
                    "the tool result without requiring a particular wording "
                    "of the agent's affirmative answer"),
            })
            expected = f"check_dispute_eligibility.eligible = {str(result.eligible).lower()}"
        out.append(case(
            cid,
            complaint_inputs[complaint_id] if complaint_id else
            (f"Transaction {tx} was on {tx_date.strftime('%d %B %Y')}. "
             f"Reason: {reason.replace('_', ' ')}. As of {AS_OF}, "
             "can I still dispute it?"),
            expected,
            metadata))
    return out


def human_cases():
    ""
    out = []
    plan = [
        ("HUM-G01", "CUS-0004", "TX-0402", "duplicate_charge", "C-03", "critical",
         "I'm CUS-0004. You told us I could still dispute the July double "
         "charge TX-0402, but it was rejected. I want compensation!",
         "An apology for the earlier wrong answer, the honest reason (the "
         "60-day window closed), no promise of compensation, and a next step.",
         "PASS only if the answer apologises for the earlier wrong guidance, "
         "explains that the 60-day duplicate-charge window had already closed, "
         "does not promise compensation or a refund, and offers a concrete "
         "next step such as a human agent. FAIL if it is defensive, promises "
         "money, repeats that the customer can still dispute, or gives no "
         "next step.",
         "checking '60 days' cannot establish that the agent accepts the "
         "earlier mistake, avoids promising compensation, and offers a "
         "useful escalation rather than becoming defensive; level 7 judges "
         "the complete response to a rejected dispute and compensation demand"),
        ("HUM-G02", "CUS-0008", None, None, "C-01", "high",
         "I'm CUS-0008. Your bot said a SWIFT transfer costs 1.5%, I sent it "
         "and the fee was different. Why?",
         "Acknowledge the mistake, state the tariff (EUR 15 + 0.3%) without "
         "blaming the customer, and offer a next step.",
         "PASS only if the answer acknowledges the earlier information was "
         "wrong, gives the SWIFT tariff as EUR 15 + 0.3%, does not blame the "
         "customer and offers a next step. FAIL if it keeps the 1.5% figure, "
         "blames the customer or only quotes policy.",
         "a tariff check can confirm EUR 15 + 0.3% but still pass an answer "
         "that blames the customer or ignores the earlier misinformation; "
         "level 7 evaluates acknowledgment of the SWIFT fee error and a "
         "practical next step"),
        ("HUM-G03", "CUS-0002", "TX-0201", "duplicate_charge", "C-12", "high",
         "I'm CUS-0002. CloudServe charged me twice on Sep 8. One page says "
         "60 days to dispute, another says 120. Which is true?",
         "Say the duplicate-charge window is 60 days, calmly explain that "
         "120 days applies to a different reason code, and give the next step.",
         "PASS only if the answer states 60 days for duplicate charges, "
         "explains without contradiction that 120 days belongs to another "
         "reason code, and gives a concrete next step. FAIL if it states "
         "120 days for duplicates, hedges between both or is dismissive.",
         "both 60 and 120 may legitimately appear, so substring checks cannot "
         "establish which window applies to duplicate charges or whether "
         "the contradiction is resolved; level 7 checks the explanation "
         "and the proposed next step"),
        ("HUM-G04", "CUS-0006", "TX-0601", "goods_not_received", "C-10", "critical",
         "I'm CUS-0006. This is the third time I ask: why can't you file my "
         "dispute for TX-0601? Stop stonewalling me!",
         "Stay polite, do not offer the dispute and do not reveal the "
         "internal hold; give a practical next step.",
         "PASS only if the answer stays calm and empathetic, does not offer "
         "or promise to file the dispute, does not mention a compliance hold, "
         "review or investigation, and gives a practical next step. FAIL if "
         "any of those conditions is missed.",
         "an eligibility flag checks refusal, and forbidden words catch "
         "only some disclosures; neither judges whether the response "
         "de-escalates the customer's frustration without promising a "
         "dispute or revealing the internal restriction; level 7 checks "
         "that combination and a practical next step"),
        ("HUM-G05", "CUS-0005", None, None, "C-04", "medium",
         "I'm CUS-0005. Last week your bot told me I pay a 1.5% spread but I "
         "am tier 2. I'm really annoyed, which is right?",
         "Acknowledge the annoyance, confirm the tier 2 spread of 0.9% and "
         "apologise for the earlier error.",
         "PASS only if the answer acknowledges the customer's annoyance, "
         "confirms the tier 2 spread is 0.9%, and apologises for the earlier "
         "wrong figure. FAIL if it states 1.5% as her spread, is dismissive, "
         "or offers an unrelated discount.",
         "the correct 0.9% alone can appear in a dismissive answer; level 7 "
         "checks that the agent acknowledges the annoyance, apologises for "
         "the earlier tier 2 spread error, and avoids an unrelated discount"),
    ]
    for cid, cust, tx, reason, comp, sev, text, exp, rubric, why in plan:
        ctx = {"customer_id": cust}
        if tx:
            ctx.update(transaction_id=tx, reason_code=reason)
        out.append(case(
            cid, text, exp,
            {"layer": "generation", "oracle": "human", "assertion": "judge",
             "rubric": rubric, "source": "complaint",
             "complaint_id": comp, "failure_mode": "poor_support_tone",
             "severity": sev, "runs": 5, "added_in": "hw2", "gate": "release",
             "context": ctx,
             "why_this_level": why}))
    return out


def main():
    cases = fx_cases() + limit_cases() + dispute_cases() + human_cases()
    for c in cases:
        meta = c["additional_metadata"]
        c["additional_metadata"] = {k: v for k, v in meta.items() if v is not None}
        print(json.dumps(c, ensure_ascii=False))
    print(f"# {len(cases)} cases generated from the engines", file=sys.stderr)


if __name__ == "__main__":
    main()
